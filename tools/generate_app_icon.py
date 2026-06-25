#!/usr/bin/env python3
"""Generate SnapOCR application icon assets without external dependencies.

Outputs:
- src/assets/app_icon.svg  vector source / design reference
- src/assets/app_icon.ico  Windows multi-size icon for PyInstaller
"""
from __future__ import annotations

import math
import os
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src" / "assets"
SVG_PATH = ASSETS / "app_icon.svg"
ICO_PATH = ASSETS / "app_icon.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]

SVG = '''<svg width="1024" height="1024" viewBox="0 0 1024 1024" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="200" y1="150" x2="824" y2="874" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#4F46E5"/>
      <stop offset="1" stop-color="#7C3AED"/>
    </linearGradient>
    <filter id="shadow" x="64" y="72" width="896" height="896" filterUnits="userSpaceOnUse">
      <feDropShadow dx="0" dy="24" stdDeviation="32" flood-color="#000000" flood-opacity="0.25"/>
    </filter>
  </defs>
  <!-- 背景圆角矩形 -->
  <rect x="112" y="112" width="800" height="800" rx="180" fill="url(#bg)" filter="url(#shadow)"/>
  <!-- 截图选区框：虚线矩形 -->
  <rect x="260" y="280" width="504" height="340" rx="20" stroke="white" stroke-width="48" stroke-dasharray="80 60" fill="none" opacity="0.9"/>
  <!-- 四角控制点 -->
  <circle cx="260" cy="280" r="32" fill="white"/>
  <circle cx="764" cy="280" r="32" fill="white"/>
  <circle cx="260" cy="620" r="32" fill="white"/>
  <circle cx="764" cy="620" r="32" fill="white"/>
  <!-- OCR 文字识别符号：底部显示 "OCR" -->
  <text x="512" y="760" font-family="Arial, sans-serif" font-size="140" font-weight="bold" fill="white" text-anchor="middle" opacity="0.95">OCR</text>
</svg>
'''


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _blend(dst, src):
    sr, sg, sb, sa = src
    if sa <= 0:
        return dst
    dr, dg, db, da = dst
    a = sa / 255.0
    ia = 1.0 - a
    out_a = sa + da * ia
    if out_a <= 0:
        return (0, 0, 0, 0)
    r = int(round((sr * sa + dr * da * ia) / out_a))
    g = int(round((sg * sa + dg * da * ia) / out_a))
    b = int(round((sb * sa + db * da * ia) / out_a))
    return (r, g, b, int(round(out_a)))


def _lerp(a, b, t):
    return int(round(a + (b - a) * t))


def _grad(x, y, n):
    # 紫色渐变：从靛蓝到紫罗兰
    c1 = _hex("#4F46E5")  # Indigo-600
    c2 = _hex("#7C3AED")  # Violet-600
    t = max(0.0, min(1.0, (x + y) / (2 * n)))
    return tuple(_lerp(c1[i], c2[i], t) for i in range(3))


def _inside_round_rect(x, y, left, top, right, bottom, radius):
    if x < left or x >= right or y < top or y >= bottom:
        return False
    cx = min(max(x, left + radius), right - radius)
    cy = min(max(y, top + radius), bottom - radius)
    return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2


def _put_rect(img, n, left, top, right, bottom, radius, color):
    left, top, right, bottom, radius = map(int, (left, top, right, bottom, radius))
    for y in range(max(0, top), min(n, bottom)):
        row = img[y]
        for x in range(max(0, left), min(n, right)):
            if radius <= 0 or _inside_round_rect(x + 0.5, y + 0.5, left, top, right, bottom, radius):
                row[x] = _blend(row[x], color)


def _put_circle(img, n, cx, cy, r, color, stroke=0):
    cx, cy, r, stroke = float(cx), float(cy), float(r), float(stroke)
    r2 = r * r
    inner = max(0.0, r - stroke)
    inner2 = inner * inner
    xmin, xmax = int(max(0, cx - r - 1)), int(min(n, cx + r + 2))
    ymin, ymax = int(max(0, cy - r - 1)), int(min(n, cy + r + 2))
    for y in range(ymin, ymax):
        row = img[y]
        for x in range(xmin, xmax):
            d2 = (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2
            if d2 <= r2 and (stroke <= 0 or d2 >= inner2):
                row[x] = _blend(row[x], color)


def _put_line(img, n, x1, y1, x2, y2, width, color):
    # Rounded thick line via capsules.
    steps = max(1, int(math.hypot(x2 - x1, y2 - y1) / max(1, width / 3)))
    r = width / 2
    for i in range(steps + 1):
        t = i / steps
        _put_circle(img, n, x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, r, color)


def _render_rgba(size: int, ss: int = 4):
    n = size * ss
    img = [[(0, 0, 0, 0) for _ in range(n)] for _ in range(n)]

    # 阴影
    _put_rect(img, n, n * 0.13, n * 0.14, n * 0.90, n * 0.93, n * 0.18, (0, 0, 0, 64))

    # 背景圆角矩形（紫色渐变）
    left, top, right, bottom = n * 0.11, n * 0.11, n * 0.89, n * 0.89
    radius = n * 0.176  # 180/1024
    for y in range(n):
        row = img[y]
        for x in range(n):
            if _inside_round_rect(x + 0.5, y + 0.5, left, top, right, bottom, radius):
                row[x] = _blend(row[x], (*_grad(x, y, n), 255))

    white = (255, 255, 255, 230)

    # 截图选区框（虚线矩形）
    frame_left = n * 0.254
    frame_top = n * 0.273
    frame_right = n * 0.746
    frame_bottom = n * 0.605
    frame_radius = n * 0.020
    stroke = n * 0.047
    dash_len = n * 0.078
    gap_len = n * 0.059

    # 绘制虚线边框（四条边分段绘制）
    edges = [
        (frame_left, frame_top, frame_right, frame_top),      # 上
        (frame_right, frame_top, frame_right, frame_bottom),  # 右
        (frame_right, frame_bottom, frame_left, frame_bottom), # 下
        (frame_left, frame_bottom, frame_left, frame_top),    # 左
    ]

    for x1, y1, x2, y2 in edges:
        length = math.hypot(x2 - x1, y2 - y1)
        dx = (x2 - x1) / length
        dy = (y2 - y1) / length
        pos = 0
        while pos < length:
            seg_end = min(pos + dash_len, length)
            _put_line(img, n,
                     x1 + dx * pos, y1 + dy * pos,
                     x1 + dx * seg_end, y1 + dy * seg_end,
                     stroke, white)
            pos += dash_len + gap_len

    # 四角控制点（白色圆点）
    dot_r = n * 0.031
    _put_circle(img, n, frame_left, frame_top, dot_r, (255, 255, 255, 255))
    _put_circle(img, n, frame_right, frame_top, dot_r, (255, 255, 255, 255))
    _put_circle(img, n, frame_left, frame_bottom, dot_r, (255, 255, 255, 255))
    _put_circle(img, n, frame_right, frame_bottom, dot_r, (255, 255, 255, 255))

    # OCR 文字（简单像素字体，仅在大尺寸显示）
    if size >= 48:
        _draw_text_ocr(img, n, white)

    # 下采样
    if ss == 1:
        return [px for row in img for px in row]
    out = []
    area = ss * ss
    for y in range(size):
        for x in range(size):
            acc = [0, 0, 0, 0]
            for yy in range(y * ss, (y + 1) * ss):
                for xx in range(x * ss, (x + 1) * ss):
                    p = img[yy][xx]
                    for k in range(4):
                        acc[k] += p[k]
            out.append(tuple(int(round(v / area)) for v in acc))
    return out


def _draw_text_ocr(img, n, color):
    """绘制 OCR 文字（简化像素字体）"""
    # 文字基线位置
    base_x = n * 0.5
    base_y = n * 0.72
    char_w = n * 0.08
    spacing = n * 0.09
    stroke = max(2, int(n * 0.018))

    # O
    cx = base_x - spacing
    _put_circle(img, n, cx, base_y, char_w * 0.5, color, stroke=stroke)

    # C
    cx = base_x
    r = char_w * 0.5
    # C 是圆环去掉右侧
    for angle in range(-120, 121, 10):
        rad = math.radians(angle)
        x1 = cx + r * math.cos(rad)
        y1 = base_y + r * math.sin(rad)
        x2 = cx + (r - stroke) * math.cos(rad)
        y2 = base_y + (r - stroke) * math.sin(rad)
        _put_line(img, n, x1, y1, x2, y2, stroke * 0.6, color)

    # R
    cx = base_x + spacing
    r = char_w * 0.4
    # R 是 P 加一撇
    _put_line(img, n, cx - r * 0.5, base_y - r, cx - r * 0.5, base_y + r, stroke, color)
    _put_circle(img, n, cx, base_y - r * 0.5, r * 0.6, color, stroke=stroke * 0.8)
    _put_line(img, n, cx, base_y, cx + r * 0.5, base_y + r, stroke, color)


def _png_bytes(size: int, rgba) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = bytearray()
    for y in range(size):
        raw.append(0)  # no filter
        for r, g, b, a in rgba[y * size:(y + 1) * size]:
            raw.extend([r, g, b, a])
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")


def _ico_bytes(images: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(images))
    entries = bytearray()
    offset = 6 + 16 * len(images)
    payload = bytearray()
    for size, data in images:
        entries.extend(struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,
            0 if size >= 256 else size,
            0,
            0,
            1,
            32,
            len(data),
            offset,
        ))
        payload.extend(data)
        offset += len(data)
    return header + bytes(entries) + bytes(payload)


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    SVG_PATH.write_text(SVG, encoding="utf-8")
    images = []
    for size in SIZES:
        rgba = _render_rgba(size, ss=4)
        images.append((size, _png_bytes(size, rgba)))
    ICO_PATH.write_bytes(_ico_bytes(images))
    print(f"wrote {SVG_PATH.relative_to(ROOT)}")
    print(f"wrote {ICO_PATH.relative_to(ROOT)} ({ICO_PATH.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
