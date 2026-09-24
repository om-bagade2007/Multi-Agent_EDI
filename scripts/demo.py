"""Validate Pune data, launch both local servers, and open the dashboard."""
from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = os.name == "nt"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def available_port(preferred: int) -> int:
    """Use the preferred demo port or find a free nearby port."""
    for port in range(preferred, preferred + 100):
        with socket.socket() as listener:
            try:
                listener.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise SystemExit(f"No free local port found starting at {preferred}.")


def main() -> None:
    """Start the Pune API and frontend, stopping both on exit."""
    sys.path.insert(0, str(ROOT / "backend"))
    from app.config import Settings
    from app.sim.pune_network import PuneNetwork

    try:
        PuneNetwork(Settings().pune_data_dir)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"Pune demo data is missing or invalid: {error}\nBuild it with: make pune-data") from error
    environment = os.environ.copy()
    environment["SIMULATION_MODE"] = "pune"
    environment.setdefault("VITE_SIMULATION_MODE", "pune")
    environment.setdefault("VITE_BASEMAP", "none")
    backend_port = available_port(8000)
    frontend_port = available_port(5173)
    environment["API_PROXY_TARGET"] = f"http://127.0.0.1:{backend_port}"
    backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(backend_port)], cwd=ROOT / "backend", env=environment, creationflags=NO_WINDOW)
    npm_command = ["npm.cmd" if WINDOWS else "npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(frontend_port), "--strictPort"]
    frontend = None
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline and backend.poll() is None:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{backend_port}/health", timeout=2) as response:
                    import json
                    health = json.loads(response.read())
                if health.get("status") != "ok" or health.get("mode") != "pune":
                    detail = health.get("detail", "unexpected backend mode")
                    raise SystemExit(f"Pune backend health check failed: {detail}\nRun `make pune-data` and restart.")
                break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(.4)
        else:
            raise SystemExit("Backend failed to start or health check timed out.")
        frontend = subprocess.Popen(npm_command, cwd=ROOT / "frontend", env=environment, creationflags=NO_WINDOW)
        time.sleep(2)
        if frontend.poll() is not None:
            raise SystemExit("Frontend server exited during startup.")
        demo_url = f"http://localhost:{frontend_port}"
        webbrowser.open(demo_url)
        print(f"Pune demo running at {demo_url}. Press Ctrl+C to stop both servers.")
        while backend.poll() is None and frontend.poll() is None:
            time.sleep(1)
        raise SystemExit("A demo server exited unexpectedly.")
    except KeyboardInterrupt:
        print("Stopping Pune demo servers.")
    finally:
        for process in (frontend, backend):
            if process is not None and process.poll() is None:
                process.terminate()
        for process in (frontend, backend):
            if process is not None:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == "__main__":
    main()
