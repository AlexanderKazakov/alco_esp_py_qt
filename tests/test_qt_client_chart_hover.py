from datetime import datetime, timedelta, timezone

from matplotlib.backend_bases import MouseEvent

from alco_esp import qt_client


def test_nearest_sample_index_picks_closer_neighbor():
    times = [
        datetime(2026, 8, 22, 12, 0, 0),
        datetime(2026, 8, 22, 12, 0, 10),
        datetime(2026, 8, 22, 12, 0, 20),
    ]

    assert qt_client.nearest_sample_index([], datetime(2026, 8, 22, 12, 0, 5)) is None
    assert qt_client.nearest_sample_index(times, datetime(2026, 8, 22, 11, 59, 0)) == 0
    assert qt_client.nearest_sample_index(times, datetime(2026, 8, 22, 12, 1, 0)) == 2
    assert qt_client.nearest_sample_index(times, datetime(2026, 8, 22, 12, 0, 12)) == 1
    assert qt_client.nearest_sample_index(times, datetime(2026, 8, 22, 12, 0, 16)) == 2


def test_find_nearest_index_within_pixel_distance_respects_radius():
    x_pixels = [10.0, 50.0, 90.0]
    y_pixels = [10.0, 50.0, 90.0]

    assert qt_client.find_nearest_index_within_pixel_distance(x_pixels, y_pixels, 52.0, 49.0, 5) == 1
    assert qt_client.find_nearest_index_within_pixel_distance(x_pixels, y_pixels, 52.0, 49.0, 1) is None
    assert qt_client.find_nearest_index_within_pixel_distance([], [], 0.0, 0.0, 18) is None


def test_format_chart_hover_text_includes_time_and_all_series():
    point_time = datetime(2026, 8, 22, 8, 22, 48, 120000)
    text = qt_client.format_chart_hover_text(
        point_time,
        [
            ("T дефл.", 56.78),
            ("T царга", None),
            ("T куб", 78.1),
        ],
    )

    assert text == (
        "Время: 08:22:48.120\n"
        "T дефл.: 56.78 °C\n"
        "T царга: -\n"
        "T куб: 78.10 °C"
    )


def test_naive_datetime_from_chart_x_strips_timezone():
    aware = datetime(2026, 8, 22, 12, 0, 0, tzinfo=timezone.utc)
    naive = datetime(2026, 8, 22, 12, 0, 0)

    assert qt_client.naive_datetime_from_chart_x(aware) == naive
    assert qt_client.naive_datetime_from_chart_x(naive) == naive
    assert qt_client.naive_datetime_from_chart_x(qt_client.mdates.date2num(naive)) == naive


def test_chart_hover_text_offset_points_stays_up_right_when_there_is_room():
    x_offset, y_offset = qt_client.chart_hover_text_offset_points(
        point_x=100,
        point_y=100,
        axes_x0=0,
        axes_y0=0,
        axes_x1=800,
        axes_y1=600,
        box_width=200,
        box_height=100,
        offset_points=14,
    )

    assert (x_offset, y_offset) == (14, 14)


def test_chart_hover_text_offset_points_mirrors_left_near_right_edge():
    x_offset, y_offset = qt_client.chart_hover_text_offset_points(
        point_x=780,
        point_y=100,
        axes_x0=0,
        axes_y0=0,
        axes_x1=800,
        axes_y1=600,
        box_width=200,
        box_height=100,
        offset_points=14,
    )

    assert x_offset == -14
    assert y_offset == 14


def test_chart_hover_text_offset_points_mirrors_down_near_top_edge():
    x_offset, y_offset = qt_client.chart_hover_text_offset_points(
        point_x=100,
        point_y=580,
        axes_x0=0,
        axes_y0=0,
        axes_x1=800,
        axes_y1=600,
        box_width=200,
        box_height=100,
        offset_points=14,
    )

    assert x_offset == 14
    assert y_offset == -14


def test_chart_hover_text_offset_points_picks_side_with_more_room_when_both_overflow():
    x_offset, y_offset = qt_client.chart_hover_text_offset_points(
        point_x=90,
        point_y=40,
        axes_x0=0,
        axes_y0=0,
        axes_x1=120,
        axes_y1=80,
        box_width=200,
        box_height=100,
        offset_points=14,
    )

    assert x_offset == -14
    assert y_offset == 14


def _fill_chart_series(monitor, now):
    monitor.timestamps["term_d"].append(now)
    monitor.data["term_d"].append(56.78)
    monitor.timestamps["term_c"].append(now + timedelta(milliseconds=200))
    monitor.data["term_c"].append(57.91)
    monitor.timestamps["term_k"].append(now)
    monitor.data["term_k"].append(78.12)
    monitor.update_plots()
    monitor.canvas.draw()


def _mouse_event_at_data_point(monitor, topic, sample_index, y_offset_pixels=0.0):
    line = monitor.lines[topic]
    x_value = line.get_xdata()[sample_index]
    y_value = float(line.get_ydata()[sample_index])
    x_num = float(monitor.ax.convert_xunits(x_value))
    pixel_x, pixel_y = monitor.ax.transData.transform((x_num, y_value))
    return MouseEvent(
        "motion_notify_event",
        monitor.canvas,
        pixel_x,
        pixel_y + y_offset_pixels,
    )


def test_chart_hover_popup_shows_all_y_values_near_a_point(qtbot, widget_monitor):
    monitor = widget_monitor
    monitor.resize(1100, 700)
    qtbot.waitUntil(lambda: monitor.canvas.width() > 100)

    now = datetime(2026, 8, 22, 8, 22, 48, 120000)
    _fill_chart_series(monitor, now)

    event = _mouse_event_at_data_point(monitor, "term_k", 0)
    monitor._on_chart_mouse_move(event)

    assert monitor.chart_hover_annotation.get_visible() is True
    hover_text = monitor.chart_hover_annotation.get_text()
    assert "Время: 08:22:48.120" in hover_text
    assert "T дефл.: 56.78 °C" in hover_text
    assert "T царга: 57.91 °C" in hover_text
    assert "T куб: 78.12 °C" in hover_text


def test_chart_hover_popup_hides_when_cursor_is_far_from_points(qtbot, widget_monitor):
    monitor = widget_monitor
    monitor.resize(1100, 700)
    qtbot.waitUntil(lambda: monitor.canvas.width() > 100)

    now = datetime(2026, 8, 22, 8, 22, 48)
    _fill_chart_series(monitor, now)

    near_event = _mouse_event_at_data_point(monitor, "term_c", 0)
    monitor._on_chart_mouse_move(near_event)
    assert monitor.chart_hover_annotation.get_visible() is True

    far_event = _mouse_event_at_data_point(monitor, "term_c", 0, y_offset_pixels=80)
    monitor._on_chart_mouse_move(far_event)
    assert monitor.chart_hover_annotation.get_visible() is False


def test_chart_hover_popup_hides_when_cursor_leaves_figure(qtbot, widget_monitor):
    monitor = widget_monitor
    monitor.resize(1100, 700)
    qtbot.waitUntil(lambda: monitor.canvas.width() > 100)

    now = datetime(2026, 8, 22, 8, 22, 48)
    _fill_chart_series(monitor, now)
    monitor._on_chart_mouse_move(_mouse_event_at_data_point(monitor, "term_d", 0))
    assert monitor.chart_hover_annotation.get_visible() is True

    monitor._hide_chart_hover()
    assert monitor.chart_hover_annotation.get_visible() is False
    assert monitor._chart_hover_point_key is None


def _fill_chart_series_range(monitor, start, point_count, step_seconds=10):
    for index in range(point_count):
        sample_time = start + timedelta(seconds=index * step_seconds)
        monitor.timestamps["term_d"].append(sample_time)
        monitor.data["term_d"].append(44.46)
        monitor.timestamps["term_c"].append(sample_time)
        monitor.data["term_c"].append(44.0)
        monitor.timestamps["term_k"].append(sample_time)
        monitor.data["term_k"].append(43.01)
    monitor.update_plots()
    monitor.canvas.draw()


def test_chart_hover_popup_stays_to_the_right_near_left_edge(qtbot, widget_monitor):
    monitor = widget_monitor
    monitor.resize(1100, 700)
    qtbot.waitUntil(lambda: monitor.canvas.width() > 100)

    _fill_chart_series_range(monitor, datetime(2026, 8, 22, 8, 0, 0), 30)
    monitor._on_chart_mouse_move(_mouse_event_at_data_point(monitor, "term_c", 0))

    x_offset, y_offset = monitor.chart_hover_annotation.xyann
    assert x_offset > 0
    assert y_offset > 0
    assert monitor.chart_hover_annotation.get_ha() == "left"
    assert monitor.chart_hover_annotation.get_va() == "bottom"


def test_chart_hover_popup_mirrors_left_near_right_edge(qtbot, widget_monitor):
    monitor = widget_monitor
    monitor.resize(1100, 700)
    qtbot.waitUntil(lambda: monitor.canvas.width() > 100)

    _fill_chart_series_range(monitor, datetime(2026, 8, 22, 8, 0, 0), 30)
    monitor._on_chart_mouse_move(_mouse_event_at_data_point(monitor, "term_c", 29))

    x_offset, _y_offset = monitor.chart_hover_annotation.xyann
    assert x_offset < 0
    assert monitor.chart_hover_annotation.get_ha() == "right"
    assert monitor.chart_hover_annotation.get_visible() is True
