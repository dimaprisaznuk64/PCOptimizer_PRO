"""PCOptimizer PRO — single-instance guard via QLocalServer.

Windows named pipe (QLocalSocket/QLocalServer) ensures only one copy of the
app runs. A second launch connects to the first instance's server, asks it to
show the window, then exits immediately.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

_SERVER_NAME = "PCOptimizer_PRO_single_instance_v1"
_SHOW = b"show"


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
        "no primary" would let two copies run at once.
        """
        for _ in range(4):
            probe = QLocalSocket(self)
            probe.connectToServer(self._name)
            if probe.waitForConnected(500):
                probe.write(_SHOW)
                probe.flush()
                probe.waitForBytesWritten(500)
                probe.disconnectFromServer()
                return False
            probe.abort()
        QLocalServer.removeServer(self._name)
        server = QLocalServer(self)
        server.newConnection.connect(self._on_connection)
        if not server.listen(self._name):
            return False
        self._server = server
        return True

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
        if bytes(conn.readAll()) == _SHOW:
            self.show_requested.emit()