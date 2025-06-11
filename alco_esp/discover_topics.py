import sys
import signal
import json
import paho.mqtt.client as mqtt
import os
import time

# --- Configuration ---
# Path to the directory of the script
APP_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SECRETS_FILE_PATH = os.path.join(APP_ROOT_DIR, "secrets.json")
CLIENT_ID = "python_topic_discoverer"


def load_secrets_cli():
    """
    Loads secrets from secrets.json.
    On error, it prints to stderr and exits.
    """
    if not os.path.exists(SECRETS_FILE_PATH):
        template_path = os.path.join(APP_ROOT_DIR, "secrets_template.json")
        msg = f"ERROR: Secrets file not found: {SECRETS_FILE_PATH}\n"
        if os.path.exists(template_path):
            msg += "Please copy 'secrets_template.json' to 'secrets.json' and fill in your details."
        else:
            msg += "Template 'secrets_template.json' is also missing. Cannot continue."
        print(msg, file=sys.stderr)
        sys.exit(1)

    try:
        with open(SECRETS_FILE_PATH, 'r', encoding='utf-8') as f:
            secrets = json.load(f)

        required_keys = ["broker", "port", "username", "password"]
        if not all(key in secrets for key in required_keys):
            missing_keys = [key for key in required_keys if key not in secrets]
            msg = f"ERROR: The secrets file {SECRETS_FILE_PATH} is missing required keys: {', '.join(missing_keys)}"
            print(msg, file=sys.stderr)
            sys.exit(1)
        
        print("Successfully loaded secrets from secrets.json.")
        return secrets

    except json.JSONDecodeError as e:
        msg = f"ERROR: Could not decode {SECRETS_FILE_PATH}. Is it valid JSON?\n{e}"
        print(msg, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        msg = f"ERROR: An unexpected error occurred while loading secrets: {e}"
        print(msg, file=sys.stderr)
        sys.exit(1)


# --- MQTT Callbacks ---
def on_connect(client, userdata, flags, rc):
    """Callback for when the client connects to the broker."""
    secrets = userdata['secrets']
    if rc == 0:
        print(f"Successfully connected to MQTT broker: {secrets['broker']}")
        # Subscribe to the wildcard topic for the user
        wildcard_topic = f"{secrets['username']}/#"
        client.subscribe(wildcard_topic)
        print(f"Subscribed to wildcard topic: '{wildcard_topic}'")
        print("Waiting for messages... Press Ctrl+C to exit.")
    else:
        print(f"Failed to connect, return code {rc}\n", file=sys.stderr)
        if rc == 3:
            print("Connection error: Server unavailable. Check broker address and port.", file=sys.stderr)
        elif rc == 4:
            print("Connection error: Bad username or password. Check your secrets.json file.", file=sys.stderr)
        elif rc == 5:
            print("Connection error: Not authorized. Check your credentials and ACLs on the broker.", file=sys.stderr)
        
        # Signal the main loop to exit on connection failure
        userdata['connection_failed'] = True

def on_message(client, userdata, msg):
    """Callback for when a PUBLISH message is received from the server."""
    try:
        payload = msg.payload.decode('utf-8')
        print(f"  Topic: {msg.topic:<40} | Payload: {payload}")
    except UnicodeDecodeError:
        print(f"  Topic: {msg.topic:<40} | Payload (raw): {msg.payload}")

def on_disconnect(client, userdata, rc):
    """Callback for when the client disconnects."""
    if rc != 0:
        print(f"Unexpected disconnection from broker (rc={rc}).")
    else:
        print("Disconnected successfully.")


def main():
    """Main function to run the MQTT topic discovery tool."""
    
    print("--- Alco ESP MQTT Topic Discoverer ---")
    secrets = load_secrets_cli()

    userdata = {'secrets': secrets, 'connection_failed': False}

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=CLIENT_ID, userdata=userdata)
    client.username_pw_set(secrets["username"], secrets["password"])
    
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    def signal_handler(sig, frame):
        print("\nCtrl+C pressed. Disconnecting gracefully...")
        client.disconnect()
        # The loop will break on its own after disconnect
    
    signal.signal(signal.SIGINT, signal_handler)

    try:
        print(f"Connecting to {secrets['broker']}...")
        client.connect(secrets["broker"], secrets["port"], 60)
    except Exception as e:
        print(f"Error during initial connection: {e}", file=sys.stderr)
        sys.exit(1)
        
    client.loop_start()

    try:
        while not userdata['connection_failed']:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt caught. Shutting down.")
    
    client.disconnect()
    client.loop_stop()
    print("Shutdown complete.")


if __name__ == '__main__':
    main() 