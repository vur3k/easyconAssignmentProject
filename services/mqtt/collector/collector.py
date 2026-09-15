import os
import time
import logging
from datetime import datetime, timezone
import json

import paho.mqtt.client as mqtt
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, PyMongoError

logging.basicConfig(level=logging.INFO)

MQTT_HOST = os.environ["MQTT_HOST"]
MQTT_PORT = int(os.environ["MQTT_PORT"])
TOPICS = [
    ("smart-home/+/+/telemetry", 1),
    ("smart-home/+/+/status", 1),
]

MONGO_HOST = os.environ["MONGO_HOST"]
MONGO_PORT = int(os.environ["MONGO_PORT"])
MONGO_DATABASE = os.environ["MONGO_DATABASE"]
MONGO_COLLECTION = os.environ["MONGO_COLLECTION"]


def connect_to_db():
    while True:
        try:
            client = MongoClient(
                host=MONGO_HOST,
                port=MONGO_PORT,
                serverSelectionTimeoutMS=5000,
            )
            client.admin.command("ping")
            logging.info(
                "Connected to MongoDB at %s:%s",
                MONGO_HOST,
                MONGO_PORT
            )
            return client
        except ConnectionFailure:
            logging.error(
                "Failed to connect to MongoDB at %s:%s. Retry in 5 seconds...",
                MONGO_HOST,
                MONGO_PORT
            )
            time.sleep(5)


def create_indexes(collection) -> None:
    collection.create_index(
        [("received_at", ASCENDING)],
        name="received_at_index",
    )
    collection.create_index(
        [("payload.device_id", ASCENDING), ("received_at", ASCENDING)],
        name="device_received_at_index",
    )


def on_connect(
    client: mqtt.Client,
    userdata: dict,
    flags: mqtt.ConnectFlags,
    reason_code: mqtt.ReasonCode,
    properties: mqtt.Properties | None,
) -> None:
    if reason_code != 0:
        logging.error(f"MQTT connection failed: {reason_code}")
        return

    logging.info(f"Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")

    result, _ = client.subscribe(TOPICS)

    if result == mqtt.MQTT_ERR_SUCCESS:
        logging.info("Subscribed to telemetry and status topics.")
    else:
        logging.error(
            f"Could not subscribe to MQTT topics. Error code: {result}"
        )


def on_message(
    client: mqtt.Client,
    userdata: dict,
    message: mqtt.MQTTMessage,
) -> None:
    try:
        payload = json.loads(message.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        logging.error(f"Skipping invalid JSON from {message.topic}: {error}")
        return

    document = {
        "topic": message.topic,
        "qos": message.qos,
        "retained": message.retain,
        "received_at": datetime.now(timezone.utc),
        "payload": payload,
    }

    try:
        result = userdata["collection"].insert_one(document)
        logging.info(
            f"Stored message {result.inserted_id} "
            f"from {message.topic}"
        )
    except PyMongoError as error:
        logging.error(f"MongoDB insert failed: {error}")


if __name__ == "__main__":
    mongo_client = connect_to_db()
    collection = mongo_client[MONGO_DATABASE][MONGO_COLLECTION]

    create_indexes(collection)
    logging.info(f"Using collection: {MONGO_DATABASE}.{MONGO_COLLECTION}")

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="mqtt-collector",
        userdata={"collection": collection},
    )

    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    try:
        client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nStopping MQTT collector.")
    finally:
        client.disconnect()
        mongo_client.close()
