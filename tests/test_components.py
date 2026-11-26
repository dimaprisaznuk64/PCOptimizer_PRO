from __future__ import annotations

from PySide6.QtWidgets import QPushButton

from app.ui import components as ui_components
from app.ui import theme
from app.ui.components import MetricCard, PerfChart, RingCard, Sparkline


def test_level_color_thresholds() -> None:
    assert ui_components.level_color(95) == ui_components.DANGER
    assert ui_components.level_color(90) == ui_components.DANGER
    assert ui_components.level_color(75) == ui_components.WARN
    assert ui_components.level_color(74) == ui_components.ACCENT
    assert ui_components.level_color(0) == ui_components.ACCENT


def test_level_color_thresholds_with_custom_base() -> None:
    assert ui_components.level_color(30, base=ui_components.OK) == ui_components.OK
    assert ui_components.level_color(90, base=ui_components.OK) == ui_components.DANGER
    assert ui_components.level_color(80, base=ui_components.OK) == ui_components.WARN


def test_metric_card_spark_range_stored(qapp) -> None:
    card = MetricCard("CPU", spark_range=(0, 100))
    assert card.spark._range == (0, 100)


def test_sparkline_explicit_range(qapp) -> None:
    assert Sparkline(value_range=(0, 100))._range == (0, 100)
    assert Sparkline()._range is None


def test_metric_card_bar_color_follows_level(qapp) -> None:
    card = MetricCard("CPU", color=ui_components.ACCENT)
    card.update_metric("80%", percent=80)
    assert card.bar._color == ui_components.WARN
    card.update_metric("95%", percent=95)
    assert card.bar._color == ui_components.DANGER
    card.update_metric("50%", percent=50)
    assert card.bar._color == ui_components.ACCENT


def test_set_mono_uses_readable_percentage_spacing(qapp) -> None:
    from PySide6.QtGui import QFont, QFontMetrics
    from PySide6.QtWidgets import QLabel

    label = QLabel("CPU 73%")
    label.setFont(QFont("Geist"))
    base_width = QFontMetrics(label.font()).horizontalAdvance(label.text())

    theme.set_mono(label, size=13, spacing_pct=14.0)

    font = label.font()
    assert font.letterSpacing() == 114.0
    assert QFontMetrics(font).horizontalAdvance(label.text()) > base_width


def test_ring_card_displays_value(qapp) -> None:
    card = RingCard("CPU", ui_components.ACCENT)
    card.update_metric("42%", percent=42.0)
    assert card.value.text() == "42%"


def test_component_animations_use_shared_motion_tokens(qapp) -> None:
    from PySide6.QtWidgets import QLabel

    assert RingCard("CPU", ui_components.ACCENT)._shadow_anim.duration() == theme.MOTION_BASE
    assert ui_components._Ring(ui_components.ACCENT)._anim.duration() == theme.MOTION_VALUE
    assert ui_components.ScoreRing(QLabel())._anim.duration() == theme.MOTION_AMOUNT


def test_perf_chart_clear_removes_old_series(qapp) -> None:
    chart = PerfChart(points=50)
    chart.push(1.0, cpu=10.0, ram=20.0)
    assert chart._canvas._history["cpu"]
    chart.clear()
    assert chart._canvas._history == {}
    assert list(chart._canvas._times) == []


def test_score_ring_color_for(qapp) -> None:
    assert ui_components.ScoreRing.color_for(90) == ui_components.OK
    assert ui_components.ScoreRing.color_for(60) == ui_components.WARN
    assert ui_components.ScoreRing.color_for(20) == ui_components.DANGER


def test_chart_time_axis_single_formatter(qapp) -> None:
    from app.ui.components import _ChartCanvas

    # Uniform -m:ss labels — mixing "min"/"s" units confused users.
    assert _ChartCanvas._span_text(0) == "-0:00"
    assert _ChartCanvas._span_text(59) == "-0:59"
    assert _ChartCanvas._span_text(60) == "-1:00"
    assert _ChartCanvas._span_text(119) == "-1:59"
    assert _ChartCanvas._span_text(120) == "-2:00"


def test_chart_axis_labels_are_monotonic(qapp) -> None:
    from app.ui.components import _ChartCanvas

    labels = [_ChartCanvas._span_text(seconds) for seconds in (119, 89, 60, 30, 0)]

    def to_seconds(text: str) -> float:
        minutes, secs = text.lstrip("-").split(":")
        return float(minutes) * 60 + float(secs)

    values = [to_seconds(text) for text in labels]
    assert values == sorted(values, reverse=True)


def test_chart_series_colors_are_distinct_and_match_cards(qapp) -> None:
    from app.ui.components import chart_series_color

    assert chart_series_color("C2") == theme.C2
    assert chart_series_color("C3") == theme.C3
    assert chart_series_color("WARN") == theme.WARN
    # CPU / GPU / RAM map to three different colours (the conftest pins EN; the
    # exact hex comes from the active theme).
    assert len({theme.C2, theme.C3, theme.WARN}) == 3



def test_perf_chart_legend_follows_selected_tab(qapp) -> None:
    from app.i18n import tr
    from app.ui.components import PerfChart

    chart = PerfChart()
    chart.select("all")
    assert set(chart._legend) == {"cpu", "gpu", "ram"}
    chart.select("net")
    assert set(chart._legend) == {"net_down", "net_up"}
    labels = {key: lbl.text() for key, lbl in chart._legend.items()}
    assert tr("dash_net_download") in labels["net_down"]
    assert tr("dash_net_upload") in labels["net_up"]
    chart.select("cpu")
    assert set(chart._legend) == {"cpu"}


def test_perf_chart_header_keeps_legend_and_tabs_readable(qapp) -> None:
    chart = PerfChart(title="Історія ресурсів")
    chart.resize(520, 300)
    chart.show()
    qapp.processEvents()
    pills = [chart._legend_layout.itemAt(i).widget() for i in range(chart._legend_layout.count())]
    tabs = [b for b in chart.findChildren(QPushButton) if b.property("seg")]
    assert pills and tabs
    assert all(p.width() >= p.sizeHint().width() - 2 for p in pills)
    assert all(b.width() >= b.sizeHint().width() - 2 for b in tabs)
    assert ui_components.CardTitleLabel("ОСТАННІ ЗАПУСКИ").wordWrap()


def test_perf_chart_range_filters_history(qapp) -> None:
    chart = PerfChart(points=120, enable_range=True)
    for i in range(120):
        chart.push(float(i * 10), cpu=float(i))
    assert chart._range_seconds == 60
    indices = chart._canvas._visible_indices()
    assert len(indices) == 7
    assert chart._canvas._series_values("cpu", indices)[-1] == 119.0
    chart.set_range(300)
    assert chart._range_buttons[300].isChecked()
    assert len(chart._canvas._visible_indices()) == 31
    chart.set_range(0)
    assert len(chart._canvas._visible_indices()) == 120


def test_perf_chart_range_controls_retranslate_and_expand(qapp) -> None:
    from app.i18n import tr

    chart = PerfChart(enable_range=True)
    chart.resize(700, 320)
    chart.show()
    qapp.processEvents()
    assert set(chart._range_buttons) == {60, 300, 900, 3600}
    assert chart._range_buttons[60].text() == tr("chart_range_60s")
    assert chart.expand_button is not None
    buttons = [*chart._range_buttons.values(), chart.expand_button]
    assert all(b.width() >= b.sizeHint().width() - 2 for b in buttons)
    before = chart._canvas.minimumHeight()
    chart.expand_button.click()
    qapp.processEvents()
    assert chart._expanded
    assert chart._canvas.minimumHeight() > before
    assert chart.expand_button.text() == tr("chart_collapse")
    chart.expand_button.click()
    qapp.processEvents()
    assert not chart._expanded
    assert chart._canvas.minimumHeight() == before
    assert chart.expand_button.text() == tr("chart_expand")


def test_chart_net_tab_draws_two_series(qapp) -> None:
    from app.ui.components import _ChartCanvas

    canvas = _ChartCanvas(points=20)
    canvas.set_key("net", percent=False)
    for i in range(6):
        canvas.push(float(i), {"net_down": 1000.0 * i, "net_up": 500.0 * i})
    series = canvas._series_to_draw()
    assert {key for key, _c, _s in series} == {"net_down", "net_up"}
    # Two distinct colours so the two lines are distinguishable.
    assert len({color.name() for _k, color, _s in series}) == 2


def test_chart_net_tab_supports_legacy_single_series(qapp) -> None:
    from app.ui.components import _ChartCanvas

    canvas = _ChartCanvas(points=20)
    canvas.set_key("net", percent=False)
    for i in range(6):
        canvas.push(float(i), {"net": 1000.0 * i})
    assert {key for key, _c, _s in canvas._series_to_draw()} == {"net"}


def test_chart_smoothing_averages_neighbours() -> None:
    from app.ui.components import _ChartCanvas

    smoothed = _ChartCanvas._smooth([0.0, 0.0, 100.0, 0.0, 0.0], window=3)
    # The lone spike is averaged down, so its peak is no longer 100.
    assert max(smoothed) < 100.0
    assert len(smoothed) == 5
    # A flat line stays flat.
    assert _ChartCanvas._smooth([5.0, 5.0, 5.0]) == [5.0, 5.0, 5.0]


def test_decimate_for_width_keeps_peaks_and_bounds_points() -> None:
    values = [float(i % 100) for i in range(3600)]
    values[1800] = 1000.0  # one sample spike must survive decimation
    points = ui_components.decimate_for_width(values, 40)
    assert len(points) <= 2 * 40 + 4
    assert points[0] == (0, values[0])
    assert points[-1] == (3599, values[-1])
    assert max(points, key=lambda pair: pair[1]) == (1800, 1000.0)
    assert all(a[0] < b[0] for a, b in zip(points, points[1:], strict=False))
    # Short series are left untouched.
    assert ui_components.decimate_for_width(values[:10], 40) == list(enumerate(values[:10]))


def test_chart_paint_decimates_long_history(qapp, monkeypatch) -> None:
    from PySide6.QtGui import QPixmap

    from app.ui.components import _ChartCanvas

    counts: list[int] = []
    monkeypatch.setattr(
        ui_components.QPainter,
        "drawPath",
        lambda self, path: counts.append(path.elementCount()),
    )
    canvas = _ChartCanvas(points=3600)
    canvas.resize(320, 160)
    for i in range(3600):
        canvas.push(float(i), {"cpu": float(i % 100)})
    canvas.render(QPixmap(canvas.size()))
    assert len(counts) == 1  # only the cpu series has data
    # ~10800 raw cubic path elements before; bounded by the plot width now.
    assert max(counts) < 1000


def test_chart_axis_hi_has_network_floor(qapp) -> None:
    from app.ui.components import _ChartCanvas

    canvas = _ChartCanvas(points=20)
    canvas.set_key("net", percent=False)
    for i in range(4):
        canvas.push(float(i), {"net_down": 200.0, "net_up": 100.0})
    series = canvas._series_to_draw()
    # Tiny idle traffic must not scale the axis up to a spike.
    assert canvas._axis_hi(series) >= 100 * 1024.0


def test_chart_axis_hi_is_percent_for_load_tabs(qapp) -> None:
    from app.ui.components import _ChartCanvas

    canvas = _ChartCanvas(points=20)
    canvas.set_key("all", percent=True)
    canvas.push(0.0, {"cpu": 10.0, "ram": 20.0, "gpu": 5.0})
    assert canvas._axis_hi(canvas._series_to_draw()) == 100.0


def test_chart_hidden_series_are_filtered(qapp) -> None:
    from app.ui.components import _ChartCanvas

    canvas = _ChartCanvas(points=20)
    canvas.set_key("all", percent=True)
    for i in range(4):
        canvas.push(float(i), {"cpu": 10.0, "ram": 20.0, "gpu": 5.0})
    canvas.set_hidden({"gpu"})
    assert {key for key, _c, _s in canvas._series_to_draw()} == {"ram", "cpu"}


def test_chart_missing_reading_repeats_last_value(qapp) -> None:
    from app.ui.components import _ChartCanvas

    canvas = _ChartCanvas(10)
    canvas.push(0.0, {"gpu": 42.0})
    canvas.push(1.0, {"gpu": None})
    # A missed reading must not look like a drop to 0.
    assert list(canvas._history["gpu"]) == [42.0, 42.0]


def test_chart_hover_paints_without_error(qapp) -> None:
    from PySide6.QtGui import QPixmap

    from app.ui.components import _ChartCanvas

    canvas = _ChartCanvas(30)
    canvas.resize(500, 200)
    for i in range(20):
        canvas.push(float(i), {"cpu": 10.0 + i, "ram": 50.0, "gpu": 5.0})
    canvas._hover_x = 250.0
    pixmap = QPixmap(canvas.size())
    canvas.render(pixmap)
    assert not pixmap.isNull()


def test_perf_chart_legend_pill_toggles_series(qapp) -> None:
    from app.ui.components import PerfChart

    chart = PerfChart()
    chart.select("all")
    for i in range(4):
        chart.push(float(i), cpu=10.0, ram=20.0, gpu=5.0)
    chart._toggle_series("gpu")
    assert "gpu" in chart._hidden
    assert {key for key, _c, _s in chart._canvas._series_to_draw()} == {"ram", "cpu"}
    # Toggling back on restores the series.
    chart._toggle_series("gpu")
    assert "gpu" not in chart._hidden
    assert {key for key, _c, _s in chart._canvas._series_to_draw()} == {"ram", "cpu", "gpu"}


def test_perf_chart_legend_never_hides_last_series(qapp) -> None:
    from app.ui.components import PerfChart

    chart = PerfChart()
    chart.select("cpu")
    chart._toggle_series("cpu")
    # The last visible series must stay on screen.
    assert "cpu" not in chart._hidden
    assert {key for key, _c, _s in chart._canvas._series_to_draw()} == {"cpu"}


# ---------- review batch: axis / line weights / threshold / hover ----------


def test_time_step_for_round_steps() -> None:
    from app.ui.components import time_step_for

    assert time_step_for(8) == 5
    assert time_step_for(40) == 10
    assert time_step_for(60) == 10
    assert time_step_for(120) == 30
    assert time_step_for(700) == 120
    assert time_step_for(100_000) == 1800


def test_chart_line_spec_emphasizes_only_cpu_when_multi() -> None:
    from app.ui.components import chart_line_spec

    # Uniform pen width; only the fill differs (CPU / single series).
    assert chart_line_spec("cpu", multi=True) == (True, 2.5)
    assert chart_line_spec("ram", multi=True) == (False, 2.5)
    assert chart_line_spec("gpu", multi=True) == (False, 2.5)
    assert chart_line_spec("ram", multi=False) == (True, 2.5)


def test_time_ticks_are_aligned_and_uniform(qapp) -> None:
    from app.ui.components import _ChartCanvas

    canvas = _ChartCanvas(120)
    # Short span -> round pure-second labels.
    ticks = canvas._time_ticks(40.0, 600.0)
    assert [label for _x, label in ticks] == ["-10s", "-20s", "-30s"]
    xs = [x for x, _ in ticks]
    assert xs == sorted(xs, reverse=True)
    assert all(x <= 600.0 - 70 for x in xs)
    # Long span -> uniform -m:ss labels (no unit mixing within one view).
    ticks = canvas._time_ticks(120.0, 600.0)
    assert [label for _x, label in ticks] == ["-0:30", "-1:00", "-1:30"]
    # Empty / tiny buffer draws nothing.
    assert canvas._time_ticks(0.0, 600.0) == []


def test_ring_keeps_series_color_and_marks_threshold_only(qapp) -> None:
    from PySide6.QtGui import QColor, QPixmap

    from app.ui.components import _Ring

    ring = _Ring(ui_components.ACCENT, size=124)
    ring.resize(124, 124)
    ring.set_percent(95.0)
    pixmap = QPixmap(ring.size())
    ring.render(pixmap)
    image = pixmap.toImage()
    danger = QColor(ui_components.DANGER)
    accent = QColor(ui_components.ACCENT)
    danger_hits = accent_hits = 0
    for y in range(image.height()):
        for x in range(image.width()):
            px = QColor(image.pixel(x, y))
            if px.alpha() < 160:
                continue
            if (px.red(), px.green(), px.blue()) == (danger.red(), danger.green(), danger.blue()):
                danger_hits += 1
            elif (px.red(), px.green(), px.blue()) == (accent.red(), accent.green(), accent.blue()):
                accent_hits += 1
    # The 95% arc stays series-coloured; red appears only as the 90% tick.
    assert accent_hits >= 50
    assert danger_hits < 100


def test_bar_marker_and_card_panel_propagation(qapp) -> None:
    from app.ui.components import Bar, CardPanel

    bar = Bar()
    bar.set_marker(85.0)
    assert bar._marker == 85.0
    bar.set_marker(150.0)
    assert bar._marker == 100.0
    bar.set_marker(None)
    assert bar._marker is None

    panel = CardPanel("Thermals")
    panel.set_rows([("CPU", 70.0, "70 C"), ("GPU", 86.0, "86 C")], marker=85.0)
    assert [b._marker for _l, b, _t in panel._rows.values()] == [85.0, 85.0]
    panel.set_rows([("CPU", 70.0, "70 C")])
    assert [b._marker for _l, b, _t in panel._rows.values()] == [None]


def test_ring_card_border_is_property_driven(qapp) -> None:
    card = RingCard("CPU", ui_components.ACCENT)
    # No CSS :hover (it could get stuck) — explicit hot property instead.
    assert "hover" not in card.styleSheet()
    assert '[hot="true"]' in card.styleSheet()
    assert card.property("hot") is False
    card._set_hot(True)
    assert card.property("hot") is True
    card._set_hot(False)
    assert card.property("hot") is False


def test_chart_hover_mouse_move_sets_hover_x(qapp) -> None:
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    from app.ui.components import _ChartCanvas

    canvas = _ChartCanvas(30)
    canvas.resize(500, 200)
    for i in range(10):
        canvas.push(float(i), {"cpu": 30.0})
    pos = QPointF(250, 100)
    canvas.mouseMoveEvent(
        QMouseEvent(
            QEvent.Type.MouseMove, pos, pos, pos,
            Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert canvas._hover_x == 250.0
    from PySide6.QtGui import QPixmap

    pixmap = QPixmap(canvas.size())
    canvas.render(pixmap)
    assert not pixmap.isNull()

def test_empty_hint_fits_short_table_at_high_scale(qapp) -> None:
    from PySide6.QtWidgets import QTableWidget

    from app.ui.components import attach_empty_hint

    original = theme.UI_SCALE
    try:
        theme.set_ui_scale(150)
        table = QTableWidget(0, 2)
        table.resize(600, 90)
        hint = attach_empty_hint(table, "bench_history_empty")
        hint.refresh()
        assert hint.heightForWidth(hint.width()) <= hint.height() + 3
    finally:
        theme.set_ui_scale(original)


def test_perf_chart_title_wraps_long_text(qapp) -> None:
    chart = PerfChart(title="Історія ресурсів · 60 хв")
    assert chart._title_label.wordWrap()
