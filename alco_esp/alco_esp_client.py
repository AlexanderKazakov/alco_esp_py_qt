import paho.mqtt.client as mqtt
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
import threading
import matplotlib.dates as mdates
from .secrets import broker, port, username, password

# MQTT settings
client_id = "python_client_viewer"
topic_prefix = f"{username}/"

# Topics to subscribe to (match those published by the emulator)
topics = [
    "term_d", "power", "term_d_m", "power_m", "work"
]

# Data storage for plotting (rolling window)
window_size = 60  # e.g., last 10 minutes if published every 10s
data = {key: deque(maxlen=window_size) for key in topics}
timestamps = {key: deque(maxlen=window_size) for key in topics}

# State for status display
latest_values = {key: None for key in topics}

# Work state names from documentation
WORK_STATE_NAMES = {
    0: "стоп",
    1: "старт",
    2: "рестарт",
    3: "сброс отображения",
    4: "разгон",
    5: "выключение разгона",
    6: "отбор выключен",
    7: "отбор голов периодикой",
    8: "отбор тела",
    9: "отбор голов покапельно",
    10: "отбор подголовников"
}

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    for key in topics:
        client.subscribe(topic_prefix + key)

def on_message(client, userdata, msg):
    topic = msg.topic.replace(topic_prefix, "")
    try:
        value = float(msg.payload.decode())
    except ValueError:
        value = msg.payload.decode()
    latest_values[topic] = value
    if topic in data:
        data[topic].append(value)
        from datetime import datetime
        timestamps[topic].append(datetime.now())  # Store timestamp for this topic

# MQTT client setup
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id)
client.username_pw_set(username, password)
client.on_connect = on_connect
client.on_message = on_message

def mqtt_loop():
    client.connect(broker, port, 60)
    client.loop_forever()

# Start MQTT in a separate thread
threading.Thread(target=mqtt_loop, daemon=True).start()


def plt_full_screen():
    manager = plt.get_current_fig_manager()
    try:
        # Try Qt backend maximize
        manager.window.showMaximized()
    except AttributeError:
        try:
            # Try Tkinter backend maximize (Windows)
            manager.window.state('zoomed')
        except Exception:
            try:
                # Try Tkinter backend maximize (Linux, some WMs)
                manager.window.attributes('-zoomed', True)
            except Exception:
                # Fallback: resize window
                manager.resize(*manager.window.maxsize())

# Matplotlib setup
plt.style.use('seaborn-v0_8-darkgrid')
fig, axs = plt.subplots(3, 1, figsize=(10, 10), sharex=True)
fig.suptitle("Alco ESP Device Real-Time Monitor")
plt_full_screen()

def animate(i):
    axs[0].clear()
    axs[0].set_title("Temperatures")
    axs[0].set_ylabel("°C")
    
    axs[1].clear()
    axs[1].set_title("Power")
    axs[1].set_ylabel("Watt")
    
    axs[2].clear()
    axs[2].set_title("Work State")
    axs[2].set_ylabel("State")
    axs[2].set_xlabel(f"Time (last {window_size} samples)")

    # Plot with datetime x-axis
    axs[0].plot(timestamps["term_d"], list(data["term_d"]), label="term_d", marker='o')
    axs[0].plot(timestamps["term_d_m"], list(data["term_d_m"]), label="term_d_m", linestyle='--', marker='o')
    axs[0].legend()
    # Show latest values for temperature
    if latest_values["term_d"] is not None:
        axs[0].text(0.99, 0.95, f'term_d: {latest_values["term_d"]:.2f}', transform=axs[0].transAxes,
                    ha='right', va='top', fontsize=10, bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
    if latest_values["term_d_m"] is not None:
        axs[0].text(0.99, 0.85, f'term_d_m: {latest_values["term_d_m"]:.2f}', transform=axs[0].transAxes,
                    ha='right', va='top', fontsize=10, bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

    axs[1].plot(timestamps["power"], list(data["power"]), label="power", marker='o')
    axs[1].plot(timestamps["power_m"], list(data["power_m"]), label="power_m", linestyle='--', marker='o')
    axs[1].legend()
    # Show latest values for power
    if latest_values["power"] is not None:
        axs[1].text(0.99, 0.95, f'power: {latest_values["power"]:.2f}', transform=axs[1].transAxes,
                    ha='right', va='top', fontsize=10, bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
    if latest_values["power_m"] is not None:
        axs[1].text(0.99, 0.85, f'power_m: {latest_values["power_m"]:.2f}', transform=axs[1].transAxes,
                    ha='right', va='top', fontsize=10, bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

    # Work state as step plot, with state names as y-ticks
    axs[2].step(timestamps["work"], list(data["work"]), label="work (state)", where='mid', marker='o')
    axs[2].legend()
    # Set y-ticks to all possible state numbers and names, and fix y-limits
    all_states = sorted(WORK_STATE_NAMES.keys())
    axs[2].set_yticks(all_states)
    axs[2].set_yticklabels([WORK_STATE_NAMES.get(s, str(s)) for s in all_states])
    axs[2].set_ylim(min(all_states) - 0.5, max(all_states) + 0.5)
    # Show latest value for work state
    if latest_values["work"] is not None:
        state_num = int(float(latest_values["work"]))
        state_name = WORK_STATE_NAMES.get(state_num, str(state_num))
        axs[2].text(0.99, 0.95, f'work: {state_num} ({state_name})', transform=axs[2].transAxes,
                    ha='right', va='top', fontsize=10, bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

    # Set x-axis to datetime and format as hh:mm:ss
    for ax in axs:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax.xaxis.set_major_locator(mdates.SecondLocator(bysecond=range(0, 60, 10)))
        ax.tick_params(axis='x', rotation=45)

ani = animation.FuncAnimation(fig, animate, interval=10000)
plt.show()
