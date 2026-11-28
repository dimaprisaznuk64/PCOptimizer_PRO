"""PCOptimizer PRO — single-instance guard via QLocalServer.

Windows named pipe (QLocalSocket/QLocalServer) ensures only one copy of the
app runs. A second launch connects to the first instance's server, asks it to
show the window, then exits immediately.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

_SERVER_NAME = "PCOptimizer_PRO_single_instance_v1"
_SHOW = b"show"
_LOCK_TIMEOUT_MS = 4_000
_LOCK_STALE_MS = 10_000


class SingleInstanceGuard(QObject):
    """Owns the local server while this process is the primary instance."""

    show_requested = Signal()

    def __init__(self, name: str = _SERVER_NAME, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._name = name
        self._server: QLocalServer | None = None

    def acquire(self) -> bool:
        """True if this process becomes the primary instance.

        The connect is retried a few times: on a busy machine the first probe can
        time out even though a primary instance is alive, and treating that as
        "no primary" would let two copies run at once. The stale-server removal
        and the listen are serialized with a cross-process lock so two launches
        cannot remove each other's fresh server.
        """
        if self._probe():
            return False
        lock = QLockFile(str(self._lock_path()))
        lock.setStaleLockTime(_LOCK_STALE_MS)
        if not lock.tryLock(_LOCK_TIMEOUT_MS):
            lock.removeStaleLockFile()
            if not lock.tryLock(_LOCK_TIMEOUT_MS):
                return self._probe()
        try:
            if self._probe():
                return False
            QLocalServer.removeServer(self._name)
            server = QLocalServer(self)
            server.newConnection.connect(self._on_connection)
            if not server.listen(self._name):
                return False
            self._server = server
            return True
        finally:
            lock.unlock()

    def _lock_path(self) -> Path:
        digest = hashlib.sha256(self._name.encode("utf-8")).hexdigest()[:16]
        return Path(tempfile.gettempdir()) / f"pcopt_single_{digest}.lock"

    def _probe(self) -> bool:
        for _ in range(4):
            probe = QLocalSocket(self)
            probe.connectToServer(self._name)
            if probe.waitForConnected(500):
                probe.write(_SHOW)
                probe.flush()
                probe.waitForBytesWritten(500)
                probe.disconnectFromServer()
                return True
            probe.abort()
        return False

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
        QLocalServer.removeServer(self._name)

    def _on_connection(self) -> None:
        conn = self._server.nextPendingConnection() if self._server else None
        if conn is None:
            return
        conn.readyRead.connect(lambda: self._read(conn))
        conn.disconnected.connect(conn.deleteLater)

    def _read(self, conn: QLocalSocket) -> None:
        if bytes(conn.readAll().data()) == _SHOW:
            self.show_requested.emit()