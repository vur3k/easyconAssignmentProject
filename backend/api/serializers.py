from rest_framework import serializers
from .models import IoTDevice, MQTTCommand


class IoTDeviceSerializer(serializers.ModelSerializer):
    """Serializer pro IoT zařízení."""

    class Meta:
        model = IoTDevice
        fields = [
            "id",
            "name",
            "serial_number",
            "description",
            "location",
            "device_type",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class MQTTCommandSerializer(serializers.ModelSerializer):
    """Serializer pro MQTT příkazy."""

    device_name = serializers.CharField(source="device.name", read_only=True)

    class Meta:
        model = MQTTCommand
        fields = [
            "id",
            "device",
            "device_name",
            "command",
            "topic",
            "payload",
            "is_sent",
            "created_at",
            "sent_at",
        ]
        read_only_fields = ["id", "is_sent", "created_at", "sent_at"]
