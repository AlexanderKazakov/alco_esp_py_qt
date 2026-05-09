# About tests

The test strategy now has three layers:

1. Unit tests (Phase 1): fast logic checks.
2. Widget tests (Phase 2): real UI interactions in headless Qt.
3. Integration/system tests (Phase 3): real UI + real MQTT worker + local broker.

Phase 2 and 3 were designed to answer two different questions:

- Phase 2 question: "When user clicks in UI, does UI logic do the right thing?"
- Phase 3 question: "When real MQTT transport is involved, does end-to-end behavior still work?"

## What changed in each phase

### Phase 2 delivered

- `29` widget tests:
  - [tests/test_qt_client_widget_controls.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/tests/test_qt_client_widget_controls.py)
  - [tests/test_qt_client_widget_dialogs_and_rendering.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/tests/test_qt_client_widget_dialogs_and_rendering.py)
- Widget-specific fixtures and helpers in [tests/conftest.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/tests/conftest.py)
- No production code changes.

### Phase 3 delivered

- `8` integration tests:
  - [tests/test_qt_client_integration.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/tests/test_qt_client_integration.py)
- Embedded broker fixture (`amqtt`) and real worker fixture in [tests/conftest.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/tests/conftest.py)
- Integration marker registered in [pytest.ini](/Users/kazakovaleksandr/code/alco_esp_py_qt/pytest.ini)
- Dev test dependency update:
  - `amqtt==0.11.3` in [requirements_dev_test.txt](/Users/kazakovaleksandr/code/alco_esp_py_qt/requirements_dev_test.txt)
- VS Code integration launch profile in [.vscode/launch.json](/Users/kazakovaleksandr/code/alco_esp_py_qt/.vscode/launch.json)

## Phase 2 in depth: Widget-level testing techniques

Phase 2 is about testing real user interaction with Qt widgets, while avoiding network and file side effects.

### 1) Headless Qt setup

Tests run without opening visible desktop windows:

- `QT_QPA_PLATFORM=offscreen`
- `MPLCONFIGDIR=.mplconfig`

This is set globally in [tests/conftest.py](/Users/kazakovaleksandr/code/alco_esp_py_qt/tests/conftest.py) so every test runs in the same controlled environment.

Why this matters:

- stable behavior in local/CI;
- no dependency on display server;
- much fewer random failures.

### 2) Dedicated widget fixture with safe monkeypatching

The main Phase 2 fixture is `widget_monitor`.

It creates real `AlcoEspMonitor`, but patches only risky external parts:

- disables real MQTT startup (`setup_mqtt` is replaced with a no-op worker/thread assignment);
- disables delayed sound init side effects (`QTimer.singleShot` patched);
- replaces CSV log writers with no-op logger stubs.

Important design point:

- UI logic and signal wiring stay real.
- External systems are muted.

This keeps tests meaningful while still fast and deterministic.

### 3) Interaction-first tests (not direct method calls)

Phase 2 tests mostly act like a real user:

- `qtbot.mouseClick(...)` for button click;
- combobox selection changes;
- spinbox value changes.

Then they assert outcomes the user can observe:

- published command signal payload;
- status label text;
- UI label style/text states;
- dialog open/close behavior.

Why this is better than calling business methods directly:

- validates UI wiring, not only core logic;
- catches broken button connections and wrong control mapping.

### 4) Signal capture helper

`publish_capture` fixture collects `publishRequested` emissions in strict order.

This allows checks like:

- stop mode emits exactly `("work", "0")`;
- razgon emits exactly `[("term_k_r", "70.0"), ("work", "4")]`.

This verifies sequencing contracts, not just "something was emitted".

### 5) Duplicate button disambiguation helper

Multiple buttons share text `"Установить"`.

`find_push_button` fixture finds by:

- visible text;
- positional index among matches.

Why this matters:

- tests remain explicit about which button is targeted;
- no accidental click on wrong control section.

### 6) Dialog stubbing technique (Settings dialog)

`settings_dialog_stub_factory` replaces the real modal dialog with a controlled stub.

The stub lets each test choose:

- accepted path or canceled path;
- exact returned settings payload.

What this gives you:

- deterministic test for both branches;
- no flaky modal interaction timing;
- direct validation of side effects (`save_settings` called once or not called).

### 7) Exact full-string assertions for UI contract

Phase 2 intentionally uses strict, full-text checks for important labels.

Examples:

- `"Настройки обновлены."`
- `"Сигнал T куба сброшен и активирован."`
- `"T дефл.: 56.8 °C"`

Why strict text checks are useful here:

- catches regressions in user-facing wording;
- catches format regressions (units, rounding, spacing);
- keeps operator-facing UX predictable.

### 8) Branch verification via instrumentation

Some tests patch specific methods to capture which branch executes.

Example:

- settings change with chart limit update should call `update_plots_and_signals`;
- other settings change should call `check_signal_conditions`.

This technique is a clean way to validate branch routing without changing production code.

### 9) Deterministic async waiting

Where async behavior is present, tests use:

- `qtbot.waitUntil(...)`

They do not use raw `sleep(...)`.

Why:

- faster when condition is already true;
- less flaky timing;
- easier debugging (condition-based failure).

### 10) Cleanup discipline

Fixture cleanup closes:

- active timers;
- child alarm dialogs;
- matplotlib figure.

And it performs graceful monitor shutdown when relevant.

Why:

- no leaking windows/timers between tests;
- prevents hidden cross-test contamination.

## Phase 3 in depth: Integration/system testing techniques

Phase 3 answers: "Does the full transport path work with real MQTT behavior?"

It is still local and deterministic: no external broker required.

### 1) Integration marker

All integration tests are marked with `@pytest.mark.integration`.

The marker is registered in [pytest.ini](/Users/kazakovaleksandr/code/alco_esp_py_qt/pytest.ini). All tests run by default, including integration. Use the marker to filter when needed:

- run only integration: `-m integration`;
- skip integration: `-m "not integration"`.

### 2) Embedded broker fixture (`amqtt`)

`integration_broker` fixture:

- finds a free localhost TCP port;
- starts an `amqtt` broker in a background asyncio loop/thread;
- yields host/port to tests;
- shuts down broker in teardown with timeout-bound cleanup.

Why this approach:

- zero external infrastructure;
- repeatable local integration tests;
- easy to run in any developer machine with `.venv`.

### 3) Per-test isolation using unique MQTT prefixes

`integration_secrets` generates unique username/prefix per test, for example:

- `integration_user_<random>`

Why:

- tests do not observe each other messages;
- no accidental cross-talk in shared session broker.

### 4) Real monitor + real worker fixture

`integration_monitor` uses real `AlcoEspMonitor` with real `setup_mqtt()` and real `MqttWorker`.

It still mutes non-functional side effects:

- CSV log writes;
- deferred sound init trigger.

Important detail:

- in integration mode, the plot timer stays running because periodic UI refresh updates labels.

Why this matters:

- this is closer to production runtime behavior;
- catches issues that unit/widget-only tests cannot catch.

### 5) Real publisher/subscriber test helpers

Two paho-based helpers are used:

- publisher fixture to inject telemetry;
- subscriber factory to capture commands from broker side.

This allows true end-to-end checks:

- UI click -> worker publish -> broker receives exact prefixed topic/payload.
- broker publish -> worker subscribe -> UI labels update.

### 6) End-to-end scenarios covered

Phase 3 tests include:

1. Monitor connects to broker and shows connected status.
2. Telemetry topics update exact UI labels.
3. Prefix stripping works (internal keys remain unprefixed).
4. UI controls publish exact prefixed commands.
5. Razgon path preserves publish order (`term_k_r` then `work=4`).
6. `term_k_m` confirmation updates status and clears pending check.
7. MQTT data timeout alarm triggers once and sets active flag.
8. Graceful shutdown stops real MQTT thread.

These are high-risk runtime contracts, not trivial checks.

### 7) Stability techniques used in Phase 3

Several practical techniques were needed to keep tests stable:

- condition-based waits (`waitUntil`) instead of sleeps;
- explicit worker-thread startup waits before assertions;
- graceful fixture cleanup to avoid Qt thread wrapper deletion races;
- timeout-bounded broker shutdown to avoid hanging teardown.

This is the "engineering part" of integration testing: correctness + reliability.

## Why these techniques are meaningful (and not test noise)

A "bad test" usually checks implementation trivia.

These Phase 2/3 tests avoid that by focusing on contracts that matter:

- user-visible text and state transitions;
- command topic/payload correctness;
- sequencing guarantees (`RAZGON` flow order);
- transport-level interoperability (prefixing/subscription path);
- lifecycle safety (shutdown and timeout behavior).

In short:

- They protect real behavior operators depend on.
- They do not just increase test count.

## Practical debugging checklist

If widget tests fail:

1. Confirm fixture is `widget_monitor` (not integration fixture).
2. Check if assertion expects exact string that has changed intentionally.
3. Check if a test forgot `qtbot.waitUntil` for async UI updates.

If integration tests fail:

1. Confirm `amqtt` is installed in `.venv`.
2. Re-run only integration with `-m integration`.
3. Check connection status assertion first (startup path).
4. Check topic prefix in subscriber assertions (`<username>/...`).
5. Look for teardown issues: thread still running, broker shutdown timeout.

