import pytest
from PyQt5.QtCore import Qt

from alco_esp import qt_client
from alco_esp.child_dialogs import WorkModeUnknownDialog
from alco_esp.constants import STYLE_MONITORING, WorkState


def click_set_button(qtbot, monitor, find_push_button, index):
    """Clicks one of the duplicate 'Установить' buttons by stable positional index."""
    qtbot.mouseClick(find_push_button(monitor, "Установить", index), Qt.LeftButton)


def capture_scheduled_callbacks(monkeypatch):
    scheduled_callbacks = []
    monkeypatch.setattr(
        qt_client.QTimer,
        "singleShot",
        staticmethod(lambda delay, callback: scheduled_callbacks.append((delay, callback))),
    )
    return scheduled_callbacks


def work_mode_unknown_dialogs(monitor):
    return monitor.findChildren(WorkModeUnknownDialog)


BODY_TAKEOFF_PARAMETER_BUTTONS = [
    pytest.param(2, "term_c_max_telo_spinbox", 78.4, ("term_c_max_new", "78.4"), id="t_stop"),
    pytest.param(3, "term_c_min_telo_spinbox", 77.1, ("term_c_min_new", "77.1"), id="t_start"),
    pytest.param(4, "otbor_t_spinbox", 42, ("otbor_t_new", "42"), id="pwm"),
]


def test_work_mode_stop_click_emits_and_resets_combobox(qtbot, widget_monitor, publish_capture):
    monitor = widget_monitor
    emitted = publish_capture(monitor)

    monitor.work_mode_combobox.setCurrentIndex(monitor.work_mode_combobox.findData(WorkState.STOP.value))
    qtbot.mouseClick(monitor.set_work_mode_button, Qt.LeftButton)

    assert emitted == [("work", "0")]
    assert monitor.work_mode_combobox.currentText() == "Выбрать"
    assert monitor.status_label.text() == "Запрос на установку режима: стоп (0)"


def test_work_mode_placeholder_click_emits_nothing(qtbot, widget_monitor, publish_capture):
    monitor = widget_monitor
    emitted = publish_capture(monitor)

    monitor.work_mode_combobox.setCurrentIndex(0)
    qtbot.mouseClick(monitor.set_work_mode_button, Qt.LeftButton)

    assert emitted == []
    assert monitor.status_label.text() == "Подключение..."


def test_work_mode_razgon_click_emits_sequence_and_sets_pending_check(qtbot, widget_monitor, publish_capture):
    monitor = widget_monitor
    emitted = publish_capture(monitor)

    monitor.work_mode_combobox.setCurrentIndex(monitor.work_mode_combobox.findData(WorkState.RAZGON.value))
    qtbot.mouseClick(monitor.set_work_mode_button, Qt.LeftButton)

    assert emitted == [("term_k_r", "70.0"), ("work", "4")]
    assert monitor.pending_term_k_m_check is True
    assert monitor._term_k_m_check_timer is not None
    assert monitor._term_k_m_check_timer.isSingleShot() is True
    assert monitor.status_label.text() == "Запрос на установку режима: разгон (4)"


def test_work_mode_otbor_tela_click_emits_expected_payload(qtbot, widget_monitor, publish_capture):
    monitor = widget_monitor
    emitted = publish_capture(monitor)

    monitor.work_mode_combobox.setCurrentIndex(monitor.work_mode_combobox.findData(WorkState.OTBOR_TELA.value))
    qtbot.mouseClick(monitor.set_work_mode_button, Qt.LeftButton)

    assert emitted == [("work", "8")]
    assert monitor.status_label.text() == "Запрос на установку режима: отбор тела (8)"


def test_otbor_golov_pwm_button_uses_spinbox_value(qtbot, widget_monitor, publish_capture, find_push_button):
    monitor = widget_monitor
    emitted = publish_capture(monitor)

    monitor.otbor_g_1_spinbox.setValue(33)
    click_set_button(qtbot, monitor, find_push_button, index=1)

    assert emitted == [("otbor_g_1_new", "33")]
    assert monitor.status_label.text() == "Запрос на ШИМ отбора голов: 33"


def test_otbor_tela_t_stop_button_uses_spinbox_value(qtbot, widget_monitor, publish_capture, find_push_button):
    monitor = widget_monitor
    emitted = publish_capture(monitor)

    monitor.term_c_max_telo_spinbox.setValue(78.4)
    click_set_button(qtbot, monitor, find_push_button, index=2)

    assert emitted == [("term_c_max_new", "78.4")]
    assert monitor.status_label.text() == "Запрос T стоп отбора тела: 78.4°C"


def test_otbor_tela_t_start_button_uses_spinbox_value(qtbot, widget_monitor, publish_capture, find_push_button):
    monitor = widget_monitor
    emitted = publish_capture(monitor)

    monitor.term_c_min_telo_spinbox.setValue(77.1)
    click_set_button(qtbot, monitor, find_push_button, index=3)

    assert emitted == [("term_c_min_new", "77.1")]
    assert monitor.status_label.text() == "Запрос T старт отбора тела: 77.1°C"


def test_otbor_tela_pwm_button_uses_spinbox_value(qtbot, widget_monitor, publish_capture, find_push_button):
    monitor = widget_monitor
    emitted = publish_capture(monitor)

    monitor.otbor_t_spinbox.setValue(42)
    click_set_button(qtbot, monitor, find_push_button, index=4)

    assert emitted == [("otbor_t_new", "42")]
    assert monitor.status_label.text() == "Запрос ШИМ отбора тела: 42%"


def test_last_work_command_label_follows_work_messages_from_broker(widget_monitor):
    monitor = widget_monitor
    assert monitor.last_work_command_label.text() == "Последняя команда режима работы: неизвестна"

    monitor.handle_message("work", "8")
    assert monitor.last_work_command_label.text() == "Последняя команда режима работы: отбор тела (8)"

    monitor.handle_message("work", "99")
    assert monitor.last_work_command_label.text() == "Последняя команда режима работы: неизвестна"


def test_heads_pwm_republishes_work_when_device_is_confirmed_in_heads_mode(
    qtbot, monkeypatch, widget_monitor, publish_capture, find_push_button
):
    monitor = widget_monitor
    emitted = publish_capture(monitor)
    scheduled_callbacks = capture_scheduled_callbacks(monkeypatch)
    monitor.handle_message("work", "9")
    monitor.handle_message("flag_otb", "Golov")

    monitor.otbor_g_1_spinbox.setValue(33)
    click_set_button(qtbot, monitor, find_push_button, index=1)

    assert emitted == [("otbor_g_1_new", "33")]
    assert [delay for delay, _callback in scheduled_callbacks] == [qt_client.WORK_MODE_REPUBLISH_DELAY_MS]

    scheduled_callbacks[0][1]()

    assert emitted == [("otbor_g_1_new", "33"), ("work", "9")]
    assert work_mode_unknown_dialogs(monitor) == []


@pytest.mark.parametrize("flag_otb", ["Telo", "OFF"])
@pytest.mark.parametrize("button_index, spinbox_name, value, expected_publish", BODY_TAKEOFF_PARAMETER_BUTTONS)
def test_body_parameter_republishes_work_when_device_is_confirmed_in_body_mode(
    qtbot, monkeypatch, widget_monitor, publish_capture, find_push_button,
    flag_otb, button_index, spinbox_name, value, expected_publish,
):
    # "OFF" is the start-stop pause. The device is still in body takeoff.
    monitor = widget_monitor
    emitted = publish_capture(monitor)
    scheduled_callbacks = capture_scheduled_callbacks(monkeypatch)
    monitor.handle_message("work", "8")
    monitor.handle_message("flag_otb", flag_otb)

    getattr(monitor, spinbox_name).setValue(value)
    click_set_button(qtbot, monitor, find_push_button, index=button_index)
    scheduled_callbacks[0][1]()

    assert emitted == [expected_publish, ("work", "8")]
    assert work_mode_unknown_dialogs(monitor) == []


def test_heads_pwm_asks_operator_when_last_work_command_is_unknown(
    qtbot, monkeypatch, widget_monitor, publish_capture, find_push_button
):
    # flag_otb alone is not enough: "Golov" does not tell which heads takeoff mode is active.
    monitor = widget_monitor
    emitted = publish_capture(monitor)
    scheduled_callbacks = capture_scheduled_callbacks(monkeypatch)
    monitor.handle_message("flag_otb", "Golov")

    monitor.otbor_g_1_spinbox.setValue(33)
    click_set_button(qtbot, monitor, find_push_button, index=1)

    assert emitted == [("otbor_g_1_new", "33")]
    assert scheduled_callbacks == []
    dialogs = work_mode_unknown_dialogs(monitor)
    assert len(dialogs) == 1
    assert dialogs[0].isVisible()
    assert dialogs[0].windowTitle() == "Режим работы неизвестен"


def test_heads_pwm_asks_operator_when_flag_otb_does_not_confirm_heads_mode(
    qtbot, monkeypatch, widget_monitor, publish_capture, find_push_button
):
    monitor = widget_monitor
    emitted = publish_capture(monitor)
    scheduled_callbacks = capture_scheduled_callbacks(monkeypatch)
    monitor.handle_message("work", "9")
    monitor.handle_message("flag_otb", "OFF")

    monitor.otbor_g_1_spinbox.setValue(33)
    click_set_button(qtbot, monitor, find_push_button, index=1)

    assert emitted == [("otbor_g_1_new", "33")]
    assert scheduled_callbacks == []
    assert len(work_mode_unknown_dialogs(monitor)) == 1


@pytest.mark.parametrize("flag_otb", ["End", "Error"])
def test_body_takeoff_stop_forgets_last_work_command_and_blocks_republish(
    qtbot, monkeypatch, widget_monitor, publish_capture, find_push_button, flag_otb
):
    # The real device reports End or Error, then OFF. OFF must not restart body takeoff.
    monitor = widget_monitor
    emitted = publish_capture(monitor)
    scheduled_callbacks = capture_scheduled_callbacks(monkeypatch)
    monitor.handle_message("work", "8")
    monitor.handle_message("flag_otb", "Telo")
    monitor.handle_message("flag_otb", flag_otb)
    monitor.handle_message("flag_otb", "OFF")

    assert monitor.last_work_command_label.text() == "Последняя команда режима работы: неизвестна"

    monitor.term_c_max_telo_spinbox.setValue(78.4)
    click_set_button(qtbot, monitor, find_push_button, index=2)

    assert emitted == [("term_c_max_new", "78.4")]
    assert scheduled_callbacks == []
    assert len(work_mode_unknown_dialogs(monitor)) == 1


def test_body_parameter_during_heat_up_neither_republishes_nor_asks_operator(
    qtbot, monkeypatch, widget_monitor, publish_capture, find_push_button
):
    # The device stores the value and uses it when body takeoff starts.
    monitor = widget_monitor
    emitted = publish_capture(monitor)
    scheduled_callbacks = capture_scheduled_callbacks(monkeypatch)
    monitor.handle_message("work", str(WorkState.RAZGON.value))
    monitor.handle_message("flag_otb", "OFF")

    monitor.term_c_max_telo_spinbox.setValue(78.4)
    click_set_button(qtbot, monitor, find_push_button, index=2)

    assert emitted == [("term_c_max_new", "78.4")]
    assert scheduled_callbacks == []
    assert work_mode_unknown_dialogs(monitor) == []


def test_second_unconfirmed_parameter_change_does_not_open_second_popup(
    qtbot, monkeypatch, widget_monitor, publish_capture, find_push_button
):
    monitor = widget_monitor
    emitted = publish_capture(monitor)
    capture_scheduled_callbacks(monkeypatch)

    monitor.term_c_max_telo_spinbox.setValue(78.4)
    click_set_button(qtbot, monitor, find_push_button, index=2)
    monitor.term_c_min_telo_spinbox.setValue(77.1)
    click_set_button(qtbot, monitor, find_push_button, index=3)

    assert emitted == [("term_c_max_new", "78.4"), ("term_c_min_new", "77.1")]
    dialogs = work_mode_unknown_dialogs(monitor)
    assert len(dialogs) == 1
    assert dialogs[0].isVisible()


def test_delayed_republish_is_skipped_if_takeoff_stops_during_delay(
    qtbot, monkeypatch, widget_monitor, publish_capture, find_push_button
):
    monitor = widget_monitor
    emitted = publish_capture(monitor)
    scheduled_callbacks = capture_scheduled_callbacks(monkeypatch)
    monitor.handle_message("work", "9")
    monitor.handle_message("flag_otb", "Golov")
    monitor.otbor_g_1_spinbox.setValue(33)
    click_set_button(qtbot, monitor, find_push_button, index=1)

    monitor.handle_message("flag_otb", "End")
    scheduled_callbacks[0][1]()

    assert emitted == [("otbor_g_1_new", "33")]


def test_reset_t_kub_button_updates_flags_and_status(qtbot, widget_monitor):
    monitor = widget_monitor
    monitor.t_kub_signal_monitoring_active = False
    monitor.t_kub_signal_triggered = True

    qtbot.mouseClick(monitor.reset_t_kub_signal_button, Qt.LeftButton)

    assert monitor.t_kub_signal_monitoring_active is True
    assert monitor.t_kub_signal_triggered is False
    assert monitor.status_label.text() == "Сигнал T куба сброшен и активирован."


def test_reset_t_deflegmator_button_updates_flags_and_status(qtbot, widget_monitor):
    monitor = widget_monitor
    monitor.t_deflegmator_signal_monitoring_active = False
    monitor.t_deflegmator_signal_triggered = True

    qtbot.mouseClick(monitor.reset_t_deflegmator_signal_button, Qt.LeftButton)

    assert monitor.t_deflegmator_signal_monitoring_active is True
    assert monitor.t_deflegmator_signal_triggered is False
    assert monitor.status_label.text() == "Сигнал T дефлегматора сброшен и активирован."


def test_reset_stability_button_updates_flags_and_status(qtbot, widget_monitor):
    monitor = widget_monitor
    monitor.stability_signal_monitoring_active = False
    monitor.stability_signal_triggered = True

    qtbot.mouseClick(monitor.reset_stability_signal_button, Qt.LeftButton)

    assert monitor.stability_signal_monitoring_active is True
    assert monitor.stability_signal_triggered is False
    assert monitor.status_label.text() == "Сигнал стабильности температур сброшен и активирован."


def test_reset_t_kub_button_sets_exact_label_text_and_style(qtbot, widget_monitor):
    monitor = widget_monitor

    qtbot.mouseClick(monitor.reset_t_kub_signal_button, Qt.LeftButton)

    assert monitor.t_kub_signal_label.text() == "T куба: Ожидание данных (порог 60.0°C)"
    assert monitor.t_kub_signal_label.styleSheet() == STYLE_MONITORING


def test_reset_t_deflegmator_button_sets_exact_label_text_and_style(qtbot, widget_monitor):
    monitor = widget_monitor

    qtbot.mouseClick(monitor.reset_t_deflegmator_signal_button, Qt.LeftButton)

    assert monitor.t_deflegmator_signal_label.text() == "T дефлегматора: Ожидание данных (порог 70.0°C)"
    assert monitor.t_deflegmator_signal_label.styleSheet() == STYLE_MONITORING


def test_reset_stability_button_sets_exact_label_text_and_style(qtbot, widget_monitor):
    monitor = widget_monitor

    qtbot.mouseClick(monitor.reset_stability_signal_button, Qt.LeftButton)

    assert monitor.stability_signal_label.text() == "ΔT: Ожидание данных Tк..."
    assert monitor.stability_signal_label.styleSheet() == STYLE_MONITORING


def test_work_mode_button_keeps_exact_default_option_text_after_multiple_clicks(qtbot, widget_monitor, publish_capture):
    monitor = widget_monitor
    emitted = publish_capture(monitor)

    monitor.work_mode_combobox.setCurrentIndex(monitor.work_mode_combobox.findData(WorkState.START.value))
    qtbot.mouseClick(monitor.set_work_mode_button, Qt.LeftButton)

    monitor.work_mode_combobox.setCurrentIndex(monitor.work_mode_combobox.findData(WorkState.RESTART.value))
    qtbot.mouseClick(monitor.set_work_mode_button, Qt.LeftButton)

    assert emitted == [("work", "1"), ("work", "2")]
    assert monitor.work_mode_combobox.currentText() == "Выбрать"
    assert monitor.status_label.text() == "Запрос на установку режима: рестарт (2)"
