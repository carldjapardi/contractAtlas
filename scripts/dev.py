"""Run both local development servers and stop the pair together."""

from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    if not (ROOT / "frontend/node_modules").exists():
        raise SystemExit("Install frontend dependencies first: npm --prefix frontend ci")
    commands = [
        [sys.executable, "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "8000", "--reload"],
        ["npm", "--prefix", "frontend", "run", "dev", "--", "--port", "5173", "--strictPort"],
    ]
    children = []

    def stop(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        for command in commands:
            children.append(subprocess.Popen(command, cwd=ROOT, start_new_session=True))
        print("Contract Atlas: http://127.0.0.1:5173\nAPI docs: http://127.0.0.1:8000/docs", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.25)
        raise SystemExit(next((child.returncode for child in children if child.returncode), 0))
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                try:
                    import os
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                import os
                os.killpg(child.pid, signal.SIGKILL)


if __name__ == "__main__":
    main()
