"""Design Token:集中定义 mockup 的视觉规范。

来源:design/BRIEF.md 与 design/mockup.html 附录「设计规范」。
供 QSS 模板占位符替换(theme_manager)与 Python 代码(阴影、自绘图标)共同引用,
确保「单一事实来源」,改色只改这里。
"""
from __future__ import annotations

# 颜色
COLORS = {
    "primary": "#2D7FF9",
    "primary_hover": "#1B68DC",
    "primary_active_bg": "#EEF4FF",
    "bg_main": "#F5F6F8",
    "bg_card": "#FFFFFF",
    "text_main": "#333333",
    "text_secondary": "#666666",
    "text_muted": "#999999",
    "border": "#E2E4E8",
    "danger": "#EF4444",
    "success": "#10B981",
}

# 圆角(px):工具栏/按钮 6,中 8,窗口/卡片 12
RADIUS = {"sm": 6, "md": 8, "lg": 12}

# 中文字体栈
FONT_FAMILY = (
    '"Microsoft YaHei", "PingFang SC", "Helvetica Neue", Helvetica, Arial, sans-serif'
)
FONT_SIZE_BASE = 13  # px

# 阴影参数(供 QGraphicsDropShadowEffect 使用;alpha 为 0-255)
# 柔和阴影 ≈ rgba(0,0,0,0.08) → alpha 20;重阴影 ≈ rgba(0,0,0,0.15) → alpha 38
SHADOW_SOFT = {"blur": 16, "x": 0, "y": 4, "alpha": 20}
SHADOW_HEAVY = {"blur": 24, "x": 0, "y": 8, "alpha": 38}


def qss_replacements() -> dict:
    """返回 QSS 模板占位符 → 值 的映射(占位符形如 @primary、@radius_lg)。"""
    mapping = {f"@{k}": v for k, v in COLORS.items()}
    mapping.update({f"@radius_{k}": f"{v}px" for k, v in RADIUS.items()})
    mapping["@font_family"] = FONT_FAMILY
    mapping["@font_size_base"] = f"{FONT_SIZE_BASE}px"
    return mapping
