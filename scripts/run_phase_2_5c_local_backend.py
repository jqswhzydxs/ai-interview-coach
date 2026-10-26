"""Run the Phase 2.5C loopback-only FastAPI server with an isolated database."""

from __future__ import annotations

import atexit
import ipaddress
import os
from pathlib import Path
import socket
import sys


_attempts: list[str] = []
_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex
_original_create_connection = socket.create_connection


def _is_loopback(address: object) -> bool:
    if not isinstance(address, tuple) or not address:
        return False
    host = str(address[0]).strip("[]").lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _safe_host(address: object) -> str:
    if isinstance(address, tuple) and address:
        return str(address[0])
    return type(address).__name__


def _guarded_connect(instance, address):
    if not _is_loopback(address):
        _attempts.append(_safe_host(address))
        raise RuntimeError("Phase 2.5C blocked a non-loopback socket")
    return _original_connect(instance, address)


def _guarded_connect_ex(instance, address):
    if not _is_loopback(address):
        _attempts.append(_safe_host(address))
        return 10013
    return _original_connect_ex(instance, address)


def _guarded_create_connection(address, *args, **kwargs):
    if not _is_loopback(address):
        _attempts.append(_safe_host(address))
        raise RuntimeError("Phase 2.5C blocked a non-loopback socket")
    return _original_create_connection(address, *args, **kwargs)


def _verify_environment() -> tuple[str, int]:
    required = {
        "APP_ENV": "test",
        "LLM_PROVIDER": "mock",
        "RUN_REAL_LLM_ACCEPTANCE": "false",
        "SAVE_FULL_LLM_LOGS": "false",
        "DEEPSEEK_API_KEY": "",
        "KIMI_API_KEY": "",
    }
    for name, expected in required.items():
        if os.getenv(name) != expected:
            raise RuntimeError(f"unsafe Phase 2.5C environment: {name}")
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.startswith("sqlite+pysqlite:///"):
        raise RuntimeError("Phase 2.5C requires an isolated SQLite DATABASE_URL")
    upload_dir = Path(os.environ.get("UPLOAD_DIR", ""))
    if not upload_dir.is_absolute():
        raise RuntimeError("Phase 2.5C requires an absolute isolated UPLOAD_DIR")
    if os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() != "false":
        raise RuntimeError("Phase 2.5C forbids CORS credentials")
    host = os.getenv("PHASE_2_5C_API_HOST", "127.0.0.1")
    port = int(os.environ["PHASE_2_5C_API_PORT"])
    if host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("Phase 2.5C backend must bind to loopback")
    return host, port


def main() -> int:
    host, port = _verify_environment()
    socket.socket.connect = _guarded_connect
    socket.socket.connect_ex = _guarded_connect_ex
    socket.create_connection = _guarded_create_connection
    atexit.register(
        lambda: print(
            f"phase_2_5c_socket_guard non_loopback_attempts={len(_attempts)}",
            file=sys.stderr,
        )
    )

    from alembic import command
    from alembic.config import Config
    import uvicorn

    command.upgrade(Config("alembic.ini"), "head")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
