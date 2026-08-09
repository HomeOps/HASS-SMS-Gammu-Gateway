# About this fork

This is a fork of [PavelVe/home-assistant-addons](https://github.com/PavelVe/home-assistant-addons),
tracking the **SMS Gammu Gateway** add-on.

## Credit

The work here rests entirely on two people's projects:

- **[pajikos/sms-gammu-gateway](https://github.com/pajikos/sms-gammu-gateway)** — the original
  REST SMS gateway that everything downstream is built on.
- **[PavelVe](https://github.com/PavelVe)** — turned it into a Home Assistant add-on and added the
  parts that make it genuinely useful day to day: MQTT auto-discovery, the send/delete buttons and
  status sensors, multipart SMS reassembly, the URC filter that keeps SIM800 modules from wedging
  gammu, and a CHANGELOG that actually explains what changed and why. The add-on works because of
  that work, and the documentation is better than most.

Fixes developed here are sent upstream first. This fork exists to add test and release
infrastructure, not to diverge.

## What this fork adds

- **Unit and integration tests** (`pytest`) covering the serial and threading behaviour that is
  hard to verify by hand — URC filtering, the SMS prompt path, and serialisation of gammu calls.
- **CI** running lint and the test suite on every pull request.
- **release-please** for versioning and CHANGELOG generation from conventional commits.

Integration tests run against gammu's `dummy` connection driver, so the suite needs no modem.

## Related upstream work

- [gammu/gammu#1176](https://github.com/gammu/gammu/issues/1176) /
  [#1177](https://github.com/gammu/gammu/pull/1177) — libGammu only recognises an SMS prompt of
  `"> "`, so modems emitting a bare `">"` (for example the SIMCom SIM7670G) stall in `GSM_SendSMS`
  until `commtimeout`. Fix verified on hardware.
- [PavelVe/home-assistant-addons#51](https://github.com/PavelVe/home-assistant-addons/issues/51) /
  [#52](https://github.com/PavelVe/home-assistant-addons/pull/52) — a timed-out gammu call leaves a
  worker thread running inside libGammu while the lock is released.
