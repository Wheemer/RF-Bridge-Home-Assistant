"""Exercise production replay handling and acknowledgement through a fake socket."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from custom_components.rf_bridge import RFBridgeHub


async def main():
    hub = object.__new__(RFBridgeHub)
    handled = []
    requests = []
    tasks = []

    async def request(payload, **kwargs):
        requests.append(payload)
        return {"type": "learn_acknowledged"}

    def task(coroutine):
        result = asyncio.create_task(coroutine)
        tasks.append(result)
        return result

    hub.hass = SimpleNamespace(async_create_task=task)
    hub._handle_rf_event = lambda event: handled.append(event)
    hub._ws_request = request
    event = {"sequence": 42, "command": "waveform", "learn_capture": True}
    await hub._handle_ws_message({"type": "rf_event", "event": event}, persistent=True)
    await hub._handle_ws_message({"type": "rf_event", "event": event}, persistent=True)
    await asyncio.gather(*tasks)
    assert len(handled) == 1
    assert len(requests) == 2
    assert all(item == {"type": "learn_ack", "sequence": 42} for item in requests)


asyncio.run(main())
print("learn_receipt_replay=passed")
