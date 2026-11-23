import logging
import threading
from contextlib import closing
from datetime import UTC, datetime, timedelta

from magstrel import db
from magstrel.refresh import now_iso, refresh_all

log = logging.getLogger("magstrel")


class Refresher:
    def __init__(self, every: timedelta) -> None:
        self.every = every
        self._wake = threading.Event()  # set by trigger() ("refresh now") or stop()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="refresher", daemon=True)

    def start(self) -> None:
        with closing(db.connect()) as conn:
            # a previous server may have been killed mid-refresh and left "running" behind
            db.set_state(conn, refresh_status="idle", current_step=None)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def trigger(self) -> None:
        self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            if self._wake.is_set() or self._due():
                self._wake.clear()
                self._run()
                self._wake.clear()  # a "refresh now" click during the run is already covered
            self._wake.wait(timeout=60)

    def _due(self) -> bool:
        with closing(db.connect()) as conn:
            last = db.get_state(conn).get("last_run_finished_at")
        return last is None or datetime.fromisoformat(last) + self.every <= datetime.now(UTC)

    def _run(self) -> None:
        with closing(db.connect()) as conn:
            db.set_state(
                conn, refresh_status="running", current_step="starting", last_run_started_at=now_iso()
            )
            try:
                refresh_all(conn, step=lambda text: db.set_state(conn, current_step=text))
                result = "ok"
            except Exception as err:  # noqa: BLE001
                log.exception("refresh failed")
                result = f"failed: {err}"
            finished = datetime.now(UTC)
            db.set_state(
                conn,
                refresh_status="idle",
                current_step=None,
                last_run_result=result,
                last_run_finished_at=finished.isoformat(),
                next_run_at=(finished + self.every).isoformat(),
            )
