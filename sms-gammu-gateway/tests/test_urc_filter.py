"""Tests for the URC filter proxy.

These need neither a modem nor libgammu: the proxy is pty based, so a second
pty stands in for the modem.
"""

import os
import pty
import time
import tty

import pytest

from urc_filter import DEFAULT_URC_PATTERNS, URCFilterProxy

# The proxy polls with a 3 ms sleep, so give it room without making the suite slow.
SETTLE = 0.3


class TestTailMightBeUrc:
    """The predicate deciding whether an unterminated tail is held back."""

    @pytest.fixture
    def proxy(self):
        return URCFilterProxy("/dev/null")

    @pytest.mark.parametrize(
        "tail",
        [b"O", b"OVER-", b"OVER-VOLTAGE WARNNING", b"UNDER-VOLTAGE POWER DOWN"],
    )
    def test_urc_prefixes_are_held(self, proxy, tail):
        assert proxy._tail_might_be_urc(tail) is True

    @pytest.mark.parametrize("tail", [b"", b"\r\n", b"\r\n\r\n"])
    def test_empty_tail_is_not_held(self, proxy, tail):
        assert proxy._tail_might_be_urc(tail) is False

    def test_sms_prompt_is_never_held(self, proxy):
        """The SMS prompt has no line terminator; holding it stalls SendSMS."""
        assert proxy._tail_might_be_urc(b"> ") is False
        assert proxy._tail_might_be_urc(b"\r\n> ") is False

    def test_bare_prompt_is_never_held(self, proxy):
        """Some modems emit ">" without the trailing space (gammu/gammu#1176)."""
        assert proxy._tail_might_be_urc(b">") is False
        assert proxy._tail_might_be_urc(b"\r\n>") is False

    @pytest.mark.parametrize("tail", [b"OK", b"+CMGS: 1", b"AT+CMGF=1"])
    def test_ordinary_traffic_is_not_held(self, proxy, tail):
        assert proxy._tail_might_be_urc(tail) is False


class TestProxyForwarding:
    """End to end through the proxy, with a pty standing in for the modem."""

    @pytest.fixture
    def link(self):
        modem_master, modem_slave = pty.openpty()
        tty.setraw(modem_master)
        tty.setraw(modem_slave)

        proxy = URCFilterProxy(os.ttyname(modem_slave))
        gammu_path = proxy.start()
        gammu_fd = os.open(gammu_path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)

        yield modem_master, gammu_fd, proxy

        os.close(gammu_fd)
        proxy.stop()
        os.close(modem_master)
        os.close(modem_slave)

    @staticmethod
    def _drain(fd, settle=SETTLE):
        time.sleep(settle)
        out = b""
        while True:
            try:
                chunk = os.read(fd, 4096)
            except (BlockingIOError, OSError):
                break
            if not chunk:
                break
            out += chunk
        return out

    def test_ordinary_line_passes_through(self, link):
        modem, gammu, _ = link
        os.write(modem, b"\r\nOK\r\n")
        assert b"OK" in self._drain(gammu)

    @pytest.mark.parametrize("urc", DEFAULT_URC_PATTERNS)
    def test_urc_line_is_dropped(self, link, urc):
        modem, gammu, proxy = link
        os.write(modem, b"\r\n" + urc + b"\r\n")
        assert urc not in self._drain(gammu)
        assert proxy.filtered_count == 1

    def test_urc_dropped_but_surrounding_traffic_survives(self, link):
        modem, gammu, proxy = link
        os.write(modem, b"\r\nOVER-VOLTAGE WARNNING\r\n+CSQ: 20,0\r\n\r\nOK\r\n")
        out = self._drain(gammu)
        assert b"OVER-VOLTAGE WARNNING" not in out
        assert b"+CSQ: 20,0" in out
        assert b"OK" in out
        assert proxy.filtered_count == 1

    def test_unterminated_prompt_is_forwarded_promptly(self, link):
        """A held prompt is what stalls SendSMS, so it must not wait for CRLF."""
        modem, gammu, _ = link
        os.write(modem, b"\r\n> ")
        assert b">" in self._drain(gammu)

    def test_unterminated_bare_prompt_is_forwarded_promptly(self, link):
        modem, gammu, _ = link
        os.write(modem, b"\r\n>")
        assert b">" in self._drain(gammu)

    def test_gammu_to_modem_is_unmodified(self, link):
        modem, gammu, _ = link
        os.write(gammu, b"AT+CMGF=1\r")
        time.sleep(SETTLE)
        assert os.read(modem, 4096) == b"AT+CMGF=1\r"
