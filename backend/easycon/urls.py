from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.views import (
    IoTDeviceViewSet,
    MQTTCommandViewSet,
    modbus_readings_latest,
    modbus_readings_list,
    send_mqtt_command,
)

router = DefaultRouter()
router.register(r"devices", IoTDeviceViewSet, basename="device")
router.register(r"mqtt-commands", MQTTCommandViewSet, basename="mqtt-command")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/modbus-readings/", modbus_readings_list, name="modbus-readings"),
    path(
        "api/modbus-readings/latest/",
        modbus_readings_latest,
        name="modbus-readings-latest",
    ),
    path(
        "api/devices/<int:device_id>/command/",
        send_mqtt_command,
        name="send-mqtt-command",
    ),
]
