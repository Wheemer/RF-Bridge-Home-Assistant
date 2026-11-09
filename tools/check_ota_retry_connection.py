"""Exercise production OTA handoff without transmitting or installing firmware."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from custom_components.rf_bridge import RFBridgeHub
from custom_components.rf_bridge import update as update_module


async def main():
    hub = object.__new__(RFBridgeHub)
    hub.host = "test"
    hub._ota_quiet_until = 999999999999.0
    hub._ota_quiet_event = asyncio.Event()
    hub.async_write_diagnostics = lambda: None
    hub._ws = SimpleNamespace(closed=False, close=AsyncMock())

    async def request(*args, **kwargs):
        assert hub._ota_quiet_until == 0
        assert hub._ota_quiet_event.is_set()
        return {"type": "update_scheduled", "ok": True}

    hub._ws_request = request
    await hub.async_schedule_firmware_update("http://test/firmware")
    assert hub._ota_quiet_until > asyncio.get_running_loop().time()
    assert not hub._ota_quiet_event.is_set()
    hub._ws.close.assert_awaited_once()
    await hub.async_resume_after_firmware_update()
    assert hub._ota_quiet_event.is_set()
    entity = object.__new__(update_module.RFBridgeFirmwareUpdate)
    entity._install_lock = asyncio.Lock()
    entity._maintenance_store = SimpleNamespace(async_save=AsyncMock())
    entity.hass = SimpleNamespace()
    entity.async_write_ha_state = lambda: None
    entity._hub = SimpleNamespace(
        async_probe_status=AsyncMock(return_value={"sw_version": "1.0.36"}),
        async_resume_after_firmware_update=AsyncMock(),
        async_schedule_firmware_update=AsyncMock(),
    )
    original = update_module._async_fetch_release
    update_module._async_fetch_release = AsyncMock(
        return_value=SimpleNamespace(version="1.0.36")
    )
    try:
        await entity.async_install(None, False)
    finally:
        update_module._async_fetch_release = original
    entity._hub.async_schedule_firmware_update.assert_not_awaited()
    entity._hub.async_resume_after_firmware_update.assert_awaited_once()
    assert entity._maintenance_until == 0
    assert entity._installation_phase == "Finished"
    assert entity._attr_in_progress is False
    print("ota_retry_connection=passed")


asyncio.run(main())
