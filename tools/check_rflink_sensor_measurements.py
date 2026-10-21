"""Validate RFLink sensor parsing and pending-discovery behavior."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from custom_components.rf_bridge import parse_rflink_message
from custom_components.rf_bridge import sensor as sensor_module
from custom_components.rf_bridge.sensor import (
    MEASUREMENTS,
    RFBridgeLegacySensorManager,
    RFBridgePendingSensorDiscoveryManager,
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

    hyundai = parse_rflink_message("20;B0;Hyundai;ID=0af;TEMPD=-4.2;HUM=43;BAT=LOW;")
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


async def check_pending_discovery_lifecycle() -> None:
    calls: list[tuple[str, dict[str, object], dict[str, object]]] = []

    async def async_init(
        domain: str, *, context: dict[str, object], data: dict[str, object]
    ) -> None:
        calls.append((domain, context, data))

    parent_entry = SimpleNamespace(entry_id="parent-entry", options={})
    config_entries = SimpleNamespace(async_entries=lambda domain: [])
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_entries=config_entries.async_entries,
            flow=SimpleNamespace(async_init=async_init),
        ),
        async_create_task=lambda coroutine: asyncio.create_task(coroutine),
    )
    hub = SimpleNamespace(entry=parent_entry)

    original_get = sensor_module.er.async_get
    original_entries = sensor_module.er.async_entries_for_config_entry
    sensor_module.er.async_get = lambda hass: object()
    sensor_module.er.async_entries_for_config_entry = lambda registry, entry_id: []
    try:
        manager = RFBridgePendingSensorDiscoveryManager(hass, hub, set())
        manager.handle_event(
            {
                "raw": True,
                "message": "20;B1;Oregon;ID=021d;TEMP=00c8;HUM=42;",
            }
        )
        manager.handle_event(
            {
                "raw": False,
                "message": "20;B1;Oregon;ID=021d;TEMP=00c8;HUM=42;",
            }
        )
        manager.handle_event(
            {
                "raw": False,
                "message": "20;B1;Oregon;ID=021d;TEMP=00c8;HUM=42;",
            }
        )
        await asyncio.sleep(0)
    finally:
        sensor_module.er.async_get = original_get
        sensor_module.er.async_entries_for_config_entry = original_entries

    assert len(calls) == 1
    domain, context, data = calls[0]
    assert domain == "rf_bridge"
    assert context == {"source": "integration_discovery"}
    assert data["sensor_measurements"] == ["hum", "temp"]


def check_legacy_entities_are_not_rediscovered() -> None:
    legacy = SimpleNamespace(
        domain="sensor",
        unique_id=_sensor_identity("parent-entry", "Oregon", "021d", "temperature"),
    )
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda domain: []),
        async_create_task=lambda coroutine: coroutine.close(),
    )
    hub = SimpleNamespace(entry=SimpleNamespace(entry_id="parent-entry", options={}))
    original_get = sensor_module.er.async_get
    original_entries = sensor_module.er.async_entries_for_config_entry
    sensor_module.er.async_get = lambda hass: object()
    sensor_module.er.async_entries_for_config_entry = lambda registry, entry_id: [
        legacy
    ]
    try:
        legacy_manager = RFBridgeLegacySensorManager(hass, hub)
        assert legacy_manager.identities == {("Oregon", "021d")}
        assert len(legacy_manager.create_entities()) == 1
        manager = RFBridgePendingSensorDiscoveryManager(
            hass, hub, legacy_manager.identities
        )
        manager.handle_event(
            {
                "raw": False,
                "message": "20;B1;Oregon;ID=021d;TEMP=00c8;HUM=42;",
            }
        )
    finally:
        sensor_module.er.async_get = original_get
        sensor_module.er.async_entries_for_config_entry = original_entries


if __name__ == "__main__":
    check_decoded_measurements()
    asyncio.run(check_pending_discovery_lifecycle())
    check_legacy_entities_are_not_rediscovered()
    print("rflink_sensor_measurements=passed")
