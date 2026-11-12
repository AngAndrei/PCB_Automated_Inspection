import importlib.util
import json
import os
import subprocess
import sys

import pytest


def test_fresh_process_disables_analytics_before_model_import(tmp_path):
    if importlib.util.find_spec("ultralytics") is None:
        pytest.skip("Optional ML runtime not installed")
    script = """
from pcb_inspection.runtime import configure_runtime
configure_runtime()
from ultralytics import settings
from ultralytics.utils import ONLINE
from ultralytics.utils.events import events
import json
print('RUNTIME_CHECK='+json.dumps({'sync':settings['sync'],'online':ONLINE,'analytics':events.enabled}))
"""
    env = dict(os.environ, YOLO_CONFIG_DIR=str(tmp_path / "settings"))
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=30
    )
    assert result.returncode == 0, result.stderr
    line = next(line for line in result.stdout.splitlines() if line.startswith("RUNTIME_CHECK="))
    assert json.loads(line.split("=", 1)[1]) == {"sync": False, "online": False, "analytics": False}
