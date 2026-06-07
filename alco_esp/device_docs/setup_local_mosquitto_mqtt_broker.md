# Mosquitto / Alco ESP: локальный MQTT-брокер в домашней WLAN

**Назначение:** локальный MQTT-брокер Mosquitto работает на том же Windows 10, что и Alco ESP Client. То есть интернет не нужен, всё работает в пределах домашней Wi-Fi/LAN сети. Дополнительные устройства тоже не нужны - программа и MQTT-сервер работают на одном компьютере.

---

## 1. Известная рабочая конфигурация


| Параметр                               | Значение                                                          |
| -------------------------------------- | ----------------------------------------------------------------- |
| MQTT-брокер                            | Eclipse Mosquitto                                                 |
| Проверенная версия                     | 2.1.2                                                             |
| Компьютер-брокер                       | Windows 10                                                        |
| Папка установки Mosquitto              | `C:\Program Files\Mosquitto`                                      |
| IP ноутбука в домашней WLAN            | `192.168.1.84`                                                    |
| MQTT-порт                              | `1883`                                                            |
| TLS / SSL                              | выключен                                                          |
| MQTT username                          | пусто                                                             |
| MQTT password                          | пусто                                                             |
| Anonymous access в Mosquitto           | включён: `allow_anonymous true`                                   |
| Домашняя Wi-Fi сеть / SSID             | `MTSRouter-135F89` (имя wifi сети)                                |
| Пароль домашней Wi-Fi сети             | `<HOME_WIFI_PASSWORD>`                                            |
| Точка доступа устройства               | `ALCO_ESP`                                                        |
| Страница настройки устройства          | `http://192.168.4.1` - следить, чтобы браузер не подставил https! |
| Префикс MQTT-топиков на Alco ESP       | `/`                                                               |
| Файл настроек MQTT для Windows-клиента | `secrets.json` рядом с `secrets_template.json`                    |


**Важно про IP `192.168.1.84`:** это адрес ноутбука во время рабочей настройки. Он может измениться, если роутер выдаст другой DHCP-адрес. Если IP изменился, нужно обновить:

1. настройку MQTT broker на Alco ESP
2. файл `secrets.json` в Windows desktop-клиенте

---

## 2. Что к чему подключено


| Компонент              | Роль                                                     | Подключение                                                                  |
| ---------------------- | -------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Windows 10 ноутбук     | Запускает Mosquitto broker и Windows desktop MQTT client | Подключён к домашней Wi-Fi сети `MTSRouter-135F89`                           |
| Mosquitto broker       | Локальный MQTT-брокер                                    | Слушает `192.168.1.84:1883`                                                  |
| Alco ESP / автоматика  | Wi-Fi устройство, которое публикует/читает MQTT-топики   | Подключается к домашней Wi-Fi сети и затем к MQTT broker `192.168.1.84:1883` |
| Windows desktop client | Локальное приложение-клиент MQTT                         | Использует `secrets.json` с `broker=192.168.1.84`, `port=1883`               |


Брокер предназначен только для локальной домашней сети. **Не пробрасывать порт `1883` наружу через роутер.**

Устройство и ноутбук должны быть в одной домашней Wi-Fi/LAN сети, не в гостевой сети с изоляцией клиентов.

---

## 3. Установка Mosquitto на Windows 10

1. Скачать Windows x64 installer с официальной страницы Eclipse Mosquitto:
  ```text
   https://mosquitto.org/download/
  ```
2. Запустить installer.
3. Рекомендуемая папка установки:
  ```text
   C:\Program Files\Mosquitto
  ```
4. Если installer предлагает установить Mosquitto как Windows service, согласиться. Это удобно, он будет автоматом запускаться при старте системы.
5. Открыть **Command Prompt as Administrator**.
6. Перейти в папку Mosquitto:
  ```bat
   cd "C:\Program Files\Mosquitto"
  ```
7. Проверить установку:
  ```bat
   mosquitto -h
  ```

Ожидаемый результат: Mosquitto печатает версию и help. В рабочей установке было:

```text
mosquitto version 2.1.2
```

---

## 4. Mosquitto service и ручной запуск

Если Mosquitto установлен как Windows service, сервис может уже быть запущен. Тогда ручной запуск:

```bat
mosquitto -v
```

может завершиться ошибкой, что порт `1883` уже используется. Это не ошибка установки. Обычно это значит, что Mosquitto service уже слушает этот порт.

Проверить статус сервиса:

```bat
sc query mosquitto
```

Если видно:

```text
STATE              : 4  RUNNING
```

значит сервис уже запущен.

---

## 5. Настройка Mosquitto для доступа из локальной WLAN

Mosquitto 2.x может стартовать в **local-only mode**, если не настроен listener. В этом режиме клиенты на самом ноутбуке работают через `localhost`, но устройства из WLAN не подключаются.

Для Alco ESP нужно, чтобы Mosquitto слушал LAN/WLAN интерфейс.

Открыть конфиг от имени администратора:

```bat
notepad "C:\Program Files\Mosquitto\mosquitto.conf"
```

Добавить минимальную рабочую конфигурацию:

```conf
listener 1883 0.0.0.0
allow_anonymous true
```

Что это значит:

- `listener 1883 0.0.0.0` — слушать TCP порт `1883` на всех IPv4-интерфейсах, включая домашний Wi-Fi адрес ноутбука.
- `allow_anonymous true` — разрешить клиентам подключаться без username/password. Это соответствует текущей конфигурации Alco ESP и Windows desktop client.

Дополнительно можно добавить persistence и лог:

```conf
persistence true
persistence_location C:\ProgramData\mosquitto\
log_dest file C:\ProgramData\mosquitto\mosquitto.log
```

Если используются эти строки, сначала создать папку:

```bat
mkdir C:\ProgramData\mosquitto
```

Проверить конфигурацию:

```bat
cd "C:\Program Files\Mosquitto"
mosquitto --test-config -c mosquitto.conf
```

Если ошибок нет, перезапустить сервис:

```bat
net stop mosquitto
net start mosquitto
```

> **Безопасность:** `allow_anonymous true` допустим для простой изолированной домашней LAN-настройки, но не для сети с гостями и не для доступа из интернета. Не настраивать port forwarding для MQTT порта `1883` на роутере.

---

## 6. Проверка брокера с Windows

### 6.1 Тест через localhost

Открыть первый терминал:

```bat
cd "C:\Program Files\Mosquitto"
mosquitto_sub -h localhost -t test/# -v
```

Открыть второй терминал:

```bat
cd "C:\Program Files\Mosquitto"
mosquitto_pub -h localhost -t test/hello -m "hello from laptop"
```

В первом терминале должно появиться:

```text
test/hello hello from laptop
```

### 6.2 Тест через WLAN IP ноутбука

Это важнее, потому что именно этот IP используют другие устройства.

Первый терминал:

```bat
cd "C:\Program Files\Mosquitto"
mosquitto_sub -h 192.168.1.84 -p 1883 -t test/# -v
```

Второй терминал:

```bat
cd "C:\Program Files\Mosquitto"
mosquitto_pub -h 192.168.1.84 -p 1883 -t test/hello -m "hello via WLAN IP"
```

---

## 7. Настройка WLAN и Windows Firewall

### 7.1 Найти IP ноутбука в WLAN

В Command Prompt:

```bat
ipconfig
```

Искать активный Wi-Fi адаптер. В рабочей конфигурации важный фрагмент был таким:

```text
Адаптер беспроводной локальной сети Беспроводная сеть:

   DNS-суффикс подключения . . . . . : Dlink
   IPv4-адрес. . . . . . . . . . . . : 192.168.1.84 <- вот интересующий нас адрес
   Маска подсети . . . . . . . . . . : 255.255.255.0
   Основной шлюз. . . . . . . . . . : 192.168.1.1
```

Адаптеры со статусом:

```text
Среда передачи недоступна
```

можно игнорировать — они отключены.

### 7.2 Сделать Wi-Fi сеть Private, а не Public

Через Windows Settings:

1. Нажать `Win + I`.
2. Открыть **Network & Internet**.
3. Открыть **Wi-Fi**.
4. Нажать на текущую подключённую Wi-Fi сеть.
5. В разделе **Network profile** выбрать **Private**, не **Public**.

Или через PowerShell:

```powershell
Get-NetConnectionProfile
```

Должно быть:

```text
NetworkCategory : Private
```

Изменить через PowerShell от имени администратора:

```powershell
Set-NetConnectionProfile -InterfaceAlias "Беспроводная сеть" -NetworkCategory Private
```

### 7.3 Открыть MQTT порт в Windows Firewall

1. Открыть **Windows Security**.
2. Перейти в **Firewall & network protection**.
3. Открыть **Advanced settings**.
4. Выбрать **Inbound Rules**.
5. Нажать **New Rule**.
6. Выбрать **Port**.
7. Выбрать **TCP**.
8. В **Specific local ports** указать:
  ```text
   1883
  ```
9. Выбрать **Allow the connection**.
10. Включить правило для **Private** сетей. Не включать для **Public**, если нет понимания риска.
11. Назвать правило:
  ```text
   Mosquitto MQTT 1883
  ```

### 7.4 (опционально) Сделать адрес брокера стабильным

Лучший вариант: настроить DHCP reservation на роутере, чтобы ноутбук всегда получал:

```text
192.168.1.84
```

Иначе, если IP изменился, обновлять настройки вручную в двух местах:

1. Alco ESP: поле MQTT broker;
2. Windows desktop client: файл `secrets.json`.

---

## 8. Настройка Alco ESP / автоматики

### 8.1 Предупреждение по безопасности

Автоматика питается от сети **220 В**.

> **Внимание:** недопустимо касание разъёмов для подключения клапанов, так как они могут находиться под напряжением сети.

Настройку Wi-Fi/MQTT можно делать без подключения датчиков температуры и клапанов. (уточнить)

### 8.2 Как открыть страницу настройки устройства

1. Если устройство уже настроено на подключение к домашнему wifi, выключить домашний wifi
2. Подключить автоматику к питающей сети 220 В.
3. Включить автоматику тумблером на лицевой панели.
4. Дождаться появления надписей на дисплее и звукового сигнала.
5. Устройство попробует подключиться к домашнему Wi-Fi с сохранёнными ранее настройками
6. Подключение не удастся (домашний wifi выключен) -> устройство создаст свою Wi-Fi точку доступа:
  ```text
   ALCO_ESP
  ```
   Пароль не требуется.
7. Внутри устройства должен начать постоянно светить синий светодиод.
8. С ноутбука или телефона подключиться к Wi-Fi сети `ALCO_ESP`.
9. Открыть в браузере:
  ```text
   http://192.168.4.1
  ```
   Использовать именно `http://`, не `https://`.

**Важно:** сеть ALCO_ESP будет создана только тогда, когда устройство подняло свою точку доступа `ALCO_ESP`. Если устройство уже успешно подключилось к домашней Wi-Fi сети, wifi-сеть самого устройства создана не будет.

### 8.3 Поля на странице Alco ESP

Заполнить поля так:


| Поле на странице устройства              | Значение                                |
| ---------------------------------------- | --------------------------------------- |
| Wi-Fi сеть / Название домашней WiFi сети | `MTSRouter-135F89` - имя домашнего wifi |
| Пароль Wi-Fi / Пароль от домашней сети   | пароль от домашнего wifi                |
| MQTT брокер / Название MQTT брокера      | `192.168.1.84`                          |
| Имя пользователя                         | оставить пустым                         |
| Пароль пользователя                      | оставить пустым                         |
| Порт пользователя                        | `1883`                                  |
| Префикс для топиков                      | `/` - ввести просто один слэш           |


После заполнения нажать **Save settings**. Должно появиться сообщение, что параметры записаны.

После этого автоматику можно отключить. При последующем включении она должна автоматически подключаться к заданной домашней Wi-Fi сети и MQTT broker.

---

## 9. Настройка Windows desktop client

Найти папку packaged app, где лежит файл:

```text
secrets_template.json
```

В этой же папке создать или отредактировать файл:

```text
secrets.json
```

Содержимое `secrets.json` для текущей рабочей конфигурации:

```json
{
  "broker": "192.168.1.84",
  "port": 1883,
  "username": "",
  "password": ""
}
```

Не менять `settings.json` для настроек MQTT-подключения. `settings.json` используется для настроек программы-клиенты, а не для MQTT подключения.

---

## 10. Troubleshooting checklist


| Симптом                                                                      | Вероятная причина                                                                                                                                | Что проверить / исправить                                                                                                             |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| `mosquitto -v` пишет, что порт `1883` уже используется                       | Mosquitto service уже запущен или другой процесс занял порт                                                                                      | `sc query mosquitto`, `netstat -ano                                                                                                   |
| Клиент на ноутбуке работает через `localhost`, но устройство не подключается | Mosquitto в local-only mode, firewall блокирует порт, или устройство в другой сети                                                               | Проверить `mosquitto.conf`: `listener 1883 0.0.0.0`; проверить Windows Firewall; убедиться, что одна Wi-Fi/LAN сеть                   |
| Устройство не достаёт до broker                                              | Неверный IP broker или IP ноутбука изменился                                                                                                     | Выполнить `ipconfig`; обновить поле MQTT broker на устройстве и `secrets.json`                                                        |
| `http://192.168.4.1` не открывается                                          | Устройство уже подключилось к домашней Wi-Fi сети, поэтому AP `ALCO_ESP` не активна. Также важно, чтобы было http, а не https в строке браузера | Подключаться только когда видна сеть `ALCO_ESP`; при необходимости временно выключить домашний роутер                                 |
| Устройство подключается к Wi-Fi, но MQTT данных нет                          | Неверный broker, port, prefix или firewall                                                                                                       | Проверить `broker=192.168.1.84`, `port=1883`, `prefix=/`, username/password пустые, TLS off; подписаться на `test/#` и рабочие топики |
| Windows desktop client не подключается                                       | Нет `secrets.json` или он лежит не в той папке                                                                                                   | Положить `secrets.json` рядом с `secrets_template.json`; не использовать `settings.json` для MQTT                                     |
| Сообщения появляются в неожиданных топиках                                   | Неверный topic prefix                                                                                                                            | Использовать prefix `/`; ожидаемые топики включают `/term_k` и `/work`                                                                |
| Соединения пропадают через некоторое время                                   | Ноутбук ушёл в sleep или IP изменился                                                                                                            | Отключить sleep while plugged in; сделать DHCP reservation на роутере                                                                 |


---

## 11. Сводка полезных команд

```bat
:: Перейти в папку Mosquitto
cd "C:\Program Files\Mosquitto"

:: Показать версию/help
mosquitto -h

:: Проверить статус сервиса
sc query mosquitto

:: Остановить/запустить сервис
net stop mosquitto
net start mosquitto

:: Ручной verbose run, предварительно остановив service
mosquitto -v

:: Запустить вручную с config
mosquitto -c mosquitto.conf -v

:: Проверить config
mosquitto --test-config -c mosquitto.conf

:: Проверить порт 1883
netstat -ano | findstr :1883

:: Подписаться на test topics через localhost
mosquitto_sub -h localhost -t test/# -v

:: Опубликовать test message через localhost
mosquitto_pub -h localhost -t test/hello -m "hello"

:: Подписаться через WLAN IP
mosquitto_sub -h 192.168.1.84 -p 1883 -t test/# -v

:: Опубликовать через WLAN IP
mosquitto_pub -h 192.168.1.84 -p 1883 -t test/hello -m "hello via WLAN IP"
```

---

## 12. Итоговые минимальные рабочие файлы

### 12.1 Фрагмент `mosquitto.conf`

```conf
listener 1883 0.0.0.0
allow_anonymous true
```

Опционально:

```conf
persistence true
persistence_location C:\ProgramData\mosquitto\
log_dest file C:\ProgramData\mosquitto\mosquitto.log
```

### 12.2 `secrets.json`

```json
{
  "broker": "192.168.1.84",
  "port": 1883,
  "username": "",
  "password": ""
}
```

### 12.3 Alco ESP настройки

```text
Wi-Fi сеть: MTSRouter-135F89
Пароль Wi-Fi: <HOME_WIFI_PASSWORD>
MQTT брокер: 192.168.1.84
Имя пользователя: пусто
Пароль пользователя: пусто
Порт: 1883
Префикс топиков: /
TLS/SSL: выключен
```

---

## 13. Что делать при следующей установке с нуля

1. Установить Mosquitto в `C:\Program Files\Mosquitto`.
2. Проверить `mosquitto -h`.
3. Настроить `mosquitto.conf`:
  ```conf
   listener 1883 0.0.0.0
   allow_anonymous true
  ```
4. Перезапустить сервис:
  ```bat
   net stop mosquitto
   net start mosquitto
  ```
5. Проверить IP ноутбука через `ipconfig`.
6. Убедиться, что Wi-Fi profile = **Private**.
7. Открыть TCP порт `1883` в Windows Firewall для Private networks.
8. Протестировать broker через `localhost`.
9. Протестировать broker через WLAN IP, например `192.168.1.84`.
10. Настроить Alco ESP через `ALCO_ESP` и `http://192.168.4.1`.
11. Создать `secrets.json` рядом с `secrets_template.json` в desktop client.
12. Проверить, что устройство и Windows client используют одинаковый broker IP, port и topic prefix `/`.

