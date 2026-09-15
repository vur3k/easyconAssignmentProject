import os
from dataclasses import dataclass
import json
from datetime import datetime, timezone
import logging

from dotenv import load_dotenv
import paho.mqtt.client as mqtt


logging.basicConfig(level=logging.INFO)
load_dotenv()


DEVICE_ID = os.environ["DEVICE_ID"]
MQTT_HOST = os.environ["MQTT_HOST"]
MQTT_PORT = int(os.environ["MQTT_PORT"])

COMMAND_TOPIC = f"smart-home/radiators/{DEVICE_ID}/commands"
STATUS_TOPIC = f"smart-home/radiators/{DEVICE_ID}/status"


@dataclass
class RadiatorState:
    is_on: bool = False


state = RadiatorState()


def create_payload() -> str:
    payload = {
        "device_id": DEVICE_ID,
        "device_type": "radiator",
        "is_on": state.is_on,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps(payload)


def publish_state(client: mqtt.Client) -> None:
    logging.info("Publishing radiator status to %s", STATUS_TOPIC)
    payload = create_payload()

    result = client.publish(
        STATUS_TOPIC,
        payload,
        qos=1,
        retain=True
    )

    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        logging.info(f"Status queued for publishing: {payload}")
    else:
        logging.error(f"Could not queue status. Error code: {result.rc}")


def handle_command(data: dict) -> bool:
    match data.get("command"):
        case "turn_on":
            state.is_on = True
            logging.info("Radiator turned on.")
            return True
        case "turn_off":
            state.is_on = False
            logging.info("Radiator turned off.")
            return True
        case _:
            logging.error("Unknown command.")
    return False


def on_connect(
    client: mqtt.Client,
    userdata: object,
    flags: mqtt.ConnectFlags,
    reason_code: mqtt.ReasonCode,
    properties: mqtt.Properties | None,
) -> None:
    if reason_code != 0:
        logging.error(f"MQTT connection failed: {reason_code}")
        return

    logging.info(f"Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")

    result, _ = client.subscribe(COMMAND_TOPIC, qos=1)

    if result == mqtt.MQTT_ERR_SUCCESS:
        logging.info(f"Subscribed to commands: {COMMAND_TOPIC}")
        publish_state(client)
    else:
        logging.error("Could not subscribe to command topic. Error code: %s",
                      result)


def on_message(
    client: mqtt.Client,
    userdata: object,
    message: mqtt.MQTTMessage,
) -> None:
    try:
        command_data = json.loads(message.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        logging.error(f"Invalid command payload: {error}")
        return

    logging.info(f"Received command on {message.topic}: {command_data}")

    if handle_command(command_data):
        publish_state(client)


if __name__ == "__main__":
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=DEVICE_ID,
    )

    client.on_connect = on_connect
    client.on_message = on_message

    client.reconnect_delay_set(max_delay=30)
    client.connect_async(MQTT_HOST, MQTT_PORT)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        logging.info("\nStopping radiator.")
    finally:
        client.disconnect()
