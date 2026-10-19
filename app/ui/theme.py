from __future__ import annotations

import re

_BASE = {
    "BG": "#070A13",
    "PANEL": "#0B1120",
    "PANEL_ALT": "#10182B",
    "BORDER": "#16233B",
    "BORDER_HI": "#24375A",
    "TEXT": "#F1F5F9",
    "TEXT_DIM": "#8292AA",
    "ACCENT": "#1E6BFF",
    "ACCENT_HOVER": "#3B82F6",
    "ACCENT_TINT": "#0D2247",
    "ACCENT_PRESSED": "#0052CC",
    "ON_ACCENT": "#FFFFFF",
    "DANGER": "#EF4444",
    "OK": "#00E599",
    "WARN": "#F59E0B",
    "SIDEBAR_TOP": "#080D1A",
    "SIDEBAR_BOTTOM": "#050812",
    "HOVER": "#131E33",
    "DANGER_BG": "#2E151B",
    "DANGER_BORDER": "#5C222D",
    "DANGER_BG_HOVER": "#3D1A23",
    "OK_BG": "#0B261C",
    "WARN_BG": "#2B2110",
    "HERO_TOP": "#0E1C38",
    "BRAND_A": "#1E6BFF",
    "BRAND_B": "#00D2FF",
    "GLOW_A": "#0066FF",
    "GLOW_B": "#9B51E0",
    "GLOW_ALPHA_A": 45,
    "GLOW_ALPHA_B": 30,
    "C1": "#00D2FF",
    "C2": "#2F80ED",
    "C3": "#A855F7",
    "C4": "#0080FF",
}

PALETTES: dict[str, dict] = {
    "GRAPHITE": {
        **_BASE,
        "BG": "#0D0F12", "PANEL": "#14171C", "PANEL_ALT": "#1B1F26", "BORDER": "#262B34", "BORDER_HI": "#38404D",
        "TEXT": "#EDF1F7", "TEXT_DIM": "#8A94A3", "ACCENT": "#4D9BFF", "ACCENT_HOVER": "#70B2FF",
        "ACCENT_TINT": "#15283F", "ACCENT_PRESSED": "#2F7FE0", "ON_ACCENT": "#F2F7FF",
        "DANGER": "#E5484D", "OK": "#46C68B", "WARN": "#E8A33D",
        "SIDEBAR_TOP": "#101318", "SIDEBAR_BOTTOM": "#0A0C0F", "HOVER": "#1D222B",
        "DANGER_BG": "#331A1C", "DANGER_BORDER": "#69383B", "DANGER_BG_HOVER": "#422224",
        "OK_BG": "#12301F", "WARN_BG": "#332A14", "HERO_TOP": "#131E2E",
        "BRAND_A": "#4D9BFF", "BRAND_B": "#7C86FF", "GLOW_A": "#4D9BFF", "GLOW_B": "#7C86FF",
        "GLOW_ALPHA_A": 42, "GLOW_ALPHA_B": 28,
        "C1": "#4FA3F7", "C2": "#8892FF", "C3": "#46C68B", "C4": "#E8A33D",
    },
    "TRUE_BLACK": {
        **_BASE,
        "BG": "#000000", "PANEL": "#0A0A0C", "PANEL_ALT": "#111114", "BORDER": "#1E1E22", "BORDER_HI": "#303036",
        "TEXT": "#F5F5F5", "TEXT_DIM": "#8A8A92", "ACCENT": "#D8D8DB", "ACCENT_HOVER": "#FFFFFF",
        "ACCENT_TINT": "#1C1C20", "ACCENT_PRESSED": "#B4B4BA", "ON_ACCENT": "#0A0A0C",
        "DANGER": "#E5484D", "OK": "#3ECF8E", "WARN": "#E0A03C",
        "SIDEBAR_TOP": "#050506", "SIDEBAR_BOTTOM": "#000000", "HOVER": "#141416",
        "DANGER_BG": "#2E1416", "DANGER_BORDER": "#6B3438", "DANGER_BG_HOVER": "#3D1B1E",
        "OK_BG": "#0F2B1E", "WARN_BG": "#2E2510", "HERO_TOP": "#151519",
        "BRAND_A": "#E8E8EA", "BRAND_B": "#B9B9C0", "GLOW_A": "#8A8A92", "GLOW_B": "#5A5A62",
        "GLOW_ALPHA_A": 38, "GLOW_ALPHA_B": 26,
        "C1": "#D8D8DB", "C2": "#A8A8B0", "C3": "#3ECF8E", "C4": "#E0A03C",
    },
    "SLATE": {
        **_BASE,
        "BG": "#131722", "PANEL": "#1A2030", "PANEL_ALT": "#222A3D", "BORDER": "#303A52", "BORDER_HI": "#45526E",
        "TEXT": "#E8EDF6", "TEXT_DIM": "#8B96AC", "ACCENT": "#5C8FCE", "ACCENT_HOVER": "#7BA7DE",
        "ACCENT_TINT": "#1B2840", "ACCENT_PRESSED": "#4370B0", "ON_ACCENT": "#0E1626",
        "DANGER": "#DC5866", "OK": "#54BF8B", "WARN": "#D9A85B",
        "SIDEBAR_TOP": "#161B28", "SIDEBAR_BOTTOM": "#11141E", "HOVER": "#242D44",
        "DANGER_BG": "#331A20", "DANGER_BORDER": "#6B3A44", "DANGER_BG_HOVER": "#422229",
        "OK_BG": "#13301F", "WARN_BG": "#332A16", "HERO_TOP": "#1B2740",
        "BRAND_A": "#5C8FCE", "BRAND_B": "#86A6DE", "GLOW_A": "#5C8FCE", "GLOW_B": "#6D7FC4",
        "GLOW_ALPHA_A": 42, "GLOW_ALPHA_B": 28,
        "C1": "#5C8FCE", "C2": "#7C9DE0", "C3": "#54BF8B", "C4": "#D9A85B",
    },
    "TITANIUM": {
        **_BASE,
        "BG": "#121416", "PANEL": "#181B1E", "PANEL_ALT": "#202327", "BORDER": "#2C3035", "BORDER_HI": "#40454C",
        "TEXT": "#ECEEF1", "TEXT_DIM": "#878E96", "ACCENT": "#8BB0D4", "ACCENT_HOVER": "#A4C6E6",
        "ACCENT_TINT": "#1B2733", "ACCENT_PRESSED": "#6E91B5", "ON_ACCENT": "#0D141B",
        "DANGER": "#E05864", "OK": "#52C28B", "WARN": "#D8A858",
        "SIDEBAR_TOP": "#16181B", "SIDEBAR_BOTTOM": "#0F1113", "HOVER": "#23262A",
        "DANGER_BG": "#34191D", "DANGER_BORDER": "#6C3A40", "DANGER_BG_HOVER": "#432125",
        "OK_BG": "#132F21", "WARN_BG": "#332A14", "HERO_TOP": "#1B2329",
        "BRAND_A": "#8BB0D4", "BRAND_B": "#5E7FA0", "GLOW_A": "#8BB0D4", "GLOW_B": "#A0A8B2",
        "GLOW_ALPHA_A": 40, "GLOW_ALPHA_B": 26,
        "C1": "#8BB0D4", "C2": "#ABB6C2", "C3": "#52C28B", "C4": "#D8A858",
    },
    "FOREST": {
        **_BASE,
        "BG": "#0E1410", "PANEL": "#151D17", "PANEL_ALT": "#1C261E", "BORDER": "#2A3A2E", "BORDER_HI": "#3C5442",
        "TEXT": "#E7F0E9", "TEXT_DIM": "#8CA08F", "ACCENT": "#74B98E", "ACCENT_HOVER": "#8FD0A5",
        "ACCENT_TINT": "#163024", "ACCENT_PRESSED": "#53976F", "ON_ACCENT": "#0C1A10",
        "DANGER": "#D9585E", "OK": "#78C98F", "WARN": "#C9A75B",
        "SIDEBAR_TOP": "#121A14", "SIDEBAR_BOTTOM": "#0C120E", "HOVER": "#1F2B22",
        "DANGER_BG": "#331A1D", "DANGER_BORDER": "#6B3A40", "DANGER_BG_HOVER": "#422327",
        "OK_BG": "#123021", "WARN_BG": "#322A16", "HERO_TOP": "#1A2A1E",
        "BRAND_A": "#74B98E", "BRAND_B": "#4D9E7E", "GLOW_A": "#74B98E", "GLOW_B": "#4D9E7E",
        "GLOW_ALPHA_A": 40, "GLOW_ALPHA_B": 26,
        "C1": "#74B98E", "C2": "#4D9E7E", "C3": "#C9A75B", "C4": "#67A8C4",
    },
    "BURGUNDY": {
        **_BASE,
        "BG": "#171012", "PANEL": "#201619", "PANEL_ALT": "#2A1C20", "BORDER": "#3E2830", "BORDER_HI": "#573844",
        "TEXT": "#F2E8EA", "TEXT_DIM": "#A18B90", "ACCENT": "#C25B74", "ACCENT_HOVER": "#DB7A90",
        "ACCENT_TINT": "#3A1F27", "ACCENT_PRESSED": "#A1435C", "ON_ACCENT": "#FFFFFF",
        "DANGER": "#E05F6B", "OK": "#6FB788", "WARN": "#C9A05B",
        "SIDEBAR_TOP": "#1B1215", "SIDEBAR_BOTTOM": "#141012", "HOVER": "#2D1F24",
        "DANGER_BG": "#3A1D22", "DANGER_BORDER": "#7A4048", "DANGER_BG_HOVER": "#4A252C",
        "OK_BG": "#14301F", "WARN_BG": "#332A14", "HERO_TOP": "#2C1A20",
        "BRAND_A": "#C25B74", "BRAND_B": "#B05C86", "GLOW_A": "#C25B74", "GLOW_B": "#8A4E66",
        "GLOW_ALPHA_A": 40, "GLOW_ALPHA_B": 26,
        "C1": "#C25B74", "C2": "#B05C86", "C3": "#6FB788", "C4": "#C9A05B",
    },
    "MIDNIGHT": {
        **_BASE,
        "BG": "#0D111E", "PANEL": "#141A2C", "PANEL_ALT": "#1C2438", "BORDER": "#2C3750", "BORDER_HI": "#415070",
        "TEXT": "#E9EEF9", "TEXT_DIM": "#8A95AF", "ACCENT": "#5A77D6", "ACCENT_HOVER": "#7B94E6",
        "ACCENT_TINT": "#1C2850", "ACCENT_PRESSED": "#405CC0", "ON_ACCENT": "#0D1326",
        "DANGER": "#DD5A66", "OK": "#55BE8B", "WARN": "#D6A45C",
        "SIDEBAR_TOP": "#131A2B", "SIDEBAR_BOTTOM": "#0B0F1A", "HOVER": "#1F2941",
        "DANGER_BG": "#341A1F", "DANGER_BORDER": "#6D3A44", "DANGER_BG_HOVER": "#432228",
        "OK_BG": "#123021", "WARN_BG": "#332A16", "HERO_TOP": "#1A2442",
        "BRAND_A": "#5A77D6", "BRAND_B": "#8A6BD8", "GLOW_A": "#5A77D6", "GLOW_B": "#7B5FD0",
        "GLOW_ALPHA_A": 42, "GLOW_ALPHA_B": 28,
        "C1": "#5A77D6", "C2": "#7B5FD0", "C3": "#4FC3E0", "C4": "#D6A45C",
    },
    "AUBERGINE": {
        **_BASE,
        "BG": "#14101E", "PANEL": "#1B162A", "PANEL_ALT": "#241E36", "BORDER": "#362B4A", "BORDER_HI": "#4C3C66",
        "TEXT": "#EFE9FA", "TEXT_DIM": "#9A8CB8", "ACCENT": "#A18BE0", "ACCENT_HOVER": "#BBA6F0",
        "ACCENT_TINT": "#2C2250", "ACCENT_PRESSED": "#7F66C8", "ON_ACCENT": "#14102A",
        "DANGER": "#DE5A70", "OK": "#5FC08E", "WARN": "#CFA85C",
        "SIDEBAR_TOP": "#181327", "SIDEBAR_BOTTOM": "#11101A", "HOVER": "#282042",
        "DANGER_BG": "#361B26", "DANGER_BORDER": "#6D3A46", "DANGER_BG_HOVER": "#45222F",
        "OK_BG": "#133021", "WARN_BG": "#332A16", "HERO_TOP": "#241A3E",
        "BRAND_A": "#A18BE0", "BRAND_B": "#B06BD6", "GLOW_A": "#A18BE0", "GLOW_B": "#B06BD6",
        "GLOW_ALPHA_A": 40, "GLOW_ALPHA_B": 26,
        "C1": "#A18BE0", "C2": "#B06BD6", "C3": "#5FC08E", "C4": "#CFA85C",
    },
    "DEEP_TEAL": {
        **_BASE,
        "BG": "#0D1416", "PANEL": "#141F22", "PANEL_ALT": "#1B282C", "BORDER": "#2C3C40", "BORDER_HI": "#42565C",
        "TEXT": "#E4EFF1", "TEXT_DIM": "#86A0A6", "ACCENT": "#2FA69C", "ACCENT_HOVER": "#57C2B8",
        "ACCENT_TINT": "#143333", "ACCENT_PRESSED": "#20877F", "ON_ACCENT": "#07231F",
        "DANGER": "#DB5A66", "OK": "#45C2A0", "WARN": "#CFA85C",
        "SIDEBAR_TOP": "#111A1D", "SIDEBAR_BOTTOM": "#0B1214", "HOVER": "#1F2D31",
        "DANGER_BG": "#331A1F", "DANGER_BORDER": "#6C3A44", "DANGER_BG_HOVER": "#422228",
        "OK_BG": "#10342C", "WARN_BG": "#332A16", "HERO_TOP": "#17272C",
        "BRAND_A": "#2FA69C", "BRAND_B": "#3EC3D0", "GLOW_A": "#2FA69C", "GLOW_B": "#3EC3D0",
        "GLOW_ALPHA_A": 42, "GLOW_ALPHA_B": 28,
        "C1": "#2FA69C", "C2": "#3EC3D0", "C3": "#6FB788", "C4": "#CFA85C",
    },
    "ESPRESSO": {
        **_BASE,
        "BG": "#16120F", "PANEL": "#1F1916", "PANEL_ALT": "#29211C", "BORDER": "#3D3229", "BORDER_HI": "#584838",
        "TEXT": "#F0E8DD", "TEXT_DIM": "#A7947D", "ACCENT": "#C99860", "ACCENT_HOVER": "#DEB27A",
        "ACCENT_TINT": "#3A2B1C", "ACCENT_PRESSED": "#A87A44", "ON_ACCENT": "#1B130B",
        "DANGER": "#D8625E", "OK": "#9EBB6E", "WARN": "#D8B05C",
        "SIDEBAR_TOP": "#1A1411", "SIDEBAR_BOTTOM": "#131010", "HOVER": "#2E2520",
        "DANGER_BG": "#371C1C", "DANGER_BORDER": "#71403A", "DANGER_BG_HOVER": "#462424",
        "OK_BG": "#2B341C", "WARN_BG": "#372C16", "HERO_TOP": "#2A201A",
        "BRAND_A": "#C99860", "BRAND_B": "#B67F58", "GLOW_A": "#C99860", "GLOW_B": "#B67F58",
        "GLOW_ALPHA_A": 38, "GLOW_ALPHA_B": 25,
        "C1": "#C99860", "C2": "#B67F58", "C3": "#9EBB6E", "C4": "#8FA6C9",
    },
    "ARCTIC": {
        **_BASE,
        "BG": "#E9EEF4", "PANEL": "#F7F9FC", "PANEL_ALT": "#F0F3F8", "BORDER": "#D7E0EA", "BORDER_HI": "#B9C7D8",
        "TEXT": "#243043", "TEXT_DIM": "#68778C", "ACCENT": "#3B7DC4", "ACCENT_HOVER": "#5593DB",
        "ACCENT_TINT": "#E0ECFB", "ACCENT_PRESSED": "#2D62A6", "ON_ACCENT": "#FFFFFF",
        "DANGER": "#D24A4F", "OK": "#2E9E6B", "WARN": "#C0801E",
        "SIDEBAR_TOP": "#FFFFFF", "SIDEBAR_BOTTOM": "#F2F6FA", "HOVER": "#E8EEF6",
        "DANGER_BG": "#F9E4E4", "DANGER_BORDER": "#E2AEB2", "DANGER_BG_HOVER": "#F6D6D7",
        "OK_BG": "#E0F3E9", "WARN_BG": "#FAF0DA", "HERO_TOP": "#DCE8F7",
        "BRAND_A": "#3B7DC4", "BRAND_B": "#6376C9", "GLOW_A": "#3B7DC4", "GLOW_B": "#6376C9",
        "GLOW_ALPHA_A": 40, "GLOW_ALPHA_B": 26,
        "C1": "#3B7DC4", "C2": "#5A6FC4", "C3": "#2E9E6B", "C4": "#C0801E",
    },
    "IVORY": {
        **_BASE,
        "BG": "#F2EEE6", "PANEL": "#FBF8F2", "PANEL_ALT": "#F4F0E7", "BORDER": "#E2DBCB", "BORDER_HI": "#C9BFA8",
        "TEXT": "#33302A", "TEXT_DIM": "#7C7468", "ACCENT": "#AB7A40", "ACCENT_HOVER": "#C78F55",
        "ACCENT_TINT": "#F4E6D4", "ACCENT_PRESSED": "#8E5F2E", "ON_ACCENT": "#FFFFFF",
        "DANGER": "#C24B46", "OK": "#5F9A5B", "WARN": "#A87612",
        "SIDEBAR_TOP": "#FFFFFF", "SIDEBAR_BOTTOM": "#F5F0E6", "HOVER": "#ECE5D8",
        "DANGER_BG": "#F8E0DF", "DANGER_BORDER": "#DFAEAB", "DANGER_BG_HOVER": "#F4D1CF",
        "OK_BG": "#E2F0DF", "WARN_BG": "#F7EDCF", "HERO_TOP": "#EFDCC4",
        "BRAND_A": "#AB7A40", "BRAND_B": "#8A7A5C", "GLOW_A": "#AB7A40", "GLOW_B": "#8A7A5C",
        "GLOW_ALPHA_A": 34, "GLOW_ALPHA_B": 22,
        "C1": "#A8743B", "C2": "#8A7A5C", "C3": "#5F9A5B", "C4": "#A87612",
    },
    "MONO": {
        **_BASE,
        "BG": "#F4F4F5", "PANEL": "#FFFFFF", "PANEL_ALT": "#F7F7F8", "BORDER": "#DCDCE0", "BORDER_HI": "#C0C0C6",
        "TEXT": "#1C1C1E", "TEXT_DIM": "#71717A", "ACCENT": "#3F3F46", "ACCENT_HOVER": "#63636C",
        "ACCENT_TINT": "#ECECEF", "ACCENT_PRESSED": "#27272A", "ON_ACCENT": "#FFFFFF",
        "DANGER": "#C23B3B", "OK": "#3E9E52", "WARN": "#A87900",
        "SIDEBAR_TOP": "#FFFFFF", "SIDEBAR_BOTTOM": "#F4F4F5", "HOVER": "#EAEAEC",
        "DANGER_BG": "#F6E2E2", "DANGER_BORDER": "#DFB3B3", "DANGER_BG_HOVER": "#F1D3D3",
        "OK_BG": "#E1F1E3", "WARN_BG": "#F5EDCF", "HERO_TOP": "#EBEBEE",
        "BRAND_A": "#3F3F46", "BRAND_B": "#86868E", "GLOW_A": "#3F3F46", "GLOW_B": "#86868E",
        "GLOW_ALPHA_A": 30, "GLOW_ALPHA_B": 20,
        "C1": "#52525B", "C2": "#86868E", "C3": "#A1A1AA", "C4": "#C0C0C6",
    },
    "SAGE": {
        **_BASE,
        "BG": "#EDF0E8", "PANEL": "#F9FAF5", "PANEL_ALT": "#F2F4ED", "BORDER": "#E0E3D6", "BORDER_HI": "#C3C9B7",
        "TEXT": "#2B2F26", "TEXT_DIM": "#72796B", "ACCENT": "#6E9363", "ACCENT_HOVER": "#89AD7D",
        "ACCENT_TINT": "#E6EEDF", "ACCENT_PRESSED": "#54764C", "ON_ACCENT": "#FFFFFF",
        "DANGER": "#C1504C", "OK": "#5E9363", "WARN": "#A17B1E",
        "SIDEBAR_TOP": "#FFFFFF", "SIDEBAR_BOTTOM": "#F0F3EA", "HOVER": "#E7EBE0",
        "DANGER_BG": "#F7E2E0", "DANGER_BORDER": "#DFAFAB", "DANGER_BG_HOVER": "#F2D3D1",
        "OK_BG": "#DFEFE0", "WARN_BG": "#F6EDCF", "HERO_TOP": "#E7EDDD",
        "BRAND_A": "#6E9363", "BRAND_B": "#7C8E70", "GLOW_A": "#6E9363", "GLOW_B": "#7C8E70",
        "GLOW_ALPHA_A": 34, "GLOW_ALPHA_B": 22,
        "C1": "#6E9363", "C2": "#7C8E70", "C3": "#A97C50", "C4": "#4E8EA0",
    },
    "PERFORMANCE_RED": {
        **_BASE,
        "BG": "#141114", "PANEL": "#1C171A", "PANEL_ALT": "#251E21", "BORDER": "#3A2B30", "BORDER_HI": "#524046",
        "TEXT": "#F4ECEE", "TEXT_DIM": "#9C8B90", "ACCENT": "#CC4440", "ACCENT_HOVER": "#E75D58",
        "ACCENT_TINT": "#3A1F20", "ACCENT_PRESSED": "#A52E2A", "ON_ACCENT": "#FFFFFF",
        "DANGER": "#E5534F", "OK": "#4EBB87", "WARN": "#D8A24E",
        "SIDEBAR_TOP": "#1A1416", "SIDEBAR_BOTTOM": "#110D0F", "HOVER": "#2A1F22",
        "DANGER_BG": "#3A1A1C", "DANGER_BORDER": "#7A3A3E", "DANGER_BG_HOVER": "#4A2225",
        "OK_BG": "#14301F", "WARN_BG": "#332A14", "HERO_TOP": "#301A1E",
        "BRAND_A": "#CC4440", "BRAND_B": "#B03A4A", "GLOW_A": "#CC4440", "GLOW_B": "#B03A4A",
        "GLOW_ALPHA_A": 45, "GLOW_ALPHA_B": 30,
        "C1": "#CC4440", "C2": "#E07A4A", "C3": "#4EBB87", "C4": "#D8A24E",
    },
    "CYBER": {
        **_BASE,
        "BG": "#0B0F12", "PANEL": "#12181D", "PANEL_ALT": "#1A2228", "BORDER": "#2A343C", "BORDER_HI": "#40505C",
        "TEXT": "#E7F2F4", "TEXT_DIM": "#84A0A8", "ACCENT": "#2FC4BA", "ACCENT_HOVER": "#52D9D0",
        "ACCENT_TINT": "#173836", "ACCENT_PRESSED": "#1E9E96", "ON_ACCENT": "#032826",
        "DANGER": "#E04F6B", "OK": "#3FC98E", "WARN": "#D3A04C",
        "SIDEBAR_TOP": "#10161A", "SIDEBAR_BOTTOM": "#0A0D10", "HOVER": "#1F2A30",
        "DANGER_BG": "#3A1C24", "DANGER_BORDER": "#7A3A48", "DANGER_BG_HOVER": "#4A232D",
        "OK_BG": "#123423", "WARN_BG": "#332A14", "HERO_TOP": "#16292E",
        "BRAND_A": "#2FC4BA", "BRAND_B": "#B060C8", "GLOW_A": "#2FC4BA", "GLOW_B": "#B060C8",
        "GLOW_ALPHA_A": 44, "GLOW_ALPHA_B": 30,
        "C1": "#2FC4BA", "C2": "#B060C8", "C3": "#3FC98E", "C4": "#D3A04C",
    },
    "INDUSTRIAL": {
        **_BASE,
        "BG": "#131416", "PANEL": "#1A1C1F", "PANEL_ALT": "#222529", "BORDER": "#31363C", "BORDER_HI": "#474E57",
        "TEXT": "#EDEEF1", "TEXT_DIM": "#8A9099", "ACCENT": "#DC9A3C", "ACCENT_HOVER": "#EDB35E",
        "ACCENT_TINT": "#3A2D1A", "ACCENT_PRESSED": "#B47E2C", "ON_ACCENT": "#1E1508",
        "DANGER": "#D9585E", "OK": "#57B88B", "WARN": "#E0A33C",
        "SIDEBAR_TOP": "#17181B", "SIDEBAR_BOTTOM": "#101113", "HOVER": "#26292E",
        "DANGER_BG": "#351A1E", "DANGER_BORDER": "#6E3A40", "DANGER_BG_HOVER": "#432226",
        "OK_BG": "#133022", "WARN_BG": "#362C18", "HERO_TOP": "#23272E",
        "BRAND_A": "#DC9A3C", "BRAND_B": "#C06A44", "GLOW_A": "#DC9A3C", "GLOW_B": "#C06A44",
        "GLOW_ALPHA_A": 40, "GLOW_ALPHA_B": 28,
        "C1": "#DC9A3C", "C2": "#C06A44", "C3": "#57B88B", "C4": "#6FA0C9",
    },
    "TACTICAL": {
        **_BASE,
        "BG": "#141510", "PANEL": "#1C1E17", "PANEL_ALT": "#25271E", "BORDER": "#383A2C", "BORDER_HI": "#4F5240",
        "TEXT": "#ECEBDF", "TEXT_DIM": "#979783", "ACCENT": "#8BA04E", "ACCENT_HOVER": "#A6BC68",
        "ACCENT_TINT": "#2E3524", "ACCENT_PRESSED": "#6F8239", "ON_ACCENT": "#13160A",
        "DANGER": "#C85A50", "OK": "#86A86B", "WARN": "#C9A24A",
        "SIDEBAR_TOP": "#191B13", "SIDEBAR_BOTTOM": "#11120D", "HOVER": "#2A2C20",
        "DANGER_BG": "#331C1A", "DANGER_BORDER": "#6B413A", "DANGER_BG_HOVER": "#422320",
        "OK_BG": "#2C3A22", "WARN_BG": "#353019", "HERO_TOP": "#262A1C",
        "BRAND_A": "#8BA04E", "BRAND_B": "#6F8252", "GLOW_A": "#8BA04E", "GLOW_B": "#6F8252",
        "GLOW_ALPHA_A": 38, "GLOW_ALPHA_B": 25,
        "C1": "#8BA04E", "C2": "#6F8252", "C3": "#86A86B", "C4": "#C9A24A",
    },
    "COBALT": {
        **_BASE,
        "BG": "#0D1222", "PANEL": "#131A30", "PANEL_ALT": "#1B2440", "BORDER": "#2C3A5E", "BORDER_HI": "#435582",
        "TEXT": "#E9EEFC", "TEXT_DIM": "#8B98BC", "ACCENT": "#2E6BE0", "ACCENT_HOVER": "#5590F0",
        "ACCENT_TINT": "#1C2C5C", "ACCENT_PRESSED": "#1F4FBC", "ON_ACCENT": "#0B1530",
        "DANGER": "#DD5A66", "OK": "#4CC08A", "WARN": "#D6A45C",
        "SIDEBAR_TOP": "#141B30", "SIDEBAR_BOTTOM": "#0B1020", "HOVER": "#223060",
        "DANGER_BG": "#351A20", "DANGER_BORDER": "#703A46", "DANGER_BG_HOVER": "#432229",
        "OK_BG": "#133022", "WARN_BG": "#332A16", "HERO_TOP": "#16224A",
        "BRAND_A": "#2E6BE0", "BRAND_B": "#4B98E0", "GLOW_A": "#2E6BE0", "GLOW_B": "#4B98E0",
        "GLOW_ALPHA_A": 46, "GLOW_ALPHA_B": 30,
        "C1": "#2E6BE0", "C2": "#4B98E0", "C3": "#4CC08A", "C4": "#D6A45C",
    },
    "COPPER": {
        **_BASE,
        "BG": "#141110", "PANEL": "#1C1816", "PANEL_ALT": "#262019", "BORDER": "#3B3128", "BORDER_HI": "#57483A",
        "TEXT": "#F0E9E1", "TEXT_DIM": "#9E8E7D", "ACCENT": "#C97E47", "ACCENT_HOVER": "#E09A63",
        "ACCENT_TINT": "#3A2A1C", "ACCENT_PRESSED": "#A86235", "ON_ACCENT": "#1E140B",
        "DANGER": "#D85A58", "OK": "#77A65E", "WARN": "#D0A04C",
        "SIDEBAR_TOP": "#191512", "SIDEBAR_BOTTOM": "#110E0C", "HOVER": "#2A2119",
        "DANGER_BG": "#371C1B", "DANGER_BORDER": "#723E3A", "DANGER_BG_HOVER": "#462322",
        "OK_BG": "#2B341F", "WARN_BG": "#352C18", "HERO_TOP": "#2B2018",
        "BRAND_A": "#C97E47", "BRAND_B": "#A2643C", "GLOW_A": "#C97E47", "GLOW_B": "#A2643C",
        "GLOW_ALPHA_A": 40, "GLOW_ALPHA_B": 27,
        "C1": "#C97E47", "C2": "#A2643C", "C3": "#77A65E", "C4": "#8FA0C9",
    },
    # --- Legacy themes restored from v1.2.2 (before the 20-palette refresh) ---
    "DARK": {
        **_BASE,
    },
    "PURPLE": {
        **_BASE,
        "BG": "#0c0817", "PANEL": "#151026", "PANEL_ALT": "#1d1736", "BORDER": "#2b2350", "BORDER_HI": "#43377a",
        "TEXT": "#eee8ff", "TEXT_DIM": "#9d93c8", "ACCENT": "#a259ff", "ACCENT_HOVER": "#b97dff",
        "ACCENT_TINT": "#2c1d52", "ACCENT_PRESSED": "#8640dc", "SIDEBAR_TOP": "#1a1230", "SIDEBAR_BOTTOM": "#110b22",
        "HOVER": "#241c42", "HERO_TOP": "#2b1b52", "BRAND_A": "#c27dff", "BRAND_B": "#ff4fd8",
        "GLOW_A": "#a259ff", "GLOW_B": "#ff4fd8", "C1": "#a259ff", "C2": "#ff4fd8", "C3": "#5ac8fa", "C4": "#ffb03a",
    },
    "GREEN": {
        **_BASE,
        "BG": "#08100d", "PANEL": "#0f1a15", "PANEL_ALT": "#15241d", "BORDER": "#1d3a2e", "BORDER_HI": "#2d5a47",
        "TEXT": "#e3f4ec", "TEXT_DIM": "#86aa99", "ACCENT": "#2ed39a", "ACCENT_HOVER": "#55e4b2",
        "ACCENT_TINT": "#123b2d", "ACCENT_PRESSED": "#1faa7c", "ON_ACCENT": "#04130d",
        "SIDEBAR_TOP": "#10201a", "SIDEBAR_BOTTOM": "#0b1511", "HOVER": "#1a2d24", "HERO_TOP": "#11392b",
        "BRAND_A": "#55e4b2", "BRAND_B": "#2f9bff", "GLOW_A": "#2ed39a", "GLOW_B": "#3fb950",
        "C1": "#2ed39a", "C2": "#5ac8fa", "C3": "#b6e04a", "C4": "#f0a03a",
    },
    "LIGHT": {
        **_BASE,
        "BG": "#eef2f8", "PANEL": "#ffffff", "PANEL_ALT": "#f4f7fb", "BORDER": "#dde4ef", "BORDER_HI": "#c3cee0",
        "TEXT": "#1b2433", "TEXT_DIM": "#66748b", "ACCENT": "#3b82f6", "ACCENT_HOVER": "#5a9bff",
        "ACCENT_TINT": "#e1ecff", "ACCENT_PRESSED": "#2a6fe0", "DANGER": "#d9423a", "OK": "#1fa65a", "WARN": "#e08a00",
        "SIDEBAR_TOP": "#ffffff", "SIDEBAR_BOTTOM": "#f6f8fc", "HOVER": "#edf2fa",
        "DANGER_BG": "#fde8e7", "DANGER_BORDER": "#f1b4b0", "DANGER_BG_HOVER": "#fbd6d4", "WARN_BG": "#fff3d6",
        "OK_BG": "#dcf4e5",
        "HERO_TOP": "#dce9ff", "BRAND_A": "#5a9bff", "BRAND_B": "#8b5cf6", "GLOW_A": "#3b82f6", "GLOW_B": "#8b5cf6",
        "GLOW_ALPHA_A": 40, "GLOW_ALPHA_B": 28, "C1": "#3b82f6", "C2": "#8b5cf6", "C3": "#14b8a6", "C4": "#f59e0b",
    },
    "AMOLED": {
        **_BASE,
        "BG": "#000000", "PANEL": "#08090b", "PANEL_ALT": "#101216", "BORDER": "#1a1d24", "BORDER_HI": "#2a2f3a",
        "TEXT": "#f1f3f7", "TEXT_DIM": "#858c9a", "ACCENT": "#2f80ff", "ACCENT_HOVER": "#5a9bff",
        "ACCENT_TINT": "#0f2347", "ACCENT_PRESSED": "#1f66d6", "SIDEBAR_TOP": "#050608", "SIDEBAR_BOTTOM": "#000000",
        "HOVER": "#14171d", "DANGER_BG": "#2a0f0e", "DANGER_BORDER": "#5c2420", "DANGER_BG_HOVER": "#3a1412",
        "OK_BG": "#0e2616", "HERO_TOP": "#0d1d3d", "BRAND_A": "#5a9bff", "BRAND_B": "#7a5cff",
        "GLOW_ALPHA_A": 55, "GLOW_ALPHA_B": 35, "C1": "#2f80ff", "C2": "#9b6dff", "C3": "#19d3e0", "C4": "#ffb03a",
    },
}

THEME_ALIASES: dict[str, str] = {
    "MATRIX": "CYBER",
    "CYBERPUNK": "CYBER",
    "NORD": "MIDNIGHT",
    "TOKYO_NIGHT": "MIDNIGHT",
    "DRACULA": "AUBERGINE",
    "GRUVBOX": "ESPRESSO",
    "MONOKAI": "GRAPHITE",
}

THEME_LABELS: dict[str, str] = {
    "GRAPHITE": "Graphite",
    "TRUE_BLACK": "True Black",
    "SLATE": "Slate",
    "TITANIUM": "Titanium",
    "FOREST": "Forest",
    "BURGUNDY": "Burgundy",
    "MIDNIGHT": "Midnight",
    "AUBERGINE": "Aubergine",
    "DEEP_TEAL": "Deep Teal",
    "ESPRESSO": "Espresso",
    "ARCTIC": "Arctic",
    "IVORY": "Ivory",
    "MONO": "Mono",
    "SAGE": "Sage",
    "PERFORMANCE_RED": "Performance Red",
    "CYBER": "Cyber",
    "INDUSTRIAL": "Industrial",
    "TACTICAL": "Tactical",
    "COBALT": "Cobalt",
    "COPPER": "Copper",
    "DARK": "Black Cyber",
    "PURPLE": "Purple Neon",
    "GREEN": "Green Nature",
    "LIGHT": "Light",
    "AMOLED": "AMOLED Neon",
}

BG: str
PANEL: str
PANEL_ALT: str
BORDER: str
BORDER_HI: str
TEXT: str
TEXT_DIM: str
ACCENT: str
ACCENT_HOVER: str
ACCENT_TINT: str
ACCENT_PRESSED: str
ON_ACCENT: str
DANGER: str
OK: str
WARN: str
SIDEBAR_TOP: str
SIDEBAR_BOTTOM: str
HOVER: str
DANGER_BG: str
DANGER_BORDER: str
DANGER_BG_HOVER: str
OK_BG: str
WARN_BG: str
HERO_TOP: str
BRAND_A: str
BRAND_B: str
GLOW_A: str
GLOW_B: str
GLOW_ALPHA_A: int
GLOW_ALPHA_B: int
C1: str
C2: str
C3: str
C4: str


DEFAULT_THEME = "GRAPHITE"


def saved_theme() -> str:
    raw: str | None = None
    try:
        from app.settings import data_root

        raw_path = data_root() / "settings.json"
        if raw_path.exists():
            import json

            raw = str(json.loads(raw_path.read_text(encoding="utf-8")).get("theme") or "").strip() or None
    except Exception:
        raw = None
    if not raw:
        try:
            from app.settings import SettingsService

            raw = str(SettingsService().get("theme"))
        except Exception:
            raw = None
    name = (raw or DEFAULT_THEME).upper()
    name = THEME_ALIASES.get(name, name)
    return name if name in PALETTES else DEFAULT_THEME


if "CURRENT_THEME" not in globals() or CURRENT_THEME not in PALETTES:
    CURRENT_THEME = saved_theme()
globals().update(PALETTES[CURRENT_THEME])


def set_theme(name: str) -> str:
    """Switch the active theme live: update module globals + application styling."""
    global CURRENT_THEME

    name = THEME_ALIASES.get(name, name)
    if name not in PALETTES:
        name = DEFAULT_THEME
    CURRENT_THEME = name
    globals().update(PALETTES[CURRENT_THEME])
    return CURRENT_THEME

NAV_WIDTH = 232

UI_FONTS = '"Inter", "Segoe UI Variable Text", "Segoe UI", sans-serif'
MONO_FONTS = '"JetBrains Mono", "Cascadia Mono", "Consolas", monospace'

FONT_UI = UI_FONTS
FONT_DISPLAY = UI_FONTS
FONT_MONO = MONO_FONTS

FONT_SCALE = 1.12
BASE_FONT_PX = round(13 * FONT_SCALE)


def fs(px: int) -> int:
    """Scale a design-time font size (px) by the global FONT_SCALE."""
    return max(1, round(px * FONT_SCALE))


def _fonts_dir():
    import sys as _sys
    from pathlib import Path

    base = Path(getattr(_sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / "assets" / "fonts"


def load_fonts() -> list[str]:
    """Register the bundled Inter / JetBrains Mono files (OFL) so the UI looks the same on every PC."""
    from PySide6.QtGui import QFontDatabase

    loaded: list[str] = []
    folder = _fonts_dir()
    if folder.is_dir():
        for path in sorted(folder.glob("*.ttf")):
            if QFontDatabase.addApplicationFont(str(path)) >= 0:
                loaded.append(path.name)
    return loaded


def _mix(a: str, b: str, t: float) -> str:
    """Blend two #RRGGBB colors: t=0 -> a, t=1 -> b."""
    a, b = a.lstrip("#"), b.lstrip("#")
    ca = [int(a[i : i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b[i : i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ca, cb, strict=False))


# Secondary buttons must stand out from the panel (border >= ~2.5:1), in every theme.
BTN_FILL = _mix(PANEL_ALT, TEXT, 0.05)
BTN_FILL_HOVER = _mix(PANEL_ALT, TEXT, 0.11)
BTN_BORDER = _mix(PANEL, TEXT_DIM, 0.58)


def _chevron_path(color: str) -> str:
    """Render a small down-chevron PNG (for combo boxes) and return its path for QSS url()."""
    import tempfile
    from pathlib import Path

    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF

    path = Path(tempfile.gettempdir()) / f"pcopt_chevron_{color.lstrip('#')}.png"
    img = QImage(24, 24, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 2.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawPolyline(QPolygonF([QPointF(6, 9), QPointF(12, 15), QPointF(18, 9)]))
    p.end()
    img.save(str(path))
    return path.as_posix()


def build_stylesheet() -> str:
    CHEVRON = _chevron_path(TEXT_DIM)
    qss = f"""
* {{
    font-family: {FONT_UI};
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QWidget#root {{
    background: {BG};
}}
QWidget#sidebar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {SIDEBAR_TOP}, stop:1 {SIDEBAR_BOTTOM});
    border-right: 1px solid {BORDER};
}}
QScrollArea#navScroll {{
    background: transparent;
    border: none;
}}
QScrollArea#navScroll QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px 0;
}}
QScrollArea#navScroll QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollArea#navScroll QScrollBar::add-line:vertical,
QScrollArea#navScroll QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollArea#navScroll QScrollBar::add-page:vertical,
QScrollArea#navScroll QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QLabel#brand {{
    font-size: 15px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#brandSub {{
    font-size: 12px;
    color: {TEXT_DIM};
}}
QPushButton[nav="true"] {{
    background: transparent;
    border: none;
    border-radius: 9px;
    color: {TEXT_DIM};
    text-align: left;
    padding: 7px 14px 7px 14px;
    margin: 1px 10px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton[nav="true"][hot="true"] {{
    background: {PANEL_ALT};
    color: {TEXT};
}}
QPushButton[nav="true"]:focus {{
    border: none;
    outline: none;
}}
QPushButton[nav="true"]:checked, QPushButton[nav="true"]:checked:focus, QPushButton[nav="true"]:checked:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {BRAND_A}, stop:1 {BRAND_B});
    border: none;
    border-radius: 9px;
    color: #FFFFFF;
    font-weight: 700;
    padding-left: 14px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: 24px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: {BORDER_HI};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QWidget#sidebarFooter {{
    border-top: 1px solid {BORDER};
}}
QLabel#footerText {{
    color: {TEXT_DIM};
    font-size: 12px;
    padding: 12px 18px;
}}
QWidget#page {{
    background: {BG};
}}
QLabel#cardValue, QLabel#gaugeValue, QLabel#heroValue, QLabel#ringValue, QLabel#clock, QLabel#scoreValue, QLabel#statValue {{
    font-family: {FONT_MONO};
}}
QLabel#pageTitle, QLabel#welcome, QLabel#heroValue, QLabel#scoreValue {{
    font-family: {FONT_UI};
}}
QLabel#pageTitle {{
    font-size: 26px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#pageDesc {{
    font-size: 13px;
    color: {TEXT_DIM};
}}
QFrame#card {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QLabel#cardTitle {{
    font-size: 12px;
    font-weight: 600;
    color: {TEXT_DIM};
}}
QLabel#cardValue {{
    font-size: 30px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#gaugeValue {{
    font-size: 28px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#gaugeTitle {{
    font-size: 16px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#iconTile {{
    background: {ACCENT_TINT};
    border-radius: 10px;
}}
QLabel#heroValue {{
    font-size: 40px;
    font-weight: 800;
    color: {TEXT};
}}
QLabel#welcome {{
    font-size: 30px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#tileTitle {{
    font-size: 14px;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#tileArrow {{
    font-size: 22px;
    color: {TEXT_DIM};
}}
QPushButton#linkButton {{
    background: transparent;
    border: none;
    padding: 4px 0;
    color: {ACCENT};
    font-weight: 600;
    text-align: left;
}}
QPushButton#linkButton:hover {{
    color: {ACCENT_HOVER};
    background: transparent;
}}
QPushButton[tile="true"] {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 12px;
    text-align: left;
    padding: 0;
}}
QPushButton[tile="true"]:hover {{
    background: {PANEL_ALT};
    border-color: {ACCENT};
}}
QFrame#gameTile {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame#gameTile:hover {{
    border-color: {BORDER_HI};
}}
QFrame#gameTile[selected="true"] {{
    border-color: {ACCENT};
    background: {PANEL_ALT};
}}
QLabel#tileCover {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QPushButton#starButton {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: 8px;
    color: {TEXT_DIM};
    font-size: 15px;
    padding: 2px;
}}
QPushButton#starButton:hover {{
    border-color: {ACCENT};
    color: {WARN};
}}
QPushButton#starButton:checked {{
    color: {WARN};
    border-color: {WARN};
}}
QListWidget#historyList {{
    background: transparent;
    border: none;
    outline: none;
}}
QListWidget#historyList::item {{
    color: {TEXT};
    padding: 6px 4px;
    border-bottom: 1px solid {BORDER};
}}
QListWidget#historyList::item:selected {{
    background: {ACCENT_TINT};
    color: {TEXT};
    border-radius: 6px;
}}
QFrame#hero {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {HERO_TOP}, stop:1 {PANEL});
    border: 1px solid {BORDER_HI};
    border-radius: 14px;
}}
QLabel#ringValue {{
    font-size: 26px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#ringSub {{
    font-size: 12px;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#clock {{
    font-size: 22px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#sysStatus {{
    font-size: 11px;
    font-weight: 600;
    color: {OK};
    padding: 12px 18px 2px 18px;
}}
QLabel#sysStatus[level="warn"] {{
    color: {WARN};
}}
QLabel#sysStatus[level="danger"] {{
    color: {DANGER};
}}
QPushButton[seg="true"] {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px 12px;
    color: {TEXT_DIM};
    font-size: 12px;
}}
QPushButton[seg="true"]:hover {{
    color: {TEXT};
    background: {PANEL_ALT};
}}
QPushButton[seg="true"]:checked {{
    background: {ACCENT_TINT};
    color: {ACCENT};
    font-weight: 600;
}}
QPushButton[quick="true"] {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 9px;
    text-align: left;
    padding: 8px 14px;
    font-weight: 600;
}}
QPushButton[quick="true"]:hover {{
    border-color: {ACCENT};
    background: {ACCENT_TINT};
}}
QLabel#scoreValue {{
    font-size: 44px;
    font-weight: 800;
    color: {TEXT};
    background: transparent;
}}
QLabel#statValue {{
    font-size: 20px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#livePill {{
    background: {OK_BG};
    color: {OK};
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#cardSub {{
    font-size: 12px;
    color: {TEXT_DIM};
}}
QLabel#cardRow {{
    font-size: 12px;
    color: {TEXT};
}}
QLabel#errorLine {{
    color: {WARN};
    background: {WARN_BG};
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
}}
QLabel#gpuName {{
    font-size: 16px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#pageBadge {{
    background: {ACCENT_TINT};
    color: {ACCENT};
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QStatusBar {{
    background: {PANEL};
    padding-left: 8px;
    color: {TEXT_DIM};
    border-top: 1px solid {BORDER};
}}
QStatusBar::item {{
    border: none;
}}
QWidget#topBar {{
    background: {PANEL};
    border-bottom: 1px solid {BORDER};
}}
QLabel#topBarTitle {{
    font-size: 16px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#topBarStatus {{
    font-size: 12px;
    font-weight: 600;
    color: {OK};
    padding: 4px 12px;
    border-radius: 14px;
    background: {OK_BG};
}}
QLabel#topBarStatus[level="warn"] {{
    background: {WARN_BG};
    color: {WARN};
}}
QLabel#topBarStatus[level="danger"] {{
    background: {DANGER_BG};
    color: {DANGER};
}}
QPushButton#topBarIcon {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 6px;
}}
QPushButton#topBarIcon:hover {{
    background: {PANEL_ALT};
}}
QPushButton#topBarIcon::menu-indicator {{
    image: none;
}}
QFrame#card:hover {{
    border-color: {BORDER_HI};
}}
QTableWidget::item {{
    padding: 6px 8px;
}}
QTableWidget::item:hover {{
    background: {HOVER};
}}
QTableWidget {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
    gridline-color: transparent;
    alternate-background-color: {PANEL_ALT};
    selection-background-color: {ACCENT_TINT};
    selection-color: {TEXT};
    padding: 4px;
}}
QHeaderView::section {{
    background: {PANEL};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 10px 8px;
    font-size: 12px;
    font-weight: 600;
    text-align: left;
}}
QLineEdit {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QLineEdit:focus {{
    border-color: {ACCENT};
}}
QPushButton[secondary="true"] {{
    background: {BTN_FILL};
    border: 1px solid {BTN_BORDER};
    border-radius: 10px;
    padding: 9px 16px;
    color: {TEXT};
}}
QPushButton[secondary="true"]:hover {{
    border-color: {ACCENT};
}}
QPushButton[compact="true"] {{
    padding: 4px 12px;
    border-radius: 8px;
}}
QPushButton[danger="true"] {{
    background: {DANGER_BG};
    color: {DANGER};
    border: 1px solid {DANGER_BORDER};
    border-radius: 10px;
    padding: 9px 16px;
    font-weight: 600;
}}
QPushButton[danger="true"]:hover {{
    background: {DANGER_BG_HOVER};
}}
QPushButton[danger="true"]:disabled {{
    background: {PANEL_ALT};
    color: {TEXT_DIM};
    border: 1px solid {BORDER};
}}
QPushButton {{
    background: {BTN_FILL};
    color: {TEXT};
    border: 1px solid {BTN_BORDER};
    border-radius: 10px;
    padding: 9px 16px;
    font-weight: 600;
}}
QPushButton:hover {{
    border-color: {ACCENT};
    background: {BTN_FILL_HOVER};
}}
QPushButton:pressed {{
    background: {ACCENT_TINT};
    border-color: {ACCENT};
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    background: transparent;
    border-color: {BORDER};
}}
QPushButton:focus {{
    outline: none;
    border-color: {ACCENT};
}}
QPushButton[primary="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {BRAND_A}, stop:1 {BRAND_B});
    border: 1px solid transparent;
    color: #FFFFFF;
    font-weight: 700;
    padding: 9px 20px;
}}
QPushButton[primary="true"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT_HOVER}, stop:1 {BRAND_B});
    border-color: rgba(255, 255, 255, 90);
}}
QPushButton[primary="true"]:pressed {{
    background: {ACCENT_PRESSED};
    border-color: transparent;
}}
QPushButton[primary="true"]:disabled {{
    background: {ACCENT_TINT};
    border-color: transparent;
    color: {TEXT_DIM};
}}
QToolTip {{
    background: {PANEL_ALT};
    color: {TEXT};
    border: 1px solid {BORDER_HI};
    padding: 5px 8px;
}}
QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {BORDER_HI};
    background: {PANEL_ALT};
}}
QCheckBox::indicator:hover {{
    border-color: {ACCENT};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QComboBox, QSpinBox {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
}}
QComboBox {{
    padding-right: 28px;
}}
QComboBox::drop-down {{
    border: none;
    width: 26px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}}
QComboBox::down-arrow {{
    image: url({CHEVRON});
    width: 12px;
    height: 12px;
}}
QComboBox:hover, QSpinBox:hover, QComboBox:focus, QSpinBox:focus {{
    border-color: {ACCENT};
}}
QComboBox QAbstractItemView {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER_HI};
    selection-background-color: {ACCENT_TINT};
    outline: none;
}}
QMenu {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER_HI};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 7px 18px;
    border-radius: 5px;
}}
QMenu::item:selected {{
    background: {ACCENT_TINT};
}}
QLabel#navSection {{
    font-size: 11px;
    font-weight: 700;
    color: {TEXT_DIM};
    padding: 16px 26px 4px 26px;
}}
QLabel#brandMark {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {BRAND_A}, stop:1 {BRAND_B});
    color: #ffffff;
    border-radius: 8px;
    font-weight: 800;
    font-size: 13px;
}}
QWidget#brandBox {{
    border-bottom: 1px solid {BORDER};
}}
QSplitter::handle {{
    background: transparent;
}}
QSplitter::handle:horizontal {{
    width: 10px;
}}
QSplitter::handle:vertical {{
    height: 10px;
}}
QMessageBox {{
    background: {PANEL};
}}
QScrollBar:vertical {{
    background: {BG};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {BG};
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 5px;
    min-width: 30px;
}}
"""
    qss = re.sub(
        r"font-size:\s*(\d+)px",
        lambda m: f"font-size: {round(int(m.group(1)) * FONT_SCALE)}px",
        qss,
    )
    return qss



def apply(app) -> None:
    from PySide6.QtGui import QColor, QFont, QPalette

    app.setStyle("Fusion")
    load_fonts()
    base = QFont()
    base.setFamilies(["Inter", "Segoe UI Variable Text", "Segoe UI"])
    base.setPixelSize(BASE_FONT_PX)
    base.setWeight(QFont.Weight.Medium)
    base.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    base.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(base)
    app.setStyleSheet(build_stylesheet())
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(PANEL_ALT))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(PANEL_ALT))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_DIM))
    app.setPalette(palette)
