import json
import os

import paho.mqtt.client as mqtt
from django.conf import settings
from django.utils import timezone
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet


from .models import IoTDevice, MQTTCommand
from .serializers import IoTDeviceSerializer, MQTTCommandSerializer


# ==================== MongoDB Connection ====================
def get_mongo_collection():
    """Získá MongoDB collection pro modbus_readings."""
    client = MongoClient(
        host=settings.MONGO_DATABASE["HOST"],
        port=settings.MONGO_DATABASE["PORT"],
        serverSelectionTimeoutMS=5000,
    )
    return client[settings.MONGO_DATABASE["NAME"]]["modbus_readings"]


# ==================== MongoDB Data API ====================
@api_view(["GET"])
def modbus_readings_list(request):
    """
    GET endpoint pro výpis měření z MongoDB.

    Query params:
    - limit: počet záznamů (default 100)
    - device_id: filter podle IoT zařízení (volitelné)
    """
    try:
        limit = int(request.query_params.get("limit", "100"))
    except ValueError:
        return Response(
            {"detail": "Limit must be an integer."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    limit = max(1, min(limit, 1000))
    device_id = request.query_params.get("device_id")

    try:
        collection = get_mongo_collection()

        query_filter = {}
        if device_id:
            query_filter["device_id"] = device_id

        readings = list(
            collection.find(query_filter)
            .sort("received_at", -1)
            .limit(limit)
        )
    except PyMongoError:
        return Response(
            {"detail": "MongoDB is unavailable."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    for reading in readings:
        reading["_id"] = str(reading["_id"])

        if reading.get("received_at"):
            reading["received_at"] = reading["received_at"].isoformat()

    return Response(
        {
            "count": len(readings),
            "limit": limit,
            "results": readings,
        }
    )


@api_view(["GET"])
def modbus_readings_latest(request):
    """GET endpoint pro poslední měření z MongoDB."""
    try:
        collection = get_mongo_collection()
        latest = collection.find_one(sort=[("received_at", -1)])
    except PyMongoError:
        return Response(
            {"detail": "MongoDB is unavailable."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if latest is None:
        return Response(
            {"detail": "No readings found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    latest["_id"] = str(latest["_id"])

    if latest.get("received_at"):
        latest["received_at"] = latest["received_at"].isoformat()

    return Response(latest)


# ==================== PostgreSQL IoT Devices API ====================
class IoTDeviceViewSet(ModelViewSet):
    """CRUD endpoint pro IoT zařízení uložená v PostgreSQL."""

    queryset = IoTDevice.objects.all()
    serializer_class = IoTDeviceSerializer


# ==================== MQTT Commands API ====================
class MQTTCommandViewSet(ModelViewSet):
    """CRUD endpoint pro MQTT příkazy uložené v PostgreSQL."""

    queryset = MQTTCommand.objects.all()
    serializer_class = MQTTCommandSerializer


def serialize_mqtt_payload(payload):
    """
    Převede JSON objekt/list na JSON řetězec.

    MQTT payload musí být bytes nebo string; Paho si string zakóduje.
    """
    if isinstance(payload, (dict, list)):
        return json.dumps(payload)

    if payload is None:
        return ""

    if isinstance(payload, str):
        return payload

    return str(payload)


@api_view(["POST"])
def send_mqtt_command(request, device_id):
    """
    Vytvoří a publikuje MQTT příkaz pro konkrétní zařízení.

    Body:
    - command: start | stop | restart | update_config
    - payload: volitelný textový nebo JSON payload
    """
    try:
        device = IoTDevice.objects.get(pk=device_id)
    except IoTDevice.DoesNotExist:
        return Response(
            {"detail": "Device not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not device.is_active:
        return Response(
            {"detail": "Device is inactive."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    command = request.data.get("command")
    payload = request.data.get("payload", "")

    if not command:
        return Response(
            {"detail": "Command is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    allowed_commands = {
        choice[0] for choice in MQTTCommand.COMMAND_CHOICES
    }

    if command not in allowed_commands:
        return Response(
            {
                "detail": "Invalid command.",
                "allowed_commands": sorted(allowed_commands),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    mqtt_payload = serialize_mqtt_payload(payload)

    mqtt_command = MQTTCommand.objects.create(
        device=device,
        command=command,
        topic=f"commands/{device.serial_number}",
        payload=mqtt_payload,
    )

    mqtt_client = None

    try:
        mqtt_client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"django-api-command-{mqtt_command.id}",
        )

        mqtt_username = os.getenv("MQTT_USERNAME")
        mqtt_password = os.getenv("MQTT_PASSWORD")

        if mqtt_username:
            mqtt_client.username_pw_set(
                username=mqtt_username,
                password=mqtt_password,
            )

        mqtt_host = os.getenv("MQTT_HOST", "mosquitto")
        mqtt_port = int(os.getenv("MQTT_PORT", "1883"))

        mqtt_client.connect(mqtt_host, mqtt_port, keepalive=60)
        mqtt_client.loop_start()

        publish_info = mqtt_client.publish(
            mqtt_command.topic,
            mqtt_command.payload,
            qos=1,
        )

        publish_info.wait_for_publish(timeout=5)

        if not publish_info.is_published():
            raise RuntimeError(
                "MQTT broker did not confirm the published message."
            )

        mqtt_command.is_sent = True
        mqtt_command.sent_at = timezone.now()
        mqtt_command.save(update_fields=["is_sent", "sent_at"])

    except (OSError, RuntimeError, ValueError) as error:
        return Response(
            {
                "detail": "MQTT command could not be delivered.",
                "command_id": mqtt_command.id,
                "error": str(error),
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    finally:
        if mqtt_client is not None:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()

    return Response(
        {
            "message": (
                f"Command '{command}' sent to device {device.name}"
            ),
            "command_id": mqtt_command.id,
            "topic": mqtt_command.topic,
            "payload": mqtt_command.payload,
            "is_sent": mqtt_command.is_sent,
            "sent_at": mqtt_command.sent_at,
        },
        status=status.HTTP_201_CREATED,
    )
