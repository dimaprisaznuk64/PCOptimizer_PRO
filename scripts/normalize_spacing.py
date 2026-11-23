"""Snap layout literals in app/ui to the design-token scale.

Usage:  python scripts/normalize_spacing.py [--write] [path ...]

Without --write it only reports. Rules (same everywhere, nearest token, ties go up):
  * layout calls  setSpacing / setContentsMargins / setHorizontalSpacing /
    setVerticalSpacing / addSpacing: ints 0, 1, 2 stay literal (hairlines);
    every other int becomes SPACING_XS/SM/MD/LG/XL/XXL (4/8/12/16/24/32).
  * f-string QSS ``border-radius: Npx`` becomes RADIUS_SM/MD/LG/XL (6/10/12/16).
Plain (non-f) strings are never rewritten automatically; they are reported.
Run ``ruff check --fix`` afterwards to merge the generated import lines.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

SCALE = [(4, "SPACING_XS"), (8, "SPACING_SM"), (12, "SPACING_MD"),
         (16, "SPACING_LG"), (24, "SPACING_XL"), (32, "SPACING_XXL")]
RADII = [(6, "RADIUS_SM"), (10, "RADIUS_MD"), (12, "RADIUS_LG"), (16, "RADIUS_XL")]
CALLS = {"setSpacing", "setContentsMargins", "setHorizontalSpacing",
         "setVerticalSpacing", "addSpacing"}
KEEP = {0, 1, 2}
RADIUS_RE = re.compile(r"border-radius:\s*(\d+)px")
STR_RE = re.compile(r"""([rRbBuUfF]*)("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')""")


def snap(value: int, table: list[tuple[int, str]]) -> str:
    best = min(table, key=lambda t: (abs(t[0] - value), -t[0]))
    return best[1]


def radius_token(value: int) -> str:
    return snap(value, RADII)


def process(path: Path, write: bool) -> tuple[int, list[str]]:
    raw = path.read_bytes().decode("utf-8")
    lines = raw.splitlines(keepends=True)
    tree = ast.parse(raw)
    used: set[str] = set()
    manual: list[str] = []
    edits: list[tuple[int, int, int, str]] = []  # line, col_start, col_end (bytes)

    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in CALLS):
            for arg in node.args:
                if (isinstance(arg, ast.Constant) and type(arg.value) is int
                        and arg.value not in KEEP):
                    token = snap(arg.value, SCALE)
                    used.add(token)
                    edits.append((arg.lineno, arg.col_offset, arg.end_col_offset, token))

    count = len(edits)
    for idx, line in enumerate(lines, 1):
        if "border-radius" not in line:
            continue
        for sm in STR_RE.finditer(line):
            prefix, body = sm.group(1), sm.group(2)
            for rm in RADIUS_RE.finditer(body):
                value = int(rm.group(1))
                if value <= 2:
                    continue
                if "f" in prefix.lower():
                    token = radius_token(value)
                    used.add(token)
                    start = len(line[: sm.start(2)].encode()) + len(body[: rm.start()].encode())
                    end = start + len(rm.group(0).encode())
                    edits.append((idx, start, end, f"border-radius: {{{token}}}px"))
                    count += 1
                else:
                    manual.append(f"{path}:{idx}: plain string, radius {value}px -> "
                                  f"{radius_token(value)} (convert to f-string by hand)")

    if write and edits:
        for lineno, start, end, text in sorted(edits, key=lambda e: (e[0], -e[1])):
            b = lines[lineno - 1].encode()
            lines[lineno - 1] = (b[:start] + text.encode() + b[end:]).decode()
        new = "".join(lines)
        if used:
            names = ", ".join(sorted(used))
            eol = "\r\n" if "\r\n" in raw else "\n"
            tree2 = ast.parse(new)
            imports = [n for n in tree2.body if isinstance(n, (ast.Import, ast.ImportFrom))]
            last = max(imports, key=lambda n: n.end_lineno)
            out = new.splitlines(keepends=True)
            out.insert(last.end_lineno, f"from .theme import {names}{eol}")
            new = "".join(out)
        ast.parse(new)  # never write a file that no longer parses
        path.write_bytes(new.encode("utf-8"))
    return count, manual


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    write = "--write" in sys.argv
    paths = [Path(a) for a in args] or sorted(Path("app/ui").glob("*.py"))
    total, manual_all = 0, []
    for p in paths:
        if p.name == "theme.py":
            continue
        n, manual = process(p, write)
        if n:
            print(f"{n:4d}  {p}")
        total += n
        manual_all += manual
    print(f"{'rewrote' if write else 'would rewrite'} {total} literals")
    for m in manual_all:
        print("MANUAL:", m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
