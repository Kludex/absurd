import asyncio

import absurd_sdk


def test_sync_absurd_prefers_absurd_database_url_over_pgdatabase(monkeypatch):
    captured = {}

    def fake_connect(dsn, autocommit=True):
        captured["dsn"] = dsn
        captured["autocommit"] = autocommit
        return object()

    monkeypatch.setenv("ABSURD_DATABASE_URL", "postgresql://localhost/absurd")
    monkeypatch.setenv("PGDATABASE", "postgresql://localhost/other")
    monkeypatch.setattr(absurd_sdk.Connection, "connect", fake_connect)

    absurd_sdk.Absurd()

    assert captured == {
        "dsn": "postgresql://localhost/absurd",
        "autocommit": True,
    }


def test_sync_absurd_falls_back_to_pgdatabase(monkeypatch):
    captured = {}

    def fake_connect(dsn, autocommit=True):
        captured["dsn"] = dsn
        return object()

    monkeypatch.delenv("ABSURD_DATABASE_URL", raising=False)
    monkeypatch.setenv("PGDATABASE", "postgresql://localhost/from-pgdatabase")
    monkeypatch.setattr(absurd_sdk.Connection, "connect", fake_connect)

    absurd_sdk.Absurd()

    assert captured["dsn"] == "postgresql://localhost/from-pgdatabase"


def test_async_absurd_falls_back_to_default_absurd_uri(monkeypatch):
    monkeypatch.delenv("ABSURD_DATABASE_URL", raising=False)
    monkeypatch.delenv("PGDATABASE", raising=False)

    client = absurd_sdk.AsyncAbsurd()

    assert client._conn_string == "postgresql://localhost/absurd"
    assert client._owned_conn is True


class _FakeAsyncConnection:
    def __init__(self):
        self.broken = False
        self.closed = False

    async def close(self):
        self.closed = True


def test_async_absurd_reuses_a_healthy_owned_connection(monkeypatch):
    connections = []

    async def fake_connect(dsn, autocommit=True):
        connection = _FakeAsyncConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(absurd_sdk.AsyncConnection, "connect", fake_connect)
    client = absurd_sdk.AsyncAbsurd("postgresql://localhost/absurd")

    asyncio.run(client._ensure_connected())
    asyncio.run(client._ensure_connected())

    assert len(connections) == 1
    assert client._conn is connections[0]


def test_async_absurd_replaces_an_interrupted_owned_connection(monkeypatch):
    connections = []

    async def fake_connect(dsn, autocommit=True):
        connection = _FakeAsyncConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(absurd_sdk.AsyncConnection, "connect", fake_connect)
    client = absurd_sdk.AsyncAbsurd("postgresql://localhost/absurd")

    asyncio.run(client._ensure_connected())
    connections[0].broken = True
    asyncio.run(client._ensure_connected())

    assert len(connections) == 2
    assert client._conn is connections[1]


def test_async_absurd_does_not_reconnect_after_an_explicit_close(monkeypatch):
    connections = []

    async def fake_connect(dsn, autocommit=True):
        connection = _FakeAsyncConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(absurd_sdk.AsyncConnection, "connect", fake_connect)
    client = absurd_sdk.AsyncAbsurd("postgresql://localhost/absurd")

    asyncio.run(client._ensure_connected())
    asyncio.run(client.close())
    asyncio.run(client._ensure_connected())

    assert len(connections) == 1
    assert client._conn is connections[0]


def test_async_absurd_does_not_replace_an_injected_broken_connection():
    connection = _FakeAsyncConnection()
    connection.broken = True
    client = absurd_sdk.AsyncAbsurd(connection)

    asyncio.run(client._ensure_connected())

    assert client._conn is connection
