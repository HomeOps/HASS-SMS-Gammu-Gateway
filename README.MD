# HomeOps Home Assistant add-on repository

A fork of [PavelVe's add-on repository](https://github.com/PavelVe/home-assistant-addons), tracking
the SMS Gammu Gateway add-on with added tests, CI and a patched libGammu. See [FORK.md](./FORK.md)
for what differs and who the work is credited to.

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FHomeOps%2FHASS-SMS-Gammu-Gateway)

## Repository installation

Press the button, or
1. Navigate to the addons page on your HA installation
2. Press the three dots in the top right corner
3. Add repository https://github.com/HomeOps/HASS-SMS-Gammu-Gateway to addon repositories
4. Install addon from addons page
5. Start addon and visit its page

The add-on installs as **SMS Gammu Gateway (HomeOps)** with slug `sms_gammu_gateway_homeops`, so it
can be installed alongside the upstream add-on without colliding.

## Add-ons

This repository contains the following add-ons

### [SMS Gammu Gateway](./sms-gammu-gateway)

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

REST API SMS Gateway using python-gammu for USB GSM modems (SIM800L, Huawei, Quectel, etc.). Send and receive SMS messages via REST API with MQTT integration and Home Assistant auto-discovery.

### [TeltonikaServer](./TeltonikaServer)

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

This addon receives AVL data from Teltonika GPS devices over TCP and logs it with timestamps for further processing or diagnostics.

### [MiniDLNA Server](./minidlna-server)

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

DLNA/UPnP media server (ReadyMedia) for streaming audio, video and photos to network devices (Smart TVs, media players, game consoles, etc.).

> TeltonikaServer and MiniDLNA Server are carried unchanged from upstream and are not maintained
> here. Report issues with those to
> [PavelVe/home-assistant-addons](https://github.com/PavelVe/home-assistant-addons/issues).

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg
