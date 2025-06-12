import sys
import signal
import json
import paho.mqtt.client as mqtt
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel,
                             QGridLayout, QHBoxLayout, QDoubleSpinBox, QPushButton,
                             QSpacerItem, QSizePolicy, QDialog, QFormLayout, QMessageBox, QComboBox)
from PyQt5.QtCore import QThread, QObject, pyqtSignal, pyqtSlot, QTimer, Qt, QUrl
from PyQt5.QtMultimedia import QSoundEffect
import os
from collections import deque
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler

from alco_esp_constants import WORK_STATE_NAMES, WorkState


# --- MQTT Settings (Copied from original script) ---
client_id = "python_qt_client_viewer" # Changed client ID slightly
# Updated topics to subscribe to based on new requirements
topics = ["term_c", "term_k", "term_d"]

# --- CSV Logging Settings ---
CSV_DATA_TOPIC_ORDER = ["term_c", "term_k", "term_d"]
CSV_DATA_HEADERS = {
    "term_c": "T царга",
    "term_k": "T куб",
    "term_d": "T дефлегматор"
}

# Path to the directory of the script or to the Pyinstaller executable directory
# to get the resources and to write logs to
APP_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Secrets Management ---
SECRETS_FILE_PATH = os.path.join(APP_ROOT_DIR, "secrets.json")

# --- Alarm signal audio file path ---
# Alarm file is expected to be directly in the APP_ROOT_DIR
ALARM_FILE_PATH = os.path.join(APP_ROOT_DIR, "alarm.wav")

# --- Maximum MQTT connection delay. When it is exceeded, user is notified ---
MQTT_DATA_TIMEOUT_SECONDS = 60.0

# --- Signal Style Definitions ---
STYLE_ALARM_TRIGGERED = "background-color: orangered; color: white; padding: 5px; border: 1px solid grey;"
STYLE_MONITORING = "background-color: lightblue; padding: 5px; border: 1px solid grey;"
STYLE_INACTIVE = "background-color: lightgray; padding: 5px; border: 1px solid grey;"

# Topics for publishing control values (will be prefixed)
control_topics = {
    "work": "work",
    "otbor_g_1_new": "otbor_g_1_new",
    "term_c_max_new": "term_c_max_new",
    "term_c_min_new": "term_c_min_new",
    "otbor_t_new": "otbor_t_new"
}


# --- Data Storage ---
window_size = 10**6
# Initialize data storage for all subscribed topics
data = {key: deque(maxlen=window_size) for key in topics}
timestamps = {key: deque(maxlen=window_size) for key in topics}
latest_values = {key: None for key in topics}

# --- Default Settings for Signal Conditions ---
DEFAULT_T_SIGNAL_KUB = 60.0  # °C
DEFAULT_T_SIGNAL_DEFLEGMATOR = 70.0  # °C
DEFAULT_DELTA_T = 0.1       # °C
DEFAULT_PERIOD_SECONDS = 60 # seconds


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


# --- Settings Dialog ---
class SettingsDialog(QDialog):
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки сигналов")
        self.setModal(True)
        layout = QFormLayout(self)

        self.t_signal_kub_spinbox = QDoubleSpinBox()
        self.t_signal_kub_spinbox.setRange(0.0, 100.0)
        self.t_signal_kub_spinbox.setDecimals(1)
        self.t_signal_kub_spinbox.setSingleStep(0.1)
        self.t_signal_kub_spinbox.setValue(current_settings.get("t_signal_kub", DEFAULT_T_SIGNAL_KUB))
        layout.addRow("T порог срабатывания по T куба (°C):", self.t_signal_kub_spinbox)

        self.t_signal_deflegmator_spinbox = QDoubleSpinBox()
        self.t_signal_deflegmator_spinbox.setRange(0.0, 100.0)
        self.t_signal_deflegmator_spinbox.setDecimals(1)
        self.t_signal_deflegmator_spinbox.setSingleStep(0.1)
        self.t_signal_deflegmator_spinbox.setValue(current_settings.get("t_signal_deflegmator", DEFAULT_T_SIGNAL_DEFLEGMATOR))
        layout.addRow("T порог срабатывания по T дефлегматора (°C):", self.t_signal_deflegmator_spinbox)

        self.delta_t_spinbox = QDoubleSpinBox()
        self.delta_t_spinbox.setRange(0.01, 10.0)
        self.delta_t_spinbox.setDecimals(2)
        self.delta_t_spinbox.setSingleStep(0.1)
        self.delta_t_spinbox.setValue(current_settings.get("delta_t", DEFAULT_DELTA_T))
        layout.addRow("Delta T для стабильности (°C):", self.delta_t_spinbox)

        self.period_spinbox = QDoubleSpinBox() # Using QDoubleSpinBox for consistency, could be QSpinBox
        self.period_spinbox.setRange(1.0, 3600.0) # Seconds
        self.period_spinbox.setDecimals(0)
        self.period_spinbox.setValue(current_settings.get("period_seconds", DEFAULT_PERIOD_SECONDS))
        layout.addRow("Период стабильности (секунд):", self.period_spinbox)

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
            "period_seconds": int(self.period_spinbox.value())
        }

# --- Alarm Notification Dialog ---
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

# --- MQTT Worker Thread ---
class MqttWorker(QObject):
    """
    Handles MQTT communication in a separate thread.
    """
    messageReceived = pyqtSignal(str, str) # topic, payload
    connectionStatus = pyqtSignal(str)    # status message
    finished = pyqtSignal()               # Signal emitted when the worker is done

    def __init__(self, broker, port, username, password, client_id, topics_to_subscribe):
        super().__init__()
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.topics_to_subscribe = topics_to_subscribe
        self.topic_prefix = f"{username}/"
        self.client = None

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log_msg = f"Подключено к MQTT брокеру: {self.broker}"
            logger.info(log_msg)
            self.connectionStatus.emit(log_msg)
            for key in self.topics_to_subscribe:
                topic_to_sub = self.topic_prefix + key
                client.subscribe(topic_to_sub)
                logger.info(f"Subscribed to: {topic_to_sub}")
        else:
            log_msg = f"Ошибка подключения, код {rc}"
            logger.error(log_msg)
            self.connectionStatus.emit(log_msg)

    def on_message(self, client, userdata, msg):
        topic = msg.topic.replace(self.topic_prefix, "")
        payload = msg.payload.decode()
        logger.debug(f"Received MQTT message: Topic='{topic}', Payload='{payload}'")
        self.messageReceived.emit(topic, payload)

    def on_disconnect(self, client, userdata, rc):
         log_msg = f"Отключено от MQTT брокера (rc={rc})"
         logger.warning(log_msg) # Using warning for disconnect
         self.connectionStatus.emit(log_msg)
         if rc != 0:
             # Paho's loop_start() handles reconnection attempts automatically.
             logger.warning("Unexpected disconnection. Paho-MQTT will attempt to reconnect.")
             self.connectionStatus.emit("Неожиданное отключение. Попытка переподключения...")

    def run(self):
        """
        Connects and starts the MQTT loop in the background.
        """
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, self.client_id)
        self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        try:
            self.connectionStatus.emit(f"Подключение к {self.broker}...")
            logger.info(f"MqttWorker: Attempting to connect to {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start() # Start network loop in background thread and return
            logger.info("MqttWorker: loop_start() called. Paho MQTT thread managing connection.")
            # The QThread's event loop will now run implicitly for this worker thread,
            # allowing it to process signals/slots like publish_message.
        except Exception as e:
            logger.error(f"MqttWorker: MQTT connection error: {e}", exc_info=True)
            self.connectionStatus.emit(f"Ошибка подключения MQTT: {e}")
            # If connection fails, we should signal finished maybe?
            # Or attempt reconnect later? For now, emit finished.
            self.finished.emit() # Emit finished if connection fails immediately

        # Note: No loop_forever() here. The run method finishes,
        # but the Paho loop runs in its own thread, and the MqttWorker
        # object continues to live in the QThread, processing Qt events.
        # We also remove the finally block that disconnected,
        # as disconnection should happen on closeEvent or explicit stop.

    @pyqtSlot(str, str)
    def publish_message(self, topic_suffix, payload):
        """Publishes a message to the specified topic suffix."""
        # logger.debug("In publish_message") # Debug
        if self.client and self.client.is_connected():
            full_topic = self.topic_prefix + topic_suffix
            try:
                # Add status update before publishing
                self.connectionStatus.emit(f"Публикация: {topic_suffix} = {payload}")
                logger.info(f"Attempting to publish: Topic='{full_topic}', Payload='{payload}'")
                rc, mid = self.client.publish(full_topic, payload=payload, qos=1) # Use QoS 1 for reliability
                if rc == mqtt.MQTT_ERR_SUCCESS:
                    logger.info(f"Successfully published: Topic='{full_topic}', Payload='{payload}', MID={mid}")
                    # Add status update on success
                    self.connectionStatus.emit(f"Опубликовано: {topic_suffix} = {payload}")
                else:
                    logger.error(f"Failed to publish to {full_topic}, return code: {rc}")
                    self.connectionStatus.emit(f"Ошибка публикации: {topic_suffix} (код {rc})")
            except Exception as e:
                logger.error(f"Error publishing message to {full_topic}: {e}", exc_info=True)
                self.connectionStatus.emit(f"Ошибка публикации: {topic_suffix}: {e}")
        else:
            logger.warning("Cannot publish, MQTT client not connected.")
            self.connectionStatus.emit("Ошибка публикации: нет подключения")


# --- Main Application Window ---
class AlcoEspMonitor(QMainWindow):
    # Add signal to request MQTT publication from the worker
    publishRequested = pyqtSignal(str, str)

    def __init__(self, secrets):
        super().__init__()
        self.secrets = secrets
        logger.info("Initializing AlcoEspMonitor main window.")
        self.setWindowTitle("Alco ESP Real-Time Monitor")
        self.setGeometry(100, 100, 1200, 700) # Adjusted size

        # --- Initialize Settings ---
        self.settings = {
            "t_signal_kub": DEFAULT_T_SIGNAL_KUB,
            "t_signal_deflegmator": DEFAULT_T_SIGNAL_DEFLEGMATOR,
            "delta_t": DEFAULT_DELTA_T,
            "period_seconds": DEFAULT_PERIOD_SECONDS
        }

        # --- Initialize Signal States ---
        self.t_kub_signal_monitoring_active = True
        self.t_kub_signal_triggered = False

        self.t_deflegmator_signal_monitoring_active = True
        self.t_deflegmator_signal_triggered = False

        self.stability_signal_monitoring_active = True
        self.stability_signal_triggered = False
        self.stability_condition_met_since = None

        # --- MQTT Data Tracking for Timeout ---
        self.last_mqtt_message_time = datetime.now() # Initialize to app start time
        self.mqtt_data_timeout_alarm_active = False  # Flag to track if "no data" alarm is shown

        # --- Initialize Sound Effect and Alarm Dialog (placeholder, actual init deferred) ---
        self.alarm_sound_effect = QSoundEffect(self)
        self.current_alarm_dialog = None # To keep track of the alarm dialog
        self._alarm_sound_initial_load_reported = False # Flag for initial load check

        # Defer the detailed sound initialization
        QTimer.singleShot(1000, self.initialize_sound_and_alarm_system)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)

        # --- Left Controls Panel ---
        self.controls_widget = QWidget()
        self.controls_layout = QVBoxLayout(self.controls_widget)
        self.controls_widget.setFixedWidth(350) # Slightly wider for more controls
        self.main_layout.addWidget(self.controls_widget)

        # --- Right Plot Panel ---
        self.plot_widget = QWidget()
        self.plot_layout = QVBoxLayout(self.plot_widget)
        self.main_layout.addWidget(self.plot_widget, 1)

        self.status_label = QLabel("Подключение...")
        self.plot_layout.addWidget(self.status_label)

        plt.style.use('seaborn-v0_8-darkgrid')
        self.figure, self.ax = plt.subplots(1, 1, figsize=(10, 6)) # Single plot
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)

        self.plot_layout.addWidget(self.toolbar)
        self.plot_layout.addWidget(self.canvas, 1)

        self.setup_controls()

        self.lines = {}
        self.latest_value_texts = {key: None for key in topics} # Updated for new topics

        self.configure_plots()
        self.setup_mqtt()

        self.plot_timer = QTimer()
        self.plot_timer.setInterval(2000)
        self.plot_timer.timeout.connect(self.update_plots_and_signals) # Combined update
        self.plot_timer.start()

    def initialize_sound_and_alarm_system(self):
        """Initializes the sound effect and sets up status checking."""
        logger.info("Initializing sound and alarm system.")
        if not os.path.exists(ALARM_FILE_PATH):
            warning_msg = (f"КРИТИЧЕСКАЯ ОШИБКА: Файл звукового сигнала НЕ НАЙДЕН:\n"
                           f"{os.path.abspath(ALARM_FILE_PATH)}")
            logger.critical(warning_msg)
            # Show this critical error immediately
            self.alarm_message_with_sound(warning_msg) # This will also log the alarm
            self._alarm_sound_initial_load_reported = True # Mark as reported
            return

        self.alarm_sound_effect.setSource(QUrl.fromLocalFile(os.path.abspath(ALARM_FILE_PATH)))
        self.alarm_sound_effect.setVolume(0.8)

        # Connect to statusChanged to know when loading is complete or if an error occurs
        self.alarm_sound_effect.statusChanged.connect(self._on_alarm_sound_status_changed)

        # Check current status immediately - it might already be loading or even ready if file is tiny/cached
        # or if setSource was called before and is being re-initialized.
        if self.alarm_sound_effect.status() == QSoundEffect.Loading:
            logger.info(f"Info: Alarm sound '{ALARM_FILE_PATH}' is loading...")
        elif self.alarm_sound_effect.status() == QSoundEffect.Ready:
            # If already ready (e.g. very fast load or re-init), handle it
            logger.info(f"Info: Alarm sound '{ALARM_FILE_PATH}' was already ready on init check.")
            self._on_alarm_sound_status_changed()
        # If status is Null or Error initially, statusChanged will likely fire soon.

    def _on_alarm_sound_status_changed(self):
        """Slot connected to alarm_sound_effect.statusChanged signal."""
        if self._alarm_sound_initial_load_reported:
            # If we've already reported the initial status (success or failure),
            # and this is just a subsequent status change, we might not need to act again here.
            # However, for robustness, if it transitions to Error later, it's good to know.
            # For now, we focus on the *initial* load result.
            # If it becomes an error *after* initial success, alarm_message_with_sound will catch it.
            return

        status = self.alarm_sound_effect.status()

        if status == QSoundEffect.Ready:
            logger.info(f"Success: Alarm sound file '{ALARM_FILE_PATH}' loaded successfully.")
            self._alarm_sound_initial_load_reported = True
            # Optionally disconnect if you only care about the very first successful load notification
            # self.alarm_sound_effect.statusChanged.disconnect(self._on_alarm_sound_status_changed)
        elif status == QSoundEffect.Error:
            error_msg = (f"ОШИБКА: Не удалось загрузить файл звукового сигнала:\n"
                         f"{os.path.abspath(ALARM_FILE_PATH)}\n\n"
                         f"Файл может быть поврежден или иметь неподдерживаемый формат. ")
            logger.error(error_msg)
            self.alarm_message_with_sound(error_msg) # Show user the problem, will also log
            self._alarm_sound_initial_load_reported = True
            # Optionally disconnect after error
            # self.alarm_sound_effect.statusChanged.disconnect(self._on_alarm_sound_status_changed)
        elif status == QSoundEffect.Loading:
            logger.info(f"Info: Alarm sound '{ALARM_FILE_PATH}' continues loading...")
        else:
            logger.debug(f"Alarm sound status changed to: {status} (Null or other). Path: '{ALARM_FILE_PATH}'")

    def setup_controls(self):
        """Creates and adds control widgets to the left panel."""
        logger.debug("Setting up UI controls.")
        controls_grid_layout = QGridLayout()
        controls_grid_layout.setSpacing(10)
        row = 0

        # --- Work Mode Control ---
        controls_grid_layout.addWidget(QLabel("<b>Управление режимом:</b>"), row, 0, 1, 2)
        row += 1

        self.work_mode_combobox = QComboBox()
        # Populate combobox, sorted by code
        for code, name in sorted(WORK_STATE_NAMES.items()):
            self.work_mode_combobox.addItem(f"{name} ({code})", userData=code)
        controls_grid_layout.addWidget(self.work_mode_combobox, row, 0, 1, 2)
        row += 1

        self.set_work_mode_button = QPushButton("Установить режим")
        self.set_work_mode_button.clicked.connect(self.publish_selected_work_mode)
        controls_grid_layout.addWidget(self.set_work_mode_button, row, 0, 1, 2)
        row += 1

        controls_grid_layout.addItem(QSpacerItem(20, 15, QSizePolicy.Minimum, QSizePolicy.Fixed), row, 0)
        row += 1

        # --- Otbor Golov Speed Control ---
        controls_grid_layout.addWidget(QLabel("<b>Отбор голов покапельно:</b>"), row, 0, 1, 2)
        row += 1
        controls_grid_layout.addWidget(QLabel("Скорость (ШИМ, %):"), row, 0)
        self.otbor_g_1_spinbox = QDoubleSpinBox()
        self.otbor_g_1_spinbox.setRange(0, 100) # PWM in %
        self.otbor_g_1_spinbox.setDecimals(0)
        controls_grid_layout.addWidget(self.otbor_g_1_spinbox, row, 1)
        row += 1
        self.set_otbor_g_1_button = QPushButton("Установить параметры отбора голов покапельно")
        self.set_otbor_g_1_button.clicked.connect(self.publish_otbor_g_1_speed)
        controls_grid_layout.addWidget(self.set_otbor_g_1_button, row, 0, 1, 2)
        row += 1

        controls_grid_layout.addItem(QSpacerItem(20, 15, QSizePolicy.Minimum, QSizePolicy.Fixed), row, 0)
        row += 1

        # --- Otbor Tela Control ---
        controls_grid_layout.addWidget(QLabel("<b>Отбор тела:</b>"), row, 0, 1, 2)
        row += 1
        controls_grid_layout.addWidget(QLabel("T стоп (°C):"), row, 0)
        self.term_c_max_telo_spinbox = QDoubleSpinBox()
        self.term_c_max_telo_spinbox.setRange(0.0, 100.0)
        self.term_c_max_telo_spinbox.setDecimals(1)
        self.term_c_max_telo_spinbox.setSingleStep(0.1)
        controls_grid_layout.addWidget(self.term_c_max_telo_spinbox, row, 1)
        row += 1
        controls_grid_layout.addWidget(QLabel("T старт (°C):"), row, 0)
        self.term_c_min_telo_spinbox = QDoubleSpinBox()
        self.term_c_min_telo_spinbox.setRange(0.0, 100.0)
        self.term_c_min_telo_spinbox.setDecimals(1)
        self.term_c_min_telo_spinbox.setSingleStep(0.1)
        controls_grid_layout.addWidget(self.term_c_min_telo_spinbox, row, 1)
        row += 1
        controls_grid_layout.addWidget(QLabel("ШИМ отбора тела (%):"), row, 0)
        self.otbor_t_spinbox = QDoubleSpinBox()
        self.otbor_t_spinbox.setRange(0, 100) # PWM in %
        self.otbor_t_spinbox.setDecimals(0)
        controls_grid_layout.addWidget(self.otbor_t_spinbox, row, 1)
        row += 1
        self.set_otbor_t_button = QPushButton("Установить параметры отбора тела")
        self.set_otbor_t_button.clicked.connect(self.publish_otbor_t_params)
        controls_grid_layout.addWidget(self.set_otbor_t_button, row, 0, 1, 2)
        row += 1

        controls_grid_layout.addItem(QSpacerItem(20, 15, QSizePolicy.Minimum, QSizePolicy.Fixed), row, 0)
        row += 1

        # --- Signal Conditions ---
        controls_grid_layout.addWidget(QLabel("<b>Сигналы (однократные):</b>"), row, 0, 1, 2)
        row += 1

        self.t_kub_signal_label = QLabel("T куба: Ожидание...")
        self.t_kub_signal_label.setStyleSheet("padding: 5px; border: 1px solid grey;")
        self.t_kub_signal_label.setAlignment(Qt.AlignCenter)
        controls_grid_layout.addWidget(self.t_kub_signal_label, row, 0, 1, 2)
        row += 1
        self.reset_t_kub_signal_button = QPushButton("Сброс сигнала T куба")
        self.reset_t_kub_signal_button.clicked.connect(lambda: self.reset_t_kub_signal())
        controls_grid_layout.addWidget(self.reset_t_kub_signal_button, row, 0, 1, 2)
        row += 1

        self.t_deflegmator_signal_label = QLabel("T дефлегматора: Ожидание...")
        self.t_deflegmator_signal_label.setStyleSheet("padding: 5px; border: 1px solid grey;")
        self.t_deflegmator_signal_label.setAlignment(Qt.AlignCenter)
        controls_grid_layout.addWidget(self.t_deflegmator_signal_label, row, 0, 1, 2)
        row += 1
        self.reset_t_deflegmator_signal_button = QPushButton("Сброс сигнала T дефлегматора")
        self.reset_t_deflegmator_signal_button.clicked.connect(lambda: self.reset_t_deflegmator_signal())
        controls_grid_layout.addWidget(self.reset_t_deflegmator_signal_button, row, 0, 1, 2)
        row += 1

        self.stability_signal_label = QLabel("Стабильность T: Ожидание...")
        self.stability_signal_label.setStyleSheet("padding: 5px; border: 1px solid grey;")
        self.stability_signal_label.setAlignment(Qt.AlignCenter)
        controls_grid_layout.addWidget(self.stability_signal_label, row, 0, 1, 2)
        row += 1
        self.reset_stability_signal_button = QPushButton("Сброс сигнала ΔT")
        self.reset_stability_signal_button.clicked.connect(lambda: self.reset_stability_signal())
        controls_grid_layout.addWidget(self.reset_stability_signal_button, row, 0, 1, 2)
        row += 1
        
        controls_grid_layout.addItem(QSpacerItem(20, 15, QSizePolicy.Minimum, QSizePolicy.Expanding), row, 0)
        row +=1

        # --- Settings Button ---
        self.settings_button = QPushButton("Настройки сигналов")
        self.settings_button.clicked.connect(self.open_settings_dialog)
        controls_grid_layout.addWidget(self.settings_button, row, 0, 1, 2)
        row += 1


        self.controls_layout.addLayout(controls_grid_layout)
        self.controls_layout.addStretch(1)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self, self.settings)
        # Store old settings for comparison
        old_t_signal_kub = self.settings.get("t_signal_kub")
        old_t_signal_deflegmator = self.settings.get("t_signal_deflegmator")
        old_delta_t = self.settings.get("delta_t")
        old_period_seconds = self.settings.get("period_seconds")

        if dialog.exec_() == QDialog.Accepted:
            self.settings = dialog.get_settings()
            log_msg = f"Settings updated: T_kub_sig={self.settings['t_signal_kub']}, T_def_sig={self.settings['t_signal_deflegmator']}, DeltaT={self.settings['delta_t']}, Period={self.settings['period_seconds']}s"
            logger.info(log_msg)
            self.update_status(log_msg) # update_status will also log this

            # Reset signals only if their relevant settings changed
            new_t_signal_kub = self.settings.get("t_signal_kub")
            new_t_signal_deflegmator = self.settings.get("t_signal_deflegmator")
            new_delta_t = self.settings.get("delta_t")
            new_period_seconds = self.settings.get("period_seconds")

            t_kub_setting_changed = (old_t_signal_kub != new_t_signal_kub)
            t_deflegmator_setting_changed = (old_t_signal_deflegmator != new_t_signal_deflegmator)
            stability_settings_changed = (old_delta_t != new_delta_t or
                                          old_period_seconds != new_period_seconds)

            if t_kub_setting_changed:
                logger.info(f"T_signal_kub setting changed from {old_t_signal_kub} to {new_t_signal_kub}. Resetting T kub signal.")
                self.reset_t_kub_signal(inform=False) # silent reset
            
            if t_deflegmator_setting_changed:
                logger.info(f"T_signal_deflegmator setting changed from {old_t_signal_deflegmator} to {new_t_signal_deflegmator}. Resetting T deflegmator signal.")
                self.reset_t_deflegmator_signal(inform=False) # silent reset
            
            if stability_settings_changed:
                logger.info(f"Stability settings changed (DeltaT: {old_delta_t}->{new_delta_t}, Period: {old_period_seconds}->{new_period_seconds}). Resetting stability signal.")
                self.reset_stability_signal(inform=False) # silent reset
            
            # Re-evaluate with new settings immediately if active,
            # or if signals were reset.
            self.check_signal_conditions()

    def publish_selected_work_mode(self):
        mode_code = self.work_mode_combobox.currentData()
        if mode_code is not None:
            self.publish_work_mode(mode_code)

    def publish_work_mode(self, mode_code):
        """Publishes the selected work mode."""
        try:
            mode_name = WORK_STATE_NAMES.get(mode_code, str(mode_code))
            logger.info(f"Requesting to set work mode: {mode_name} ({mode_code})")
            self.publishRequested.emit(control_topics["work"], str(mode_code))
            self.update_status(f"Запрос на установку режима: {mode_name} ({mode_code})")
        except Exception as e:
            logger.error(f"Error preparing work mode publication: {e}", exc_info=True)
            self.update_status(f"Ошибка подготовки публикации режима: {e}")

    def publish_otbor_g_1_speed(self):
        """Publishes the speed for 'otbor golov 1'."""
        try:
            speed_val = int(self.otbor_g_1_spinbox.value())
            logger.info(f"Requesting to set otbor golov speed (PWM): {speed_val}")
            self.publishRequested.emit(control_topics["otbor_g_1_new"], str(speed_val))
            self.update_status(f"Запрос на ШИМ отбора голов: {speed_val}")
        except Exception as e:
            logger.error(f"Error preparing otbor golov speed publication: {e}", exc_info=True)
            self.update_status(f"Ошибка подготовки ШИМ отбора голов: {e}")

    def publish_otbor_t_params(self):
        """Publishes parameters for 'otbor tela'."""
        try:
            t_stop = self.term_c_max_telo_spinbox.value()
            t_start = self.term_c_min_telo_spinbox.value()
            pwm_val = int(self.otbor_t_spinbox.value())

            if t_start >= t_stop:
                logger.warning(f"Invalid input for otbor tela params: T_start ({t_start}) >= T_stop ({t_stop}).")
                QMessageBox.warning(self, "Ошибка ввода", "T старт должна быть меньше T стоп.")
                return
            
            log_msg = f"Requesting otbor tela params: T_stop={t_stop}, T_start={t_start}, PWM={pwm_val}"
            logger.info(log_msg)
            self.publishRequested.emit(control_topics["term_c_max_new"], str(t_stop))
            self.publishRequested.emit(control_topics["term_c_min_new"], str(t_start))
            self.publishRequested.emit(control_topics["otbor_t_new"], str(pwm_val))
            self.update_status(f"Запрос параметров отбора тела: T_stop={t_stop}, T_start={t_start}, ШИМ={pwm_val}")
        except Exception as e:
            logger.error(f"Error preparing otbor tela params publication: {e}", exc_info=True)
            self.update_status(f"Ошибка подготовки параметров отбора тела: {e}")

    def configure_plots(self):
        """Sets up the static parts of the plots and creates line objects."""
        self.ax.clear() # Clear existing axes
        self.ax.set_title("Температуры")
        self.ax.set_ylabel("°C")
        self.ax.set_ylim(10, 110)
        
        self.base_line_labels = {
            "term_c": "T царга (term_c)",
            "term_k": "T куб (term_k)",
            "term_d": "T дефлегматор (term_d)",
        }

        self.lines["term_d"], = self.ax.plot([], [], label=self.base_line_labels["term_d"], marker='.', linestyle='-', color='tab:green')
        self.lines["term_c"], = self.ax.plot([], [], label=self.base_line_labels["term_c"], marker='.', linestyle='-', color='tab:blue')
        self.lines["term_k"], = self.ax.plot([], [], label=self.base_line_labels["term_k"], marker='.', linestyle='-', color='tab:red')
        self.ax.legend(loc='upper left', fontsize='small')

        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=10, maxticks=10))
        self.ax.tick_params(axis='x', rotation=30)
        
        self.figure.tight_layout(rect=[0, 0.03, 1, 0.95])

    def setup_mqtt(self):
        """Creates and starts the MQTT worker thread."""
        self.mqtt_thread = QThread()
        self.mqtt_worker = MqttWorker(
            self.secrets["broker"],
            self.secrets["port"],
            self.secrets["username"],
            self.secrets["password"],
            client_id,
            topics
        )
        self.mqtt_worker.moveToThread(self.mqtt_thread)

        # Connect signals and slots
        self.mqtt_thread.started.connect(self.mqtt_worker.run)
        self.mqtt_worker.messageReceived.connect(self.handle_message)
        self.mqtt_worker.connectionStatus.connect(self.update_status)
        # Connect the main window's publish request signal to the worker's slot
        # Note: This connection happens across threads, Qt handles it.
        self.publishRequested.connect(self.mqtt_worker.publish_message)

        # Ensure thread quits when finished or window closes
        self.mqtt_worker.finished.connect(self.mqtt_thread.quit)
        self.mqtt_worker.finished.connect(self.mqtt_worker.deleteLater)
        self.mqtt_thread.finished.connect(self.mqtt_thread.deleteLater)

        self.mqtt_thread.start()

    @pyqtSlot(str)
    def update_status(self, message):
        """Updates the status bar label."""
        logger.info(f"Status update: {message}") # Log status messages
        self.status_label.setText(message)

    @pyqtSlot(str, str)
    def handle_message(self, topic, payload_str):
        """Processes incoming MQTT messages."""
        self.last_mqtt_message_time = datetime.now() # Update time of last message
        if self.mqtt_data_timeout_alarm_active: # If "no data" alarm was active, reset its flag
            self.mqtt_data_timeout_alarm_active = False
            # The dialog itself will remain until dismissed by the user.
            # This flag prevents re-triggering the alarm logic.

        current_time = datetime.now()

        try:
            if topic in ["term_c", "term_k", "term_d"]:
                temp_value = float(payload_str)
                latest_values[topic] = temp_value
                if topic in data: # data is a global dictionary
                    data[topic].append(temp_value)
                    timestamps[topic].append(current_time)

                # --- CSV Logging for temperature topics ---
                try:
                    time_str = current_time.strftime('%Y-%m-%d %H:%M:%S') + '.' + str(current_time.microsecond // 1000).zfill(3)
                    values = [''] * len(CSV_DATA_TOPIC_ORDER)
                    idx = CSV_DATA_TOPIC_ORDER.index(topic)
                    values[idx] = str(temp_value)
                    log_line = f"{time_str};" + ";".join(values)
                    data_logger.info(log_line)
                except Exception as e:
                    logger.error(f"Failed to write data to CSV for topic {topic}: {e}", exc_info=True)
            
            else:
                # print(f"Warning: Received message for unexpected topic '{topic}'")
                logger.debug(f"Received message for unhandled topic '{topic}': '{payload_str}'")
                return # Exit if topic is not recognized

        except ValueError:
            logger.warning(f"Could not convert payload '{payload_str}' for topic '{topic}' to number.")
            return
        except Exception as e:
            logger.error(f"Error handling MQTT message topic='{topic}', payload='{payload_str}': {e}", exc_info=True)
            return

    def update_plots_and_signals(self):
        """Updates plots and checks signal conditions."""
        self.update_plots()
        self.check_signal_conditions()
        self.check_mqtt_data_timeout() # Add check for MQTT data timeout

    def update_plots(self):
        """Updates the Matplotlib plots with the latest data."""
        # --- Update Temperature Data and legend ---
        for key in ["term_c", "term_k", "term_d"]:
            if key in self.lines:
                if timestamps[key]:
                    self.lines[key].set_data(list(timestamps[key]), list(data[key])) # Ensure lists
                    self.lines[key].set_visible(True)
                else:
                    self.lines[key].set_data([], [])
                    self.lines[key].set_visible(False)
                
                # Update the label for the legend
                base_label = self.base_line_labels.get(key, key)
                value_str = f": {latest_values[key]:.2f}°C" if latest_values[key] is not None else ""
                self.lines[key].set_label(f"{base_label}{value_str}")

        self.ax.relim()

        # Only autoscale the x-axis if the user hasn't zoomed or panned.
        # User interaction with zoom/pan tools turns autoscaling off for that axis.
        # The 'Home' button on the toolbar will re-enable it, and this logic will
        # then take over again.
        if self.ax.get_autoscalex_on():
            self.ax.autoscale_view(scalex=True, scaley=False) # autoscale X, but not Y

            # Adjust x-axis limits based on the actual time range present in the data
            all_times = [t for topic_times in timestamps.values() for t in topic_times if topic_times] # Filter empty
            if all_times:
                min_time = min(all_times)
                max_time = max(all_times)
                # Add a small buffer to max_time if only one point, or if window is small
                if min_time == max_time:
                    max_time = min_time + timedelta(seconds=10) # Show a 10s window for single point

                self.ax.set_xlim(min_time, max_time)
                self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                self.ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=7)) # Fewer ticks
                self.ax.tick_params(axis='x', rotation=30)
            else: # No data yet, set a default view
                now = datetime.now()
                self.ax.set_xlim(now - timedelta(seconds=60), now)

            # set_xlim turns autoscale off, so we re-enable it to remember we are in auto mode.
            self.ax.set_autoscalex_on(True)

        self.ax.legend(loc='upper left')

        try:
            self.figure.tight_layout(rect=[0, 0.03, 1, 0.95])
            self.canvas.draw()
        except Exception as e:
            logger.error(f"Error drawing canvas: {e}", exc_info=True)

    def check_signal_conditions(self):
        """Checks the conditions and updates the signal labels."""
        logger.debug("Checking all signal conditions.")
        self.check_t_kub_signal()
        self.check_t_deflegmator_signal()
        self.check_temperature_stability_signal()

    def check_mqtt_data_timeout(self):
        """Checks if data has been received from MQTT recently."""
        if self.last_mqtt_message_time: # Ensure it's initialized
            time_since_last_message = (datetime.now() - self.last_mqtt_message_time).total_seconds()

            if time_since_last_message > MQTT_DATA_TIMEOUT_SECONDS and \
               not self.mqtt_data_timeout_alarm_active:
                # Check if MQTT worker is supposed to be running to avoid false alarms
                # e.g. during startup before connection or during shutdown.
                if self.mqtt_thread and self.mqtt_thread.isRunning(): # and self.mqtt_worker and self.mqtt_worker.client and self.mqtt_worker.client.is_connected(): # More precise check?
                    logger.warning(f"No MQTT data for {time_since_last_message:.0f} seconds. Triggering 'no data' alarm.")
                    self.alarm_message_with_sound(
                        f"Нет данных от устройства в течение {time_since_last_message / 60:.1f} мин., проверьте устройство или соединение"
                    )
                    self.mqtt_data_timeout_alarm_active = True # Set flag to prevent re-alarming immediately
                else:
                    logger.debug(f"MQTT data timeout check: MQTT thread not running or worker not fully connected. Suppressing alarm. Time since last msg: {time_since_last_message:.0f}s")

    def alarm_message_with_sound(self, message):
        """Displays a non-modal alarm message window and optionally plays a sound."""
        logger.warning(f"ВНИМАНИЕ: {message}") # Log to console (and file)

        # If an old alarm dialog exists, handle its sound and closure first.
        if self.current_alarm_dialog:
            # Stop its sound if it's playing (it uses the shared self.alarm_sound_effect)
            if self.alarm_sound_effect.isPlaying():
                self.alarm_sound_effect.stop()
            
            # Close and clean up the old dialog
            if self.current_alarm_dialog.isVisible():
                self.current_alarm_dialog.close() # This will trigger its closeEvent
            self.current_alarm_dialog.deleteLater()
            self.current_alarm_dialog = None # Clear the reference

        # Now, play sound for the new alarm (if requested and usable)
        if self.alarm_sound_effect.isLoaded() and self.alarm_sound_effect.source().isValid():
            self.alarm_sound_effect.setLoopCount(QSoundEffect.Infinite) # Loop indefinitely
            self.alarm_sound_effect.play()
        else:
            # Fallback to system beep if sound was requested but main effect is not ready/loaded
            QApplication.beep()
            if not (self.alarm_sound_effect.isLoaded() and self.alarm_sound_effect.source().isValid()):
                logger.warning("Alarm sound effect not loaded or source invalid, attempted system beep.")

        # Create and show the new notification window
        # Pass the main sound_effect instance; the dialog will handle stopping it on dismiss/close.
        self.current_alarm_dialog = AlarmNotificationDialog(message, self.alarm_sound_effect, self)
        self.current_alarm_dialog.show()

    def _check_temperature_signal(
            self,
            topic_key,
            setting_key,
            monitoring_active_attr,
            triggered_attr,
            label_attr,
            reset_func,
            name_for_log,
            name_for_ui,
            short_name_for_ui
        ):
        temp_value = latest_values.get(topic_key)
        threshold = self.settings[setting_key]
        monitoring_active = getattr(self, monitoring_active_attr)
        label_widget = getattr(self, label_attr)
        
        logger.debug(f"Checking {name_for_log} signal: {topic_key}={temp_value}, threshold={threshold}, monitoring_active={monitoring_active}")

        if monitoring_active:
            logger.debug(f"{name_for_log} signal monitoring is active.")
            if temp_value is not None:
                logger.debug(f"{topic_key} is {temp_value}.")
                if temp_value >= threshold:
                    logger.info(f"{name_for_log} signal TRIGGERED: {topic_key} ({temp_value}) >= threshold ({threshold})")
                    setattr(self, triggered_attr, True)
                    setattr(self, monitoring_active_attr, False)
                    message = f"ВНИМАНИЕ: {name_for_ui} ({temp_value:.1f}°C) ≥ {threshold:.1f}°C"
                    style_sheet = STYLE_ALARM_TRIGGERED
                    self.alarm_message_with_sound(message)
                else:
                    logger.debug(f"{name_for_log} signal: Monitoring, condition not met ({topic_key} {temp_value} < threshold {threshold}).")
                    message = f"Мониторинг ({short_name_for_ui} {temp_value:.1f}°C, порог {threshold:.1f}°C)"
                    style_sheet = STYLE_MONITORING
            else:
                logger.debug(f"{name_for_log} signal: Waiting for {topic_key} data.")
                message = f"{name_for_ui}: Ожидание данных (порог {threshold:.1f}°C)"
                style_sheet = STYLE_MONITORING
        
        else: # Monitoring not active
            if temp_value is not None and temp_value < threshold:
                logger.info(f"{name_for_log} below threshold while monitoring off, resetting signal.")
                reset_func() # This will re-evaluate and update the UI.
                self.reset_stability_signal()
                return # Exit to avoid overwriting the UI with stale data from this run.

            logger.debug(f"{name_for_log} signal monitoring is NOT active.")
            message = f"{name_for_ui}: Мониторинг отключен"
            style_sheet = STYLE_INACTIVE

        label_widget.setText(message)
        label_widget.setStyleSheet(style_sheet)

    def check_t_kub_signal(self):
        """Checks the T kub signal condition and updates its label."""
        self._check_temperature_signal(
            topic_key="term_k",
            setting_key="t_signal_kub",
            monitoring_active_attr="t_kub_signal_monitoring_active",
            triggered_attr="t_kub_signal_triggered",
            label_attr="t_kub_signal_label",
            reset_func=self.reset_t_kub_signal,
            name_for_log="T_kub",
            name_for_ui="T куба",
            short_name_for_ui="T куба",
        )

    def check_t_deflegmator_signal(self):
        """Checks the T deflegmator signal condition and updates its label."""
        self._check_temperature_signal(
            topic_key="term_d",
            setting_key="t_signal_deflegmator",
            monitoring_active_attr="t_deflegmator_signal_monitoring_active",
            triggered_attr="t_deflegmator_signal_triggered",
            label_attr="t_deflegmator_signal_label",
            reset_func=self.reset_t_deflegmator_signal,
            name_for_log="T_deflegmator",
            name_for_ui="T дефлегматора",
            short_name_for_ui="T дефл.",
        )

    def check_temperature_stability_signal(self):
        """Checks the temperature stability signal condition and updates its label."""
        term_k = latest_values.get("term_k")
        term_c = latest_values.get("term_c")
        delta_t_threshold = self.settings["delta_t"]
        period_seconds_threshold = self.settings["period_seconds"]
        TERM_K_70 = 70.0
        logger.debug(f"Checking stability signal: term_k={term_k}, term_c={term_c}, delta_thresh={delta_t_threshold}, period_thresh={period_seconds_threshold}s, monitoring_active={self.stability_signal_monitoring_active}")

        if self.stability_signal_monitoring_active: # Signal is armed and monitoring
            logger.debug("Stability signal monitoring is active.")
            if term_k is not None and term_c is not None:
                delta = abs(term_k - term_c)
                logger.debug(f"Stability signal: term_k={term_k}, term_c={term_c}, calculated_delta={delta:.2f}")

                is_stable_condition = (delta < delta_t_threshold) and (term_k > TERM_K_70)

                if is_stable_condition: # Stability condition met
                    logger.debug(f"Stability signal: Condition met (delta {delta:.2f} < threshold {delta_t_threshold:.2f} AND T_kub {term_k} > {TERM_K_70}).")
                    if self.stability_condition_met_since is None:
                        logger.info("Stability signal: Condition met for the first time, starting timer.")
                        self.stability_condition_met_since = datetime.now()
                    elapsed_seconds = (datetime.now() - self.stability_condition_met_since).total_seconds()
                    logger.debug(f"Stability signal: Time elapsed since condition met: {elapsed_seconds:.0f}s.")
                    if elapsed_seconds >= period_seconds_threshold: # Time condition also met - stability achieved
                        logger.info(f"Stability signal TRIGGERED: Stable for {elapsed_seconds:.0f}s (>= {period_seconds_threshold}s).")
                        self.stability_signal_triggered = True
                        self.stability_signal_monitoring_active = False  # Deactivate after achieving (one-shot)
                        message = f"ВНИМАНИЕ: СТАБИЛЬНО: ΔT ({delta:.2f}°C) < {delta_t_threshold:.2f}°C и Tк > {TERM_K_70:.0f}°C в течение {elapsed_seconds:.0f}с"
                        style_sheet = STYLE_ALARM_TRIGGERED
                        self.alarm_message_with_sound(message)
                    else: # Stability condition met, timer running
                        logger.debug("Stability signal: Condition met, timer running.")
                        message = f"Стабильно: ΔT ({delta:.2f}°C) < {delta_t_threshold:.2f}°C и Tк > {TERM_K_70:.0f}°C в течение {elapsed_seconds:.0f}с"
                        style_sheet = STYLE_MONITORING
                else:  # Stability condition NOT met, reset timer
                    if self.stability_condition_met_since is not None: # Log only if timer was running
                        logger.info("Stability signal: Condition no longer met, resetting timer.")
                    self.stability_condition_met_since = None

                    if term_k <= TERM_K_70:
                        message = f"ΔT: Мониторинг (Tк={term_k:.1f}°C ≤ {TERM_K_70:.0f}°C)"
                    else: # delta condition failed
                        message = f"ΔT: Мониторинг (ΔT={delta:.2f}°C, порог ΔT < {delta_t_threshold:.2f}°C)"
                    style_sheet = STYLE_MONITORING
            else:  # Not enough data (term_k or term_c is None)
                logger.debug("Stability signal: Waiting for term_k and/or term_c data.")
                if self.stability_condition_met_since is not None: # Log only if timer was running
                    logger.info("Stability signal: Data became unavailable, resetting timer.")
                self.stability_condition_met_since = None # Reset timer if data becomes unavailable
                message = "ΔT: Ожидание данных Tк/Tц..."
                style_sheet = STYLE_MONITORING # Still monitoring, just waiting for data
        else:
            logger.debug("Stability signal monitoring is NOT active.")
            message = f"ΔT: Мониторинг отключен"
            style_sheet = STYLE_INACTIVE

        self.stability_signal_label.setText(message)
        self.stability_signal_label.setStyleSheet(style_sheet)

    def reset_t_kub_signal(self, inform=True):
        self.t_kub_signal_monitoring_active = True
        self.t_kub_signal_triggered = False
        log_msg = "Сигнал T куба сброшен и активирован."
        logger.info(log_msg)
        if inform: self.update_status(log_msg)
        self.check_signal_conditions() # Re-evaluate immediately

    def reset_t_deflegmator_signal(self, inform=True):
        self.t_deflegmator_signal_monitoring_active = True
        self.t_deflegmator_signal_triggered = False
        log_msg = "Сигнал T дефлегматора сброшен и активирован."
        logger.info(log_msg)
        if inform: self.update_status(log_msg)
        self.check_signal_conditions() # Re-evaluate immediately

    def reset_stability_signal(self, inform=True):
        self.stability_signal_monitoring_active = True
        self.stability_signal_triggered = False
        self.stability_condition_met_since = None
        log_msg = "Сигнал стабильности температур сброшен и активирован."
        logger.info(log_msg)
        if inform: self.update_status(log_msg)
        self.check_signal_conditions() # Re-evaluate immediately

    def perform_graceful_shutdown(self):
        """Handles the MQTT and thread cleanup."""
        logger.info("Performing graceful shutdown...")
        if self.mqtt_thread and self.mqtt_thread.isRunning():
            logger.info("Stopping MQTT worker...")
            if self.mqtt_worker and self.mqtt_worker.client: # Added check for self.mqtt_worker
                logger.info("Stopping Paho loop...")
                self.mqtt_worker.client.loop_stop() # Wait for Paho's internal thread to stop
                if self.mqtt_worker.client.is_connected():
                    logger.info("Disconnecting MQTT client...")
                    self.mqtt_worker.client.disconnect() # Wait for disconnect to complete

            logger.info("Quitting MQTT QThread...")
            self.mqtt_thread.quit()
            if not self.mqtt_thread.wait(5000): # Increased timeout slightly
                logger.warning("MQTT thread did not stop gracefully. Terminating.")
                self.mqtt_thread.terminate()
            else:
                logger.info("MQTT thread stopped.")
        else:
            logger.info("MQTT thread not running or already stopped.")

    def closeEvent(self, event):
        """Ensure MQTT thread and Paho loop are stopped cleanly on window close."""
        logger.info("closeEvent triggered. Initiating shutdown.")
        self.perform_graceful_shutdown()
        event.accept()


class CsvRotatingFileHandler(RotatingFileHandler):
    """
    A RotatingFileHandler that writes a header to new files.
    """
    def __init__(self, filename, *args, header=None, **kwargs):
        self.header = header
        # We need to determine if the header needs to be written BEFORE the file is opened for appending.
        # The base class opens the file in its __init__.
        # So, we check for file existence and size here.
        write_header = not os.path.exists(filename) or os.path.getsize(filename) == 0

        super().__init__(filename, *args, **kwargs)

        if write_header and self.header:
            self.stream.write(self.header + '\n')
            self.stream.flush()

    def doRollover(self):
        super().doRollover()
        # After rollover, the new file (self.baseFilename) is empty.
        # The stream has been reopened by the base class.
        if self.header:
            self.stream.write(self.header + '\n')
            self.stream.flush()


def setup_data_logging():
    """Sets up a separate logger for CSV data."""
    data_logger.setLevel(logging.INFO)

    log_dir = os.path.join(APP_ROOT_DIR, "log")
    log_file = os.path.join(log_dir, "alco_esp_data.csv")
    csv_header = "Время;" + ";".join([CSV_DATA_HEADERS[topic] for topic in CSV_DATA_TOPIC_ORDER])

    # Use our custom handler to manage the header
    file_handler = CsvRotatingFileHandler(
        log_file,
        mode='a',
        maxBytes=100 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8-sig',
        header=csv_header
    )

    # Formatter that just passes the message through, as we format it ourselves.
    formatter = logging.Formatter('%(message)s')
    file_handler.setFormatter(formatter)

    data_logger.addHandler(file_handler)

    # Prevent data logs from propagating to the root logger (and thus the console)
    data_logger.propagate = False
    logger.info("Data logging to CSV setup complete.")


def setup_logging():
    logger.setLevel(logging.DEBUG)  # Set the logging level for the logger

    # --- Define log directory and file path ---
    # Log directory is APP_ROOT_DIR/log
    log_dir = os.path.join(APP_ROOT_DIR, "log")
    log_dir_error = None
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except OSError as e:
            log_dir_error = f"CRITICAL ERROR: Could not create log directory {log_dir}: {e}"
            logger.error(log_dir_error)
            log_dir = APP_ROOT_DIR

    log_file = os.path.join(log_dir, "alco_esp_monitor.log")
    # Rotate log file when it reaches 100MB, keep 5 backup logs
    file_handler = RotatingFileHandler(log_file, maxBytes=100 * 1024 * 1024, backupCount=5, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)  # Log everything to file

    # Create a console handler for higher level messages
    console_handler = logging.StreamHandler(sys.stdout) # Explicitly use sys.stdout for the console
    console_handler.setLevel(logging.INFO)  # Show INFO and above on console

    # Create a formatter and set it for both handlers
    # Added module, funcName, and lineno for more detailed logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("Logging setup complete.")
    if log_dir_error:
        logger.error(log_dir_error)


if __name__ == '__main__':
    # --- Global Logger Setup ---
    logger = logging.getLogger("AlcoEspMonitorApp")
    data_logger = logging.getLogger("AlcoEspDataLogger")
    setup_logging() # Call setup_logging here
    setup_data_logging()
    logger.info("Application starting...")

    app = QApplication(sys.argv)
    secrets = load_secrets_with_gui_feedback()
    main_window = AlcoEspMonitor(secrets)

    # --- Graceful shutdown on Ctrl+C ---
    def sigint_handler(*args):
        """Handler for the SIGINT signal."""
        logger.info("Ctrl+C (SIGINT) pressed. Shutting down...")
        # It's important that main_window still exists.
        if main_window:
            main_window.perform_graceful_shutdown()
        
        # Ensure Qt application exits
        # QApplication.quit() might be better if the event loop is still running
        instance = QApplication.instance()
        if instance:
            instance.quit()

    signal.signal(signal.SIGINT, sigint_handler)
    # --- End graceful shutdown ---

    logger.info("Showing main window.")
    main_window.showMaximized()
    exit_code = app.exec_()
    logger.info(f"Application event loop finished. Exiting with code {exit_code}.")
    # perform_graceful_shutdown is called by closeEvent, so not strictly needed here again
    # unless app.exec_() returns due to other reasons before closeEvent.
    # However, sigint_handler should cover Ctrl+C.
    sys.exit(exit_code)
