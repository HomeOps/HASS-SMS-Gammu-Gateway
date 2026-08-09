# SMS Gammu Gateway (HomeOps)

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]

Home Assistant add-on: REST API SMS gateway for USB GSM modems, with MQTT integration and
auto-discovery. Send and receive SMS from automations, the UI, or the REST API.

A fork of [PavelVe's add-on](https://github.com/PavelVe/home-assistant-addons), adding tests, CI and
a patched libGammu. See [FORK.md](./FORK.md) for what differs and who the work is credited to.

> **US users:** 2G-only modems (SIM800L and similar) no longer work anywhere in the United States —
> T-Mobile completed its shutdown on 2 August 2026, AT&T and Verizon years earlier. This add-on
> ships a patched libGammu so modern LTE modules work; the SIMCom SIM7670G is verified send/receive.
> See [supported hardware](./sms-gammu-gateway/README.md#supported-hardware).

## Installation

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FHomeOps%2FHASS-SMS-Gammu-Gateway)

Press the button, or:

1. Navigate to the add-ons page on your Home Assistant installation
2. Press the three dots in the top right corner
3. Add `https://github.com/HomeOps/HASS-SMS-Gammu-Gateway` to add-on repositories
4. Install **SMS Gammu Gateway (HomeOps)** from the add-on store
5. Configure and start it

It installs with slug `sms_gammu_gateway_homeops` and its own MQTT topics, so it can run alongside
the upstream add-on without colliding.

Configuration reference, supported hardware and API documentation:
[sms-gammu-gateway/README.md](./sms-gammu-gateway/README.md)

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
