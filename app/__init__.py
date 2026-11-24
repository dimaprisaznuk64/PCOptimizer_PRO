"""PCOptimizer PRO application package."""

__version__ = "2.1.0"


def main() -> int:
    """Entry point for console_scripts."""
    from app.ui.main_window import run

    return run()
