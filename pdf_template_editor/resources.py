from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative_path: str) -> Path:
    """Resolve a bundled PyInstaller resource or a source-tree resource."""
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return bundle_root / relative_path
