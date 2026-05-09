import json
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import pytest
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import QMainWindow

from alco_esp import child_dialogs


@pytest.fixture
def patched_secrets_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(child_dialogs, "APP_ROOT_DIR", str(tmp_path))
    monkeypatch.setattr(child_dialogs, "SECRETS_FILE_PATH", str(tmp_path / "secrets.json"))
    return tmp_path


def test_load_secrets_exits_when_file_missing(monkeypatch, patched_secrets_paths):
    messages = []
    monkeypatch.setattr(child_dialogs.QMessageBox, "critical", lambda *args: messages.append(args))

    with pytest.raises(SystemExit):
        child_dialogs.load_secrets_with_gui_feedback()

    assert messages
    assert "Файл с секретами не найден" in messages[0][2]


def test_load_secrets_exits_when_required_keys_missing(monkeypatch, patched_secrets_paths):
    secrets_path = patched_secrets_paths / "secrets.json"
    secrets_path.write_text(json.dumps({"broker": "x", "port": 1, "username": "u"}), encoding="utf-8")

    messages = []
    monkeypatch.setattr(child_dialogs.QMessageBox, "critical", lambda *args: messages.append(args))

    with pytest.raises(SystemExit):
        child_dialogs.load_secrets_with_gui_feedback()

    assert messages
    assert "отсутствуют необходимые ключи" in messages[0][2]


def test_load_secrets_exits_on_invalid_json(monkeypatch, patched_secrets_paths):
    secrets_path = patched_secrets_paths / "secrets.json"
    secrets_path.write_text("{broken-json", encoding="utf-8")

    messages = []
    monkeypatch.setattr(child_dialogs.QMessageBox, "critical", lambda *args: messages.append(args))

    with pytest.raises(SystemExit):
        child_dialogs.load_secrets_with_gui_feedback()

    assert messages
    assert "Ошибка чтения secrets.json" in messages[0][2]


def test_load_secrets_success(monkeypatch, patched_secrets_paths):
    secrets_payload = {
        "broker": "host",
        "port": 1883,
        "username": "user",
        "password": "pass",
    }
    (patched_secrets_paths / "secrets.json").write_text(json.dumps(secrets_payload), encoding="utf-8")

    critical_calls = []
    monkeypatch.setattr(child_dialogs.QMessageBox, "critical", lambda *args: critical_calls.append(args))

    loaded = child_dialogs.load_secrets_with_gui_feedback()

    assert loaded == secrets_payload
    assert critical_calls == []


class FakeSoundEffect:
    def __init__(self, playing=True):
        self.playing = playing
        self.stop_calls = 0

    def isPlaying(self):
        return self.playing

    def stop(self):
        self.stop_calls += 1
        self.playing = False


def test_alarm_dialog_accept_stops_sound(qtbot):
    sound = FakeSoundEffect(playing=True)
    dialog = child_dialogs.AlarmNotificationDialog("alarm", sound)
    qtbot.addWidget(dialog)

    dialog.accept()

    assert sound.stop_calls == 1


def test_alarm_dialog_close_event_stops_sound(qtbot):
    sound = FakeSoundEffect(playing=True)
    dialog = child_dialogs.AlarmNotificationDialog("alarm", sound)
    qtbot.addWidget(dialog)

    dialog.show()
    dialog.close()

    assert sound.stop_calls == 1


def test_all_data_viewer_dialog_sorts_rows_deterministically(qtbot):
    dialog = child_dialogs.AllDataViewerDialog({"b": 2, "a": 1})
    qtbot.addWidget(dialog)

    assert dialog.table.item(0, 0).text() == "a"
    assert dialog.table.item(1, 0).text() == "b"


def test_all_data_viewer_update_data_replaces_rows_and_resorts(qtbot):
    dialog = child_dialogs.AllDataViewerDialog({"z": 9})
    qtbot.addWidget(dialog)

    dialog.update_data({"c": 3, "b": 2})

    assert dialog.table.rowCount() == 2
    assert dialog.table.item(0, 0).text() == "b"
    assert dialog.table.item(1, 0).text() == "c"


class DummyMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = {"chart_y_min": 5.0, "chart_y_max": 105.0}


def test_custom_toolbar_home_resets_view_with_data(qtbot):
    fig, ax = plt.subplots()
    canvas = FigureCanvas(fig)
    parent = DummyMainWindow()
    qtbot.addWidget(parent)

    now = datetime.now()
    timestamps = {
        "term_k": [now - timedelta(seconds=20), now],
        "term_c": [],
        "term_d": [],
    }

    toolbar = child_dialogs.CustomNavigationToolbar(canvas, parent, timestamps)
    qtbot.addWidget(toolbar)

    ax.set_xlim(now, now + timedelta(seconds=1))
    ax.set_ylim(0, 1)

    toolbar.home()

    ymin, ymax = ax.get_ylim()
    x_min, x_max = ax.get_xlim()
    assert ymin == pytest.approx(5.0)
    assert ymax == pytest.approx(105.0)
    assert x_max > x_min
    assert ax.get_autoscalex_on() is True


def test_custom_toolbar_home_sets_default_window_without_data(qtbot):
    fig, ax = plt.subplots()
    canvas = FigureCanvas(fig)
    parent = DummyMainWindow()
    qtbot.addWidget(parent)

    timestamps = {"term_k": [], "term_c": [], "term_d": []}
    toolbar = child_dialogs.CustomNavigationToolbar(canvas, parent, timestamps)
    qtbot.addWidget(toolbar)

    toolbar.home()

    x_min, x_max = ax.get_xlim()
    # With no data, toolbar enforces a short default horizon around "now".
    assert (x_max - x_min) > 0
    assert ax.get_autoscalex_on() is True
