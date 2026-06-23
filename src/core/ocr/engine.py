"""本地离线 OCR 引擎封装(RapidOCR / ONNX)。

设计要点:
- 顶层**不 import** PySide6 / rapidocr / numpy → 纯逻辑可单测、缺依赖不崩。
- rapidocr 仅在首次识别(懒加载)时 import;线程安全单例,避免重复加载模型(1~2s)。
- recognize(image_bytes, lang) 喂 **PNG/JPEG 字节**(RapidOCR 的 LoadImage 支持 bytes),
  规避 QImage→ndarray 的 RGB/BGR 通道顺序坑。
- 返回统一的 OcrResult;rapidocr 缺失 / 模型缺失 / DLL 缺失 / 空结果 → ok=False + 中文说明,不抛。
"""
from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass, field

from src.core.logger import get_logger

log = get_logger("ocr.engine")

# 语言选项:value → 中文标签。模型挂载见 _get_engine。
# mix=内置中英混合;en/ja 需把对应模型(+日语还需字典)放到本包 models/ 目录才真正生效,
# 缺文件则自动降级为内置中英混合(不假装支持)。
LANG_OPTIONS = [
    ("mix", "中英混合(内置)"),
    ("en", "仅英文"),
    ("ja", "日语"),
]
_EN_REC_MODEL = "en_PP-OCRv3_rec_infer.onnx"     # 存在则「仅英文」真正切换,否则降级混合
_JA_REC_MODEL = "japan_PP-OCRv4_rec_mobile.onnx"  # 日语识别模型(onnx,PP-OCRv4 mobile)
_JA_REC_KEYS = "japan_dict.txt"                   # 日语字符字典(必须与模型配套,否则乱码)


@dataclass
class OcrLine:
    """单行识别结果。box 为文字框四角像素坐标 [[x,y],...](相对识别图),供原地叠加。"""
    text: str
    score: float
    box: list | None = None


@dataclass
class OcrResult:
    """一次识别的统一结果。"""
    ok: bool
    text: str = ""
    lines: list[OcrLine] = field(default_factory=list)
    avg_confidence: float = 0.0
    elapsed_ms: float = 0.0
    error: str = ""


def average_confidence(scores: list[float]) -> float:
    """对置信度列表求平均(空列表→0.0)。"""
    valid = [float(s) for s in scores if s is not None]
    if not valid:
        return 0.0
    return sum(valid) / len(valid)


def join_lines(texts: list[str]) -> str:
    """把多行文本按换行拼接(去掉首尾空白行,保留行内原样)。"""
    return "\n".join(t for t in texts).strip()


def format_elapsed(ms: float) -> str:
    """耗时格式化:>=1000ms 显示秒(1 位小数),否则毫秒(整数)。"""
    if ms >= 1000:
        return f"{ms / 1000:.1f}s"
    return f"{int(round(ms))}ms"


def format_confidence(avg: float) -> str:
    """置信度格式化为百分比整数,如 0.962 → '96%'。"""
    return f"{int(round(avg * 100))}%"


def lang_label(value: str) -> str:
    """语言 value → 中文标签;未知值回退第一项。"""
    for v, label in LANG_OPTIONS:
        if v == value:
            return label
    return LANG_OPTIONS[0][1]


def _resource_base() -> str:
    """模型资源根目录:PyInstaller onefile 用 sys._MEIPASS,否则用本包目录。"""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _bundled_model(filename: str) -> str | None:
    """在 <base>/models/ 下找模型文件,存在返回绝对路径,否则 None。"""
    path = os.path.join(_resource_base(), "models", filename)
    return path if os.path.exists(path) else None


def _parse_result(result) -> list[OcrLine]:
    """把 RapidOCR 的 result(可能为 None)解析为 OcrLine 列表。

    单项形如 [box, text, confidence];结构异常的项跳过。
    """
    lines: list[OcrLine] = []
    if not result:  # 空结果为 None,需显式判空
        return lines
    for item in result:
        try:
            box, text, score = item[0], item[1], item[2]
            lines.append(OcrLine(text=str(text), score=float(score), box=box))
        except (IndexError, TypeError, ValueError):
            continue
    return lines


def _sum_elapse_ms(elapse, fallback_ms: float) -> float:
    """RapidOCR 的 elapse(可能是 [det,cls,rec] 秒列表)求和转毫秒;拿不到用 fallback。"""
    try:
        if isinstance(elapse, (list, tuple)):
            s = sum(float(x) for x in elapse if x is not None)
            if s > 0:
                return s * 1000.0
    except (TypeError, ValueError):
        pass
    return fallback_ms


class OcrEngine:
    """RapidOCR 懒加载线程安全单例。每个 rec 模型缓存一个引擎实例。"""

    _lock = threading.Lock()
    _engines: dict[str, object] = {}

    @classmethod
    def _get_engine(cls, lang: str):
        """按语言取(或创建)RapidOCR 实例。缺 rapidocr / 模型 → 抛出,由 recognize 兜中文错。"""
        with cls._lock:
            if lang in cls._engines:
                return cls._engines[lang]

            from rapidocr_onnxruntime import RapidOCR  # 延迟 import:缺失才在此暴露

            kwargs = {}
            if lang == "en":
                en_model = _bundled_model(_EN_REC_MODEL)
                if en_model:
                    kwargs["rec_model_path"] = en_model
                else:
                    log.info("未找到纯英文模型,降级为内置中英混合模型")
            elif lang == "ja":
                # 日语需「识别模型 + 配套字典」两者齐全才生效,缺任一则降级内置混合
                ja_model = _bundled_model(_JA_REC_MODEL)
                ja_keys = _bundled_model(_JA_REC_KEYS)
                if ja_model and ja_keys:
                    kwargs["rec_model_path"] = ja_model
                    kwargs["rec_keys_path"] = ja_keys
                else:
                    log.info("未找到日语模型或字典(需 %s + %s),降级为内置中英混合模型",
                             _JA_REC_MODEL, _JA_REC_KEYS)
            engine = RapidOCR(**kwargs)
            cls._engines[lang] = engine
            log.info("RapidOCR 引擎已初始化(lang=%s)", lang)
            return engine

    @classmethod
    def recognize(cls, image_bytes: bytes, lang: str = "mix") -> OcrResult:
        """识别图片字节(PNG/JPEG)。任何异常都转成 ok=False + 中文说明,不抛。"""
        if not image_bytes:
            return OcrResult(ok=False, error="没有可识别的图片内容")

        try:
            engine = cls._get_engine(lang)
        except ImportError as e:
            # 区分「真没装」与「装了但缺 VC++ 运行库」(后者也抛 ImportError: DLL load failed)
            msg = str(e)
            if "DLL load failed" in msg or "找不到指定的" in msg:
                return OcrResult(ok=False, error="系统缺少微软 VC++ 运行库,请安装后重试")
            return OcrResult(ok=False, error="OCR 组件未安装(rapidocr-onnxruntime),请先安装后重试")
        except Exception as e:  # 模型缺失 / DLL 缺失等
            return OcrResult(ok=False, error=cls._friendly_error(e))

        import time
        t0 = time.perf_counter()
        # RapidOCR/ONNX 推理非完全重入安全:多窗口/快速重试并发调用同一单例会污染或 C++ 崩溃,
        # 用类锁串行化(单机 OCR 低频瞬发,串行无感知开销)。
        try:
            with cls._lock:
                result, elapse = engine(image_bytes)
        except Exception as e:
            return OcrResult(ok=False, error=cls._friendly_error(e))
        wall_ms = (time.perf_counter() - t0) * 1000.0

        lines = _parse_result(result)
        elapsed_ms = _sum_elapse_ms(elapse, fallback_ms=wall_ms)
        if not lines:
            log.info("OCR 未识别到文字")
        return OcrResult(
            ok=True,
            text=join_lines([ln.text for ln in lines]),
            lines=lines,
            avg_confidence=average_confidence([ln.score for ln in lines]),
            elapsed_ms=elapsed_ms,
        )

    @staticmethod
    def _friendly_error(e: Exception) -> str:
        """把底层异常翻成非技术用户能懂的中文。"""
        msg = str(e)
        if "DLL load failed" in msg or "LoadLibrary" in msg:
            return "系统缺少 VC++ 运行库,请安装微软 VC++ 运行库后重试"
        if "model" in msg.lower() and ("not" in msg.lower() or "找不到" in msg):
            return "OCR 模型文件缺失,请确认安装包完整"
        log.error("OCR 识别异常:%s", msg)
        return f"文字识别失败:{msg}"
