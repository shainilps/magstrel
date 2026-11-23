import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from magstrel import db


def pid_file() -> Path:
    return db.path().parent / "magstrel.pid"


def log_file() -> Path:
    return db.path().parent / "magstrel.log"


def running_pid() -> int | None:
    try:
        pid = int(pid_file().read_text())
    except (FileNotFoundError, ValueError):
        return None
    try:
        os.kill(pid, 0)  # signal 0 sends nothing: it only checks that the process exists
    except ProcessLookupError:
        pid_file().unlink(missing_ok=True)  # stale: the server died without `down`
        return None
    except PermissionError:
        pass  # exists, owned by someone else
    return pid


def start(server_args: list[str], url: str) -> int:
    # run `magstrel server ...` as a separate, detached process that outlives this terminal
    env = os.environ | {"MAGSTREL_DB": str(db.path())}
    command = [sys.executable, "-c", "from magstrel.cli import main; main()", "server", *server_args]
    with open(log_file(), "a") as log:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,  # own session: closing the terminal doesn't kill it
        )
    pid_file().write_text(str(process.pid))

    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pid_file().unlink(missing_ok=True)
            raise RuntimeError("the server exited right away:\n" + _tail(log_file()))
        try:
            urllib.request.urlopen(url, timeout=1).close()
            return process.pid
        except OSError:
            time.sleep(0.3)
    raise RuntimeError(f"the server didn't answer on {url} within 20s, see {log_file()}")


def stop(timeout: float = 15) -> int | None:
    pid = running_pid()
    if pid is None:
        return None
    os.kill(pid, signal.SIGTERM)  # polite: uvicorn shuts down cleanly on SIGTERM
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.2)
    else:
        os.kill(pid, signal.SIGKILL)  # still alive after the timeout: force it
    pid_file().unlink(missing_ok=True)
    return pid


def _tail(path: Path, lines: int = 20) -> str:
    return "\n".join(path.read_text(errors="replace").splitlines()[-lines:])
