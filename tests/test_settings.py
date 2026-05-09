import json
from pathlib import Path

import pytest

from alco_esp import settings


def test_load_settings_creates_defaults_when_file_missing(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(settings, "SETTINGS_FILE_PATH", str(settings_path))

    loaded = settings.load_settings()

    assert settings_path.exists()
    assert loaded == json.loads(settings_path.read_text(encoding="utf-8"))
    assert loaded["t_signal_kub"] == settings.DEFAULT_T_SIGNAL_KUB
    assert loaded["chart_y_max"] == settings.DEFAULT_CHART_Y_MAX


def test_load_settings_merges_missing_keys_and_persists(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"t_signal_kub": 61.5}), encoding="utf-8")
    monkeypatch.setattr(settings, "SETTINGS_FILE_PATH", str(settings_path))

    loaded = settings.load_settings()
    persisted = json.loads(settings_path.read_text(encoding="utf-8"))

    assert loaded["t_signal_kub"] == 61.5
    assert "period_seconds" in loaded
    assert persisted == loaded


def test_load_settings_returns_defaults_on_invalid_json(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{invalid-json", encoding="utf-8")
    monkeypatch.setattr(settings, "SETTINGS_FILE_PATH", str(settings_path))

    loaded = settings.load_settings()

    assert loaded["delta_t"] == settings.DEFAULT_DELTA_T
    assert loaded["temp_stop_razgon"] == settings.DEFAULT_TEMP_STOP_RAZGON


def test_load_settings_does_not_resave_when_keys_are_complete(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"
    full = {
        "t_signal_kub": 60.1,
        "t_signal_deflegmator": 70.2,
        "delta_t": 0.4,
        "period_seconds": 45,
        "temp_stop_razgon": 72.0,
        "chart_y_min": 9.0,
        "chart_y_max": 112.0,
    }
    settings_path.write_text(json.dumps(full), encoding="utf-8")
    monkeypatch.setattr(settings, "SETTINGS_FILE_PATH", str(settings_path))

    save_calls = []
    monkeypatch.setattr(settings, "save_settings", lambda payload: save_calls.append(payload))

    loaded = settings.load_settings()

    assert loaded == full
    assert save_calls == []


def test_load_settings_calls_save_when_missing_keys(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"period_seconds": 33}), encoding="utf-8")
    monkeypatch.setattr(settings, "SETTINGS_FILE_PATH", str(settings_path))

    save_calls = []
    monkeypatch.setattr(settings, "save_settings", lambda payload: save_calls.append(payload.copy()))

    loaded = settings.load_settings()

    assert len(save_calls) == 1
    assert save_calls[0] == loaded
    assert loaded["period_seconds"] == 33


def test_save_settings_logs_error_on_write_failure(monkeypatch):
    expected_path = settings.SETTINGS_FILE_PATH

    class Boom(Exception):
        pass

    def raising_open(path, *_args, **_kwargs):
        if path == expected_path:
            raise Boom("cannot write")
        return Path(path).open(*_args, **_kwargs)

    error_messages = []
    monkeypatch.setattr("builtins.open", raising_open)
    monkeypatch.setattr(settings.logger, "error", lambda msg, **_kwargs: error_messages.append(msg))

    settings.save_settings({"k": "v"})

    assert any("Ошибка сохранения настроек" in msg for msg in error_messages)


def test_settings_dialog_get_settings_returns_expected_types(qtbot, default_settings):
    dialog = settings.SettingsDialog(current_settings=default_settings.copy())
    qtbot.addWidget(dialog)

    dialog.t_signal_kub_spinbox.setValue(63.7)
    dialog.period_spinbox.setValue(123)
    dialog.chart_y_min_spinbox.setValue(5)

    payload = dialog.get_settings()

    assert isinstance(payload["period_seconds"], int)
    assert isinstance(payload["t_signal_kub"], float)
    assert payload["period_seconds"] == 123
    assert payload["t_signal_kub"] == pytest.approx(63.7)
