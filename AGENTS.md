# AGENTS Guide

## Project purpose

This repository is a desktop monitoring and control client for **Alco ESP** distillation automation hardware.
It connects to an MQTT broker, shows live telemetry, lets the operator send control commands, and raises audible/visual alarms for configured conditions.

The main app is a **PyQt5 + Matplotlib** GUI in `[alco_esp/qt_client.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp/qt_client.py)`.

## Repository layout

- `[alco_esp/](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp)`: all runtime Python code, app resources, and device docs.
- `[build_pyinstaller.sh](/Users/kazakovaleksandr/code/alco_esp_py_qt/build_pyinstaller.sh)`: Linux build script.
- `[build_pyinstaller.cmd](/Users/kazakovaleksandr/code/alco_esp_py_qt/build_pyinstaller.cmd)`: Windows build script.
- `requirements_*.txt`: pinned dependencies per platform.

## Running locally

Use only the local `.venv` virtual environment. Never call system `python` or `pip`. 

## Runtime model (important for safe edits)

- MQTT topic prefix is `"{username}/"` and is applied in `[alco_esp/mqtt_utils.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp/mqtt_utils.py)`.
- UI code works with **unprefixed** topic names (`term_k`, `work`, `otbor_t_new`, etc.).
- The GUI thread must stay responsive: avoid blocking calls in UI handlers.
- MQTT publishing from the UI must go through `publishRequested` signal (thread-safe handoff to worker).

## Validation after changes

There is no automated test suite in this repository right now.
Do manual checks for every behavior change:

1. Launch GUI and verify it starts without configuration/runtime errors.
2. Connect to emulator or real broker and confirm telemetry updates.
3. Confirm command publishing still works (for example `work`, `term_c_max_new`, `otbor_t_new`).
4. Trigger at least one alarm path and confirm sound/dialog behavior.
5. Check generated logs in `alco_esp/log/`.

## Editing expectations for agents

- Keep topic names and settings keys consistent across `qt_client.py`, `constants.py`, `settings.py`, and `device_emulator.py`.
- Preserve Russian user-facing labels unless the task explicitly requests localization changes.
- Prefer small, surgical edits and keep side effects explicit in logs/status messages.
- If changing MQTT control behavior, cross-check topic names against `[alco_esp/device_docs/TOPIC_REFERENCE.md](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp/device_docs/TOPIC_REFERENCE.md)`.

## Where to find deeper module rules

See module-level guidance in `[alco_esp/AGENTS.md](/Users/kazakovaleksandr/code/alco_esp_py_qt/alco_esp/AGENTS.md)`.