import asyncio
import concurrent.futures
import os
import socket
import threading
import uuid
from pathlib import Path

import pytest
from PyQt5.QtWidgets import QDialog, QPushButton
from paho.mqtt import client as paho_mqtt

# Force a deterministic headless Qt environment for all test runs.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".mplconfig"))


class NoopLogger:
    """Logger stub used in tests where persistent CSV writes are intentionally suppressed."""

    def info(self, *_args, **_kwargs):
        return None


@pytest.fixture
def default_settings():
    return {
        "t_signal_kub": 60.0,
        "t_signal_deflegmator": 70.0,
        "delta_t": 0.2,
        "period_seconds": 60,
        "temp_stop_razgon": 70.0,
        "chart_y_min": 10.0,
        "chart_y_max": 110.0,
    }


@pytest.fixture
def mqtt_secrets():
    return {
        "broker": "test-broker",
        "port": 1883,
        "username": "unit_user",
        "password": "unit_pass",
    }


@pytest.fixture
def signal_collector():
    def _collect(signal):
        emitted = []
        signal.connect(lambda *args: emitted.append(args))
        return emitted

    return _collect


def _cleanup_monitor(qt_client_module, monitor):
    """Performs deterministic monitor cleanup for every fixture that creates a window."""
    if monitor.plot_timer.isActive():
        monitor.plot_timer.stop()
    if monitor.current_alarm_dialog is not None:
        if hasattr(monitor.current_alarm_dialog, "close"):
            monitor.current_alarm_dialog.close()
        if hasattr(monitor.current_alarm_dialog, "deleteLater"):
            monitor.current_alarm_dialog.deleteLater()
    # Shut down the MQTT thread before closing the widget to avoid closeEvent
    # re-entering shutdown against an already deleted QThread wrapper.
    try:
        monitor.perform_graceful_shutdown()
    except RuntimeError:
        # Qt may delete the underlying C++ QThread object between checks in
        # tests that already called perform_graceful_shutdown() explicitly.
        pass
    finally:
        monitor.mqtt_worker = None
        monitor.mqtt_thread = None
    # Explicitly close the Matplotlib figure to avoid figure accumulation across tests.
    qt_client_module.plt.close(monitor.figure)
    monitor.close()


def _find_free_tcp_port():
    """Reserves and returns a free localhost TCP port for ephemeral broker startup."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
        test_socket.bind(("127.0.0.1", 0))
        return test_socket.getsockname()[1]


@pytest.fixture
def monitor_fixture(qtbot, monkeypatch, default_settings, mqtt_secrets):
    from alco_esp import qt_client

    # Keep app behavior untouched while isolating tests from file/network side effects.
    monkeypatch.setattr(qt_client, "load_settings", lambda: default_settings.copy())
    monkeypatch.setattr(qt_client.QTimer, "singleShot", staticmethod(lambda *_args, **_kwargs: None))

    def fake_setup_mqtt(self):
        self.mqtt_thread = None
        self.mqtt_worker = None

    monkeypatch.setattr(qt_client.AlcoEspMonitor, "setup_mqtt", fake_setup_mqtt)

    monitor = qt_client.AlcoEspMonitor(mqtt_secrets.copy())
    monitor.plot_timer.stop()
    qtbot.addWidget(monitor)

    yield monitor

    _cleanup_monitor(qt_client, monitor)


@pytest.fixture
def widget_monitor(qtbot, monkeypatch, default_settings, mqtt_secrets):
    """
    Dedicated fixture for widget-phase tests.

    It keeps production widget wiring intact while removing external side effects:
    no real MQTT thread startup, no delayed alarm initialization, no file logging writes.
    """
    from alco_esp import qt_client

    monkeypatch.setattr(qt_client, "load_settings", lambda: default_settings.copy())
    monkeypatch.setattr(qt_client.QTimer, "singleShot", staticmethod(lambda *_args, **_kwargs: None))

    def fake_setup_mqtt(self):
        self.mqtt_thread = None
        self.mqtt_worker = None

    monkeypatch.setattr(qt_client.AlcoEspMonitor, "setup_mqtt", fake_setup_mqtt)
    monkeypatch.setattr(qt_client, "all_data_logger", NoopLogger())
    monkeypatch.setattr(qt_client, "main_data_logger", NoopLogger())

    monitor = qt_client.AlcoEspMonitor(mqtt_secrets.copy())
    monitor.plot_timer.stop()
    monitor.show()
    qtbot.addWidget(monitor)

    yield monitor

    _cleanup_monitor(qt_client, monitor)


@pytest.fixture
def publish_capture():
    """Collects publishRequested emissions in strict order for UI interaction assertions."""

    def _attach(monitor):
        emitted = []
        monitor.publishRequested.connect(lambda topic, payload: emitted.append((topic, payload)))
        return emitted

    return _attach


@pytest.fixture
def find_push_button():
    """Finds a button by visible text and positional index among duplicates."""

    def _find(parent_widget, text, index=0):
        matching_buttons = [button for button in parent_widget.findChildren(QPushButton) if button.text() == text]
        assert len(matching_buttons) > index, (
            f"Button '{text}' with index {index} not found. "
            f"Available count: {len(matching_buttons)}"
        )
        return matching_buttons[index]

    return _find


@pytest.fixture
def settings_dialog_stub_factory(monkeypatch):
    """
    Installs a SettingsDialog stub for dialog-flow tests.

    Returned helper records init/exec/get_settings calls and allows choosing
    accepted/cancel outcomes without opening real modal windows.
    """
    from alco_esp import qt_client

    def _install(*, accepted, returned_settings):
        call_log = []
        dialog_result = QDialog.Accepted if accepted else QDialog.Rejected

        class StubSettingsDialog:
            def __init__(self, parent=None, current_settings=None):
                self.parent = parent
                self.current_settings = current_settings.copy() if current_settings else {}
                call_log.append(("init", self.current_settings.copy()))

            def exec_(self):
                call_log.append(("exec", dialog_result))
                return dialog_result

            def get_settings(self):
                call_log.append(("get_settings", None))
                return returned_settings.copy()

        monkeypatch.setattr(qt_client, "SettingsDialog", StubSettingsDialog)
        return call_log

    return _install


@pytest.fixture(scope="session")
def integration_broker():
    """
    Starts one embedded MQTT broker for integration tests.

    A session-scoped broker keeps integration runtime low while still allowing
    per-test isolation via unique username prefixes.
    """
    amqtt = pytest.importorskip("amqtt.broker", reason="Install test dependencies with requirements_dev_test.txt")
    broker_host = "127.0.0.1"
    broker_port = _find_free_tcp_port()

    broker_loop = asyncio.new_event_loop()
    broker_thread = threading.Thread(
        target=lambda: (asyncio.set_event_loop(broker_loop), broker_loop.run_forever()),
        daemon=True,
    )
    broker_thread.start()

    broker_config = {
        "listeners": {
            "default": {
                "type": "tcp",
                "bind": f"{broker_host}:{broker_port}",
            }
        }
    }
    broker_instance = amqtt.Broker(config=broker_config, loop=broker_loop)

    start_future = asyncio.run_coroutine_threadsafe(broker_instance.start(), broker_loop)
    start_future.result(timeout=10)

    try:
        yield {"host": broker_host, "port": broker_port}
    finally:
        shutdown_future = asyncio.run_coroutine_threadsafe(broker_instance.shutdown(), broker_loop)
        try:
            # Give broker shutdown enough time to complete cleanly.
            shutdown_future.result(timeout=10)
        except concurrent.futures.TimeoutError:
            # If shutdown stalls, continue with forced loop stop to keep teardown bounded.
            pass
        broker_loop.call_soon_threadsafe(broker_loop.stop)
        broker_thread.join(timeout=10)
        if not broker_thread.is_alive():
            pending_tasks = asyncio.all_tasks(loop=broker_loop)
            if pending_tasks:
                for task in pending_tasks:
                    task.cancel()
                broker_loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
        broker_loop.close()


@pytest.fixture
def integration_secrets(integration_broker):
    """Provides per-test MQTT credentials/prefix while sharing one local broker."""
    unique_user = f"integration_user_{uuid.uuid4().hex[:8]}"
    return {
        "broker": integration_broker["host"],
        "port": integration_broker["port"],
        "username": unique_user,
        "password": "integration_pass",
    }


@pytest.fixture
def integration_monitor(qtbot, monkeypatch, default_settings, integration_secrets):
    """
    Builds AlcoEspMonitor with real MQTT worker wiring for end-to-end transport tests.

    Non-functional side effects (delayed sound init and CSV data writes) are muted,
    while network thread behavior remains production-real.
    """
    from alco_esp import qt_client

    monkeypatch.setattr(qt_client, "load_settings", lambda: default_settings.copy())
    monkeypatch.setattr(
        qt_client.AlcoEspMonitor,
        "initialize_sound_and_alarm_system",
        lambda self: None,
    )
    monkeypatch.setattr(qt_client, "all_data_logger", NoopLogger())
    monkeypatch.setattr(qt_client, "main_data_logger", NoopLogger())

    monitor = qt_client.AlcoEspMonitor(integration_secrets.copy())
    # Keep the production timer running in integration mode because
    # update_text_displays() is driven by periodic UI refresh ticks.
    monitor.show()
    qtbot.addWidget(monitor)

    # Wait for real worker thread bootstrap and connection confirmation.
    qtbot.waitUntil(lambda: monitor.mqtt_thread is not None and monitor.mqtt_thread.isRunning(), timeout=6000)
    qtbot.waitUntil(lambda: "Подключено к MQTT брокеру" in monitor.status_label.text(), timeout=8000)

    yield monitor

    _cleanup_monitor(qt_client, monitor)


@pytest.fixture
def mqtt_publisher_client(integration_secrets):
    """
    Provides a connected paho client for deterministic telemetry injection in integration tests.
    """
    client = paho_mqtt.Client(
        paho_mqtt.CallbackAPIVersion.VERSION1,
        client_id=f"integration_publisher_{uuid.uuid4().hex[:8]}",
    )
    connected_event = threading.Event()
    client.username_pw_set(integration_secrets["username"], integration_secrets["password"])
    client.on_connect = lambda _client, _userdata, _flags, rc: connected_event.set() if rc == 0 else None
    client.connect(integration_secrets["broker"], integration_secrets["port"], 60)
    client.loop_start()

    assert connected_event.wait(5), "Publisher client failed to connect to local integration broker."

    try:
        yield client
    finally:
        client.loop_stop()
        client.disconnect()


@pytest.fixture
def mqtt_subscriber_factory(integration_secrets):
    """
    Builds connected subscriber clients and returns captured message lists.

    The factory allows tests to assert exact published topic/payload values
    observed at broker level.
    """
    subscriber_clients = []

    def _create(topic_filter):
        messages = []
        connected_event = threading.Event()
        client = paho_mqtt.Client(
            paho_mqtt.CallbackAPIVersion.VERSION1,
            client_id=f"integration_subscriber_{uuid.uuid4().hex[:8]}",
        )
        client.username_pw_set(integration_secrets["username"], integration_secrets["password"])

        def _on_connect(connected_client, _userdata, _flags, rc):
            if rc == 0:
                connected_client.subscribe(topic_filter, qos=0)
                connected_event.set()

        def _on_message(_client, _userdata, msg):
            messages.append((msg.topic, msg.payload.decode("utf-8")))

        client.on_connect = _on_connect
        client.on_message = _on_message
        client.connect(integration_secrets["broker"], integration_secrets["port"], 60)
        client.loop_start()

        assert connected_event.wait(5), f"Subscriber failed to connect/subscribe: {topic_filter}"
        subscriber_clients.append(client)
        return messages

    try:
        yield _create
    finally:
        for client in subscriber_clients:
            client.loop_stop()
            client.disconnect()
