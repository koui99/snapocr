"""Core screenshot package.

Provides screenshot grabber and output composite writer.
"""
from src.core.screenshot.capture import CaptureEngine
from src.core.screenshot.writer import ScreenshotWriter

__all__ = ["CaptureEngine", "ScreenshotWriter"]
