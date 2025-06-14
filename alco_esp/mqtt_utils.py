from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from paho.mqtt import client as mqtt

from alco_esp.logging import logger


class MqttWorker(QObject):
    """
    Handles MQTT communication in a separate thread.
    """
    messageReceived = pyqtSignal(str, str) # topic, payload
    connectionStatus = pyqtSignal(str)    # status message
    finished = pyqtSignal()               # Signal emitted when the worker is done

    def __init__(self, broker, port, username, password):  #, topics_to_subscribe):
        super().__init__()
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.client_id = "python_qt_client_viewer"
        # self.topics_to_subscribe = topics_to_subscribe
        self.topic_prefix = f"{username}/"
        self.client = None

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log_msg = f"Подключено к MQTT брокеру: {self.broker}"
            logger.info(log_msg)
            self.connectionStatus.emit(log_msg)

            # Subscribe to the wildcard topic to get all messages from the device.
            # The handle_message function will then filter for topics of interest.
            # Subscribing to individual topics in addition to the wildcard caused duplicate message delivery.
            wildcard_topic = f"{self.topic_prefix}#"
            client.subscribe(wildcard_topic, qos=0)
            logger.info(f"Subscribed to wildcard topic to receive all device data: {wildcard_topic}")

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
