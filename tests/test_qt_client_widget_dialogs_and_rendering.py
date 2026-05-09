from datetime import datetime

from PyQt5.QtCore import Qt

from alco_esp import qt_client


def test_all_data_button_first_click_creates_visible_dialog(qtbot, widget_monitor):
    monitor = widget_monitor

    qtbot.mouseClick(monitor.all_data_button, Qt.LeftButton)

    assert monitor.all_data_viewer_dialog is not None
    assert monitor.all_data_viewer_dialog.isVisible() is True


def test_all_data_button_second_click_reuses_existing_instance(qtbot, widget_monitor):
    monitor = widget_monitor

    qtbot.mouseClick(monitor.all_data_button, Qt.LeftButton)
    first_dialog = monitor.all_data_viewer_dialog

    qtbot.mouseClick(monitor.all_data_button, Qt.LeftButton)

    assert monitor.all_data_viewer_dialog is first_dialog


def test_closing_all_data_dialog_clears_window_reference(qtbot, widget_monitor):
    monitor = widget_monitor

    qtbot.mouseClick(monitor.all_data_button, Qt.LeftButton)
    dialog = monitor.all_data_viewer_dialog
    dialog.close()

    qtbot.waitUntil(lambda: monitor.all_data_viewer_dialog is None)


def test_settings_dialog_cancel_keeps_existing_settings_and_status(
    qtbot,
    widget_monitor,
    settings_dialog_stub_factory,
    default_settings,
    monkeypatch,
):
    monitor = widget_monitor
    settings_before = monitor.settings.copy()
    save_calls = []

    settings_dialog_stub_factory(accepted=False, returned_settings=default_settings)
    monkeypatch.setattr(qt_client, "save_settings", lambda payload: save_calls.append(payload))

    qtbot.mouseClick(monitor.settings_button, Qt.LeftButton)

    assert monitor.settings == settings_before
    assert save_calls == []
    assert monitor.status_label.text() == "Подключение..."


def test_settings_dialog_accept_saves_once_and_sets_exact_status(
    qtbot,
    widget_monitor,
    settings_dialog_stub_factory,
    monkeypatch,
):
    monitor = widget_monitor
    save_calls = []

    new_settings = monitor.settings.copy()
    new_settings["temp_stop_razgon"] = 73.0

    settings_dialog_stub_factory(accepted=True, returned_settings=new_settings)
    monkeypatch.setattr(qt_client, "save_settings", lambda payload: save_calls.append(payload.copy()))

    qtbot.mouseClick(monitor.settings_button, Qt.LeftButton)

    assert save_calls == [new_settings]
    assert monitor.settings == new_settings
    assert monitor.status_label.text() == "Настройки обновлены."


def test_settings_dialog_accept_chart_change_uses_plot_update_branch(
    qtbot,
    widget_monitor,
    settings_dialog_stub_factory,
    monkeypatch,
):
    monitor = widget_monitor
    new_settings = monitor.settings.copy()
    new_settings["chart_y_min"] = 5.0

    branch_calls = []
    settings_dialog_stub_factory(accepted=True, returned_settings=new_settings)
    monkeypatch.setattr(qt_client, "save_settings", lambda _payload: None)
    monkeypatch.setattr(monitor, "update_plots_and_signals", lambda: branch_calls.append("plot_update"))
    monkeypatch.setattr(monitor, "check_signal_conditions", lambda: branch_calls.append("signal_check"))

    qtbot.mouseClick(monitor.settings_button, Qt.LeftButton)

    assert branch_calls == ["plot_update"]


def test_settings_dialog_accept_without_chart_change_uses_signal_check_branch(
    qtbot,
    widget_monitor,
    settings_dialog_stub_factory,
    monkeypatch,
):
    monitor = widget_monitor
    new_settings = monitor.settings.copy()
    new_settings["temp_stop_razgon"] = 71.0

    branch_calls = []
    settings_dialog_stub_factory(accepted=True, returned_settings=new_settings)
    monkeypatch.setattr(qt_client, "save_settings", lambda _payload: None)
    monkeypatch.setattr(monitor, "update_plots_and_signals", lambda: branch_calls.append("plot_update"))
    monkeypatch.setattr(monitor, "check_signal_conditions", lambda: branch_calls.append("signal_check"))

    qtbot.mouseClick(monitor.settings_button, Qt.LeftButton)

    assert branch_calls == ["signal_check"]


def test_settings_dialog_accept_changed_t_kub_threshold_calls_silent_reset(
    qtbot,
    widget_monitor,
    settings_dialog_stub_factory,
    monkeypatch,
):
    monitor = widget_monitor
    new_settings = monitor.settings.copy()
    new_settings["t_signal_kub"] = 61.0

    reset_calls = []
    settings_dialog_stub_factory(accepted=True, returned_settings=new_settings)
    monkeypatch.setattr(qt_client, "save_settings", lambda _payload: None)
    monkeypatch.setattr(monitor, "reset_t_kub_signal", lambda inform=False: reset_calls.append(inform))

    qtbot.mouseClick(monitor.settings_button, Qt.LeftButton)

    assert reset_calls == [False]


def test_settings_dialog_accept_changed_t_deflegmator_threshold_calls_silent_reset(
    qtbot,
    widget_monitor,
    settings_dialog_stub_factory,
    monkeypatch,
):
    monitor = widget_monitor
    new_settings = monitor.settings.copy()
    new_settings["t_signal_deflegmator"] = 71.0

    reset_calls = []
    settings_dialog_stub_factory(accepted=True, returned_settings=new_settings)
    monkeypatch.setattr(qt_client, "save_settings", lambda _payload: None)
    monkeypatch.setattr(monitor, "reset_t_deflegmator_signal", lambda inform=False: reset_calls.append(inform))

    qtbot.mouseClick(monitor.settings_button, Qt.LeftButton)

    assert reset_calls == [False]


def test_settings_dialog_accept_changed_stability_settings_calls_silent_reset(
    qtbot,
    widget_monitor,
    settings_dialog_stub_factory,
    monkeypatch,
):
    monitor = widget_monitor
    new_settings = monitor.settings.copy()
    new_settings["delta_t"] = 0.4

    reset_calls = []
    settings_dialog_stub_factory(accepted=True, returned_settings=new_settings)
    monkeypatch.setattr(qt_client, "save_settings", lambda _payload: None)
    monkeypatch.setattr(monitor, "reset_stability_signal", lambda inform=False: reset_calls.append(inform))

    qtbot.mouseClick(monitor.settings_button, Qt.LeftButton)

    assert reset_calls == [False]


def test_update_text_displays_with_empty_data_shows_exact_dash_lines(widget_monitor):
    monitor = widget_monitor

    monitor.last_mqtt_message_time = None
    monitor.all_latest_values.clear()
    monitor.update_text_displays()

    assert monitor.term_d_label.text() == "T дефл.: -"
    assert monitor.term_c_label.text() == "T царга: -"
    assert monitor.term_k_label.text() == "T куб: -"
    assert monitor.power_label.text() == "Мощность: -"
    assert monitor.press_a_label.text() == "Атм. давл.: -"
    assert monitor.flag_otb_label.text() == "Флаг отбора: -"
    assert monitor.term_k_m_label.text() == "Остановка разгона при T куба: -"


def test_telemetry_numeric_rendering_updates_main_labels_exactly(widget_monitor):
    monitor = widget_monitor

    monitor.all_latest_values.update(
        {
            "term_d": "56.78",
            "term_c": "57.89",
            "term_k": "58.91",
            "power": "1200.25",
            "press_a": "760.48",
            "flag_otb": "разгон",
        }
    )
    monitor.last_mqtt_message_time = datetime(2026, 5, 9, 10, 11, 12)
    monitor.update_text_displays()

    assert monitor.last_update_time_label.text() == "Последнее сообщение от устройства: 10:11:12"
    assert monitor.term_d_label.text() == "T дефл.: 56.8 °C"
    assert monitor.term_c_label.text() == "T царга: 57.9 °C"
    assert monitor.term_k_label.text() == "T куб:     58.9 °C"
    assert monitor.power_label.text() == "Мощность: 1200.2 Вт"
    assert monitor.press_a_label.text() == "Атм. давл.: 760.5 мм.рт.ст"
    assert monitor.flag_otb_label.text() == "Флаг отбора: разгон"


def test_telemetry_control_current_values_render_exactly(widget_monitor):
    monitor = widget_monitor

    monitor.all_latest_values.update(
        {
            "otbor_g_1": "21",
            "term_c_max": "80.2",
            "term_c_min": "79.7",
            "otbor_t": "41",
            "term_k_m": "99.95",
        }
    )
    monitor.update_text_displays()

    assert monitor.otbor_g_1_label.text() == "ШИМ, % (сейчас <b>21</b>):"
    assert monitor.term_c_max_telo_label.text() == "T стоп, °C (сейчас <b>80.2</b>):"
    assert monitor.term_c_min_telo_label.text() == "T старт, °C (сейчас <b>79.7</b>):"
    assert monitor.otbor_t_label.text() == "ШИМ, % (сейчас <b>41</b>):"
    assert monitor.term_k_m_label.text() == "Остановка разгона при T куба: <b>100.0°C</b>"


def test_telemetry_non_numeric_control_values_render_exactly(widget_monitor):
    monitor = widget_monitor

    monitor.all_latest_values.update(
        {
            "term_c_max": "N/A",
            "term_c_min": "not_ready",
            "term_k_m": "pending",
        }
    )
    monitor.update_text_displays()

    assert monitor.term_c_max_telo_label.text() == "T стоп, °C (сейчас <b>N/A</b>):"
    assert monitor.term_c_min_telo_label.text() == "T старт, °C (сейчас <b>not_ready</b>):"
    assert monitor.term_k_m_label.text() == "Остановка разгона при T куба: <b>pending</b>"
