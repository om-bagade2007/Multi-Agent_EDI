"""Launch local API and dashboard processes, opening the UI in a browser."""
import os
from pathlib import Path
import subprocess
import sys
import time
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = os.name == "nt"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def main() -> None:
    """Start both development servers and keep them alive until interrupted."""
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=ROOT / "backend",
        creationflags=NO_WINDOW,
    )
    npm_command = ["npm.cmd", "run", "dev", "--", "--host", "127.0.0.1"] if WINDOWS else ["npm", "run", "dev", "--", "--host", "127.0.0.1"]
    frontend = subprocess.Popen(
        npm_command,
        cwd=ROOT / "frontend",
        shell=False,
        creationflags=NO_WINDOW,
    )
    try:
        time.sleep(2)
        webbrowser.open("http://localhost:5173")
        print("Dashboard running at http://localhost:5173. Press Ctrl+C to stop both servers.")
        while backend.poll() is None and frontend.poll() is None:
            time.sleep(1)
        if backend.poll() is not None or frontend.poll() is not None:
            raise SystemExit("A demo server exited unexpectedly.")
    except KeyboardInterrupt:
        print("Stopping demo servers.")
    finally:
        for process in (frontend, backend):
            if process.poll() is None:
                process.terminate()
        for process in (frontend, backend):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
