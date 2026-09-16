from django.db import models


class IoTDevice(models.Model):
    """Metadata o IoT zařízení - uloženo v PostgreSQL."""

    name = models.CharField(max_length=100)
    serial_number = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    device_type = models.CharField(
        max_length=50,
        choices=[
            ("modbus_client", "Modbus TCP Client"),
            ("mqtt_sensor", "MQTT Sensor"),
            ("mqtt_actuator", "MQTT Actuator"),
        ],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.serial_number})"

    class Meta:
        ordering = ["name"]


class MQTTCommand(models.Model):
    """Příkazy pro MQTT klienty - uloženo v PostgreSQL."""

    COMMAND_CHOICES = [
        ("start", "Start sending data"),
        ("stop", "Stop sending data"),
        ("restart", "Restart client"),
        ("update_config", "Update configuration"),
    ]

    device = models.ForeignKey(
        IoTDevice,
        on_delete=models.CASCADE,
        related_name="commands",
    )
    command = models.CharField(max_length=20, choices=COMMAND_CHOICES)
    topic = models.CharField(max_length=200)  # MQTT topic pro příkaz
    payload = models.TextField(blank=True, null=True)
    is_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.device.name} - {self.command}"

    class Meta:
        ordering = ["-created_at"]
