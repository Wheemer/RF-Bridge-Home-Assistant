"""Exercise the RF Bridge firmware download view without an HA server."""

from __future__ import annotations

import asyncio
import hashlib
import sys
import tempfile
from pathlib import Path

# Home Assistant installs its bundled validation compatibility layer during
# package import. Mirror that order before importing the integration.
import homeassistant  # noqa: F401
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.rf_bridge.update import FirmwareDownloadView


async def _check() -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        artifact = Path(temporary_directory) / "firmware.bin.gz.signed"
        payload = b"\x1f\x8b" + bytes(range(251)) * 1024 + b"signed-trailer"
        artifact.write_bytes(payload)

        view = FirmwareDownloadView()
        token = view.add(artifact)
        app = web.Application()
        app.router.add_get(
            "/firmware/{token}", lambda request: view.get(request, request.match_info["token"])
        )
        server = TestServer(app)
        client = TestClient(server)
        await client.start_server()
        try:
            response = await client.get(
                f"/firmware/{token}",
                headers={"Accept-Encoding": "identity;q=1,chunked;q=0.1,*;q=0"},
            )
            assert await response.read() == payload
            assert response.headers["Content-Length"] == str(len(payload))
            assert response.headers["Content-Encoding"] == "identity"
            assert response.headers["Content-Type"] == "application/octet-stream"
        finally:
            await client.close()

        audit = view.audit(token)
        assert audit is not None
        assert audit["requests"] == 1
        assert audit["artifact_bytes"] == len(payload)
        assert audit["artifact_sha256"] == hashlib.sha256(payload).hexdigest()


if __name__ == "__main__":
    asyncio.run(_check())
    print("firmware_download_view=passed")
