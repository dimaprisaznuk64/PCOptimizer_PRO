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


def test_chart_time_axis_single_formatter(qapp) -> None:
    from app.ui.components import _ChartCanvas

    assert _ChartCanvas._span_text(0) == "0 s"
    assert _ChartCanvas._span_text(59) == "59 s"
    assert _ChartCanvas._span_text(60) == "1 min"
    assert _ChartCanvas._span_text(119) == "2 min"


def test_chart_axis_labels_are_monotonic(qapp) -> None:
    from app.ui.components import _ChartCanvas

    labels = [_ChartCanvas._span_text(seconds) for seconds in (119, 89, 60, 30, 0)]

    def to_seconds(text: str) -> float:
        value = float(text.split()[0])
        return value * 60 if text.endswith("min") else value

    values = [to_seconds(text) for text in labels]
    assert values == sorted(values, reverse=True)
    assert "min" not in labels[-1]