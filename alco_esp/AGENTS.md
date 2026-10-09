# AGENTS Guide for `alco_esp/`

## Module map

- `[qt_client.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp/qt_client.py)`: main PyQt window, controls, plotting, alarms, and application lifecycle.
- `[app_version.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp/app_version.py)`: git commit of the running code for the startup log line.
- `[application_icon.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp/application_icon.py)`: app icon loading for the window, Dock, and Windows taskbar.
- `[mqtt_utils.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp/mqtt_utils.py)`: MQTT worker object running in a separate Qt thread.
- `[settings.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp/settings.py)`: persisted UI/signal settings (`settings.json`) and settings dialog.
- `[logging.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp/logging.py)`: app logger + CSV rotating loggers.
- `[child_dialogs.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp/child_dialogs.py)`: secrets loader dialog logic, alarm dialog, all-data viewer, custom toolbar.
- `[constants.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp/constants.py)`: shared enums, topic lists, style constants.
- `[device_emulator.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp/device_emulator.py)`: MQTT simulator for local/manual testing.
- `[discover_topics.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp/discover_topics.py)`: wildcard subscriber utility for inspecting live topics.

## Critical behavior contracts

### 1) Topic naming and prefixing

- In app logic, topics are referenced without prefix (`term_k`, `work`, `otbor_t_new`).
- Prefix is added only in `MqttWorker.publish_message()` and removed in `MqttWorker.on_message()`.
- Do not add ad-hoc prefix handling in UI code, or you will break topic matching.

### 2) Work mode command flow

- `work` values map to `WorkState` enum in `constants.py`.
- Special case for `RAZGON` in `qt_client.py`:
  1. publish `term_k_r` first using the configured stop temperature.
  2. then publish `work=4`.
  3. wait for `term_k_m` confirmation or timeout alarm.
- Keep this sequence intact when refactoring command logic.
- The device never publishes `work`. `flag_otb` is the takeoff state (`Golov`, `Telo`, `OFF`, `End`, `Error`), not the `work` mode.
- After a takeoff parameter change, `work` is re-sent only if the last `work` command seen on the broker is that mode and `flag_otb` agrees with it (`FLAG_OTB_VALUES_BY_WORK_MODE`). The last `work` command is forgotten on MQTT disconnect and on `flag_otb` `End`/`Error`.
- A value confirmation waits until the device reports the value that the app sent. It shows an alarm after `VALUE_CONFIRMATION_TIMEOUT`.
  1. After a takeoff parameter is sent to a `_new` topic, the app waits for the stored value on the paired topic (`TAKEOFF_PARAMETER_REPORT_TOPICS`).
  2. After a `work` re-send for a PWM change, the app waits for the new PWM on `otbor` (`ACTIVE_TAKEOFF_PWM_TOPIC`).
  3. A report with another value does not fail the check, because the device can send an older report first. Only the timeout fails it.

### 3) Threading model

- UI runs on main Qt thread.
- MQTT client runs via `MqttWorker` moved to a `QThread`.
- UI must publish via `publishRequested` signal only.
- Avoid direct network calls or `time.sleep()` inside GUI methods.

### 4) Logging model

- `logger`: operational log (`alco_esp_monitor.log`).
  - Every received message is a DEBUG line. A change of a value in `VALUE_CHANGE_LOG_TOPICS` also gets an INFO line.
  - The "Application starting..." line has the app version from `app_version.get_app_version()`. A build reads it from `build_version.txt`, which the build scripts write.
- `main_data_logger`: compact CSV for key telemetry topics.
- `all_data_logger`: CSV for all incoming device topics.
- If you add new telemetry that should be in compact CSV, update:
  - `TOPICS_OF_MAIN_INTEREST`
  - `CSV_DATA_TOPIC_ORDER`
  - `CSV_DATA_HEADERS`  
  in `[constants.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp/constants.py)`.

## Russian only in UI

- Anything user-facing is always in Russian!

