"""单实例:基于 QLocalServer/QLocalSocket;重复启动时唤醒已有实例。

选用本地套接字而非 QSharedMemory,避免进程异常退出后残留锁段、导致再也打不开。
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from src.core.logger import get_logger

log = get_logger("single_instance")

_SERVER_NAME = "SnapOCR_SingleInstance"
_WAKE_MSG = b"WAKE_UP"


class SingleInstance(QObject):
    """单实例守卫。

    典型用法::

        guard = SingleInstance()
        if guard.is_running():
            guard.send_wake()      # 唤醒已有实例后自身退出
            sys.exit(0)
        guard.start_server()       # 当前为首个实例,监听后续唤醒
        guard.activated.connect(window.show_and_raise)
    """

    activated = Signal()  # 收到其它实例的唤醒请求时发射

    def __init__(self) -> None:
        super().__init__()
        self._server: QLocalServer | None = None
        self._already_running = self._probe()

    def _probe(self) -> bool:
        """尝试连接已有 server,判断是否已有实例在运行。"""
        socket = QLocalSocket()
        socket.connectToServer(_SERVER_NAME)
        connected = socket.waitForConnected(300)
        if connected:
            socket.disconnectFromServer()
        return connected

    def is_running(self) -> bool:
        return self._already_running

    def send_wake(self) -> bool:
        """向已有实例发送唤醒消息;成功返回 True。"""
        socket = QLocalSocket()
        socket.connectToServer(_SERVER_NAME)
        if not socket.waitForConnected(300):
            return False
        socket.write(_WAKE_MSG)
        socket.flush()
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        return True

    def start_server(self) -> None:
        """作为首个实例开始监听后续唤醒请求。"""
        # 清理可能残留的同名 server(上次异常退出留下的)
        QLocalServer.removeServer(_SERVER_NAME)
        self._server = QLocalServer(self)
        if not self._server.listen(_SERVER_NAME):
            log.warning("单实例监听失败:%s", self._server.errorString())
            return
        self._server.newConnection.connect(self._on_new_connection)
        log.info("单实例服务已监听:%s", _SERVER_NAME)

    def _on_new_connection(self) -> None:
        if self._server is None:
            return
        conn = self._server.nextPendingConnection()
        if conn is None:
            return
        if conn.waitForReadyRead(300):
            _ = conn.readAll()  # 读取唤醒消息(当前只关心“收到”这一事件)
        conn.disconnectFromServer()
        log.info("收到唤醒请求,激活主界面")
        self.activated.emit()
