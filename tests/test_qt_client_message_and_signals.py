from datetime import datetime, timedelta

import pytest

from alco_esp import qt_client


class CapturingLogger:
    def __init__(self):
        self.lines = []

    def info(self, message):
        self.lines.append(message)


class RunningThreadStub:
    def __init__(self, running):
        self.running = running

    def isRunning(self):
        return self.running

    def quit(self):
        self.running = False

    def wait(self, _timeout_ms):
        return True

    def terminate(self):
        self.running = False


def append_series(monitor, topic, values, now=None, step_seconds=5):
    now = now or datetime.now()
    for idx, value in enumerate(values):
        monitor.timestamps[topic].append(now - timedelta(seconds=step_seconds * (len(values) - idx)))
        monitor.data[topic].append(value)


def test_handle_message_updates_chart_and_logs(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    all_logger = CapturingLogger()
    main_logger = CapturingLogger()

    monkeypatch.setattr(qt_client, "all_data_logger", all_logger)
    monkeypatch.setattr(qt_client, "main_data_logger", main_logger)

    monitor.handle_message("term_k", "75.0")

    assert monitor.all_latest_values["term_k"] == "75.0"
    assert monitor.data["term_k"][-1] == pytest.approx(75.0)
    assert monitor.timestamps["term_k"]
    assert any("term_k" in line and "7.500000e+01" in line for line in all_logger.lines)
    assert main_logger.lines and "7.500000e+01" in main_logger.lines[0]


def test_handle_message_non_numeric_payload_stays_as_text(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    all_logger = CapturingLogger()
    main_logger = CapturingLogger()

    monkeypatch.setattr(qt_client, "all_data_logger", all_logger)
    monkeypatch.setattr(qt_client, "main_data_logger", main_logger)

    monitor.handle_message("flag_otb", "режим")

    assert monitor.all_latest_values["flag_otb"] == "режим"
    assert any("режим" in line for line in all_logger.lines)
    assert any("режим" in line for line in main_logger.lines)


def test_handle_message_non_interest_topic_skips_main_csv(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    all_logger = CapturingLogger()
    main_logger = CapturingLogger()

    monkeypatch.setattr(qt_client, "all_data_logger", all_logger)
    monkeypatch.setattr(qt_client, "main_data_logger", main_logger)

    monitor.handle_message("term_k_m", "88.8")

    assert all_logger.lines
    assert main_logger.lines == []


def test_handle_message_calls_term_k_m_confirmation_when_pending(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.pending_term_k_m_check = True

    calls = []
    monkeypatch.setattr(monitor, "check_term_k_m_confirmation", lambda value: calls.append(value))

    monitor.handle_message("term_k_m", "70.0")

    assert calls == ["70.0"]


def test_handle_message_invalid_chart_payload_does_not_append(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    all_logger = CapturingLogger()
    main_logger = CapturingLogger()

    monkeypatch.setattr(qt_client, "all_data_logger", all_logger)
    monkeypatch.setattr(qt_client, "main_data_logger", main_logger)

    before_len = len(monitor.data["term_k"])
    monitor.handle_message("term_k", "not-float")

    assert len(monitor.data["term_k"]) == before_len
    assert all_logger.lines


def test_handle_message_clears_timeout_alarm_flag(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.mqtt_data_timeout_alarm_active = True

    monkeypatch.setattr(qt_client, "all_data_logger", CapturingLogger())
    monkeypatch.setattr(qt_client, "main_data_logger", CapturingLogger())

    monitor.handle_message("power", "900")

    assert monitor.mqtt_data_timeout_alarm_active is False


def test_check_mqtt_data_timeout_triggers_when_thread_running(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.last_mqtt_message_time = datetime.now() - timedelta(seconds=61)
    monitor.mqtt_data_timeout_alarm_active = False
    monitor.mqtt_thread = RunningThreadStub(True)

    alarms = []
    monkeypatch.setattr(monitor, "alarm_message_with_sound", lambda message: alarms.append(message))

    monitor.check_mqtt_data_timeout()

    assert len(alarms) == 1
    assert "Нет данных" in alarms[0]
    assert monitor.mqtt_data_timeout_alarm_active is True


def test_check_mqtt_data_timeout_suppressed_when_thread_stopped(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.last_mqtt_message_time = datetime.now() - timedelta(seconds=61)
    monitor.mqtt_data_timeout_alarm_active = False
    monitor.mqtt_thread = RunningThreadStub(False)

    alarms = []
    monkeypatch.setattr(monitor, "alarm_message_with_sound", lambda message: alarms.append(message))

    monitor.check_mqtt_data_timeout()

    assert alarms == []
    assert monitor.mqtt_data_timeout_alarm_active is False


def test_check_mqtt_data_timeout_not_retriggered_if_already_active(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.last_mqtt_message_time = datetime.now() - timedelta(seconds=120)
    monitor.mqtt_data_timeout_alarm_active = True
    monitor.mqtt_thread = RunningThreadStub(True)

    alarms = []
    monkeypatch.setattr(monitor, "alarm_message_with_sound", lambda message: alarms.append(message))

    monitor.check_mqtt_data_timeout()

    assert alarms == []


def test_check_mqtt_data_timeout_noop_without_any_messages(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.last_mqtt_message_time = None
    monitor.mqtt_thread = RunningThreadStub(True)

    alarms = []
    monkeypatch.setattr(monitor, "alarm_message_with_sound", lambda message: alarms.append(message))

    monitor.check_mqtt_data_timeout()

    assert alarms == []


def test_check_t_kub_signal_triggers_and_disables_monitoring(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.all_latest_values["term_k"] = "65.0"

    alarms = []
    monkeypatch.setattr(monitor, "alarm_message_with_sound", lambda message: alarms.append(message))

    monitor.check_t_kub_signal()

    assert monitor.t_kub_signal_triggered is True
    assert monitor.t_kub_signal_monitoring_active is False
    assert len(alarms) == 1


def test_check_t_kub_signal_monitoring_message_when_below_threshold(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.all_latest_values["term_k"] = "50.0"

    alarms = []
    monkeypatch.setattr(monitor, "alarm_message_with_sound", lambda message: alarms.append(message))

    monitor.check_t_kub_signal()

    assert monitor.t_kub_signal_triggered is False
    assert "Мониторинг" in monitor.t_kub_signal_label.text()
    assert alarms == []


def test_check_t_kub_signal_inactive_and_dropped_below_threshold_resets(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.t_kub_signal_monitoring_active = False
    monitor.all_latest_values["term_k"] = "50.0"

    reset_calls = []
    stability_calls = []
    monkeypatch.setattr(monitor, "reset_t_kub_signal", lambda: reset_calls.append(True))
    monkeypatch.setattr(monitor, "reset_stability_signal", lambda: stability_calls.append(True))

    monitor.check_t_kub_signal()

    assert reset_calls == [True]
    assert stability_calls == [True]


def test_check_t_deflegmator_signal_triggers(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.all_latest_values["term_d"] = "72.0"

    alarms = []
    monkeypatch.setattr(monitor, "alarm_message_with_sound", lambda message: alarms.append(message))

    monitor.check_t_deflegmator_signal()

    assert monitor.t_deflegmator_signal_triggered is True
    assert monitor.t_deflegmator_signal_monitoring_active is False
    assert len(alarms) == 1


def test_check_temperature_stability_signal_when_monitoring_disabled(monitor_fixture):
    monitor = monitor_fixture
    monitor.stability_signal_monitoring_active = False

    monitor.check_temperature_stability_signal()

    assert "Мониторинг отключен" in monitor.stability_signal_label.text()


def test_check_temperature_stability_signal_waits_for_term_k(monitor_fixture):
    monitor = monitor_fixture
    monitor.all_latest_values.pop("term_k", None)

    monitor.check_temperature_stability_signal()

    assert "Ожидание данных Tк" in monitor.stability_signal_label.text()


def test_check_temperature_stability_signal_skips_when_term_k_not_hot_enough(monitor_fixture):
    monitor = monitor_fixture
    monitor.all_latest_values["term_k"] = "69.5"

    monitor.check_temperature_stability_signal()

    assert "≤ 70.0°C" in monitor.stability_signal_label.text()


def test_check_temperature_stability_signal_reports_insufficient_pairs(monitor_fixture):
    monitor = monitor_fixture
    monitor.all_latest_values["term_k"] = "80.0"

    now = datetime.now()
    monitor.timestamps["term_k"].append(now)
    monitor.data["term_k"].append(80.0)
    monitor.timestamps["term_c"].append(now)
    monitor.data["term_c"].append(79.8)

    monitor.check_temperature_stability_signal()

    assert "Мало данных" in monitor.stability_signal_label.text()


def test_check_temperature_stability_signal_triggers_on_stable_delta(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.all_latest_values["term_k"] = "80.0"

    now = datetime.now()
    append_series(monitor, "term_k", [80.0, 80.2, 80.4], now=now)
    append_series(monitor, "term_c", [79.5, 79.7, 79.9], now=now)

    alarms = []
    monkeypatch.setattr(monitor, "alarm_message_with_sound", lambda message: alarms.append(message))

    monitor.check_temperature_stability_signal()

    assert monitor.stability_signal_triggered is True
    assert monitor.stability_signal_monitoring_active is False
    assert len(alarms) == 1
    assert "СТАБИЛЬНО" in alarms[0]


def test_check_temperature_stability_signal_keeps_monitoring_when_unstable(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.all_latest_values["term_k"] = "82.0"

    now = datetime.now()
    append_series(monitor, "term_k", [82.0, 82.4, 82.8], now=now)
    append_series(monitor, "term_c", [81.8, 81.7, 81.2], now=now)

    alarms = []
    monkeypatch.setattr(monitor, "alarm_message_with_sound", lambda message: alarms.append(message))

    monitor.check_temperature_stability_signal()

    assert monitor.stability_signal_triggered is False
    assert monitor.stability_signal_monitoring_active is True
    assert alarms == []
    assert "Разброс" in monitor.stability_signal_label.text()


def test_check_temperature_stability_signal_uses_window_filtering(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.all_latest_values["term_k"] = "83.0"

    now = datetime.now()
    # Old out-of-window points are intentionally noisy and should be ignored.
    monitor.timestamps["term_k"].append(now - timedelta(seconds=300))
    monitor.data["term_k"].append(95.0)
    monitor.timestamps["term_c"].append(now - timedelta(seconds=300))
    monitor.data["term_c"].append(70.0)

    append_series(monitor, "term_k", [83.0, 83.1, 83.2], now=now)
    append_series(monitor, "term_c", [82.7, 82.8, 82.9], now=now)

    alarms = []
    monkeypatch.setattr(monitor, "alarm_message_with_sound", lambda message: alarms.append(message))

    monitor.check_temperature_stability_signal()

    assert len(alarms) == 1
    assert "СТАБИЛЬНО" in alarms[0]
