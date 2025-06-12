from enum import Enum

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
