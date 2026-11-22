"""Make the HA-free modules importable without executing the package __init__."""

import sys
import types
from pathlib import Path

_pkg = types.ModuleType("hsveitur")
_pkg.__path__ = [str(Path(__file__).parent.parent / "custom_components" / "hsveitur")]
sys.modules.setdefault("hsveitur", _pkg)
