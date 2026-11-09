"""Exercise RF Bridge OTA progress state without a running HA instance."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import homeassistant  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant.components.update import UpdateEntityFeature

from custom_components.rf_bridge import update as update_module
from custom_components.rf_bridge.update import RFBridgeFirmwareUpdate


def main() -> None:
    entity = object.__new__(RFBridgeFirmwareUpdate)
    assert entity.supported_features & UpdateEntityFeature.PROGRESS
    writes = 0

    def write_state() -> None:
        nonlocal writes
        writes += 1

    entity.async_write_ha_state = write_state
    entity._set_install_progress(35)
    assert entity._attr_in_progress is True
    assert entity._attr_update_percentage == 35
    assert writes == 1

    entity._set_install_progress(35)
    assert writes == 1

    entity._set_install_progress(85)
    assert entity._attr_update_percentage == 85
    assert writes == 2

    entity._set_install_progress(35)
    assert entity._attr_update_percentage == 85
    assert writes == 2

    entity._set_install_progress(90)
    assert entity._attr_update_percentage == 90
    assert writes == 3

    entity._set_install_progress(95)
    assert entity._attr_update_percentage == 95
    assert writes == 4

    entity._clear_install_progress()
    assert entity._attr_in_progress is False
    assert entity._attr_update_percentage is None
    assert writes == 5

    entity._transfer_complete = False
    entity._set_install_phase("Preparing firmware")
    assert entity._attr_in_progress is True
    assert entity._attr_update_percentage is None
    entity._report_bridge_download_progress(50, 100)
    assert entity._attr_update_percentage == 50
    entity._report_bridge_download_progress(100, 100)
    assert entity._attr_in_progress is True
    assert entity._attr_update_percentage is None
    assert "Verifying firmware / waiting for reboot" in entity.title
    entity._report_bridge_download_progress(10, 100)
    assert entity._attr_update_percentage is None
    before = writes
    entity._set_install_phase("Verifying firmware / waiting for reboot")
    assert writes == before
    asyncio.run(check_confirmation(entity))
    entity._clear_install_progress()
    assert entity._attr_in_progress is False
    assert entity.title == "RF Bridge firmware"


async def check_confirmation(entity):
    snapshots = []
    entity.async_write_ha_state = lambda: snapshots.append(
        (entity._attr_update_percentage, entity.title)
    )
    entity._hub = SimpleNamespace(
        status={"sw_version": "old"},
        async_probe_status=AsyncMock(side_effect=[
            {"sw_version": "old", "update_last_result": "staged"},
            {"sw_version": "new"},
        ]),
    )
    original = update_module.FIRMWARE_UPDATE_SETTLE_SECONDS
    update_module.FIRMWARE_UPDATE_SETTLE_SECONDS = 0
    try:
        assert await entity._async_wait_for_version("new")
    finally:
        update_module.FIRMWARE_UPDATE_SETTLE_SECONDS = original
    assert snapshots[0] == (
        None, "RF Bridge firmware: Rebooting / waiting for version confirmation"
    )
    assert snapshots[-1][0] == 100
    assert all(percent is None for percent, _ in snapshots[:-1])


if __name__ == "__main__":
    main()
    print("ota_update_progress=passed")
