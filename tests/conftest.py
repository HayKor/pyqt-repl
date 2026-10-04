"""Pytest setup: offscreen Qt, skip GUI tests when PyQt6 is missing."""

import importlib.util
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

collect_ignore = (
    [] if importlib.util.find_spec("PyQt6") else ["test_gui_smoke.py"]
)
