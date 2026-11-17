from app.i18n.translations import TRANSLATIONS
from app.ui.icons import _DRAWERS
from app.ui.pages import build_pages
from app.ui.sidebar import NAV_KEYS


def test_nav_registration_contract(qapp) -> None:
    pairs = build_pages()
    pages = dict(pairs)
    nav_keys = {key for key, _ in NAV_KEYS}

    assert len(pages) == len(pairs)
    assert nav_keys == set(pages)
    assert nav_keys <= set(_DRAWERS)

    for _, tr_key in NAV_KEYS:
        assert tr_key in TRANSLATIONS["EN"]
        assert tr_key in TRANSLATIONS["UA"]

    for key, page in pages.items():
        assert hasattr(page, "retranslate"), key
