# AGENTS Guide for `alco_esp/`

## Module map

- `[qt_client.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp/qt_client.py)`: main PyQt window, controls, plotting, alarms, and application lifecycle.
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

### 3) Threading model

- UI runs on main Qt thread.
- MQTT client runs via `MqttWorker` moved to a `QThread`.
- UI must publish via `publishRequested` signal only.
- Avoid direct network calls or `time.sleep()` inside GUI methods.

### 4) Logging model

- `logger`: operational log (`alco_esp_monitor.log`).
- `main_data_logger`: compact CSV for key telemetry topics.
- `all_data_logger`: CSV for all incoming device topics.
- If you add new telemetry that should be in compact CSV, update:
  - `TOPICS_OF_MAIN_INTEREST`
  - `CSV_DATA_TOPIC_ORDER`
  - `CSV_DATA_HEADERS`  
  in `[constants.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp/constants.py)`.

## Russian only in UI

- Anything user-facing is always in Russian!

