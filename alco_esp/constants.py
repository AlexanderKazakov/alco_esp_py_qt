import os
from enum import Enum

# Path to the directory of the script or to the Pyinstaller executable directory
# to get the resources and to write logs to
APP_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

class WorkState(Enum):
    STOP = 0
    START = 1
    RESTART = 2
    SBROS_OTOBRAJENIYA = 3
    RAZGON = 4
    VYKLUCHENIE_RAZGONA = 5
    OTBOR_VYKLUCHEN = 6
    OTBOR_GOLOV_PERIODIKOY = 7
    OTBOR_TELA = 8
    OTBOR_GOLOV_POKAPELNO = 9
    OTBOR_PODGOLOVNIKOV = 10

WORK_STATE_NAMES = {
    WorkState.STOP.value: "стоп",
    WorkState.START.value: "старт",
    WorkState.RESTART.value: "рестарт",
    WorkState.SBROS_OTOBRAJENIYA.value: "сброс отображения",
    WorkState.RAZGON.value: "разгон",
    WorkState.VYKLUCHENIE_RAZGONA.value: "выключение разгона",
    WorkState.OTBOR_VYKLUCHEN.value: "отбор выключен",
    WorkState.OTBOR_GOLOV_PERIODIKOY.value: "отбор голов периодикой",
    WorkState.OTBOR_TELA.value: "отбор тела",
    WorkState.OTBOR_GOLOV_POKAPELNO.value: "отбор голов покапельно",
    WorkState.OTBOR_PODGOLOVNIKOV.value: "отбор подголовников"
}

CHART_TEMPERATURE_TOPICS = ["term_d", "term_c", "term_k"]

TOPICS_OF_MAIN_INTEREST = CHART_TEMPERATURE_TOPICS + ["power", "press_a", "flag_otb"]

CSV_DATA_TOPIC_ORDER = CHART_TEMPERATURE_TOPICS + ["power", "press_a", "flag_otb"]

CSV_DATA_HEADERS = {
    "term_d": "T дефлегматор",
    "term_c": "T царга",
    "term_k": "T куб",
    "power": "Мощность",
    "press_a": "Атм. давление",
    "flag_otb": "Флаг отбора"
}

# --- Signal Style Definitions ---
STYLE_ALARM_TRIGGERED = "background-color: orangered; color: white; padding: 5px; border: 1px solid grey;"
STYLE_MONITORING = "background-color: lightblue; padding: 5px; border: 1px solid grey;"
STYLE_INACTIVE = "background-color: lightgray; padding: 5px; border: 1px solid grey;"
