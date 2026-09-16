import asyncio
import logging
import requests
import os

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext
)
from pymodbus.server import StartAsyncTcpServer

logging.basicConfig(level=logging.INFO)

MODBUS_HOST = os.environ.get("MODBUS_HOST", "0.0.0.0")
MODBUS_PORT = int(os.environ.get("MODBUS_PORT", "5020"))

LATITUDE = float(os.environ["LATITUDE"])
LONGITUDE = float(os.environ["LONGITUDE"])
UPDATE_INTERVAL = int(os.environ["UPDATE_INTERVAL"])

API_URL = os.environ["OPEN_METEO_API_URL"]
API_PARAMS = {
    "latitude": LATITUDE,
    "longitude": LONGITUDE,
    "current": "pm2_5,pm10,nitrogen_dioxide,ozone,european_aqi"
}

INITIAL_INPUT_REGISTERS = [0, 0, 0, 0, 0, 0]


def create_context() -> tuple[ModbusServerContext, ModbusSequentialDataBlock]:
    input_registers = ModbusSequentialDataBlock(
        1,
        INITIAL_INPUT_REGISTERS,
    )

    slave_context = ModbusSlaveContext(
        ir=input_registers,
    )

    server_context = ModbusServerContext(
        slaves=slave_context,
        single=True,
    )

    return server_context, input_registers


def fetch_air_quality() -> list[int] | None:
    try:
        response = requests.get(API_URL, params=API_PARAMS, timeout=15)
        response.raise_for_status()
        data = response.json()
        current = data.get("current", {})
        logging.info(current)
        if not current:
            logging.warning("Malformed API response: %s", data)
            return None
        return [
            int(current["pm2_5"] * 10),
            int(current["pm10"] * 10),
            int(current["nitrogen_dioxide"] * 10),
            int(current["ozone"] * 10),
            current["european_aqi"],
            1
        ]
    except Exception as e:
        logging.error(
            "Failed to fetch air quality data: %s",
            e
        )
        return None


async def update_registers_task(
    input_registers: ModbusSequentialDataBlock
) -> None:
    while True:
        new_data = fetch_air_quality()
        await input_registers.async_setValues(
            1,
            new_data,
        )
        logging.info("Updated registers: %s", new_data)
        await asyncio.sleep(UPDATE_INTERVAL)


async def async_loop() -> None:
    context, input_registers = create_context()
    asyncio.create_task(
        update_registers_task(input_registers)
    )

    logging.info(
        "Starting air-quality Modbus TCP server on %s:%s",
        MODBUS_HOST,
        MODBUS_PORT,
    )

    await StartAsyncTcpServer(
        context=context,
        address=(MODBUS_HOST, MODBUS_PORT),
    )


if __name__ == "__main__":
    asyncio.run(async_loop())
