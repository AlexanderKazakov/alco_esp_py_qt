import json
import os
import sys
from datetime import timedelta, datetime

from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QMessageBox, QDialog, QVBoxLayout, QPushButton, QTableWidget, QHeaderView, QTableWidgetItem, QLabel)

from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar

from alco_esp.logging import logger
from alco_esp.constants import APP_ROOT_DIR, STYLE_ALARM_TRIGGERED

SECRETS_FILE_PATH = os.path.join(APP_ROOT_DIR, "secrets.json")


def load_secrets_with_gui_feedback():
    """
    Loads secrets from secrets.json.
    On error, it logs, shows a QMessageBox, and exits.
    """
    if not os.path.exists(SECRETS_FILE_PATH):
        template_path = os.path.join(APP_ROOT_DIR, "secrets_template.json")
        msg = f"Файл с секретами не найден: {SECRETS_FILE_PATH}\n\n"
        if os.path.exists(template_path):
            msg += "Пожалуйста, скопируйте 'secrets_template.json' в 'secrets.json' и укажите ваши данные."
        else:
            msg += "Шаблон 'secrets_template.json' также отсутствует. Продолжение невозможно."
        logger.critical(msg)
        QMessageBox.critical(None, "Ошибка конфигурации", msg)
        sys.exit(1)

    try:
        with open(SECRETS_FILE_PATH, 'r', encoding='utf-8') as f:
            secrets = json.load(f)

        required_keys = ["broker", "port", "username", "password"]
        if not all(key in secrets for key in required_keys):
            missing_keys = [key for key in required_keys if key not in secrets]
            msg = f"В файле секретов {SECRETS_FILE_PATH} отсутствуют необходимые ключи: {', '.join(missing_keys)}"
            logger.critical(msg)
            QMessageBox.critical(None, "Ошибка конфигурации", msg)
            sys.exit(1)

        logger.info("Successfully loaded secrets from secrets.json.")
        return secrets

    except json.JSONDecodeError as e:
        msg = f"Error decoding {SECRETS_FILE_PATH}: {e}"
        logger.critical(msg, exc_info=True)
        QMessageBox.critical(None, "Ошибка конфигурации", f"Ошибка чтения secrets.json. Является ли он корректным JSON?\n\n{e}")
        sys.exit(1)
    except Exception as e:
        msg = f"An unexpected error occurred while loading secrets: {e}"
        logger.critical(msg, exc_info=True)
        QMessageBox.critical(None, "Ошибка конфигурации", msg)
        sys.exit(1)


class CustomNavigationToolbar(NavigationToolbar):
    def __init__(self, canvas, parent, timestamps_ref):
        super().__init__(canvas, parent)
        self.main_window = parent
        self.timestamps_ref = timestamps_ref

    def home(self, *args):
        """Overrides the default home button behavior to zoom to full data range
        and re-enable auto-scrolling."""
        logger.debug("Custom 'Home' button pressed. Resetting view to full data range and enabling autoscroll.")
        ax = self.canvas.figure.axes[0]

        all_times = [t for topic_times in self.timestamps_ref.values() for t in topic_times if topic_times]
        if all_times:
            min_time = min(all_times)
            max_time = max(all_times)
            if min_time == max_time:
                max_time = max_time + timedelta(seconds=10)
            else:
                time_range = max_time - min_time
                max_time = max_time + time_range * 0.05
                min_time = min_time - time_range * 0.01
            ax.set_xlim(min_time, max_time)
            logger.debug(f"Home button: setting xlim to ({min_time}, {max_time})")
        else:
            now = datetime.now()
            ax.set_xlim(now - timedelta(seconds=60), now)

        # Reset Y-axis to default view
        ax.set_ylim(self.main_window.settings["chart_y_min"], self.main_window.settings["chart_y_max"])

        # Re-enable autoscale on the x-axis so the plot continues to scroll
        ax.set_autoscalex_on(True)

        # Tell the toolbar that this is the new "home" view.
        # This clears the zoom history and sets the current view as the base.
        self.update()
        self.canvas.draw()


class AllDataViewerDialog(QDialog):
    def __init__(self, data_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Все данные от устройства")
        self.setModal(False)

        layout = QVBoxLayout(self)

        self.log_button = QPushButton("Показать журналы данных")
        self.log_button.clicked.connect(self.open_log_folder)
        layout.addWidget(self.log_button)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Параметр", "Значение"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.setSortingEnabled(True)

        layout.addWidget(self.table)
        self.update_data(data_dict)

        self.adjustSize()  # Adjust to content width

    def open_log_folder(self):
        log_dir = os.path.join(APP_ROOT_DIR, "log")
        if os.path.isdir(log_dir):
            QDesktopServices.openUrl(QUrl.fromLocalFile(log_dir))
        else:
            QMessageBox.warning(self, "Папка не найдена", f"Папка с журналами не найдена:\n{log_dir}")

    def update_data(self, data_dict):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(data_dict))

        # Using a list from items() is sufficient
        sorted_items = sorted(data_dict.items())

        for row, (key, value) in enumerate(sorted_items):
            self.table.setItem(row, 0, QTableWidgetItem(str(key)))
            self.table.setItem(row, 1, QTableWidgetItem(str(value)))

        self.table.resizeRowsToContents()
        self.table.setSortingEnabled(True)


class AlarmNotificationDialog(QDialog):
    def __init__(self, message, sound_effect, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ВНИМАНИЕ!")
        self.setModal(True)
        self.sound_effect = sound_effect # Store the sound effect instance

        layout = QVBoxLayout(self)

        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet(STYLE_ALARM_TRIGGERED)
        self.message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.message_label)

        self.ok_button = QPushButton("Сбросить")
        self.ok_button.clicked.connect(self.accept) # accept() will close the dialog
        layout.addWidget(self.ok_button)

        self.setMinimumWidth(350)
        self.adjustSize() # Adjust size to content

        # Optional: Center on parent or screen
        if parent:
            parent_rect = parent.geometry()
            self.move(parent_rect.center().x() - self.width() // 2,
                      parent_rect.center().y() - self.height() // 2)

    def accept(self):
        """Called when OK button is clicked."""
        if self.sound_effect and self.sound_effect.isPlaying():
            self.sound_effect.stop()
        super().accept()

    def closeEvent(self, event):
        """Ensure sound stops if dialog is closed by other means."""
        if self.sound_effect and self.sound_effect.isPlaying():
            self.sound_effect.stop()
        super().closeEvent(event)
