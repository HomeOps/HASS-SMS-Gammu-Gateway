"""A fake GSM modem on a pseudo terminal.

gammu's dummy driver replaces libGammu's AT layer entirely, so it proves the add-on's
Python and nothing about the protocol. This speaks real AT over a real character
device, which is what the add-on opens in production, so libGammu's parser is in the
loop.

That matters for one reason above all: the SMS edit prompt. libGammu accepts only the
exact string "> ", while the SIMCom SIM7670G answers with a bare ">" and terminates
the line (0d 0a 3e 0d 0a). Sending then stalls until the timeout with no other
symptom. This modem can emit either form, so a build carrying the fix
(https://github.com/gammu/gammu/pull/1177) sends in both cases and a build without it
fails on the bare prompt -- the check that a patched libGammu is actually in the
image, rather than assumed to be.
"""

import os
import pty
import re
import termios
import threading

# 3GPP TS 27.005 section 3.5.1 describes the prompt as <CR><LF><greater_than><space>.
# This is the only form stock libGammu accepts, and it always works.
PROMPT_PADDED = b"\r\n> "
# What the SIM7670G really sends: no space, line terminated instead. Works only on a
# libGammu carrying gammu/gammu#1177.
PROMPT_BARE = b"\r\n>\r\n"
# Corrupt: a prompt-like sequence that is not a prompt in any reading. No libGammu
# should ever accept it, patched or not, so it drives the failure and recovery path
# rather than the success path.
PROMPT_GARBAGE = b"\r\n>@\r\n"
# Nothing at all: the modem stops answering mid-transaction. libGammu waits out its
# timeout with no bytes to parse.
PROMPT_SILENT = b""

PROMPTS = {
    "padded": PROMPT_PADDED,
    "bare": PROMPT_BARE,
    "garbage": PROMPT_GARBAGE,
    "silent": PROMPT_SILENT,
}

SUBMIT_TERMINATOR = 0x1A  # Ctrl-Z, send
ABORT = 0x1B  # ESC, what libGammu sends when it gives up waiting for the prompt

# Enough of an identity for libGammu to finish its init handshake. Anything not
# listed is answered with a bare OK, which is how a real module treats the many
# capability probes it does not implement.
RESPONSES = {
    # Charset negotiation happens during Init and a bare OK fails it.
    "AT+CSCS?": '+CSCS: "GSM"',
    "AT+CSCS=?": '+CSCS: ("GSM","IRA","UCS2","UTF-8")',
    "AT+CMGF=?": "+CMGF: (0,1)",
    "AT+CNMI=?": "+CNMI: (0-2),(0-3),(0,2),(0-2),(0,1)",
    "AT+CPMS=?": '+CPMS: ("SM","ME"),("SM","ME"),("SM","ME")',
    "AT+CSMS=?": "+CSMS: (0,1)",
    "AT+CSMS?": "+CSMS: 0,1,1,1",
    "ATI": "SIM7670G",
    "AT+CGMI": "SIMCOM_Ltd",
    "AT+CGMM": "SIM7670G",
    "AT+CGMR": "Revision: 2382B02SIM767XM5A",
    "AT+CGSN": "867584030000000",
    "AT+CIMI": "310280000000000",
    "AT+CPIN?": "+CPIN: READY",
    "AT+CSCA?": '+CSCA: "+12063130004",145',
    "AT+CSQ": "+CSQ: 21,99",
    "AT+CREG?": "+CREG: 0,1",
    "AT+CGREG?": "+CGREG: 0,1",
    "AT+COPS?": '+COPS: 0,0,"FakeNet",7',
    "AT+CPMS?": '+CPMS: "SM",0,20,"SM",0,20,"SM",0,20',
    "AT+CNUM": '+CNUM: "","+15555550100",145',
}


class FakeModem:
    """Answers AT commands on a pty, so libGammu can be driven without hardware."""

    def __init__(self, prompt="padded"):
        self.prompt = PROMPTS[prompt]
        self.commands = []
        self.submitted = []
        self.aborted = False

        self._master, slave = pty.openpty()
        self.device = os.ttyname(slave)

        # Raw mode on the side libGammu opens. Without this the line discipline
        # echoes and rewrites bytes, and the modem's own echo is then duplicated.
        attrs = termios.tcgetattr(slave)
        attrs[0] = attrs[1] = attrs[3] = 0  # iflag, oflag, lflag: no processing
        attrs[6][termios.VMIN] = 1
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(slave, termios.TCSANOW, attrs)

        self._echo = True
        self._collecting_pdu = False
        self._pdu = bytearray()
        self._buffer = bytearray()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="fake-modem", daemon=True)
        self._thread.start()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self._stop.set()
        try:
            os.close(self._master)
        except OSError:
            pass

    def _write(self, data):
        if not data:
            return
        try:
            os.write(self._master, data)
        except OSError:
            # The pty went away, which on shutdown is expected: the reader thread
            # can be mid-echo when close() runs.
            self._stop.set()

    def _reply(self, body=None):
        if body:
            self._write(f"\r\n{body}\r\n".encode())
        self._write(b"\r\nOK\r\n")

    def _run(self):
        try:
            while not self._stop.is_set():
                try:
                    chunk = os.read(self._master, 1024)
                except OSError:
                    return
                if not chunk:
                    return
                for byte in chunk:
                    self._feed(byte)
        except (OSError, ValueError):
            # Raised when the interpreter tears down around this daemon thread.
            return

    def _feed(self, byte):
        if self._collecting_pdu:
            self._feed_pdu(byte)
            return

        if self._echo:
            self._write(bytes([byte]))

        if byte in (13, 10):  # CR or LF ends a command
            line = self._buffer.decode(errors="replace").strip()
            self._buffer.clear()
            if line:
                self._handle(line)
        else:
            self._buffer.append(byte)

    def _feed_pdu(self, byte):
        if byte == ABORT:
            # libGammu gave up waiting for a prompt it did not recognise. Recording
            # this is what makes the bare prompt failure legible instead of a hang.
            self.aborted = True
            self._collecting_pdu = False
            self._pdu.clear()
            self._write(b"\r\nOK\r\n")
            return

        if byte == SUBMIT_TERMINATOR:
            self.submitted.append(self._pdu.decode(errors="replace").strip())
            self._pdu.clear()
            self._collecting_pdu = False
            self._reply(f"+CMGS: {len(self.submitted)}")
            return

        self._pdu.append(byte)

    def _handle(self, line):
        self.commands.append(line)

        if line.upper().startswith("ATE"):
            self._echo = not line.upper().startswith("ATE0")
            self._reply()
            return

        if re.match(r"^AT\+CMGS=", line, re.IGNORECASE):
            # The whole point of the harness: hand back a prompt in the shape being
            # tested, then take the PDU.
            self._collecting_pdu = True
            self._write(self.prompt)
            return

        for command, response in RESPONSES.items():
            if line.upper() == command.upper():
                self._reply(response)
                return

        self._reply()
