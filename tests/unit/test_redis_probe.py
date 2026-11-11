import socket
import threading
import time

import pytest
import redis

from app import health
from app.config import settings
from app.utils import connection

# what a Redis answers to `HELLO 3`: a map, at least with the protocol
HELLO_REPLY = (
    b"%3\r\n$6\r\nserver\r\n$5\r\nredis\r\n$7\r\nversion\r\n$5\r\n7.2.0\r\n"
    b"$5\r\nproto\r\n:3\r\n"
)


class FakeRedis:
    """A server on a local port, to see what a client does with it.

    :param behaviour: "silent" accepts connections and never answers,
        "closing" accepts and closes at once, "pong" answers `+PONG`
    """

    def __init__(self, behaviour: str):
        self.behaviour = behaviour
        self.accepted = 0
        self._held: list[socket.socket] = []
        self._server = socket.socket()
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(50)
        self.port = self._server.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                client, _ = self._server.accept()
            except OSError:
                return
            self.accepted += 1
            if self.behaviour == "closing":
                client.close()
            elif self.behaviour == "pong":
                threading.Thread(target=self._pong, args=(client,), daemon=True).start()
            else:
                self._held.append(client)

    @staticmethod
    def _pong(client: socket.socket):
        """Answer the commands (RESP arrays) of a client, as a Redis would:
        an error to HELLO (the client then speaks RESP2), OK to CLIENT, PONG"""
        buffer = b""
        while True:
            data = client.recv(1024)
            if not data:
                return
            buffer += data
            # each command is "*<n>\r\n" then n times "$<len>\r\n<arg>\r\n"
            while buffer.startswith(b"*"):
                parts = buffer.split(b"\r\n")
                count = int(parts[0][1:])
                if len(parts) < 1 + 2 * count + 1:
                    break  # the command is not complete yet
                command = parts[2].upper()
                buffer = b"\r\n".join(parts[1 + 2 * count :])
                client.sendall(
                    {
                        b"HELLO": HELLO_REPLY,
                        b"PING": b"+PONG\r\n",
                        b"CLIENT": b"+OK\r\n",
                    }.get(command, b"-ERR unknown command\r\n")
                )

    def close(self):
        self._server.close()
        for client in self._held:
            client.close()


@pytest.fixture
def fake_redis(monkeypatch):
    """Make the application use a FakeRedis, built with `fake_redis(behaviour)`"""
    servers: list[FakeRedis] = []

    def use(behaviour: str) -> FakeRedis:
        server = FakeRedis(behaviour)
        servers.append(server)
        monkeypatch.setattr(settings, "redis_host", "127.0.0.1")
        monkeypatch.setattr(settings, "redis_port", server.port)
        return server

    # short, so that the tests do not wait for the real timeout
    monkeypatch.setattr(connection, "REDIS_PROBE_TIMEOUT", 0.5)
    yield use
    for server in servers:
        server.close()


def test_probe_client_gives_up_on_a_redis_that_never_answers(fake_redis):
    """It used to wait forever: only the connection had a timeout"""
    fake_redis("silent")
    started = time.perf_counter()
    with pytest.raises(redis.TimeoutError):
        connection.get_redis_probe_client().ping()
    assert time.perf_counter() - started < 5


def test_probe_client_does_not_try_again(fake_redis):
    """By default redis-py makes 11 attempts against a Redis that drops us"""
    server = fake_redis("closing")
    with pytest.raises(redis.ConnectionError):
        connection.get_redis_probe_client().ping()
    assert server.accepted == 1


def test_default_client_still_tries_again(fake_redis):
    """Control: the retries are specific to the probe client"""
    server = fake_redis("closing")
    with pytest.raises(redis.ConnectionError):
        connection.get_redis_client(socket_connect_timeout=1).ping()
    assert server.accepted > 1


def test_probe_client_gets_the_answer_of_a_redis(fake_redis):
    fake_redis("pong")
    assert connection.get_redis_probe_client().ping() is True


def test_health_check_redis_gives_up_on_a_redis_that_never_answers(fake_redis):
    fake_redis("silent")
    started = time.perf_counter()
    with pytest.raises(redis.TimeoutError):
        health.test_connect_redis()
    assert time.perf_counter() - started < 5


def test_health_check_redis_passes_with_a_redis_that_answers(fake_redis):
    fake_redis("pong")
    assert health.test_connect_redis() == (True, "Redis connection check succedded!")
