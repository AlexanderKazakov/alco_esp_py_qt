import os
import sys

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from alco_esp.constants import APP_ROOT_DIR
from alco_esp.logging import logger

APP_ICON_PATH = os.path.join(APP_ROOT_DIR, "app_icon.png")
APP_ICON_ICO_PATH = os.path.join(APP_ROOT_DIR, "app_icon.ico")
WINDOWS_APP_USER_MODEL_ID = "AlcoEsp.Monitor"


def load_application_icon(icon_path=APP_ICON_PATH):
    """Loads the app icon, or a null QIcon if the file is missing or unreadable."""
    try:
        if QApplication.instance() is None:
            logger.warning("Cannot load application icon before QApplication is created.")
            return QIcon()
        if not os.path.isfile(icon_path):
            logger.warning("Application icon file not found: %s", icon_path)
            return QIcon()
        icon = QIcon(icon_path)
        if icon.isNull():
            logger.warning("Application icon file could not be loaded: %s", icon_path)
        return icon
    except Exception:
        logger.warning("Could not load application icon: %s", icon_path, exc_info=True)
        return QIcon()


def apply_window_icon(window, icon_path=APP_ICON_PATH):
    """Sets the icon on one Qt window. Failures are logged and ignored."""
    try:
        icon = load_application_icon(icon_path)
        if icon.isNull():
            return icon
        window.setWindowIcon(icon)
        return icon
    except Exception:
        logger.warning("Could not set window icon.", exc_info=True)
        return QIcon()


def apply_windows_app_user_model_id(app_id=WINDOWS_APP_USER_MODEL_ID):
    """Gives the process its own Windows taskbar identity instead of python.exe."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        logger.debug("Could not set Windows AppUserModelID.", exc_info=True)


def apply_macos_dock_icon(icon_path):
    """Sets the macOS Dock icon for this process when AppKit is available."""
    if sys.platform != "darwin" or not os.path.isfile(icon_path):
        return
    try:
        import ctypes
        import ctypes.util

        appkit_path = ctypes.util.find_library("AppKit")
        objc_path = ctypes.util.find_library("objc")
        if not appkit_path or not objc_path:
            return
        ctypes.cdll.LoadLibrary(appkit_path)
        objc = ctypes.cdll.LoadLibrary(objc_path)
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]

        def make_sender(restype, *argtypes):
            return ctypes.CFUNCTYPE(restype, *argtypes)(("objc_msgSend", objc))

        msg_id = make_sender(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
        msg_id_id = make_sender(
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
        )
        msg_id_str = make_sender(
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p
        )

        ns_string_class = objc.objc_getClass(b"NSString")
        ns_image_class = objc.objc_getClass(b"NSImage")
        ns_application_class = objc.objc_getClass(b"NSApplication")
        if not ns_string_class or not ns_image_class or not ns_application_class:
            return

        ns_path = msg_id_str(
            ns_string_class,
            objc.sel_registerName(b"stringWithUTF8String:"),
            icon_path.encode("utf-8"),
        )
        ns_image = msg_id_id(
            msg_id(ns_image_class, objc.sel_registerName(b"alloc")),
            objc.sel_registerName(b"initWithContentsOfFile:"),
            ns_path,
        )
        if not ns_image:
            return
        ns_app = msg_id(
            ns_application_class, objc.sel_registerName(b"sharedApplication")
        )
        if not ns_app:
            return
        msg_id_id(
            ns_app,
            objc.sel_registerName(b"setApplicationIconImage:"),
            ns_image,
        )
    except Exception:
        logger.debug("Could not set macOS Dock icon.", exc_info=True)


def apply_application_icon(app, icon_path=APP_ICON_PATH):
    """Applies the app icon to Qt and to the macOS Dock. Failures are logged and ignored."""
    try:
        icon = load_application_icon(icon_path)
        if icon.isNull():
            return icon
        app.setWindowIcon(icon)
        apply_macos_dock_icon(icon_path)
        return icon
    except Exception:
        logger.warning("Could not apply application icon.", exc_info=True)
        return QIcon()
