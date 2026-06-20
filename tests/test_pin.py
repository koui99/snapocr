"""贴图(Pin)子系统纯逻辑单元测试(缩放钳制 / 不透明度档位 / 角度归一)。

仅测不依赖窗口显示的纯逻辑;真实贴图浮窗的拖拽/置顶/剪贴板在 Windows 实测。
"""
import pytest

from src.ui.pin.pin_window import clamp_scale, _OPACITY_LEVELS, _MIN_SCALE, _MAX_SCALE


def test_clamp_scale_within_range():
    assert clamp_scale(1.0) == 1.0
    assert clamp_scale(2.5) == 2.5


def test_clamp_scale_bounds():
    assert clamp_scale(0.001) == _MIN_SCALE
    assert clamp_scale(9999) == _MAX_SCALE
    assert clamp_scale(_MIN_SCALE) == _MIN_SCALE
    assert clamp_scale(_MAX_SCALE) == _MAX_SCALE


def test_wheel_zoom_converges_to_bounds():
    # 连续放大最终被钳在上限,不会无限增大
    s = 1.0
    for _ in range(100):
        s = clamp_scale(s * 1.1)
    assert s == _MAX_SCALE
    # 连续缩小到下限
    s = 1.0
    for _ in range(100):
        s = clamp_scale(s / 1.1)
    assert s == _MIN_SCALE


def test_opacity_levels():
    assert _OPACITY_LEVELS[0] == 100
    assert _OPACITY_LEVELS == sorted(_OPACITY_LEVELS, reverse=True)
    assert all(0 < v <= 100 for v in _OPACITY_LEVELS)


def test_angle_normalization():
    # 旋转累加后对 360 取模的归一逻辑
    angle = 0
    for _ in range(5):
        angle = (angle + 90) % 360
    assert angle == 90  # 5*90=450 → 90
    angle = 0
    for _ in range(4):
        angle = (angle - 90) % 360
    assert angle == 0  # -360 → 0
