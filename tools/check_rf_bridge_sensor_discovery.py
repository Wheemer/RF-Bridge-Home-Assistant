"""Check that RF Bridge uses native pending-discovery entries for RF sensors."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SENSOR = (ROOT / "custom_components/rf_bridge/sensor.py").read_text()
FLOW = (ROOT / "custom_components/rf_bridge/config_flow.py").read_text()
INIT = (ROOT / "custom_components/rf_bridge/__init__.py").read_text()

assert "SOURCE_INTEGRATION_DISCOVERY" in SENSOR
assert "flow.async_init(" in SENSOR
assert "async_step_integration_discovery" in FLOW
assert "async_step_sensor_confirm" in FLOW
assert "ENTRY_TYPE_SENSOR" in FLOW
assert "if is_sensor_entry(entry):" in INIT
assert 'async_forward_entry_setups(entry, ["sensor"])' in INIT
assert "rf_event_signal(parent_entry_id)" in SENSOR
assert "class RFBridgeLegacySensorManager" in SENSOR
assert "legacy_manager.handle_event(event)" in SENSOR
print("rf_bridge_sensor_discovery=passed")
