"""Shared fixtures.

Integration tests run against gammu's dummy phone, a simulated device backed by
a directory tree. It is part of libgammu, so the suite needs no modem: gammu's
own test suite drives it the same way, with connection "none" and model "dummy".
"""

import pytest

gammu = pytest.importorskip("gammu", reason="python-gammu is not installed")

# Directories the dummy backend expects to exist under its device path.
DUMMY_TREE = ("sms/1", "sms/2", "pbk", "note", "todo", "calendar", "fs")


@pytest.fixture
def dummy_phone(tmp_path):
    """An initialised gammu StateMachine backed by the dummy phone."""
    device = tmp_path / "phone"
    for sub in DUMMY_TREE:
        (device / sub).mkdir(parents=True, exist_ok=True)

    machine = gammu.StateMachine()
    machine.SetConfig(0, {"Device": str(device), "Connection": "none", "Model": "dummy"})
    machine.Init()
    try:
        yield machine
    finally:
        try:
            machine.Terminate()
        except gammu.GSMError:
            pass


@pytest.fixture
def dummy_worker(tmp_path):
    """A GammuWorkerProxy driving the dummy phone.

    Same device the dummy_phone fixture uses, reached through the worker thread
    instead of directly, so the proxy is exercised as the add-on uses it.
    """
    # Imported here so collection still reports a clean skip when gammu is absent.
    from gammu_worker import GammuWorkerProxy

    device = tmp_path / "worker-phone"
    for sub in DUMMY_TREE:
        (device / sub).mkdir(parents=True, exist_ok=True)

    proxy = GammuWorkerProxy({"Device": str(device), "Connection": "none", "Model": "dummy"})
    proxy.init()
    try:
        yield proxy
    finally:
        proxy.terminate()


@pytest.fixture
def smsc():
    """SMSC entry accepted by the dummy backend."""
    return {"Number": "+123456789"}
