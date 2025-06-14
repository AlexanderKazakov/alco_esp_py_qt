import json
import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QFormLayout, QLabel, QDoubleSpinBox, QHBoxLayout, QPushButton

from alco_esp.constants import APP_ROOT_DIR
from alco_esp.logging import logger


DEFAULT_T_SIGNAL_KUB = 60.0  # °C
DEFAULT_T_SIGNAL_DEFLEGMATOR = 70.0  # °C
DEFAULT_DELTA_T = 0.2 # °C
DEFAULT_PERIOD_SECONDS = 60 # seconds
DEFAULT_TEMP_STOP_RAZGON = 70.0  # °C
DEFAULT_CHART_Y_MIN = 10.0 # °C
DEFAULT_CHART_Y_MAX = 110.0 # °C
TERM_K_M_CHECK_TIMEOUT = 20 # seconds

SETTINGS_FILE_PATH = os.path.join(APP_ROOT_DIR, "settings.json")


def save_settings(settings):
    """Saves settings to the JSON file."""
    try:
        with open(SETTINGS_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        logger.info(f"Настройки сохранены в {SETTINGS_FILE_PATH}")
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек в {SETTINGS_FILE_PATH}: {e}", exc_info=True)


def load_settings():
    """Loads settings from the JSON file, or returns defaults if it fails."""
    defaults = {
        "t_signal_kub": DEFAULT_T_SIGNAL_KUB,
        "t_signal_deflegmator": DEFAULT_T_SIGNAL_DEFLEGMATOR,
        "delta_t": DEFAULT_DELTA_T,
        "period_seconds": DEFAULT_PERIOD_SECONDS,
        "temp_stop_razgon": DEFAULT_TEMP_STOP_RAZGON,
        "chart_y_min": DEFAULT_CHART_Y_MIN,
        "chart_y_max": DEFAULT_CHART_Y_MAX
    }

    if not os.path.exists(SETTINGS_FILE_PATH):
        logger.warning(f"Файл настроек не найден: {SETTINGS_FILE_PATH}. "
                       f"Используются настройки по-умолчанию, файл будет создан.")
        save_settings(defaults)
        return defaults

    try:
        with open(SETTINGS_FILE_PATH, 'r', encoding='utf-8') as f:
            loaded_settings = json.load(f)

        # Check for missing keys and add them from defaults if necessary
        settings_updated = False
        for key, value in defaults.items():
            if key not in loaded_settings:
                loaded_settings[key] = value
                settings_updated = True
                logger.warning(f"Отсутствующий ключ '{key}' добавлен в настройки со значением по умолчанию.")

        if settings_updated:
            save_settings(loaded_settings)

        logger.info(f"Настройки загружены из {SETTINGS_FILE_PATH}")
        return loaded_settings
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Ошибка загрузки или парсинга файла настроек {SETTINGS_FILE_PATH}: {e}. "
                     f"Используются настройки по-умолчанию.")
        return defaults


class SettingsDialog(QDialog):
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setModal(True)
        layout = QFormLayout(self)
        layout.setRowWrapPolicy(QFormLayout.WrapAllRows)

        # --- Сигналы ---
        heading_signals = QLabel("<b>Сигналы</b>")
        heading_signals.setAlignment(Qt.AlignCenter)
        layout.addRow(heading_signals)

        self.t_signal_kub_spinbox = QDoubleSpinBox()
        self.t_signal_kub_spinbox.setRange(0.0, 100.0)
        self.t_signal_kub_spinbox.setDecimals(1)
        self.t_signal_kub_spinbox.setSingleStep(0.1)
        self.t_signal_kub_spinbox.setValue(current_settings.get("t_signal_kub", DEFAULT_T_SIGNAL_KUB))
        layout.addRow("Порог сигнала T куба (°C):", self.t_signal_kub_spinbox)

        self.t_signal_deflegmator_spinbox = QDoubleSpinBox()
        self.t_signal_deflegmator_spinbox.setRange(0.0, 100.0)
        self.t_signal_deflegmator_spinbox.setDecimals(1)
        self.t_signal_deflegmator_spinbox.setSingleStep(0.1)
        self.t_signal_deflegmator_spinbox.setValue(
            current_settings.get("t_signal_deflegmator", DEFAULT_T_SIGNAL_DEFLEGMATOR))
        layout.addRow("Порог сигнала T дефлегматора (°C):", self.t_signal_deflegmator_spinbox)

        heading_temp_signal = QLabel("<b>Сигнал стабильности температуры</b>")
        heading_temp_signal.setAlignment(Qt.AlignCenter)
        layout.addRow(heading_temp_signal)

        self.delta_t_spinbox = QDoubleSpinBox()
        self.delta_t_spinbox.setRange(0.01, 10.0)
        self.delta_t_spinbox.setDecimals(2)
        self.delta_t_spinbox.setSingleStep(0.01)
        self.delta_t_spinbox.setValue(current_settings.get("delta_t", DEFAULT_DELTA_T))
        layout.addRow("Порог разброса ΔT <i>(max(ΔT) - min(ΔT))</i> за период (°C):", self.delta_t_spinbox)

        self.period_spinbox = QDoubleSpinBox()  # Using QDoubleSpinBox for consistency, could be QSpinBox
        self.period_spinbox.setRange(1.0, 3600.0)  # Seconds
        self.period_spinbox.setDecimals(0)
        self.period_spinbox.setValue(current_settings.get("period_seconds", DEFAULT_PERIOD_SECONDS))
        layout.addRow("Период оценки разброса ΔT (с):", self.period_spinbox)

        # --- Разгон ---
        heading_razgon = QLabel("<b>Разгон</b>")
        heading_razgon.setAlignment(Qt.AlignCenter)
        layout.addRow(heading_razgon)

        self.temp_stop_razgon_spinbox = QDoubleSpinBox()
        self.temp_stop_razgon_spinbox.setRange(0.0, 100.0)
        self.temp_stop_razgon_spinbox.setDecimals(1)
        self.temp_stop_razgon_spinbox.setSingleStep(0.1)
        self.temp_stop_razgon_spinbox.setValue(current_settings.get("temp_stop_razgon", DEFAULT_TEMP_STOP_RAZGON))
        layout.addRow("Температура остановки разгона куба (°C):", self.temp_stop_razgon_spinbox)

        # --- График ---
        heading_chart = QLabel("<b>График</b>")
        heading_chart.setAlignment(Qt.AlignCenter)
        layout.addRow(heading_chart)

        self.chart_y_min_spinbox = QDoubleSpinBox()
        self.chart_y_min_spinbox.setRange(-50.0, 200.0)
        self.chart_y_min_spinbox.setDecimals(0)
        self.chart_y_min_spinbox.setSingleStep(1.0)
        self.chart_y_min_spinbox.setValue(current_settings.get("chart_y_min", DEFAULT_CHART_Y_MIN))
        layout.addRow("Пределы температур на графике, мин (°C):", self.chart_y_min_spinbox)

        self.chart_y_max_spinbox = QDoubleSpinBox()
        self.chart_y_max_spinbox.setRange(-50.0, 200.0)
        self.chart_y_max_spinbox.setDecimals(0)
        self.chart_y_max_spinbox.setSingleStep(1.0)
        self.chart_y_max_spinbox.setValue(current_settings.get("chart_y_max", DEFAULT_CHART_Y_MAX))
        layout.addRow("Пределы температур на графике, макс (°C):", self.chart_y_max_spinbox)


        self.buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.reject)
        self.buttons_layout.addStretch()
        self.buttons_layout.addWidget(self.ok_button)
        self.buttons_layout.addWidget(self.cancel_button)
        layout.addRow(self.buttons_layout)

    def get_settings(self):
        return {
            "t_signal_kub": self.t_signal_kub_spinbox.value(),
            "t_signal_deflegmator": self.t_signal_deflegmator_spinbox.value(),
            "delta_t": self.delta_t_spinbox.value(),
            "period_seconds": int(self.period_spinbox.value()),
            "temp_stop_razgon": self.temp_stop_razgon_spinbox.value(),
            "chart_y_min": self.chart_y_min_spinbox.value(),
            "chart_y_max": self.chart_y_max_spinbox.value()
        }
