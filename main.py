"""PCOptimizer_PRO — Windows system monitor & optimizer. Entry point."""

import os
import sys
from pathlib import Path


def _use_project_venv() -> None:
    if sys.prefix != sys.base_prefix:
        return
    venv_python = Path(__file__).resolve().parent / ".venv" / "Scripts" / "python.exe"
    if not venv_python.is_file():
        return
    if Path(sys.executable).resolve() == venv_python.resolve():
        return
    os.execv(str(venv_python), [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]])


if __name__ == "__main__":
    _use_project_venv()
    from app.settings.service import SettingsService

    scale = int(SettingsService().get("ui_scale"))
    os.environ["PCOPTIMIZER_UI_SCALE"] = str(scale)

    from app.ui import theme

    os.environ.pop("PCOPTIMIZER_UI_SCALE", None)
    theme.set_ui_scale(scale)

    from app.ui.main_window import run

    raise SystemExit(run())
