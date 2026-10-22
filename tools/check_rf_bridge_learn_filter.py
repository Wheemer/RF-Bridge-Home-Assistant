"""Validate configured-command filtering for the RF Bridge learn flow."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import custom_components.rf_bridge as integration
from custom_components.rf_bridge import RFBridgeHub, is_known_rf_event

KNOWN = {"newkaku_01234567_1_on": {"name": "Kitchen remote on"}}


def main() -> None:
    known_event = {"message": "20;00;NewKaku;ID=01234567;SWITCH=1;CMD=ON;"}
    unknown_decoded_event = {"message": "20;00;NewKaku;ID=89ABCDEF;SWITCH=1;CMD=ON;"}
    raw_event = {"raw": True, "command": "10;signal;sendRF;{...}"}

    assert is_known_rf_event(known_event, KNOWN)
    assert not is_known_rf_event(unknown_decoded_event, KNOWN)
    assert not is_known_rf_event(raw_event, KNOWN)

    dispatched: list[dict[str, object]] = []
    original_dispatch = integration.async_dispatcher_send
    integration.async_dispatcher_send = lambda _hass, _signal, event: dispatched.append(
        event
    )
    try:
        hub = object.__new__(RFBridgeHub)
        hub.entry = type(
            "Entry",
            (),
            {"entry_id": "entry", "options": {"known_commands": KNOWN}},
        )()
        hub.status = {"raw_learning_armed": True}
        hub.host = "bridge"
        hub.hass = object()
        hub.last_rf_event = None
        hub.rf_event_cursor = 0
        hub._cancel_learning_expiry = lambda: None
        hub.async_write_diagnostics = lambda: None

        hub._handle_rf_event({**known_event, "sequence": 1})
        assert dispatched == []
        assert hub.status["raw_learning_armed"] is True

        hub._handle_rf_event({**unknown_decoded_event, "sequence": 2})
        assert len(dispatched) == 1
        assert dispatched[0]["learning"] is True
        assert dispatched[0]["candidate"] is True
        assert hub.status["raw_learning_armed"] is False

        # Any unrecognized RF frame is a valid learn candidate, including raw
        # protocols that do not have a built-in decoder.
        dispatched.clear()
        hub.status["raw_learning_armed"] = True
        hub._handle_rf_event({**raw_event, "sequence": 3})
        assert len(dispatched) == 1
        assert dispatched[0]["learning"] is True
        assert dispatched[0]["candidate"] is True
        assert hub.status["raw_learning_armed"] is False
    finally:
        integration.async_dispatcher_send = original_dispatch


if __name__ == "__main__":
    main()
