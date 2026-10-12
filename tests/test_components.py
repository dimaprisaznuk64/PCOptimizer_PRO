from __future__ import annotations

from app.ui.components import MetricCard, RingCard, ScoreRing, Sparkline, level_color
from app.ui.theme import ACCENT, DANGER, OK, WARN


def test_level_color_thresholds() -> None:
    assert level_color(95) == DANGER
    assert level_color(90) == DANGER
    assert level_color(75) == WARN
    assert level_color(74) == ACCENT
    assert level_color(0) == ACCENT


def test_level_color_thresholds_with_custom_base() -> None:
    assert level_color(30, base=OK) == OK
    assert level_color(90, base=OK) == DANGER
    assert level_color(80, base=OK) == WARN


def test_metric_card_spark_range_stored(qapp) -> None:
    card = MetricCard("CPU", spark_range=(0, 100))
    assert card.spark._range == (0, 100)


def test_sparkline_explicit_range(qapp) -> None:
    assert Sparkline(value_range=(0, 100))._range == (0, 100)
    assert Sparkline()._range is None


def test_metric_card_bar_color_follows_level(qapp) -> None:
    card = MetricCard("CPU", color=ACCENT)
    card.update_metric("80%", percent=80)
    assert card.bar._color == WARN
    card.update_metric("95%", percent=95)
    assert card.bar._color == DANGER
    card.update_metric("50%", percent=50)
    assert card.bar._color == ACCENT


def test_ring_card_displays_value(qapp) -> None:
    card = RingCard("CPU", ACCENT)
    card.update_metric("42%", percent=42.0)
    assert card.value.text() == "42%"


def test_score_ring_color_for(qapp) -> None:
    assert ScoreRing.color_for(90) == OK
    assert ScoreRing.color_for(60) == WARN
    assert ScoreRing.color_for(20) == DANGER