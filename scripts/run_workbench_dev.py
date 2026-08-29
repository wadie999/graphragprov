"""Start the workbench API and Vite frontend from the single TOML config."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from graphragprov.workbench_api.config import CONFIG_ENV, load_config  # noqa: E402


def main() -> None:
    config_path = Path(os.getenv(CONFIG_ENV, ROOT / "workbench.toml")).resolve()
    config = load_config(config_path)
    env = os.environ.copy()
    env[CONFIG_ENV] = str(config_path)
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env["GRAPHRAGPROV_API_PROXY"] = f"http://{config.host}:{config.port}"
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "graphragprov.workbench_api.app:app",
         "--host", config.host, "--port", str(config.port), "--reload"],
        cwd=ROOT, env=env,
    )
    frontend = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", config.host,
         "--port", str(config.frontend_dev_port)],
        cwd=ROOT / "frontend", env=env,
    )
    print(f"Workbench: http://{config.host}:{config.frontend_dev_port}")
    try:
        _wait(api, frontend)
    except KeyboardInterrupt:
        pass
    finally:
        _stop(api, frontend)


def _wait(*processes: subprocess.Popen[bytes]) -> None:
    while all(process.poll() is None for process in processes):
        time.sleep(0.5)


def _stop(*processes: subprocess.Popen[bytes]) -> None:
    for process in processes:
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()


if __name__ == "__main__":
    main()
