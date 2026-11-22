"""PCOptimizer PRO application package."""

__version__ = "2.0.1"


def main() -> int:
    """Entry point for console_scripts."""
    from app.ui.main_window import run

    return run()
