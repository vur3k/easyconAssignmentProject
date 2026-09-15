import json
import logging
import os
from dataclasses import dataclass

import paho.mqtt.client as mqtt


logging.basicConfig(level=logging.INFO)

MQTT_HOST = os.environ["MQTT_HOST"]
MQTT_PORT = int(os.environ["MQTT_PORT"])

THERMOMETER_ID = os.environ["THERMOMETER_ID"]
RADIATOR_ID = os.environ["RADIATOR_ID"]
DEVICE_ID = os.environ["DEVICE_ID"]

TELEMETRY_TOPIC = f"smart-home/thermometers/{THERMOMETER_ID}/telemetry"
RADIATOR_STATUS_TOPIC = f"smart-home/radiators/{RADIATOR_ID}/status"
RADIATOR_COMMAND_TOPIC = f"smart-home/radiators/{RADIATOR_ID}/commands"
CONFIG_TOPIC = f"smart-home/controllers/{DEVICE_ID}/config"


@dataclass
class HeatingConfig:
    enabled: bool = True
    target_temperature_c: float = 21.0
    hysteresis_c: float = 0.3


@dataclass
class ControllerState:
    current_temperature_c: float | None = None
    radiator_is_on: bool | None = None


config = HeatingConfig()
state = ControllerState()


def publish_radiator_command(client: mqtt.Client, command: str) -> None:
    payload = json.dumps({"command": command})

    result = client.publish(
        RADIATOR_COMMAND_TOPIC,
        payload,
        qos=1,
    )

    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        logging.info("Command queued: %s", command)
    else:
        logging.error("Could not queue command: %s", result.rc)


def evaluate_heating(client: mqtt.Client) -> None:
    if not config.enabled:
        logging.info("Automation is disabled.")
        return

    if state.current_temperature_c is None:
        logging.warning("Temperature is not available yet.")
        return

    if state.radiator_is_on is None:
        logging.warning("Radiator state is not available yet.")
        return

    lower_threshold = (
        config.target_temperature_c - config.hysteresis_c
    )
    upper_threshold = (
        config.target_temperature_c + config.hysteresis_c
    )

    if state.current_temperature_c < lower_threshold and \
            not state.radiator_is_on:
        publish_radiator_command(client, "turn_on")
        return

    if state.current_temperature_c >= upper_threshold \
            and state.radiator_is_on:
        publish_radiator_command(client, "turn_off")
        return

    logging.info(
        "No action. Temperature: %.1f, target: %.1f, radiator: %s",
        state.current_temperature_c,
        config.target_temperature_c,
        state.radiator_is_on,
    )


def update_config(payload: dict) -> None:
    if "enabled" in payload and isinstance(payload["enabled"], bool):
        config.enabled = payload["enabled"]

    if "target_temperature_c" in payload:
        temperature = payload["target_temperature_c"]

        if isinstance(temperature, (int, float)) and 5 <= temperature <= 30:
            config.target_temperature_c = float(temperature)

    if "hysteresis_c" in payload:
        hysteresis = payload["hysteresis_c"]

        if isinstance(hysteresis, (int, float)) and 0 < hysteresis <= 5:
            config.hysteresis_c = float(hysteresis)

    logging.info("Configuration updated: %s", config)


def on_connect(
    client: mqtt.Client,
    userdata: object,
    flags: mqtt.ConnectFlags,
    reason_code: mqtt.ReasonCode,
    properties: mqtt.Properties | None,
) -> None:
    if reason_code != 0:
        logging.error("MQTT connection failed: %s", reason_code)
        return

    topics = [
        (TELEMETRY_TOPIC, 1),
        (RADIATOR_STATUS_TOPIC, 1),
        (CONFIG_TOPIC, 1),
    ]

    result, _ = client.subscribe(topics)

    if result == mqtt.MQTT_ERR_SUCCESS:
        logging.info("Controller connected and subscribed.")
    else:
        logging.error("Subscription failed: %s", result)


def on_message(
    client: mqtt.Client,
    userdata: object,
    message: mqtt.MQTTMessage,
) -> None:
    try:
        payload = json.loads(message.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logging.warning("Invalid JSON received from %s", message.topic)
        return

    if message.topic == TELEMETRY_TOPIC:
        temperature = payload.get("temperature_c")

        if isinstance(temperature, (int, float)):
            state.current_temperature_c = float(temperature)
            logging.info(
                "Temperature updated: %.1f C",
                state.current_temperature_c,
            )
            evaluate_heating(client)
        return

    if message.topic == RADIATOR_STATUS_TOPIC:
        is_on = payload.get("is_on")

        if isinstance(is_on, bool):
            state.radiator_is_on = is_on
            logging.info("Radiator state updated: %s", is_on)
            evaluate_heating(client)
        return

    if message.topic == CONFIG_TOPIC:
        update_config(payload)
        evaluate_heating(client)


if __name__ == "__main__":
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=DEVICE_ID,
    )

    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    try:
        client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_forever()
    except KeyboardInterrupt:
        logging.info("Stopping heating controller.")
    finally:
        client.disconnect()
