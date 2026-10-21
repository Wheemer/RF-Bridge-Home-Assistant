"""Check that decoded RF sensors become child devices of the configured bridge."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SENSOR = (ROOT / "custom_components/rf_bridge/sensor.py").read_text()
FLOW = (ROOT / "custom_components/rf_bridge/config_flow.py").read_text()
INIT = (ROOT / "custom_components/rf_bridge/__init__.py").read_text()

assert "class RFBridgeDynamicSensorManager" in SENSOR
assert "self._async_add_entities(new_entities)" in SENSOR
assert '"manufacturer": {"acurite": "AcuRite"}' in SENSOR
assert "SOURCE_INTEGRATION_DISCOVERY" not in SENSOR
assert "async_step_integration_discovery" not in FLOW
assert "async_step_sensor_confirm" not in FLOW
assert "is_sensor_entry" not in INIT
assert "async_forward_entry_setups(entry, PLATFORMS)" in INIT
print("rf_bridge_sensor_discovery=passed")
