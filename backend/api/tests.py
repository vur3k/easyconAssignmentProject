from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import IoTDevice


class IoTDeviceApiTests(APITestCase):
    def test_create_device(self):
        payload = {
            "name": "Meteostanice LKPR",
            "serial_number": "LKPR-TEST-001",
            "description": "Testovaci zdroj meteorologickych dat",
            "location": "Prague, Czech Republic",
            "device_type": "mqtt_sensor",
            "is_active": True,
        }

        response = self.client.post(
            reverse("device-list"),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], payload["name"])
        self.assertEqual(response.data["device_type"], "mqtt_sensor")
        self.assertTrue(
            IoTDevice.objects.filter(
                serial_number="LKPR-TEST-001"
            ).exists()
        )

    def test_create_device_rejects_invalid_type(self):
        payload = {
            "name": "Neplatne zarizeni",
            "serial_number": "INVALID-001",
            "device_type": "weather_station",
        }

        response = self.client.post(
            reverse("device-list"),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("device_type", response.data)
        self.assertEqual(IoTDevice.objects.count(), 0)

    def test_device_detail_returns_404_for_missing_id(self):
        response = self.client.get(
            reverse("device-detail", kwargs={"pk": 9999})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_send_stop_command_for_existing_device(self):
        device = IoTDevice.objects.create(
            name="Test MQTT sensor",
            serial_number="TEST-MQTT-001",
            device_type="mqtt_sensor",
        )

        response = self.client.post(
            f"/api/devices/{device.id}/command/",
            {"command": "stop"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["command_id"], 1)
        self.assertEqual(
            response.data["topic"],
            "commands/TEST-MQTT-001",
        )
