import paho.mqtt.client as mqtt
import time
import random
from datetime import datetime
import json
import os
import sys

from alco_esp.constants import WorkState, WORK_STATE_NAMES


# --- Secrets Management ---
APP_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SECRETS_FILE_PATH = os.path.join(APP_ROOT_DIR, "secrets.json")

def load_secrets():
    """Loads secrets from secrets.json and exits on error."""
    if not os.path.exists(SECRETS_FILE_PATH):
        print(f"CRITICAL: Secrets file not found: {SECRETS_FILE_PATH}")
        print("Please copy 'secrets_template.json' to 'secrets.json' and fill in your credentials.")
        sys.exit(1)

    try:
        with open(SECRETS_FILE_PATH, 'r', encoding='utf-8') as f:
            secrets = json.load(f)

        required_keys = ["broker", "port", "username", "password"]
        if not all(key in secrets for key in required_keys):
            missing_keys = [key for key in required_keys if key not in secrets]
            print(f"CRITICAL: Secrets file {SECRETS_FILE_PATH} is missing required keys: {', '.join(missing_keys)}")
            sys.exit(1)

        print("Successfully loaded secrets from secrets.json.")
        return secrets

    except json.JSONDecodeError as e:
        print(f"CRITICAL: Error decoding {SECRETS_FILE_PATH}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"CRITICAL: An unexpected error occurred while loading secrets: {e}")
        sys.exit(1)

# Load secrets at startup
secrets = load_secrets()
broker = secrets["broker"]
port = secrets["port"]
username = secrets["username"]
password = secrets["password"]


client_id = "python_device_simulator"
topic_prefix = f"{username}/"


# Начальные значения параметров устройства
device_state = {
    # Read-Only Status
    "term_c": 58.0,        # Температура в царге
    "term_k": 59.0,        # Температура в кубе
    "term_d": 58.5,        # Температура в дефлегматоре
    "power": 0.0,          # Измеренная мощность
    "press_a": 760.0,      # Атмосферное давление
    "flag_otb": WORK_STATE_NAMES[WorkState.STOP.value], # Режим работы (публикуемый)
    "term_v": 0.0,
    "term_vent": 30.0,
    "count_vent": 0,
    "num_error": 0,

    # Commandable States (Read part)
    "term_c_max": 78.8,    # Температура старт-стопа (для отбора тела)
    "term_c_min": 78.2,    # Температура возобновления отбора (для отбора тела)
    "otbor_g_1": 15,       # ШИМ отбора для голов покапельно
    "otbor_t": 35,         # ШИМ отбора для тела
    "term_d_m": 95.0,      # Аварийная температура в дефлегматоре
    "press_c_m": 800.0,    # Аварийное давление в кубе
    "term_k_m": 100.0,     # Максимальная температура в кубе
    "term_nasos": 50.0,    # Температура включения клапана на воду
    "power_m": 2000.0,     # Стабилизируемая мощность
    "otbor": 0,            # ШИМ отбора (текущий)
    "time_stop": 300,      # Максимальное время старт-стопа
    "otbor_minus": 1,      # Декремент отбора тела
    "min_otb": 60,         # Период при отборе голов
    "sek_otb": 2,          # Время открытого клапана при отборе голов
    "otbor_g_2": 10,       # ШИМ отбора для подголовников
    "delta_t": 0.5,        # Разница температуры для старт-стопа

    # Internal state, not published
    "work": WorkState.STOP.value
}


# Функция при подключении к брокеру
def on_connect(client, userdata, flags, rc):
    print(f"on_connect: Подключено с кодом результата {rc}")
    
    # Подписываемся на топики для получения команд
    client.subscribe(topic_prefix + "work")
    client.subscribe(f"{topic_prefix}term_k_r") # For setting razgon stop temp

    # Subscribe to all commandable topics (_new suffix)
    commandable_topics = [
        "term_d_m", "press_c_m", "term_c_max", "term_c_min", "term_k_m",
        "term_nasos", "power_m", "otbor", "time_stop", "otbor_minus",
        "min_otb", "sek_otb", "otbor_g_1", "otbor_g_2", "otbor_t", "delta_t"
    ]
    for topic in commandable_topics:
        client.subscribe(f"{topic_prefix}{topic}_new")


# Функция при получении сообщения
def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode()
    # print(f"on_message: Получено сообщение: {topic} = {payload}")

    relative_topic = topic.replace(topic_prefix, "")
    
    # Обрабатываем команды
    if relative_topic == "work":
        try:
            requested_work_mode = int(payload)
            # Only process if the requested mode is different from the current mode
            if device_state["work"] != requested_work_mode:
                print(f"on_message: Получена команда ИЗМЕНИТЬ режим работы на: {requested_work_mode}")
                device_state["work"] = requested_work_mode
                device_state["flag_otb"] = WORK_STATE_NAMES.get(requested_work_mode, f"Unknown({requested_work_mode})") # Sync flag_otb
                print(f"on_message: Режим работы изменен на: {device_state['work']}, Флаг отбора: '{device_state['flag_otb']}'")
            else:
                # Message received, but it matches the current state. Ignore it (or log for debugging).
                # print(f"on_message: Режим работы уже {requested_work_mode}. Команда проигнорирована.")
                pass # Do nothing if the mode is already set

        except ValueError:
            print(f"on_message: Некорректное значение для режима работы ({relative_topic}): {payload}")
    
    elif relative_topic == "term_k_r":
        try:
            temp_stop_razgon = float(payload)
            print(f"on_message: Получена команда (term_k_r) установить term_k_m на: {temp_stop_razgon}")
            device_state["term_k_m"] = temp_stop_razgon
            print(f"on_message: Параметр term_k_m обновлен на {device_state['term_k_m']}")
        except ValueError:
            print(f"on_message: Некорректное значение для term_k_r: {payload}")
    
    elif relative_topic.endswith("_new"):
        # Извлекаем базовый топик из имени с _new
        base_topic = relative_topic.replace("_new", "")
        
        try:
            # Обновляем соответствующее значение
            if base_topic in device_state:
                 requested_value = float(payload)
                 # --- State Comparison Logic (Optional but good practice) ---
                 if device_state[base_topic] != requested_value:
                     print(f"on_message: Получена команда ИЗМЕНИТЬ {base_topic} на: {requested_value}")
                     device_state[base_topic] = requested_value
                     print(f"on_message: Параметр {base_topic} обновлен на {device_state[base_topic]}")
                     # Optionally, immediately publish the updated status
                     # client.publish(topic_prefix + base_topic, str(device_state[base_topic]))
                 else:
                     # print(f"on_message: Параметр {base_topic} уже установлен на: {requested_value}. Команда проигнорирована.")
                     pass # Do nothing if the value is already set
            else:
                print(f"on_message: Неизвестный параметр для обновления: {base_topic}")

        except ValueError:
            print(f"on_message: Некорректное значение для {base_topic}: {payload}")
    
    else:
        print(f"on_message: Неизвестная команда или необрабатываемый топик: {relative_topic}")


# Функция для имитации изменения параметров устройства
def simulate_device_changes():
    current_work_mode = device_state["work"]

    # --- Simulate dynamic parameters based on work mode ---
    
    # Simulate power
    if current_work_mode == WorkState.RAZGON.value:
        device_state["power"] = device_state["power_m"] + random.uniform(-50, 50)
    elif current_work_mode == WorkState.OTBOR_TELA.value or current_work_mode == WorkState.OTBOR_GOLOV_POKAPELNO.value:
        device_state["power"] = device_state["power_m"] * 0.9 + random.uniform(-50, 50)
    else:  # STOP, etc.
        device_state["power"] = 0.0
    device_state["power"] = max(0, device_state["power"])
    
    # Simulate atmospheric pressure
    device_state["press_a"] += random.uniform(-0.1, 0.1)

    # Update 'otbor' based on current work mode
    if current_work_mode == WorkState.OTBOR_GOLOV_POKAPELNO.value:
        device_state["otbor"] = device_state["otbor_g_1"]
    elif current_work_mode == WorkState.OTBOR_TELA.value:
        device_state["otbor"] = device_state["otbor_t"]
    else:
        device_state["otbor"] = 0

    # --- Existing simulation logic for temperatures ---
    
    # Имитация изменения term_k (температура в кубе)
    if current_work_mode == WorkState.RAZGON.value:
        term_k_change = random.uniform(2.0, 5.0)  # Быстрый нагрев
    elif current_work_mode == WorkState.OTBOR_TELA.value or current_work_mode == WorkState.OTBOR_GOLOV_POKAPELNO.value:
        # Медленный нагрев, поддержание температуры или небольшой рост
        if device_state["term_k"] < 98: # Пока не достигли пика кипения
            term_k_change = random.uniform(0.05, 0.3)
        else:
            term_k_change = random.uniform(-0.05, 0.05) # Стабилизация у пика
    elif current_work_mode == WorkState.STOP.value or current_work_mode == WorkState.OTBOR_VYKLUCHEN.value:
        # Медленное остывание или стабильно
        term_k_change = random.uniform(-0.2, 0.05)
    else:  # Другие режимы или по умолчанию
        term_k_change = random.uniform(-0.1, 0.1)  # Небольшие колебания

    device_state["term_k"] += term_k_change
    # Ограничиваем term_k разумными пределами
    device_state["term_k"] = max(20.0, min(device_state["term_k"], 102.0)) # Мин. темп., макс. темп. кипения

    # ============
    # Имитация изменения term_c (температура в царге)
    # term_c обычно следует за term_k, но ниже и может быть более стабильной при отборе.

    if current_work_mode == WorkState.RAZGON.value:  # Разгон
        # term_c растет, следуя за term_k, но обычно ниже
        term_c_change = (device_state["term_k"] - device_state["term_c"]) * 0.9
            
    elif current_work_mode == WorkState.OTBOR_GOLOV_POKAPELNO.value:  # Отбор голов
        # Стремится к стабилизации в районе температур отбора голов (например, 65-78°C)
        # Это упрощенная модель; реально зависит от term_k.
        if device_state["term_k"] > 65:  # Только если куб достаточно нагрет
            if device_state["term_c"] < 70: # Условная нижняя граница для голов
                term_c_change = random.uniform(0.1, 0.4)
            elif device_state["term_c"] > 78: # Условная верхняя граница для голов
                term_c_change = random.uniform(-0.3, -0.1)
            else:
                term_c_change = random.uniform(-0.1, 0.1)  # Колебания
        else:
            # Медленно нагревается, если куб еще не горячий
            if device_state["term_k"] > device_state["term_c"] + 1:
                 term_c_change = random.uniform(0.1, 0.3)
            else:
                 term_c_change = random.uniform(-0.05, 0.05)
            
    elif current_work_mode == WorkState.OTBOR_TELA.value:  # Отбор тела
        # Должна колебаться в районе term_c_min / term_c_max, если куб достаточно нагрет
        if device_state["term_k"] > 78:  # Куб должен быть достаточно горячим для отбора тела
            if device_state["term_c"] < device_state["term_c_min"] - 0.2: # Если ниже term_c_min, может расти
                term_c_change = random.uniform(0.05, 0.2)
            elif device_state["term_c"] > device_state["term_c_max"] + 0.2: # Если выше term_c_max, может "остывать"
                term_c_change = random.uniform(-0.2, -0.05)
            else: # В "рабочей зоне" или приближается к границам
                term_c_change = random.uniform(-0.05, 0.05) # Очень стабильно / небольшой дрейф
        else:
            # Если куб не достаточно горяч для тела, term_c может просто следовать общему нагреву
            if device_state["term_k"] > device_state["term_c"] + 1:
                term_c_change = random.uniform(0.1, 0.3)
            else:
                term_c_change = random.uniform(-0.05, 0.05)

    elif current_work_mode == WorkState.STOP.value or current_work_mode == WorkState.OTBOR_VYKLUCHEN.value:
        # Медленное остывание или стабильно, может медленно падать, если term_k падает
        if device_state["term_k"] < device_state["term_c"] - 1 and device_state["term_c"] > 18:
            term_c_change = random.uniform(-0.15, -0.05)
        else:
            term_c_change = random.uniform(-0.1, 0.05)
    else:  # Другие режимы или по умолчанию
        term_c_change = random.uniform(-0.1, 0.1)

    device_state["term_c"] += term_c_change

    # ============
    # Имитация изменения term_d (температура в дефлегматоре)
    # term_d обычно немного ниже term_c, так как дефлегматор охлаждает пар для создания флегмы.

    if current_work_mode == WorkState.RAZGON.value:
        # term_d растет, следуя за term_c, но с небольшим отставанием
        if device_state["term_c"] > device_state["term_d"]:
            term_d_change = (device_state["term_c"] - device_state["term_d"]) * 0.8
        else: # Если вдруг обогнала, колеблется
            term_d_change = random.uniform(-0.1, 0.1)

    elif current_work_mode == WorkState.OTBOR_GOLOV_POKAPELNO.value or current_work_mode == WorkState.OTBOR_TELA.value:
        # При отборе дефлегматор активно поддерживает температуру для стабильного возврата флегмы.
        # Она должна быть очень стабильной и чуть ниже царги.
        target_d_temp = device_state["term_c"] - random.uniform(0.3, 0.8) # Цель - немного холоднее царги
        # Медленно движется к цели
        diff = target_d_temp - device_state["term_d"]
        term_d_change = diff * 0.4 # Плавное приближение + колебания

    elif current_work_mode == WorkState.STOP.value or current_work_mode == WorkState.OTBOR_VYKLUCHEN.value:
        # Медленное остывание вместе с царгой
        if device_state["term_c"] < device_state["term_d"] - 0.5 and device_state["term_d"] > 18:
            term_d_change = random.uniform(-0.15, -0.05)
        else:
            term_d_change = random.uniform(-0.1, 0.05)
            
    else: # Другие режимы
        term_d_change = random.uniform(-0.1, 0.1)

    device_state["term_d"] += term_d_change


# Создаем клиент
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id)
client.username_pw_set(username, password)
client.on_connect = on_connect
client.on_message = on_message

# Подключаемся к брокеру
client.connect(broker, port, 60)

# Запускаем цикл обработки сетевого трафика в фоне
client.loop_start()

try:
    print("Симулятор устройства запущен. Нажмите Ctrl+C для остановки.")
    
    while True:
        # Имитируем изменения в устройстве
        simulate_device_changes()
        
        # Публикуем текущие значения (статус)
        current_time = datetime.now().strftime('%H:%M:%S')
        # Optional: Reduce noise by printing publish summary less often or conditionally
        # print(f"[{current_time}] Публикация данных:") 
        for key, value in device_state.items():
            if key == "work":
                continue # Do not publish internal 'work' state
            topic_to_publish = topic_prefix + key # Status topics remain the same
            client.publish(topic_to_publish, str(value))
            # Optional: Add print statement to see what's being published
            # print(f"  -> {topic_to_publish}: {value}")

        # Ждем 10 секунд перед следующей публикацией
        time.sleep(10)

except KeyboardInterrupt:
    print("Симулятор остановлен")

finally:
    # Останавливаем цикл и отключаемся
    client.loop_stop()
    client.disconnect()


