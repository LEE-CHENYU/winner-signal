"""Run one API and one worker sharing a volume; restart the machine if either exits."""

import signal
import subprocess
import sys
import time
from analysis.storage import init_db

init_db()
children = []
stopping = False


def stop(signum, frame):
    global stopping
    stopping = True
    for child in children:
        if child.poll() is None:
            child.terminate()


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
children.append(
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "analysis.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--proxy-headers",
            "--no-access-log",
        ]
    )
)
children.append(subprocess.Popen([sys.executable, "-m", "analysis.worker"]))
while not stopping and all(child.poll() is None for child in children):
    time.sleep(1)
failed = not stopping
stop(None, None)
for child in children:
    try:
        child.wait(timeout=20)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()
sys.exit(1 if failed else 0)
