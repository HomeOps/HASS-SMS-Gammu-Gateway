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


def log(message):
    print(f"[e2e] {message}", flush=True)


def write_options(device, urc_filter):
    """Stand in for the Supervisor, which normally renders /data/options.json."""
    options = {
        "device_path": device,
        "pin": "",
        "ssl": False,
        "username": USERNAME,
        "password": PASSWORD,
        # No broker in CI. The add-on treats MQTT as optional.
        "mqtt_enabled": False,
        "sms_monitoring_enabled": False,
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prompt", default="padded", choices=["padded", "bare", "garbage", "silent"]
    )
    parser.add_argument("--expect", default="sent", choices=["sent", "failed"])
    parser.add_argument("--urc-filter", action="store_true", help="leave the URC filter proxy on")
    parser.add_argument("--app", default="/app", help="directory holding run.py")
    args = parser.parse_args()

    with FakeModem(prompt=args.prompt) as modem:
        log(f"fake modem on {modem.device}, prompt style={args.prompt}")
        write_options(modem.device, args.urc_filter)

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
