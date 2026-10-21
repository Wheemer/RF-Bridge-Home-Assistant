from __future__ import annotations

import base64
import binascii
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.const import (
    DEGREE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import (
    RFBridgeHub,
    diagnostics_signal,
    is_sensor_entry,
    parse_rflink_message,
    rf_event_signal,
)
from .const import (
    CONF_PARENT_ENTRY_ID,
    CONF_PROTOCOL,
    CONF_SENSOR_DISCOVERY,
    CONF_SENSOR_IDENTIFIER,
    CONF_SENSOR_MEASUREMENTS,
    DOMAIN,
)


@dataclass(frozen=True, slots=True)
class RFBridgeSensorDescription:
    key: str
    name: str
    icon: str
    value_fn: Callable[[RFBridgeHub], str | datetime | None]
    device_class: SensorDeviceClass | None = None


@dataclass(frozen=True, slots=True)
class RFBridgeMeasurementDescription:
    key: str
    name: str
    icon: str | None = None
    device_class: SensorDeviceClass | None = None
    native_unit_of_measurement: str | None = None
    state_class: SensorStateClass | None = None


def _bridge_status(hub: RFBridgeHub) -> str:
    if hub.status.get("raw_learning_armed") is True:
        return "learning"
    if hub.last_command is not None and hub.last_success is None:
        return "transmitting"
    return "idle"


def _bridge_uptime(hub: RFBridgeHub) -> datetime | None:
    value = hub.status.get("uptime")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    status_at = dt_util.parse_datetime(hub.last_status_at) if hub.last_status_at else None
    if status_at is None:
        status_at = dt_util.utcnow()
    if status_at.tzinfo is None:
        status_at = status_at.replace(tzinfo=UTC)
    return status_at - timedelta(seconds=value)


SENSORS: tuple[RFBridgeSensorDescription, ...] = (
    RFBridgeSensorDescription("status", "Status", "mdi:list-status", _bridge_status),
    RFBridgeSensorDescription(
        "uptime", "Uptime", "mdi:timer-outline", _bridge_uptime, SensorDeviceClass.TIMESTAMP
    ),
)


# Matches RFLink's PACKET_FIELDS/VALUE_TRANSLATION table. Only measurement
# fields are included; decoded remotes and raw captures never create sensors.
MEASUREMENTS: dict[str, RFBridgeMeasurementDescription] = {
    "awinsp": RFBridgeMeasurementDescription("average_windspeed", "Average wind speed", "mdi:weather-windy", SensorDeviceClass.WIND_SPEED, "km/h", SensorStateClass.MEASUREMENT),
    "baro": RFBridgeMeasurementDescription("barometric_pressure", "Barometric pressure", "mdi:gauge", SensorDeviceClass.PRESSURE, "hPa", SensorStateClass.MEASUREMENT),
    "bat": RFBridgeMeasurementDescription("battery", "Battery", "mdi:battery"),
    "bforecast": RFBridgeMeasurementDescription("weather_forecast", "Weather forecast", "mdi:weather-cloudy-clock"),
    "co2": RFBridgeMeasurementDescription("co2_air_quality", "CO2 air quality", "mdi:molecule-co2", SensorDeviceClass.CO2, "ppm", SensorStateClass.MEASUREMENT),
    "current": RFBridgeMeasurementDescription("current_phase_1", "Current", "mdi:current-ac", SensorDeviceClass.CURRENT, "A", SensorStateClass.MEASUREMENT),
    "current2": RFBridgeMeasurementDescription("current_phase_2", "Current phase 2", "mdi:current-ac", SensorDeviceClass.CURRENT, "A", SensorStateClass.MEASUREMENT),
    "current3": RFBridgeMeasurementDescription("current_phase_3", "Current phase 3", "mdi:current-ac", SensorDeviceClass.CURRENT, "A", SensorStateClass.MEASUREMENT),
    "dist": RFBridgeMeasurementDescription("distance", "Distance", "mdi:map-marker-distance", SensorDeviceClass.DISTANCE, "mm", SensorStateClass.MEASUREMENT),
    "hstatus": RFBridgeMeasurementDescription("humidity_status", "Humidity status", "mdi:water-percent"),
    "hum": RFBridgeMeasurementDescription("humidity", "Humidity", "mdi:water-percent", SensorDeviceClass.HUMIDITY, "%", SensorStateClass.MEASUREMENT),
    "kwatt": RFBridgeMeasurementDescription("kilowatt", "Power", "mdi:flash", SensorDeviceClass.POWER, "kW", SensorStateClass.MEASUREMENT),
    "lux": RFBridgeMeasurementDescription("light_intensity", "Illuminance", "mdi:brightness-5", SensorDeviceClass.ILLUMINANCE, "lx", SensorStateClass.MEASUREMENT),
    "meter": RFBridgeMeasurementDescription("meter_value", "Meter value", "mdi:counter"),
    "rain": RFBridgeMeasurementDescription("rain", "Rain", "mdi:weather-rainy", SensorDeviceClass.PRECIPITATION, "mm", SensorStateClass.TOTAL_INCREASING),
    "rainrate": RFBridgeMeasurementDescription("rain_rate", "Rain rate", "mdi:weather-pouring", SensorDeviceClass.PRECIPITATION_INTENSITY, "mm/h", SensorStateClass.MEASUREMENT),
    "raintot": RFBridgeMeasurementDescription("total_rain", "Total rain", "mdi:weather-rainy", SensorDeviceClass.PRECIPITATION, "mm", SensorStateClass.TOTAL_INCREASING),
    "temp": RFBridgeMeasurementDescription("temperature", "Temperature", "mdi:thermometer", SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, SensorStateClass.MEASUREMENT),
    "tempd": RFBridgeMeasurementDescription("temperature", "Temperature", "mdi:thermometer", SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, SensorStateClass.MEASUREMENT),
    "sound": RFBridgeMeasurementDescription("noise_level", "Noise level", "mdi:bell-alert"),
    "uv": RFBridgeMeasurementDescription("uv_intensity", "UV index", "mdi:sunglasses", None, None, SensorStateClass.MEASUREMENT),
    "volt": RFBridgeMeasurementDescription("voltage", "Voltage", "mdi:flash-outline", SensorDeviceClass.VOLTAGE, "V", SensorStateClass.MEASUREMENT),
    "watt": RFBridgeMeasurementDescription("watt", "Power", "mdi:flash", SensorDeviceClass.POWER, "W", SensorStateClass.MEASUREMENT),
    "winchl": RFBridgeMeasurementDescription("windchill", "Wind chill", "mdi:thermometer", SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, SensorStateClass.MEASUREMENT),
    "windir": RFBridgeMeasurementDescription("winddirection", "Wind direction", "mdi:compass", SensorDeviceClass.WIND_DIRECTION, DEGREE, SensorStateClass.MEASUREMENT_ANGLE),
    "wind": RFBridgeMeasurementDescription("windspeed", "Wind speed", "mdi:weather-windy", SensorDeviceClass.WIND_SPEED, "km/h", SensorStateClass.MEASUREMENT),
    "wings": RFBridgeMeasurementDescription("windgusts", "Wind gust", "mdi:weather-windy", SensorDeviceClass.WIND_SPEED, "km/h", SensorStateClass.MEASUREMENT),
    "winsp": RFBridgeMeasurementDescription("windspeed", "Wind speed", "mdi:weather-windy", SensorDeviceClass.WIND_SPEED, "km/h", SensorStateClass.MEASUREMENT),
    "wintmp": RFBridgeMeasurementDescription("windtemp", "Wind temperature", "mdi:thermometer", SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, SensorStateClass.MEASUREMENT),
}
MEASUREMENTS_BY_KEY = {description.key: description for description in MEASUREMENTS.values()}


def _decode_hex(value: str) -> int | None:
    try:
        return int(value, 16)
    except ValueError:
        return None


def _decode_signed_tenths(value: str) -> float | None:
    integer = _decode_hex(value)
    if integer is None:
        return None
    return -(integer & 0x7FFF) / 10 if integer & 0x8000 else integer / 10


def _decode_measurement(field: str, value: str) -> str | int | float | None:
    if field == "bat":
        return value.upper()
    if field == "bforecast":
        return {
            0: "No information",
            1: "Sunny",
            2: "Partly cloudy",
            3: "Cloudy",
            4: "Rain",
        }.get(_decode_hex(value), "Unknown")
    if field in {"temp", "winchl", "wintmp"}:
        return _decode_signed_tenths(value)
    if field == "tempd":
        try:
            return float(value)
        except ValueError:
            return None
    if field in {"awinsp", "rain", "rainrate", "raintot", "wings", "winsp"}:
        integer = _decode_hex(value)
        return integer / 10 if integer is not None else None
    if field == "windir":
        try:
            return int(value) * 22.5
        except ValueError:
            return None
    if field in {"baro", "kwatt", "lux", "uv", "watt"}:
        return _decode_hex(value)
    if field == "hstatus":
        return {0: "Normal", 1: "Comfortable", 2: "Dry", 3: "Wet"}.get(
            _decode_hex(value), "Unknown"
        )
    try:
        return int(value)
    except ValueError:
        return None


def _sensor_token(protocol: str, identifier: str, measurement_key: str) -> str:
    value = f"{protocol}\x1f{identifier}\x1f{measurement_key}".encode()
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _sensor_identity(entry_id: str, protocol: str, identifier: str, measurement_key: str) -> str:
    return f"{entry_id}_rf_sensor_{_sensor_token(protocol, identifier, measurement_key)}"


def _decode_sensor_identity(entry_id: str, unique_id: str) -> tuple[str, str, str] | None:
    prefix = f"{entry_id}_rf_sensor_"
    if not unique_id.startswith(prefix):
        return None
    try:
        token = unique_id.removeprefix(prefix)
        padding = "=" * (-len(token) % 4)
        protocol, identifier, measurement_key = base64.urlsafe_b64decode(token + padding).decode("utf-8").split("\x1f")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    if not protocol or not identifier or measurement_key not in MEASUREMENTS_BY_KEY:
        return None
    return protocol, identifier, measurement_key


class RFBridgeSensor(SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: RFBridgeHub, description: RFBridgeSensorDescription) -> None:
        self._hub = hub
        self._description = description
        self._attr_icon = description.icon
        self._attr_name = description.name
        self._attr_unique_id = f"{hub.entry.entry_id}_{description.key}"
        self._attr_device_class = description.device_class

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, diagnostics_signal(self._hub.entry.entry_id), self.async_write_ha_state))

    @property
    def available(self) -> bool:
        return self._hub.available

    @property
    def device_info(self) -> dict[str, object]:
        return self._hub.device_info

    @property
    def native_value(self) -> str | datetime | None:
        return self._description.value_fn(self._hub)


class RFBridgeDiscoveredSensor(RestoreSensor):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hub: RFBridgeHub,
        entry: ConfigEntry,
        protocol: str,
        identifier: str,
        description: RFBridgeMeasurementDescription,
        value: str | float | None = None,
        create_device: bool = True,
    ) -> None:
        self._hub = hub
        self._description = description
        self._value = value
        self._attr_unique_id = _sensor_identity(
            entry.entry_id, protocol, identifier, description.key
        )
        self._attr_name = description.name
        self._attr_icon = description.icon
        self._attr_device_class = description.device_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_state_class = description.state_class
        if create_device:
            self._attr_device_info = {
                "identifiers": {
                    (
                        DOMAIN,
                        f"{entry.entry_id}_{protocol.lower()}_{identifier.lower()}",
                    )
                },
                "name": f"{protocol} {identifier}",
                "manufacturer": "433 MHz",
                "model": protocol,
            }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                diagnostics_signal(self._hub.entry.entry_id),
                self.async_write_ha_state,
            )
        )
        if self._value is not None:
            return
        state = await self.async_get_last_state()
        if state is not None and state.state not in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
            self._value = state.state

    @property
    def available(self) -> bool:
        return self._hub.available

    @property
    def native_value(self) -> str | int | float | None:
        return self._value

    def async_set_value(self, value: str | float) -> None:
        if self._value == value:
            return
        self._value = value
        self.async_write_ha_state()


class RFBridgeLegacySensorManager:
    """Keep pre-discovery sensor entities updating without creating new ones."""

    def __init__(self, hass: HomeAssistant, hub: RFBridgeHub) -> None:
        self._hub = hub
        self._sensors: dict[tuple[str, str, str], RFBridgeDiscoveredSensor] = {}
        registry = er.async_get(hass)
        for entity_entry in er.async_entries_for_config_entry(
            registry, hub.entry.entry_id
        ):
            if entity_entry.domain != "sensor":
                continue
            identity = _decode_sensor_identity(
                hub.entry.entry_id, entity_entry.unique_id
            )
            if identity is None:
                continue
            protocol, identifier, measurement_key = identity
            description = MEASUREMENTS_BY_KEY[measurement_key]
            self._sensors[identity] = RFBridgeDiscoveredSensor(
                hub,
                hub.entry,
                protocol,
                identifier,
                description,
                create_device=False,
            )

    @property
    def identities(self) -> set[tuple[str, str]]:
        return {(protocol, identifier) for protocol, identifier, _ in self._sensors}

    def create_entities(self) -> list[RFBridgeDiscoveredSensor]:
        return list(self._sensors.values())

    @callback
    def handle_event(self, event: dict[str, Any]) -> None:
        if event.get("raw") is True:
            return
        message = event.get("message")
        if not isinstance(message, str):
            return
        data = parse_rflink_message(message)
        protocol = data.get("protocol")
        identifier = data.get("id")
        if not isinstance(protocol, str) or not isinstance(identifier, str):
            return
        for (sensor_protocol, sensor_identifier, key), sensor in self._sensors.items():
            if (sensor_protocol, sensor_identifier) != (protocol, identifier):
                continue
            raw_value = data.get(key)
            if (
                isinstance(raw_value, str)
                and (value := _decode_measurement(key, raw_value)) is not None
            ):
                sensor.async_set_value(value)


class RFBridgePendingSensorDiscoveryManager:
    """Offer unseen decoded sensors through Home Assistant discovery."""

    def __init__(
        self,
        hass: HomeAssistant,
        hub: RFBridgeHub,
        legacy_identities: set[tuple[str, str]],
    ) -> None:
        self._hass = hass
        self._hub = hub
        self._pending: set[tuple[str, str]] = set()
        self._accepted = legacy_identities | {
            (entry.data.get(CONF_PROTOCOL), entry.data.get(CONF_SENSOR_IDENTIFIER))
            for entry in hass.config_entries.async_entries(DOMAIN)
            if is_sensor_entry(entry)
            and entry.data.get(CONF_PARENT_ENTRY_ID) == hub.entry.entry_id
            and isinstance(entry.data.get(CONF_PROTOCOL), str)
            and isinstance(entry.data.get(CONF_SENSOR_IDENTIFIER), str)
        }

    @callback
    def handle_event(self, event: dict[str, Any]) -> None:
        if self._hub.entry.options.get(CONF_SENSOR_DISCOVERY, True) is not True:
            return
        if event.get("raw") is True:
            return
        message = event.get("message")
        if not isinstance(message, str):
            return
        data = parse_rflink_message(message)
        protocol = data.get("protocol")
        identifier = data.get("id")
        if not isinstance(protocol, str) or not isinstance(identifier, str):
            return
        measurement_keys = sorted(
            key
            for key in MEASUREMENTS
            if isinstance(data.get(key), str)
            and _decode_measurement(key, data[key]) is not None
        )
        if not measurement_keys:
            return
        sensor_key = (protocol, identifier)
        if sensor_key in self._accepted or sensor_key in self._pending:
            return
        self._pending.add(sensor_key)
        self._hass.async_create_task(
            self._hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_INTEGRATION_DISCOVERY},
                data={
                    CONF_PARENT_ENTRY_ID: self._hub.entry.entry_id,
                    CONF_PROTOCOL: protocol,
                    CONF_SENSOR_IDENTIFIER: identifier,
                    CONF_SENSOR_MEASUREMENTS: measurement_keys,
                },
            )
        )


class RFBridgeAcceptedSensorManager:
    """Maintain an accepted sensor's entities from the bridge event stream."""

    def __init__(
        self,
        hub: RFBridgeHub,
        entry: ConfigEntry,
    ) -> None:
        self._hub = hub
        self._entry = entry
        self._protocol = entry.data[CONF_PROTOCOL]
        self._identifier = entry.data[CONF_SENSOR_IDENTIFIER]
        self._sensors: dict[str, RFBridgeDiscoveredSensor] = {}

    def create_entities(self) -> list[RFBridgeDiscoveredSensor]:
        entities = []
        for key in self._entry.data.get(CONF_SENSOR_MEASUREMENTS, []):
            description = MEASUREMENTS_BY_KEY.get(key)
            if description is None:
                continue
            sensor = RFBridgeDiscoveredSensor(
                self._hub, self._entry, self._protocol, self._identifier, description
            )
            self._sensors[description.key] = sensor
            entities.append(sensor)
        return entities

    @callback
    def handle_event(self, event: dict[str, Any]) -> None:
        if event.get("raw") is True:
            return
        message = event.get("message")
        if not isinstance(message, str):
            return
        data = parse_rflink_message(message)
        if data.get("protocol") != self._protocol or data.get("id") != self._identifier:
            return
        for key, sensor in self._sensors.items():
            raw_value = data.get(key)
            if (
                isinstance(raw_value, str)
                and (value := _decode_measurement(key, raw_value)) is not None
            ):
                sensor.async_set_value(value)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    if is_sensor_entry(entry):
        parent_entry_id = entry.data[CONF_PARENT_ENTRY_ID]
        hub: RFBridgeHub = hass.data[DOMAIN][parent_entry_id]
        manager = RFBridgeAcceptedSensorManager(hub, entry)
        async_add_entities(manager.create_entities())
        entry.async_on_unload(
            async_dispatcher_connect(
                hass, rf_event_signal(parent_entry_id), manager.handle_event
            )
        )
        return

    hub: RFBridgeHub = hass.data[DOMAIN][entry.entry_id]
    legacy_manager = RFBridgeLegacySensorManager(hass, hub)
    discovery_manager = RFBridgePendingSensorDiscoveryManager(
        hass, hub, legacy_manager.identities
    )
    async_add_entities(
        [RFBridgeSensor(hub, description) for description in SENSORS]
        + legacy_manager.create_entities()
    )

    @callback
    def handle_event(event: dict[str, Any]) -> None:
        legacy_manager.handle_event(event)
        discovery_manager.handle_event(event)

    entry.async_on_unload(
        async_dispatcher_connect(hass, rf_event_signal(entry.entry_id), handle_event)
    )
