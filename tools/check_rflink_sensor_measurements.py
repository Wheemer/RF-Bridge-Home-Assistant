"""Validate stable decoded sensor-device discovery under the existing bridge."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from custom_components.rf_bridge import sensor as sensor_module
from custom_components.rf_bridge.sensor import (
    RFBridgeDynamicSensorManager,
    _decode_measurement,
)


def check_measurements() -> None:
    assert _decode_measurement("temp", "00c8") == 20.0
    assert _decode_measurement("hum", "42") == 42


def check_dynamic_sensor_device() -> None:
    added = []
    hub = SimpleNamespace(
        entry=SimpleNamespace(
            entry_id="bridge-entry", options={"sensor_discovery": True}
        )
    )
    hass = SimpleNamespace()
    event = {
        "raw": False,
        "message": "20;AF;AcuRite 986;ID=ff02;TEMP=00c8;HUM=42;BAT=OK;",
    }
    original_get = sensor_module.er.async_get
    original_entries = sensor_module.er.async_entries_for_config_entry
    original_monotonic = sensor_module.monotonic
    sensor_module.er.async_get = lambda _hass: object()
    sensor_module.er.async_entries_for_config_entry = lambda _registry, _entry_id: []
    timestamps = iter((0.0, 6.0, 12.0))
    sensor_module.monotonic = lambda: next(timestamps)
    try:
        manager = RFBridgeDynamicSensorManager(
            hass, hub, lambda entities: added.extend(entities)
        )
        manager.handle_event(event)
        manager.handle_event(event)
        assert added == []
        manager.handle_event(event)
    finally:
        sensor_module.er.async_get = original_get
        sensor_module.er.async_entries_for_config_entry = original_entries
        sensor_module.monotonic = original_monotonic

    assert len(added) == 3
    assert {entity._attr_name for entity in added} == {
        "Temperature",
        "Humidity",
        "Battery",
    }
    assert all(
        entity._attr_device_info["name"] == "AcuRite 986 ff02" for entity in added
    )
    assert all(
        entity._attr_device_info["manufacturer"] == "AcuRite" for entity in added
    )
    assert all(entity._attr_device_info["model"] == "986" for entity in added)


if __name__ == "__main__":
    check_measurements()
    check_dynamic_sensor_device()
    print("rflink_sensor_measurements=passed")
