import os
import socket
import sys


def _real_smoke_was_explicitly_requested() -> bool:
    if os.getenv("RUN_REAL_LLM_SMOKE_TESTS") != "1":
        return False
    arguments = [argument.lower().replace("\\", "/") for argument in sys.argv[1:]]
    return any("tests/smoke" in argument or "real_llm" in argument for argument in arguments)


REAL_LLM_TEST_SESSION = _real_smoke_was_explicitly_requested()

# This executes before test modules import application settings.
os.environ["APP_ENV"] = "test"
if not REAL_LLM_TEST_SESSION:
    os.environ["LLM_PROVIDER"] = "mock"
    os.environ["LLM_MODEL"] = "mock-test-model"
    os.environ["DEEPSEEK_API_KEY"] = ""
    os.environ["KIMI_API_KEY"] = ""
    os.environ["RUN_REAL_LLM_SMOKE_TESTS"] = "0"
    os.environ["RUN_REAL_LLM_ACCEPTANCE"] = "false"
    os.environ["SAVE_FULL_LLM_LOGS"] = "false"


_network_attempts: list[str] = []
_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex
_original_create_connection = socket.create_connection


def _blocked_connect(_socket, address):
    if _is_loopback(address):
        return _original_connect(_socket, address)
    _network_attempts.append(_safe_address(address))
    raise AssertionError("offline pytest attempted a real socket connection")


def _blocked_connect_ex(_socket, address):
    if _is_loopback(address):
        return _original_connect_ex(_socket, address)
    _network_attempts.append(_safe_address(address))
    raise AssertionError("offline pytest attempted a real socket connection")


def _blocked_create_connection(address, *args, **kwargs):
    if _is_loopback(address):
        return _original_create_connection(address, *args, **kwargs)
    _network_attempts.append(_safe_address(address))
    raise AssertionError("offline pytest attempted a real socket connection")


def _safe_address(address) -> str:
    if isinstance(address, tuple) and address:
        return str(address[0])
    return type(address).__name__


def _is_loopback(address) -> bool:
    if not isinstance(address, tuple) or not address:
        return False
    host = str(address[0]).strip("[]").lower()
    return host == "localhost" or host == "::1" or host.startswith("127.")


def pytest_configure(config) -> None:
    if REAL_LLM_TEST_SESSION:
        return
    socket.socket.connect = _blocked_connect
    socket.socket.connect_ex = _blocked_connect_ex
    socket.create_connection = _blocked_create_connection


def pytest_unconfigure(config) -> None:
    if REAL_LLM_TEST_SESSION:
        return
    socket.socket.connect = _original_connect
    socket.socket.connect_ex = _original_connect_ex
    socket.create_connection = _original_create_connection


def pytest_terminal_summary(terminalreporter) -> None:
    if REAL_LLM_TEST_SESSION:
        terminalreporter.write_line("real LLM test session: explicit network access enabled")
        return
    terminalreporter.write_line(
        "offline isolation: provider=mock, credentials=cleared, "
        f"real socket attempts={len(_network_attempts)}"
    )
