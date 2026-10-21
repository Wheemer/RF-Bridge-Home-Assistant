"""Validate RFLink sensor fields against the firmware's display format."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from custom_components.rf_bridge import parse_rflink_message
from custom_components.rf_bridge import sensor as sensor_module
from custom_components.rf_bridge.sensor import (
    MEASUREMENTS,
    RFBridgeDiscoveredSensorManager,
    _decode_measurement,
    _sensor_identity,
)


def check_decoded_measurements() -> None:
    alecto = parse_rflink_message(
        "20;AF;Alecto V3;ID=009a;TEMP=8019;HUM=68;BFORECAST=04;HSTATUS=02;BAT=OK;"
    )
    assert alecto["protocol"] == "Alecto V3"
    assert alecto["id"] == "009a"
    assert _decode_measurement("temp", alecto["temp"]) == -2.5
    assert _decode_measurement("hum", alecto["hum"]) == 68
    assert _decode_measurement("bforecast", alecto["bforecast"]) == "Rain"
    assert _decode_measurement("hstatus", alecto["hstatus"]) == "Dry"

    hyundai = parse_rflink_message(
        "20;B0;Hyundai;ID=0af;TEMPD=-4.2;HUM=43;BAT=LOW;"
    )
    assert _decode_measurement("tempd", hyundai["tempd"]) == -4.2
    assert _decode_measurement("bat", hyundai["bat"]) == "LOW"

    oregon = parse_rflink_message(
        "20;B1;Oregon;ID=021d;RAIN=0014;RAINTOT=0064;RAINRATE=0003;"
    )
    assert _decode_measurement("rain", oregon["rain"]) == 2.0
    assert _decode_measurement("raintot", oregon["raintot"]) == 10.0
    assert _decode_measurement("rainrate", oregon["rainrate"]) == 0.3
    assert MEASUREMENTS["rain"].key == "rain"
    assert MEASUREMENTS["raintot"].key == "total_rain"


def check_discovery_lifecycle() -> None:
    added: list[object] = []
    hub = SimpleNamespace(entry=SimpleNamespace(entry_id="test-entry", options={}))
    manager = RFBridgeDiscoveredSensorManager(
        SimpleNamespace(), hub, lambda entities: added.extend(entities)
    )

    manager.handle_event(
        {
            "raw": True,
            "message": "20;B1;Oregon;ID=021d;TEMP=00c8;HUM=42;",
        }
    )
    assert not added

    manager.handle_event(
        {
            "raw": False,
            "message": "20;B1;Oregon;ID=021d;TEMP=00c8;HUM=42;",
        }
    )
    assert len(added) == 2
    assert {entity.name for entity in added} == {
        "Oregon 021d Temperature",
        "Oregon 021d Humidity",
    }

    disabled_added: list[object] = []
    disabled_hub = SimpleNamespace(
        entry=SimpleNamespace(entry_id="disabled-entry", options={"sensor_discovery": False})
    )
    disabled_manager = RFBridgeDiscoveredSensorManager(
        SimpleNamespace(), disabled_hub, lambda entities: disabled_added.extend(entities)
    )
    disabled_manager.handle_event(
        {
            "raw": False,
            "message": "20;B1;Oregon;ID=021d;TEMP=00c8;HUM=42;",
        }
    )
    assert not disabled_added


def check_registry_restore() -> None:
    hub = SimpleNamespace(entry=SimpleNamespace(entry_id="test-entry", options={}))
    manager = RFBridgeDiscoveredSensorManager(SimpleNamespace(), hub, lambda entities: None)
    registry = SimpleNamespace()
    entity_entry = SimpleNamespace(
        domain="sensor",
        unique_id=_sensor_identity("test-entry", "Alecto V3", "009a", "temperature"),
    )
    original_get = sensor_module.er.async_get
    original_entries = sensor_module.er.async_entries_for_config_entry
    sensor_module.er.async_get = lambda hass: registry
    sensor_module.er.async_entries_for_config_entry = lambda current, entry_id: [entity_entry]
    try:
        restored = manager.restore()
    finally:
        sensor_module.er.async_get = original_get
        sensor_module.er.async_entries_for_config_entry = original_entries
    assert len(restored) == 1
    assert restored[0].name == "Alecto V3 009a Temperature"


if __name__ == "__main__":
    check_decoded_measurements()
    check_discovery_lifecycle()
    check_registry_restore()
    print("rflink_sensor_measurements=passed")
