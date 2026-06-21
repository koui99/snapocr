"""OCR 引擎纯逻辑单元测试(不依赖 rapidocr / PySide6 / 模型)。

只测可在 headless 跑的纯函数:置信度求平均、行文本拼接、耗时/置信度格式化、语言标签映射。
真实识别 / 模型加载留待 Windows 实测。
"""
import pytest

from src.core.ocr.engine import (
    LANG_OPTIONS,
    OcrResult,
    average_confidence,
    format_confidence,
    format_elapsed,
    join_lines,
    lang_label,
)


def test_average_confidence_basic():
    assert average_confidence([0.9, 0.8, 1.0]) == pytest.approx(0.9)


def test_average_confidence_empty():
    assert average_confidence([]) == 0.0


def test_average_confidence_skips_none():
    assert average_confidence([0.8, None, 1.0]) == pytest.approx(0.9)


def test_join_lines_strip_and_newline():
    assert join_lines(["第一行", "second line", "第三行"]) == "第一行\nsecond line\n第三行"


def test_join_lines_empty():
    assert join_lines([]) == ""


def test_format_elapsed_ms_and_seconds():
    assert format_elapsed(800) == "800ms"
    assert format_elapsed(1500) == "1.5s"
    assert format_elapsed(999) == "999ms"
    assert format_elapsed(1000) == "1.0s"


def test_format_confidence():
    assert format_confidence(0.962) == "96%"
    assert format_confidence(1.0) == "100%"
    assert format_confidence(0.0) == "0%"


def test_lang_label_known_and_fallback():
    assert lang_label("mix") == "中英混合(内置)"
    assert lang_label("en") == "仅英文"
    # 未知值回退第一项
    assert lang_label("xyz") == LANG_OPTIONS[0][1]


def test_lang_options_shape():
    assert ("mix", "中英混合(内置)") in LANG_OPTIONS
    values = [v for v, _ in LANG_OPTIONS]
    assert "en" in values
    # 每项是 (value, label) 二元组
    assert all(len(opt) == 2 for opt in LANG_OPTIONS)


def test_ocr_result_defaults():
    r = OcrResult(ok=False, error="x")
    assert r.text == ""
    assert r.lines == []
    assert r.avg_confidence == 0.0
    assert r.elapsed_ms == 0.0


def test_ocr_line_box_optional():
    from src.core.ocr.engine import OcrLine
    # box 默认 None(剪贴板/老路径无坐标)
    assert OcrLine(text="x", score=0.9).box is None
    # 带坐标(原地叠加用)
    ln = OcrLine(text="y", score=0.8, box=[[0, 0], [5, 0], [5, 2], [0, 2]])
    assert ln.box[1][0] == 5

