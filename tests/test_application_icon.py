import os
import types

from PyQt5.QtWidgets import QWidget

from alco_esp import application_icon


def test_application_icon_files_exist():
    assert os.path.isfile(application_icon.APP_ICON_PATH)
    assert os.path.isfile(application_icon.APP_ICON_ICO_PATH)


def test_load_application_icon_from_real_file(qapp):
    icon = application_icon.load_application_icon()
    assert icon.isNull() is False


def test_load_application_icon_missing_file_returns_null(qapp, tmp_path):
    icon = application_icon.load_application_icon(str(tmp_path / "missing.png"))
    assert icon.isNull() is True


def test_load_application_icon_corrupt_file_does_not_raise(qapp, tmp_path):
    bad_icon = tmp_path / "app_icon.png"
    bad_icon.write_bytes(b"this is not a png")

    application_icon.load_application_icon(str(bad_icon))


def test_load_application_icon_oserror_returns_null(qapp, monkeypatch):
    def raise_oserror(_path):
        raise OSError("stat failed")

    monkeypatch.setattr(application_icon.os.path, "isfile", raise_oserror)

    icon = application_icon.load_application_icon("/any/path.png")

    assert icon.isNull() is True


def test_apply_application_icon_sets_qapp_icon(qapp):
    icon = application_icon.apply_application_icon(qapp)
    assert icon.isNull() is False
    assert qapp.windowIcon().isNull() is False


def test_apply_application_icon_missing_file_does_not_raise(qapp, tmp_path):
    icon = application_icon.apply_application_icon(qapp, str(tmp_path / "missing.png"))
    assert icon.isNull() is True


def test_apply_application_icon_setWindowIcon_error_does_not_raise(qapp, monkeypatch):
    def raise_runtime_error(_icon):
        raise RuntimeError("setWindowIcon failed")

    monkeypatch.setattr(qapp, "setWindowIcon", raise_runtime_error)

    icon = application_icon.apply_application_icon(qapp)

    assert icon.isNull() is True


def test_apply_window_icon_sets_widget_icon(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)

    icon = application_icon.apply_window_icon(widget)

    assert icon.isNull() is False
    assert widget.windowIcon().isNull() is False


def test_apply_window_icon_setWindowIcon_error_does_not_raise(qapp, monkeypatch):
    class FakeWindow:
        def setWindowIcon(self, _icon):
            raise RuntimeError("setWindowIcon failed")

    icon = application_icon.apply_window_icon(FakeWindow())

    assert icon.isNull() is True


def test_apply_macos_dock_icon_missing_file_does_not_raise(tmp_path):
    application_icon.apply_macos_dock_icon(str(tmp_path / "missing.png"))


def test_apply_macos_dock_icon_library_error_does_not_raise(monkeypatch):
    import ctypes.util

    def raise_oserror(_name):
        raise OSError("library lookup failed")

    monkeypatch.setattr(application_icon.os.path, "isfile", lambda _path: True)
    monkeypatch.setattr(application_icon.sys, "platform", "darwin")
    monkeypatch.setattr(ctypes.util, "find_library", raise_oserror)

    application_icon.apply_macos_dock_icon(application_icon.APP_ICON_PATH)


def test_apply_windows_app_user_model_id_does_not_raise():
    application_icon.apply_windows_app_user_model_id()


def test_apply_windows_app_user_model_id_os_error_does_not_raise(monkeypatch):
    import ctypes

    def raise_oserror(_app_id):
        raise OSError("SetCurrentProcessExplicitAppUserModelID failed")

    fake_shell32 = types.SimpleNamespace(
        SetCurrentProcessExplicitAppUserModelID=raise_oserror
    )
    monkeypatch.setattr(application_icon.sys, "platform", "win32")
    monkeypatch.setattr(
        ctypes,
        "windll",
        types.SimpleNamespace(shell32=fake_shell32),
        raising=False,
    )

    application_icon.apply_windows_app_user_model_id()
