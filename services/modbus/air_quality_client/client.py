import logging
import os
import time
import asyncio

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from pymodbus.client import ModbusTcpClient

logging.basicConfig(level=logging.INFO)

MODBUS_HOST = os.environ["MODBUS_HOST"]
MODBUS_PORT = int(os.environ["MODBUS_PORT"])
MODBUS_DEVICE_ID = int(os.environ.get("MODBUS_DEVICE_ID", "1"))
MODBUS_POLL_INTERVAL = int(os.environ["MODBUS_POLL_INTERVAL"])

REGISTER_COUNT = 6

MONGO_HOST = os.environ["MONGO_HOST"]
MONGO_PORT = int(os.environ["MONGO_PORT"])
MONGO_DATABASE = os.environ["MONGO_DATABASE"]
MONGO_COLLECTION = os.environ["MONGO_COLLECTION"]


def connect_to_db() -> MongoClient:
    while True:
        try:
            client = MongoClient(
                host=MONGO_HOST,
                port=MONGO_PORT,
                serverSelectionTimeoutMS=5000,  # 5 seconds timeout
            )
            client.admin.command("ping")  # Check if the server is available
            logging.warning(
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


def save_reading(client: MongoClient, reading: dict) -> None:
    collection = client[MONGO_DATABASE][MONGO_COLLECTION]
    result = collection.insert_one(reading)
    logging.info(f"Stored reading with id {result.inserted_id} {reading}")


async def read_air_quality() -> dict | None:
    client = ModbusTcpClient(
        host=MODBUS_HOST,
        port=MODBUS_PORT,
        timeout=15,
    )
    try:
        if not client.connect():
            logging.error(
                "Cannot connect to Modbus server at %s:%s",
                MODBUS_HOST,
                MODBUS_PORT,
            )
            return None

        response = client.read_input_registers(
            address=0,
            count=REGISTER_COUNT,
            slave=MODBUS_DEVICE_ID,
        )

        if response.isError():
            logging.error(
                "Modbus read failed: %s",
                response,
            )
            return None

        registers = response.registers

        if len(registers) != REGISTER_COUNT:
            logging.error(
                "Expected %d registers, got %d",
                REGISTER_COUNT,
                len(registers),
            )
            return None

        logging.info(
            "Raw registers: %s",
            registers,
        )

        return {
            "pm2_5_ug_m3": registers[0] / 10.0,
            "pm10_ug_m3": registers[1] / 10.0,
            "nitrogen_dioxide_ug_m3": registers[2] / 10.0,
            "ozone_ug_m3": registers[3] / 10.0,
            "european_aqi": registers[4],
            "data_valid": bool(registers[5]),
        }

    except Exception:
        logging.exception(
            "Unexpected Modbus exception"
        )
        return None

    finally:
        client.close()


async def async_loop() -> None:
    mongo_client = connect_to_db()

    try:
        while True:
            reading = await read_air_quality()
            if reading:
                save_reading(mongo_client, reading)
            else:
                logging.warning("Couldn't save malformed data")

            logging.info(time.time())
            await asyncio.sleep(MODBUS_POLL_INTERVAL)
    except KeyboardInterrupt:
        logging.info("Stopping Modbus Client.")
    finally:
        mongo_client.close()

if __name__ == "__main__":
    asyncio.run(async_loop())
