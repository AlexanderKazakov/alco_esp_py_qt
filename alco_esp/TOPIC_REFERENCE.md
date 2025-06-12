# Alco ESP MQTT Topic Reference

This is a AI summary of all MQTT topics used by the Alco ESP device, parsed from the official documentation.

**Note:** All topics must be prefixed with your user-specific prefix (e.g., `user_b9edb6c8/`).

---

## 1. Read-Only Topics (Device Status)

These topics are published by the device. You subscribe to them to read the device's state.

- `term_d`: Температура в дефлегматоре (Temperature in dephlegmator)
- `term_c`: Температура в царге (Temperature in column)
- `term_k`: Температура в кубе (Temperature in still pot)
- `power`: Измеренная мощность (Measured power)
- `press_a`: Атмосферное давление (Atmospheric pressure)
- `flag_otb`: Режим работы (Operating mode)
- `term_v`: (Unlisted in documentation, observed value: `0.0`)
- `term_vent`: (Unlisted in documentation, observed value: `30.0`)
- `count_vent`: (Unlisted in documentation, observed value: `0`)
- `num_error`: (Unlisted in documentation, observed value: `0`)


---

## 2. Commandable Topics (Read/Write Pairs)

For these, the device publishes its current state on one topic, and you publish a new value to a corresponding `_new` topic to change it.

| State Topic (Read) | Command Topic (Write) | Description |
|--------------------|-----------------------|-------------|
| `term_d_m`         | `term_d_m_new`        | Аварийная температура в дефлегматоре (Dephlegmator emergency temp) |
| `press_c_m`        | `press_c_m_new`       | Аварийное давление в кубе (Still pot emergency pressure) |
| `term_c_max`       | `term_c_max_new`      | Температура старт-стопа (Start-stop temperature) |
| `term_c_min`       | `term_c_min_new`      | Температура возобновления отбора (Resumption temperature) |
| `term_k_m`         | `term_k_m_new`        | Максимальная температура в кубе (Max temp in still pot) |
| `term_nasos`       | `term_nasos_new`      | Температура включения клапана на воду (Water valve activation temp) |
| `power_m`          | `power_m_new`         | Стабилизируемая мощность (Stabilized power setpoint) |
| `otbor`            | `otbor_new`           | ШИМ отбора (PWM for product takeoff) |
| `time_stop`        | `time_stop_new`       | Максимальное время старт-стопа (Max start-stop time) |
| `otbor_minus`      | `otbor_minus_new`     | Декремент отбора тела (Body takeoff decrement) |
| `min_otb`          | `min_otb_new`         | Период при отборе голов (Heads takeoff period) |
| `sek_otb`          | `sek_otb_new`         | Время открытого клапана при отборе голов (Heads takeoff valve open time) |
| `otbor_g_1`        | `otbor_g_1_new`       | ШИМ отбора для голов (Heads takeoff PWM) |
| `otbor_g_2`        | `otbor_g_2_new`       | ШИМ отбора для подголовников (Late heads takeoff PWM) |
| `otbor_t`          | `otbor_t_new`         | ШИМ отбора для тела (Body takeoff PWM) |
| `delta_t`          | `delta_t_new`         | Разница температуры для старт-стопа (Start-stop temp delta) |
| `term_k_m` (read)  | `term_k_r` (write)    | Температура в кубе для разгона (Still pot temp for heat-up phase) - *Special case* |

---

## 3. Direct Command Topics

### `work`
This is a multi-command topic. You publish a number to change the device's main operating mode. The device listens to this topic but does not publish to it unless commanded.

- `0`: Стоп (Stop)
- `1`: Старт (Start)
- `2`: Рестарт (Restart)
- `3`: Сброс отображения (Reset display)
- `4`: Разгон (Heat-up phase)
- `5`: Выключение разгона (End heat-up phase)
- `6`: Отбор выключен (Product takeoff off)
- `7`: Отбор голов периодикой (Heads takeoff - periodic)
- `8`: Отбор тела (Body takeoff)
- `9`: Отбор голов покапельно (Heads takeoff - drop-by-drop)
- `10`: Отбор подголовников (Late heads takeoff)

**Warning:** The documentation advises not to use `2` (рестарт) or `3` (сброс отображения) without good reason.

### `kontaktor`
This is both a status and command topic for a contactor/relay.

- **Publish `1`**: To turn the contactor ON.
- **Publish `0`**: To turn the contactor OFF.
- **Subscribe**: To get the current state (e.g., `Power ON`). 