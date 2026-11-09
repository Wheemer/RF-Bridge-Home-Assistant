"""Check actual update availability property under OTA/disconnect combinations."""
import ast
import time
from pathlib import Path
from types import SimpleNamespace

source = Path("custom_components/rf_bridge/update.py").read_text()
tree = ast.parse(source)
cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
           and node.name == "RFBridgeFirmwareUpdate")
method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
              and node.name == "available")
method.decorator_list = []
module = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
namespace = {"time": time}
exec(compile(module, "<production availability>", "exec"), namespace)  # noqa: S102 - trusted production AST
for connected, installing, expected in [
    (True, False, True), (False, False, False),
    (False, True, True), (True, True, True),
]:
    instance = SimpleNamespace(
        _hub=SimpleNamespace(available=connected), _attr_in_progress=installing
    )
    assert namespace["available"](instance) is expected
for deadline, expected in [(time.time() + 600, True), (time.time() - 1, False), (0, False)]:
    instance = SimpleNamespace(
        _hub=SimpleNamespace(available=False),
        _attr_in_progress=False,
        _maintenance_until=deadline,
    )
    assert namespace["available"](instance) is expected
install = next(node for node in cls.body if isinstance(node, ast.AsyncFunctionDef)
               and node.name == "async_install")
install_source = ast.get_source_segment(source, install)
assert install_source.index("async_save") < install_source.index("async_schedule_firmware_update")
assert 'async_save({"until": 0.0})' in install_source
assert "await self._async_wait_for_version" in install_source
print("update_availability_contract=passed")
