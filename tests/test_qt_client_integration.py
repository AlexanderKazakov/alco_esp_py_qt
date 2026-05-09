from datetime import datetime, timedelta

import pytest
from PyQt5.QtCore import Qt

from alco_esp import qt_client
from alco_esp.constants import WorkState

pytestmark = pytest.mark.integration


def _publish_prefixed(publisher_client, integration_secrets, topic_suffix, payload):
    """Publishes one topic under the active test prefix and waits for broker ACK."""
    info = publisher_client.publish(
        f"{integration_secrets['username']}/{topic_suffix}",
        payload=str(payload),
        qos=1,
    )
    assert info.rc == 0
    info.wait_for_publish()


def _click_set_button(qtbot, monitor, find_push_button, index):
    """Clicks one of repeated 'Установить' buttons by stable positional index."""
    qtbot.mouseClick(find_push_button(monitor, "Установить", index), Qt.LeftButton)


def test_integration_monitor_connects_to_local_broker(integration_monitor, integration_secrets):
    monitor = integration_monitor

    assert monitor.mqtt_thread is not None
    assert monitor.mqtt_thread.isRunning() is True
    assert monitor.status_label.text() == f"Подключено к MQTT брокеру: {integration_secrets['broker']}"


def test_integration_telemetry_updates_labels_end_to_end(
    qtbot,
    integration_monitor,
    integration_secrets,
    mqtt_publisher_client,
):
    monitor = integration_monitor

    _publish_prefixed(mqtt_publisher_client, integration_secrets, "term_d", "56.8")
    _publish_prefixed(mqtt_publisher_client, integration_secrets, "term_c", "57.9")
    _publish_prefixed(mqtt_publisher_client, integration_secrets, "term_k", "58.9")
    _publish_prefixed(mqtt_publisher_client, integration_secrets, "power", "1200.2")
    _publish_prefixed(mqtt_publisher_client, integration_secrets, "press_a", "760.5")
    _publish_prefixed(mqtt_publisher_client, integration_secrets, "flag_otb", "разгон")

    qtbot.waitUntil(
        lambda: (
            monitor.term_d_label.text() == "T дефл.: 56.8 °C"
            and monitor.term_c_label.text() == "T царга: 57.9 °C"
            and monitor.term_k_label.text() == "T куб:     58.9 °C"
            and monitor.power_label.text() == "Мощность: 1200.2 Вт"
            and monitor.press_a_label.text() == "Атм. давл.: 760.5 мм.рт.ст"
            and monitor.flag_otb_label.text() == "Флаг отбора: разгон"
        ),
        timeout=6000,
    )


def test_integration_prefix_stripping_keeps_unprefixed_internal_keys(
    qtbot,
    integration_monitor,
    integration_secrets,
    mqtt_publisher_client,
):
    monitor = integration_monitor
    full_topic = f"{integration_secrets['username']}/term_k"

    _publish_prefixed(mqtt_publisher_client, integration_secrets, "term_k", "67.1")

    qtbot.waitUntil(lambda: monitor.all_latest_values.get("term_k") == "67.1", timeout=4000)
    qtbot.waitUntil(lambda: monitor.term_k_label.text() == "T куб:     67.1 °C", timeout=6000)

    assert full_topic not in monitor.all_latest_values
    assert monitor.term_k_label.text() == "T куб:     67.1 °C"


def test_integration_ui_commands_publish_expected_prefixed_topics(
    qtbot,
    integration_monitor,
    integration_secrets,
    mqtt_subscriber_factory,
    find_push_button,
):
    monitor = integration_monitor
    prefix = integration_secrets["username"]
    broker_messages = mqtt_subscriber_factory(f"{prefix}/#")

    monitor.work_mode_combobox.setCurrentIndex(monitor.work_mode_combobox.findData(WorkState.STOP.value))
    qtbot.mouseClick(monitor.set_work_mode_button, Qt.LeftButton)

    monitor.otbor_g_1_spinbox.setValue(33)
    _click_set_button(qtbot, monitor, find_push_button, index=1)

    monitor.term_c_max_telo_spinbox.setValue(78.4)
    _click_set_button(qtbot, monitor, find_push_button, index=2)

    monitor.term_c_min_telo_spinbox.setValue(77.1)
    _click_set_button(qtbot, monitor, find_push_button, index=3)

    monitor.otbor_t_spinbox.setValue(42)
    _click_set_button(qtbot, monitor, find_push_button, index=4)

    qtbot.waitUntil(lambda: len(broker_messages) >= 5, timeout=6000)

    expected = [
        (f"{prefix}/work", "0"),
        (f"{prefix}/otbor_g_1_new", "33"),
        (f"{prefix}/term_c_max_new", "78.4"),
        (f"{prefix}/term_c_min_new", "77.1"),
        (f"{prefix}/otbor_t_new", "42"),
    ]
    assert broker_messages[:5] == expected


def test_integration_razgon_ui_flow_publishes_term_k_r_before_work(
    qtbot,
    integration_monitor,
    integration_secrets,
    mqtt_subscriber_factory,
):
    monitor = integration_monitor
    prefix = integration_secrets["username"]
    broker_messages = mqtt_subscriber_factory(f"{prefix}/#")

    monitor.work_mode_combobox.setCurrentIndex(monitor.work_mode_combobox.findData(WorkState.RAZGON.value))
    qtbot.mouseClick(monitor.set_work_mode_button, Qt.LeftButton)

    qtbot.waitUntil(lambda: len(broker_messages) >= 2, timeout=6000)

    # We assert transport-level ordering for the RAZGON sequence contract.
    assert broker_messages[0] == (f"{prefix}/term_k_r", "70.0")
    assert broker_messages[1] == (f"{prefix}/work", "4")


def test_integration_term_k_m_confirmation_updates_status(
    qtbot,
    integration_monitor,
    integration_secrets,
    mqtt_publisher_client,
):
    monitor = integration_monitor

    monitor.work_mode_combobox.setCurrentIndex(monitor.work_mode_combobox.findData(WorkState.RAZGON.value))
    qtbot.mouseClick(monitor.set_work_mode_button, Qt.LeftButton)

    _publish_prefixed(mqtt_publisher_client, integration_secrets, "term_k_m", "70.0")

    qtbot.waitUntil(lambda: monitor.status_label.text() == "Проверено: term_k_m = 70.0°C", timeout=6000)
    assert monitor.pending_term_k_m_check is False


def test_integration_timeout_alarm_triggers_once_with_real_worker(
    monkeypatch,
    integration_monitor,
):
    monitor = integration_monitor
    alarm_messages = []

    monkeypatch.setattr(qt_client, "MQTT_DATA_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(monitor, "alarm_message_with_sound", lambda message: alarm_messages.append(message))

    monitor.last_mqtt_message_time = datetime.now() - timedelta(seconds=1)
    monitor.mqtt_data_timeout_alarm_active = False

    monitor.check_mqtt_data_timeout()
    monitor.check_mqtt_data_timeout()

    assert len(alarm_messages) == 1
    assert "Нет данных от устройства" in alarm_messages[0]
    assert monitor.mqtt_data_timeout_alarm_active is True


def test_integration_graceful_shutdown_stops_real_mqtt_thread(qtbot, integration_monitor):
    monitor = integration_monitor

    assert monitor.mqtt_thread.isRunning() is True

    monitor.perform_graceful_shutdown()
    qtbot.waitUntil(lambda: monitor.mqtt_thread.isRunning() is False, timeout=6000)
    # Prevent a second closeEvent shutdown call from touching a deleted QThread
    # wrapper when pytest-qt closes remaining widgets at teardown.
    monitor.mqtt_worker = None
    monitor.mqtt_thread = None
