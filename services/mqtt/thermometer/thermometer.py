import json
import logging
import os
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import requests
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()


LOCATION_ID = os.environ["LOCATION_ID"]
MQTT_HOST = os.environ["MQTT_HOST"]
MQTT_PORT = int(os.environ["MQTT_PORT"])
API_URL = f"{os.environ["CHECKWX_API_URL"]}/{LOCATION_ID}/decoded"
API_KEY = os.environ["CHECKWX_API_KEY"]

TOPIC = f"smart-home/thermometers/{LOCATION_ID}/telemetry"
DEVICE_ID = f"{LOCATION_ID}-weather_client-01"
PUBLISH_INTERVAL = 30  # seconds


def fetch_weather_data():
    headers = {
        "X-API-Key": API_KEY,
    }

    response = requests.get(API_URL, headers=headers, timeout=10)
    response.raise_for_status()

    response_data = response.json()
    metar_data = response_data["data"][0]
    logging.info(f"Fetched weather data: {metar_data}")
    return metar_data


def create_payload(data) -> str:
    payload = {
        "device_id": f"{LOCATION_ID}-weather-client-01",
        "device_type": "weather-client",
        "location_id": LOCATION_ID,
        "temperature_c": data["temperature"]["celsius"],
        "wind_speed_mps": data["wind"]["speed"]["mps"],
        "wind_direction_deg": data["wind"]["degrees"],
        "humidity_percent": data["humidity"],
        "source": "checkwx",
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }
    logging.info(f"Created payload: {payload}")
    return json.dumps(payload)


if __name__ == "__main__":
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=DEVICE_ID,
    )
    client.connect(MQTT_HOST, MQTT_PORT)
    client.loop_start()

    try:
        while True:
            try:
                weather_data = fetch_weather_data()
                payload = create_payload(weather_data)
                client.publish(TOPIC, payload)
                logging.info(f"Published weather data: {payload}")
            except Exception as e:
                logging.error(f"Error processing weather data: {e}")

            time.sleep(PUBLISH_INTERVAL)
    except KeyboardInterrupt:
        logging.info("Stopping weather publisher...")
    finally:
        client.loop_stop()
        client.disconnect()
