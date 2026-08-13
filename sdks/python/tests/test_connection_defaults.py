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


class MockConnection:
    def __init__(self):
        self.broken = False
        self.closed = False

    async def close(self):
        self.closed = True


def test_async_absurd_replaces_an_interrupted_owned_connection(monkeypatch):
    made = []

    async def connect(dsn, autocommit=True):
        made.append(MockConnection())
        return made[-1]

    monkeypatch.setattr(absurd_sdk.AsyncConnection, "connect", connect)
    client = absurd_sdk.AsyncAbsurd("postgresql://localhost/absurd")

    async def run():
        await client._ensure_connected()
        made[0].broken = True
        await client._ensure_connected()

    asyncio.run(run())

    assert len(made) == 2
    assert client._conn is made[1]


def test_async_absurd_does_not_reconnect_after_an_explicit_close(monkeypatch):
    made = []

    async def connect(dsn, autocommit=True):
        made.append(MockConnection())
        return made[-1]

    monkeypatch.setattr(absurd_sdk.AsyncConnection, "connect", connect)
    client = absurd_sdk.AsyncAbsurd("postgresql://localhost/absurd")

    async def run():
        await client._ensure_connected()
        await client.close()
        await client._ensure_connected()

    asyncio.run(run())

    assert made == [client._conn]
    assert client._conn.closed
