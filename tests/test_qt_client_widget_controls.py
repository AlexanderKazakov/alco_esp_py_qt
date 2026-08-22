from PyQt5.QtCore import Qt

from alco_esp.constants import STYLE_MONITORING, WorkState


def click_set_button(qtbot, monitor, find_push_button, index):
    """Clicks one of the duplicate 'Установить' buttons by stable positional index."""
    qtbot.mouseClick(find_push_button(monitor, "Установить", index), Qt.LeftButton)


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


def test_otbor_golov_pwm_republishes_work_when_flag_otb_matches(
    qtbot, widget_monitor, publish_capture, find_push_button
):
    monitor = widget_monitor
    emitted = publish_capture(monitor)
    monitor.all_latest_values["flag_otb"] = "отбор голов покапельно"

    monitor.otbor_g_1_spinbox.setValue(33)
    click_set_button(qtbot, monitor, find_push_button, index=1)

    assert emitted == [("otbor_g_1_new", "33"), ("work", "9")]
    assert monitor.status_label.text() == "Запрос на ШИМ отбора голов: 33"


def test_otbor_golov_pwm_republishes_work_after_this_client_set_that_mode(
    qtbot, widget_monitor, publish_capture, find_push_button
):
    monitor = widget_monitor
    emitted = publish_capture(monitor)

    monitor.work_mode_combobox.setCurrentIndex(
        monitor.work_mode_combobox.findData(WorkState.OTBOR_GOLOV_POKAPELNO.value)
    )
    qtbot.mouseClick(monitor.set_work_mode_button, Qt.LeftButton)

    monitor.otbor_g_1_spinbox.setValue(33)
    click_set_button(qtbot, monitor, find_push_button, index=1)

    assert emitted == [("work", "9"), ("otbor_g_1_new", "33"), ("work", "9")]


def test_otbor_golov_pwm_does_not_republish_work_when_in_other_mode(
    qtbot, widget_monitor, publish_capture, find_push_button
):
    monitor = widget_monitor
    emitted = publish_capture(monitor)
    monitor.all_latest_values["flag_otb"] = "отбор тела"

    monitor.otbor_g_1_spinbox.setValue(33)
    click_set_button(qtbot, monitor, find_push_button, index=1)

    assert emitted == [("otbor_g_1_new", "33")]


def test_otbor_tela_t_stop_button_uses_spinbox_value(qtbot, widget_monitor, publish_capture, find_push_button):
    monitor = widget_monitor
    emitted = publish_capture(monitor)

    monitor.term_c_max_telo_spinbox.setValue(78.4)
    click_set_button(qtbot, monitor, find_push_button, index=2)

    assert emitted == [("term_c_max_new", "78.4")]
    assert monitor.status_label.text() == "Запрос T стоп отбора тела: 78.4°C"


def test_otbor_tela_t_stop_republishes_work_when_flag_otb_matches(
    qtbot, widget_monitor, publish_capture, find_push_button
):
    monitor = widget_monitor
    emitted = publish_capture(monitor)
    monitor.all_latest_values["flag_otb"] = "отбор тела"

    monitor.term_c_max_telo_spinbox.setValue(78.4)
    click_set_button(qtbot, monitor, find_push_button, index=2)

    assert emitted == [("term_c_max_new", "78.4"), ("work", "8")]


def test_otbor_tela_t_start_button_uses_spinbox_value(qtbot, widget_monitor, publish_capture, find_push_button):
    monitor = widget_monitor
    emitted = publish_capture(monitor)

    monitor.term_c_min_telo_spinbox.setValue(77.1)
    click_set_button(qtbot, monitor, find_push_button, index=3)

    assert emitted == [("term_c_min_new", "77.1")]
    assert monitor.status_label.text() == "Запрос T старт отбора тела: 77.1°C"


def test_otbor_tela_t_start_republishes_work_when_flag_otb_matches(
    qtbot, widget_monitor, publish_capture, find_push_button
):
    monitor = widget_monitor
    emitted = publish_capture(monitor)
    monitor.all_latest_values["flag_otb"] = "отбор тела"

    monitor.term_c_min_telo_spinbox.setValue(77.1)
    click_set_button(qtbot, monitor, find_push_button, index=3)

    assert emitted == [("term_c_min_new", "77.1"), ("work", "8")]


def test_otbor_tela_pwm_button_uses_spinbox_value(qtbot, widget_monitor, publish_capture, find_push_button):
    monitor = widget_monitor
    emitted = publish_capture(monitor)

    monitor.otbor_t_spinbox.setValue(42)
    click_set_button(qtbot, monitor, find_push_button, index=4)

    assert emitted == [("otbor_t_new", "42")]
    assert monitor.status_label.text() == "Запрос ШИМ отбора тела: 42%"


def test_otbor_tela_pwm_republishes_work_when_flag_otb_matches(
    qtbot, widget_monitor, publish_capture, find_push_button
):
    monitor = widget_monitor
    emitted = publish_capture(monitor)
    monitor.all_latest_values["flag_otb"] = "отбор тела"

    monitor.otbor_t_spinbox.setValue(42)
    click_set_button(qtbot, monitor, find_push_button, index=4)

    assert emitted == [("otbor_t_new", "42"), ("work", "8")]


def test_otbor_tela_pwm_does_not_republish_work_when_in_heads_mode(
    qtbot, widget_monitor, publish_capture, find_push_button
):
    monitor = widget_monitor
    emitted = publish_capture(monitor)
    monitor.all_latest_values["flag_otb"] = "отбор голов покапельно"

    monitor.otbor_t_spinbox.setValue(42)
    click_set_button(qtbot, monitor, find_push_button, index=4)

    assert emitted == [("otbor_t_new", "42")]


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
