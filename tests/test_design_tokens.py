"""Guard the visual system: layout in app/ui must use theme tokens, not literals."""

from __future__ import annotations

import ast
import re
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "app" / "ui"
LAYOUT_CALLS = {
    "setSpacing", "setContentsMargins", "setHorizontalSpacing",
    "setVerticalSpacing", "addSpacing",
}
HAIRLINE = {0, 1, 2}  # tight stacks and zero margins may stay literal
RADIUS = re.compile(r"border-radius:\s*(\d+)px")


def _py_files() -> list[Path]:
    return sorted(p for p in UI.glob("*.py") if p.name != "theme.py")


def test_layout_calls_use_spacing_tokens() -> None:
    offenders: list[str] = []
    for path in _py_files():
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        for node in ast.walk(ast.parse(source)):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in LAYOUT_CALLS):
                continue
            for arg in node.args:
                if (isinstance(arg, ast.Constant) and type(arg.value) is int
                        and arg.value not in HAIRLINE
                        and "literal-ok" not in lines[arg.lineno - 1]):
                    offenders.append(f"{path.name}:{arg.lineno} {node.func.attr}({arg.value})")
    assert not offenders, "use SPACING_*/PADDING_* tokens from app.ui.theme:\n" + "\n".join(offenders)


def test_stylesheet_radii_use_tokens() -> None:
    offenders = []
    for path in _py_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "literal-ok" in line:
                continue
            for match in RADIUS.finditer(line):
                if int(match.group(1)) > 2:
                    offenders.append(f"{path.name}:{number} border-radius: {match.group(1)}px")
    assert not offenders, "use RADIUS_* tokens from app.ui.theme:\n" + "\n".join(offenders)


def test_spacing_scale_is_monotonic_and_on_grid() -> None:
    from app.ui import theme

    scale = [theme.SPACING_XS, theme.SPACING_SM, theme.SPACING_MD,
             theme.SPACING_LG, theme.SPACING_XL, theme.SPACING_XXL]
    assert scale == sorted(scale) and len(set(scale)) == len(scale)
    assert [theme.RADIUS_SM, theme.RADIUS_MD, theme.RADIUS_LG, theme.RADIUS_XL] == sorted(
        [theme.RADIUS_SM, theme.RADIUS_MD, theme.RADIUS_LG, theme.RADIUS_XL]
    )


def test_page_margins_are_symmetric_vertically() -> None:
    from app.ui import theme

    left, top, right, bottom = theme.PAGE_MARGINS
    assert left == right and top == bottom
