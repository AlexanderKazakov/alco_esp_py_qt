from types import SimpleNamespace

import pytest

from alco_esp import qt_client
from alco_esp.constants import WorkState
from alco_esp.settings import TERM_K_M_CHECK_TIMEOUT


class DummySignal:
    def __init__(self):
        self.callback = None

    def connect(self, callback):
        self.callback = callback


class FakeTimer:
    instances = []

    def __init__(self):
        self.single_shot = False
        self.started_ms = None
        self.stopped = False
        self.deleted = False
        self.timeout = DummySignal()
        FakeTimer.instances.append(self)

    def setSingleShot(self, value):
        self.single_shot = value

    def start(self, milliseconds):
        self.started_ms = milliseconds

    def stop(self):
        self.stopped = True

    def deleteLater(self):
        self.deleted = True


class ResettableTimer:
    def __init__(self):
        self.stopped = False
        self.deleted = False

    def stop(self):
        self.stopped = True

    def deleteLater(self):
        self.deleted = True


class FakeSource:
    def __init__(self, valid):
        self.valid = valid

    def isValid(self):
        return self.valid


class FakeSoundEffect:
    def __init__(self, loaded=True, valid=True, playing=False):
        self.loaded = loaded
        self.valid = valid
        self.playing = playing
        self.loop_count = None
        self.play_calls = 0
        self.stop_calls = 0

    def isPlaying(self):
        return self.playing

    def stop(self):
        self.stop_calls += 1
        self.playing = False

    def isLoaded(self):
        return self.loaded

    def source(self):
        return FakeSource(self.valid)

    def setLoopCount(self, loop_count):
        self.loop_count = loop_count

    def play(self):
        self.play_calls += 1
        self.playing = True


class FakeDialogRef:
    def __init__(self, visible=True):
        self.visible = visible
        self.close_calls = 0
        self.delete_calls = 0

    def isVisible(self):
        return self.visible

    def close(self):
        self.close_calls += 1
        self.visible = False

    def deleteLater(self):
        self.delete_calls += 1


class FakeAlarmDialog:
    created = []

    def __init__(self, message, sound_effect, parent):
        self.message = message
        self.sound_effect = sound_effect
        self.parent = parent
        self.shown = False
        FakeAlarmDialog.created.append(self)

    def show(self):
        self.shown = True

    def close(self):
        self.shown = False

    def deleteLater(self):
        pass


class FakeClient:
    def __init__(self, connected=True):
        self.connected = connected
        self.loop_stop_calls = 0
        self.disconnect_calls = 0

    def loop_stop(self):
        self.loop_stop_calls += 1

    def is_connected(self):
        return self.connected

    def disconnect(self):
        self.disconnect_calls += 1


class FakeThread:
    def __init__(self, running=True, wait_result=True):
        self.running = running
        self.wait_result = wait_result
        self.quit_calls = 0
        self.wait_calls = []
        self.terminate_calls = 0

    def isRunning(self):
        return self.running

    def quit(self):
        self.quit_calls += 1

    def wait(self, timeout_ms):
        self.wait_calls.append(timeout_ms)
        return self.wait_result

    def terminate(self):
        self.terminate_calls += 1


def test_publish_selected_work_mode_resets_combobox(monitor_fixture):
    monitor = monitor_fixture
    emitted = []
    monitor.publishRequested.connect(lambda topic, payload: emitted.append((topic, payload)))

    # Pick a real mode entry, then call the UI handler that should reset back to "Выбрать".
    monitor.work_mode_combobox.setCurrentIndex(monitor.work_mode_combobox.findData(WorkState.OTBOR_TELA.value))
    monitor.publish_selected_work_mode()

    assert emitted[-1] == ("work", str(WorkState.OTBOR_TELA.value))
    assert monitor.work_mode_combobox.currentData() is None


def test_publish_selected_work_mode_ignores_placeholder(monitor_fixture):
    monitor = monitor_fixture
    emitted = []
    monitor.publishRequested.connect(lambda topic, payload: emitted.append((topic, payload)))

    monitor.work_mode_combobox.setCurrentIndex(0)
    monitor.publish_selected_work_mode()

    assert emitted == []


def test_publish_work_mode_non_razgon_emits_work_only(monitor_fixture):
    monitor = monitor_fixture
    emitted = []
    monitor.publishRequested.connect(lambda topic, payload: emitted.append((topic, payload)))

    monitor.publish_work_mode(WorkState.STOP.value)

    assert emitted == [("work", "0")]
    assert monitor.pending_term_k_m_check is False


def test_publish_work_mode_razgon_emits_sequence_and_starts_timer(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    emitted = []
    monitor.publishRequested.connect(lambda topic, payload: emitted.append((topic, payload)))

    FakeTimer.instances.clear()
    monkeypatch.setattr(qt_client, "QTimer", FakeTimer)

    monitor.publish_work_mode(WorkState.RAZGON.value)

    assert emitted == [("term_k_r", "70.0"), ("work", "4")]
    assert monitor.pending_term_k_m_check is True
    timer = FakeTimer.instances[-1]
    assert timer.single_shot is True
    assert timer.started_ms == TERM_K_M_CHECK_TIMEOUT * 1000
    assert monitor._term_k_m_check_timer is timer


def test_publish_work_mode_razgon_replaces_existing_timer(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    old_timer = ResettableTimer()
    monitor._term_k_m_check_timer = old_timer

    FakeTimer.instances.clear()
    monkeypatch.setattr(qt_client, "QTimer", FakeTimer)

    monitor.publish_work_mode(WorkState.RAZGON.value)

    assert old_timer.stopped is True
    assert isinstance(monitor._term_k_m_check_timer, FakeTimer)


def test_check_term_k_m_confirmation_success_resets_state(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.pending_term_k_m_check = True
    timer = ResettableTimer()
    monitor._term_k_m_check_timer = timer

    status_messages = []
    alarms = []
    monkeypatch.setattr(monitor, "update_status", lambda message: status_messages.append(message))
    monkeypatch.setattr(monitor, "alarm_message_with_sound", lambda message: alarms.append(message))

    monitor.check_term_k_m_confirmation("70.0")

    assert status_messages and "Проверено" in status_messages[-1]
    assert alarms == []
    assert monitor.pending_term_k_m_check is False
    assert monitor._term_k_m_check_timer is None
    assert timer.stopped is True
    assert timer.deleted is True


def test_check_term_k_m_confirmation_mismatch_triggers_alarm(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.pending_term_k_m_check = True
    monitor._term_k_m_check_timer = ResettableTimer()

    alarms = []
    monkeypatch.setattr(monitor, "alarm_message_with_sound", lambda message: alarms.append(message))

    monitor.check_term_k_m_confirmation("71.3")

    assert len(alarms) == 1
    assert "НЕВЕРНОЕ ЗНАЧЕНИЕ" in alarms[0]
    assert monitor.pending_term_k_m_check is False


def test_check_term_k_m_confirmation_parse_error_triggers_alarm(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.pending_term_k_m_check = True
    monitor._term_k_m_check_timer = ResettableTimer()

    alarms = []
    monkeypatch.setattr(monitor, "alarm_message_with_sound", lambda message: alarms.append(message))

    monitor.check_term_k_m_confirmation("not-a-number")

    assert len(alarms) == 1
    assert "ОШИБКА ПРОВЕРКИ" in alarms[0]
    assert monitor.pending_term_k_m_check is False


def test_check_term_k_m_timeout_triggers_alarm_and_resets(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.pending_term_k_m_check = True
    timer = ResettableTimer()
    monitor._term_k_m_check_timer = timer

    alarms = []
    monkeypatch.setattr(monitor, "alarm_message_with_sound", lambda message: alarms.append(message))

    monitor.check_term_k_m_timeout()

    assert len(alarms) == 1
    assert "Нет данных от term_k_m" in alarms[0]
    assert monitor.pending_term_k_m_check is False
    assert monitor._term_k_m_check_timer is None
    assert timer.stopped is True


def test_check_term_k_m_timeout_noop_when_not_pending(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.pending_term_k_m_check = False

    alarms = []
    monkeypatch.setattr(monitor, "alarm_message_with_sound", lambda message: alarms.append(message))

    monitor.check_term_k_m_timeout()

    assert alarms == []


def test_reset_pending_check_without_timer_is_safe(monitor_fixture):
    monitor = monitor_fixture
    monitor.pending_term_k_m_check = True
    monitor._term_k_m_check_timer = None

    monitor._reset_pending_check()

    assert monitor.pending_term_k_m_check is False
    assert monitor._term_k_m_check_timer is None


def test_alarm_message_with_sound_replaces_existing_dialog(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    previous_dialog = FakeDialogRef(visible=True)
    monitor.current_alarm_dialog = previous_dialog
    monitor.alarm_sound_effect = FakeSoundEffect(loaded=True, valid=True, playing=True)

    FakeAlarmDialog.created.clear()
    monkeypatch.setattr(qt_client, "AlarmNotificationDialog", FakeAlarmDialog)

    monitor.alarm_message_with_sound("Alarm text")

    assert previous_dialog.close_calls == 1
    assert previous_dialog.delete_calls == 1
    assert monitor.alarm_sound_effect.stop_calls == 1
    assert monitor.alarm_sound_effect.play_calls == 1
    assert monitor.alarm_sound_effect.loop_count == qt_client.QSoundEffect.Infinite

    assert len(FakeAlarmDialog.created) == 1
    assert FakeAlarmDialog.created[0].shown is True
    assert monitor.current_alarm_dialog is FakeAlarmDialog.created[0]


def test_alarm_message_with_sound_falls_back_to_beep(monkeypatch, monitor_fixture):
    monitor = monitor_fixture
    monitor.current_alarm_dialog = None
    monitor.alarm_sound_effect = FakeSoundEffect(loaded=False, valid=False, playing=False)

    FakeAlarmDialog.created.clear()
    monkeypatch.setattr(qt_client, "AlarmNotificationDialog", FakeAlarmDialog)

    beep_calls = []
    monkeypatch.setattr(qt_client.QApplication, "beep", staticmethod(lambda: beep_calls.append(True)))

    monitor.alarm_message_with_sound("Alarm text")

    assert monitor.alarm_sound_effect.play_calls == 0
    assert len(beep_calls) == 1
    assert len(FakeAlarmDialog.created) == 1


def test_perform_graceful_shutdown_normal_path(monitor_fixture):
    monitor = monitor_fixture
    client = FakeClient(connected=True)
    thread = FakeThread(running=True, wait_result=True)

    monitor.mqtt_worker = SimpleNamespace(client=client)
    monitor.mqtt_thread = thread

    monitor.perform_graceful_shutdown()

    assert client.loop_stop_calls == 1
    assert client.disconnect_calls == 1
    assert thread.quit_calls == 1
    assert thread.wait_calls == [5000]
    assert thread.terminate_calls == 0


def test_perform_graceful_shutdown_terminates_if_wait_times_out(monitor_fixture):
    monitor = monitor_fixture
    client = FakeClient(connected=False)
    thread = FakeThread(running=True, wait_result=False)

    monitor.mqtt_worker = SimpleNamespace(client=client)
    monitor.mqtt_thread = thread

    monitor.perform_graceful_shutdown()

    assert client.loop_stop_calls == 1
    assert client.disconnect_calls == 0
    assert thread.quit_calls == 1
    assert thread.terminate_calls == 1


def test_perform_graceful_shutdown_noop_when_thread_not_running(monitor_fixture):
    monitor = monitor_fixture
    thread = FakeThread(running=False, wait_result=True)

    monitor.mqtt_worker = SimpleNamespace(client=FakeClient(connected=True))
    monitor.mqtt_thread = thread

    monitor.perform_graceful_shutdown()

    assert thread.quit_calls == 0
    assert thread.terminate_calls == 0
