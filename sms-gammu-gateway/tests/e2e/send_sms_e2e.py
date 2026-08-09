#!/usr/bin/env python3
"""End to end: start the add-on against a fake modem and send an SMS over its API.

Runs inside the built image, so everything the image ships is in the loop -- the
libGammu compiled into it, python-gammu linked against that libGammu, support.py,
the Flask API and the send path -- with a pseudo terminal standing in for the modem.

The interesting case is --prompt bare. A stock libGammu fails it with TIMEOUT[14]
after roughly 30s, while one carrying gammu/gammu#1177 sends normally. Running it
against the image on every build is what keeps "the patch is applied" a fact rather
than an assumption: if the Dockerfile's patch step ever stops working, this fails.

Usage:
    send_sms_e2e.py --prompt bare --expect sent
    send_sms_e2e.py --prompt garbage --expect failed
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fake_modem import FakeModem  # noqa: E402

USERNAME = "e2e"
PASSWORD = "e2e-secret"
BASE_URL = "http://127.0.0.1:5000"
# Reserved for fiction (NANP 555-0100..555-0199), so a stray real send cannot route.
DESTINATION = "+15555550100"
SMSC = "+12063130004"

# libGammu waits about 30s for the prompt before escaping, so a failing send needs
# more than that before the harness may call it hung.
SEND_TIMEOUT = 90
STARTUP_TIMEOUT = 90

# EX_SOFTWARE, what gammu_worker exits with when the modem stops answering entirely.
STALL_EXIT_CODE = 70


def log(message):
    print(f"[e2e] {message}", flush=True)


def write_options(device, urc_filter, monitoring=False):
    """Stand in for the Supervisor, which normally renders /data/options.json."""
    options = {
        "device_path": device,
        "pin": "",
        "ssl": False,
        "username": USERNAME,
        "password": PASSWORD,
        # No broker in CI. The add-on treats MQTT as optional.
        "mqtt_enabled": False,
        # Off by default so a send test measures only the send. The recovery
        # scenario turns it on, because the soft reset lives in that loop.
        "sms_monitoring_enabled": monitoring,
        "sms_check_interval": 10,
        "modem_baud_rate": "115200",
        "urc_filter_enabled": urc_filter,
    }
    os.makedirs("/data", exist_ok=True)
    with open("/data/options.json", "w") as handle:
        json.dump(options, handle)
    return options


def request(path, payload=None, timeout=30):
    credentials = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
    headers = {"Authorization": f"Basic {credentials}", "Content-Type": "application/json"}
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")
    except Exception as exc:  # noqa: BLE001
        # The watchdog exits the process mid-request, so the connection dies under
        # us. That is the behaviour being tested, not an error in the harness.
        return 0, f"no response: {type(exc).__name__}: {exc}"


def wait_for_api(process):
    deadline = time.time() + STARTUP_TIMEOUT
    while time.time() < deadline:
        if process.poll() is not None:
            raise SystemExit(f"add-on exited during startup with code {process.returncode}")
        try:
            urllib.request.urlopen(f"{BASE_URL}/", timeout=2).read()
            return
        except Exception:
            time.sleep(1)
    raise SystemExit(f"add-on API did not come up within {STARTUP_TIMEOUT}s")


def send(payload_text="end to end", timeout=SEND_TIMEOUT):
    return request(
        "/sms",
        {"text": payload_text, "number": DESTINATION, "smsc": SMSC},
        timeout=timeout,
    )


def scenario_recovery(modem, process):
    """A modem that fails, then answers properly again, without restarting the add-on.

    This is the user visible question behind the whole worker change: does a bad
    stretch leave the gateway permanently degraded, or does it come back on its own?
    """
    status, _ = send()
    log(f"first send while the modem is broken -> {status}")
    if status == 200:
        log("FAIL: the send should not have succeeded while the prompt was corrupt")
        return False

    modem.switch_to("padded")
    log("modem now answers with a well formed prompt")

    status, body = send()
    log(f"second send -> {status}: {body.strip()[:120]}")

    if process.poll() is not None:
        log(
            f"FAIL: the add-on exited (code {process.returncode}); recovery must not need a restart"
        )
        return False
    if status != 200 or len(modem.submitted) != 1:
        log(
            f"FAIL: expected a successful send after recovery, got {status} "
            f"and {len(modem.submitted)} PDU(s)"
        )
        return False

    log("PASS: recovered in place, same process, message reached the modem")
    return True


def scenario_concurrent(modem, process):
    """Several callers during a stall must not interleave on the port.

    The old design submitted each operation to its own executor and abandoned it on
    timeout, so a later command could reach the modem while an earlier one was still
    mid-transaction. The modem counts that: a PDU cannot contain "AT".
    """
    results = []
    threads = [
        threading.Thread(target=lambda i=i: results.append(send(f"concurrent {i}")))
        for i in range(3)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=SEND_TIMEOUT + 30)

    log(f"three concurrent sends returned {[status for status, _ in results]}")
    log(f"modem observed {modem.overlaps} overlapping transaction(s)")

    if modem.overlaps:
        log("FAIL: commands interleaved on the port")
        return False
    if any(status == 200 for status, _ in results):
        log("FAIL: no send should have succeeded against a silent modem")
        return False

    modem.switch_to("padded")
    status, _ = send()
    if status != 200:
        log(f"FAIL: the port should be usable once the stall clears, got {status}")
        return False

    log("PASS: no interleaving, and the port still works afterwards")
    return True


def scenario_watchdog(modem, process):
    """A modem that never answers cannot be recovered from inside the process.

    Every later command queues behind a call that cannot be interrupted, including
    the soft reset meant to fix it. The worker gives up and exits so the Supervisor
    restarts the add-on.
    """
    for attempt in range(4):
        status, _ = send(timeout=30)
        log(f"send {attempt + 1} -> {status}")
        if process.poll() is not None:
            break

    try:
        code = process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        log("FAIL: the add-on is still running after repeated stalls")
        return False

    log(f"add-on exited with code {code}")
    if code != STALL_EXIT_CODE:
        log(f"FAIL: expected EX_SOFTWARE ({STALL_EXIT_CODE})")
        return False
    if modem.submitted:
        log("FAIL: nothing should have reached the modem")
        return False

    log("PASS: gave up and exited for the Supervisor to restart")
    return True


SCENARIOS = {
    "recovery": scenario_recovery,
    "concurrent": scenario_concurrent,
    "watchdog": scenario_watchdog,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prompt", default="padded", choices=["padded", "bare", "garbage", "silent"]
    )
    parser.add_argument("--expect", default="sent", choices=["sent", "failed"])
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), help="run a recovery scenario")
    parser.add_argument("--monitoring", action="store_true", help="enable the SMS monitor loop")
    parser.add_argument("--urc-filter", action="store_true", help="leave the URC filter proxy on")
    parser.add_argument("--app", default="/app", help="directory holding run.py")
    args = parser.parse_args()

    with FakeModem(prompt=args.prompt) as modem:
        log(f"fake modem on {modem.device}, prompt style={args.prompt}")
        write_options(modem.device, args.urc_filter, args.monitoring)

        process = subprocess.Popen(
            [sys.executable, "-u", "run.py"],
            cwd=args.app,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            wait_for_api(process)
            log("add-on API is up; modem completed init")

            if args.scenario:
                return 0 if SCENARIOS[args.scenario](modem, process) else 1

            started = time.time()
            status, body = request(
                "/sms",
                {"text": "end to end", "number": DESTINATION, "smsc": SMSC},
                timeout=SEND_TIMEOUT,
            )
            elapsed = time.time() - started
            log(f"POST /sms -> {status} in {elapsed:.1f}s: {body.strip()[:200]}")
            log(f"modem received {len(modem.submitted)} PDU(s)")

            if args.expect == "sent":
                ok = status == 200 and len(modem.submitted) == 1
                if ok:
                    log(f"PASS: message accepted by the modem, PDU={modem.submitted[0]}")
                else:
                    log("FAIL: expected the send to succeed")
            else:
                ok = status != 200 and not modem.submitted
                if ok:
                    log("PASS: send failed as expected and no PDU reached the modem")
                else:
                    log("FAIL: expected the send to fail")

            if not ok:
                log(f"last AT commands: {modem.commands[-15:]}")
            return 0 if ok else 1
        finally:
            process.terminate()
            try:
                output = process.communicate(timeout=15)[0]
            except subprocess.TimeoutExpired:
                process.kill()
                output = process.communicate()[0]
            if output:
                log("--- add-on log (tail) ---")
                for line in output.strip().splitlines()[-25:]:
                    print(f"    {line}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
