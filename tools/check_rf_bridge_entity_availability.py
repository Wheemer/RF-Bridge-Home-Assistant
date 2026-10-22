from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUTTON = ROOT / "custom_components" / "rf_bridge" / "button.py"
EVENT = ROOT / "custom_components" / "rf_bridge" / "event.py"
INIT = ROOT / "custom_components" / "rf_bridge" / "__init__.py"
SENSOR = ROOT / "custom_components" / "rf_bridge" / "sensor.py"
CONFIG_FLOW = ROOT / "custom_components" / "rf_bridge" / "config_flow.py"


def require(source: str, fragment: str, label: str) -> None:
    if fragment not in source:
        raise SystemExit(f"Missing {label}: {fragment}")


button = BUTTON.read_text(encoding="utf-8")
event = EVENT.read_text(encoding="utf-8")
init = INIT.read_text(encoding="utf-8")
sensor = SENSOR.read_text(encoding="utf-8")
config_flow = CONFIG_FLOW.read_text(encoding="utf-8")

for source, label in ((button, "button"), (event, "event")):
    require(
        source,
        "from homeassistant.helpers.dispatcher import async_dispatcher_connect",
        label,
    )
    require(source, "diagnostics_signal(self._hub.entry.entry_id)", label)
    require(source, "self.async_write_ha_state", label)

require(
    init,
    "@callback\n    def _async_publish_initial_diagnostics",
    "event-loop startup callback",
)
require(
    init,
    "async_call_later(hass, 0, _async_publish_initial_diagnostics)",
    "startup state refresh",
)
require(sensor, "class RFBridgeSensor", "bridge diagnostic sensor")
require(
    sensor,
    "async_add_entities([RFBridgeSensor(hub, description) for description in SENSORS])",
    "static bridge sensor setup",
)
if "RFBridgeDynamicSensorManager" in sensor:
    raise SystemExit("Environmental sensor discovery must not be present")
if "async_get_options_flow" in config_flow:
    raise SystemExit(
        "The removed sensor-discovery setting must not leave an options flow"
    )
