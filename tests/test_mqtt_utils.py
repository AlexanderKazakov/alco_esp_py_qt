from types import SimpleNamespace

from paho.mqtt import client as paho_mqtt

from alco_esp.mqtt_utils import MqttWorker
from alco_esp import mqtt_utils


class FakePublishClient:
    def __init__(self, connected=True, publish_result=(0, 1), publish_exception=None):
        self._connected = connected
        self.publish_result = publish_result
        self.publish_exception = publish_exception
        self.calls = []

    def is_connected(self):
        return self._connected

    def publish(self, topic, payload, qos):
        self.calls.append((topic, payload, qos))
        if self.publish_exception is not None:
            raise self.publish_exception
        return self.publish_result


class FakeRunClient:
    def __init__(self):
        self.username_password = None
        self.on_connect = None
        self.on_message = None
        self.on_disconnect = None
        self.connect_calls = []
        self.loop_started = False

    def username_pw_set(self, username, password):
        self.username_password = (username, password)

    def connect(self, host, port, keepalive):
        self.connect_calls.append((host, port, keepalive))

    def loop_start(self):
        self.loop_started = True


def build_worker():
    return MqttWorker("broker.example", 1883, "demo", "secret")


def test_on_connect_success_subscribes_wildcard(signal_collector):
    worker = build_worker()
    status_events = signal_collector(worker.connectionStatus)

    calls = []
    client = SimpleNamespace(subscribe=lambda topic, qos: calls.append((topic, qos)))

    worker.on_connect(client, None, None, 0)

    assert calls == [("demo/#", 0)]
    assert any("Подключено к MQTT брокеру" in event[0] for event in status_events)


def test_on_connect_failure_emits_error_without_subscribe(signal_collector):
    worker = build_worker()
    status_events = signal_collector(worker.connectionStatus)

    calls = []
    client = SimpleNamespace(subscribe=lambda topic, qos: calls.append((topic, qos)))

    worker.on_connect(client, None, None, 5)

    assert calls == []
    assert any("Ошибка подключения" in event[0] for event in status_events)


def test_on_message_removes_prefix_and_emits(signal_collector):
    worker = build_worker()
    events = signal_collector(worker.messageReceived)

    msg = SimpleNamespace(topic="demo/term_k", payload=b"78.2")
    worker.on_message(None, None, msg)

    assert events == [("term_k", "78.2")]


def test_on_disconnect_expected(signal_collector):
    worker = build_worker()
    events = signal_collector(worker.connectionStatus)

    worker.on_disconnect(None, None, 0)

    assert len(events) == 1
    assert "Отключено от MQTT брокера" in events[0][0]


def test_on_disconnect_unexpected_adds_reconnect_message(signal_collector):
    worker = build_worker()
    events = signal_collector(worker.connectionStatus)

    worker.on_disconnect(None, None, 1)

    assert len(events) == 2
    assert "Попытка переподключения" in events[1][0]


def test_publish_message_success(signal_collector):
    worker = build_worker()
    worker.client = FakePublishClient(
        connected=True,
        publish_result=(paho_mqtt.MQTT_ERR_SUCCESS, 42),
    )
    events = signal_collector(worker.connectionStatus)

    worker.publish_message("work", "4")

    assert worker.client.calls == [("demo/work", "4", 1)]
    assert events[0][0] == "Публикация: work = 4"
    assert events[1][0] == "Опубликовано: work = 4"


def test_publish_message_failure_code(signal_collector):
    worker = build_worker()
    worker.client = FakePublishClient(connected=True, publish_result=(7, 21))
    events = signal_collector(worker.connectionStatus)

    worker.publish_message("work", "4")

    assert "Ошибка публикации: work (код 7)" in events[-1][0]


def test_publish_message_exception(signal_collector):
    worker = build_worker()
    worker.client = FakePublishClient(connected=True, publish_exception=RuntimeError("boom"))
    events = signal_collector(worker.connectionStatus)

    worker.publish_message("work", "4")

    assert "Ошибка публикации: work: boom" in events[-1][0]


def test_publish_message_when_disconnected(signal_collector):
    worker = build_worker()
    worker.client = FakePublishClient(connected=False)
    events = signal_collector(worker.connectionStatus)

    worker.publish_message("work", "4")

    assert events[-1][0] == "Ошибка публикации: нет подключения"


def test_run_success_configures_client_and_starts_loop(monkeypatch, signal_collector):
    worker = build_worker()
    status_events = signal_collector(worker.connectionStatus)
    finished_events = signal_collector(worker.finished)
    created = []

    def fake_client_factory(*_args, **_kwargs):
        client = FakeRunClient()
        created.append(client)
        return client

    monkeypatch.setattr(mqtt_utils.mqtt, "Client", fake_client_factory)

    worker.run()

    assert len(created) == 1
    client = created[0]
    assert client.username_password == ("demo", "secret")
    assert client.on_connect == worker.on_connect
    assert client.on_message == worker.on_message
    assert client.on_disconnect == worker.on_disconnect
    assert client.connect_calls == [("broker.example", 1883, 60)]
    assert client.loop_started is True
    assert any("Подключение к broker.example" in event[0] for event in status_events)
    assert finished_events == []


def test_run_connect_failure_emits_finished(monkeypatch, signal_collector):
    worker = build_worker()
    status_events = signal_collector(worker.connectionStatus)
    finished_events = signal_collector(worker.finished)

    class FailingClient(FakeRunClient):
        def connect(self, host, port, keepalive):
            super().connect(host, port, keepalive)
            raise RuntimeError("connect failed")

    monkeypatch.setattr(mqtt_utils.mqtt, "Client", lambda *_a, **_k: FailingClient())

    worker.run()

    assert len(finished_events) == 1
    assert any("Ошибка подключения MQTT" in event[0] for event in status_events)
