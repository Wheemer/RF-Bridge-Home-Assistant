"""Verify the RF Bridge integration side of the signed OTA contract."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    hub_source = (ROOT / "custom_components/rf_bridge/__init__.py").read_text(
        encoding="utf-8"
    )
    update_source = (ROOT / "custom_components/rf_bridge/update.py").read_text(
        encoding="utf-8"
    )

    for required in (
        "FIRMWARE_UPDATE_QUIET_SECONDS = 75",
        "self._ota_quiet_until",
        "self._ota_quiet_event = asyncio.Event()",
        "self._ota_quiet_event.wait()",
        "def async_resume_after_firmware_update(self)",
    ):
        if required not in hub_source:
            raise SystemExit(f"OTA reconnect contract is incomplete: {required}")

    for required in (
        "FIRMWARE_UPDATE_VERIFY_SECONDS = 75",
        "FIRMWARE_UPDATE_SETTLE_SECONDS = 3",
        "verified = await self._async_wait_for_version(release.version)",
        "self._hub.async_resume_after_firmware_update()",
        "def _set_install_progress(self, percentage: int)",
        "self._set_install_progress(35)",
        "def _report_bridge_download_progress(self, sent: int, total: int)",
        "self._set_install_progress(100)",
        "self._clear_install_progress()",
    ):
        if required not in update_source:
            raise SystemExit(f"OTA update contract is incomplete: {required}")

    print("ota_integration_lifecycle=passed")


if __name__ == "__main__":
    main()
