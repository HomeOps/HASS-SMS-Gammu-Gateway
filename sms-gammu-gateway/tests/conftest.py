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
def smsc():
    """SMSC entry accepted by the dummy backend."""
    return {"Number": "+123456789"}
