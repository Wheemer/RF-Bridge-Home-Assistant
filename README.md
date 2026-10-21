<div align="center">

<img src="https://raw.githubusercontent.com/Wheemer/RF-Bridge-Home-Assistant/main/custom_components/rf_bridge/brand/dark_header_logo.png#gh-dark-mode-only" alt="RF Bridge" width="440">
<img src="https://raw.githubusercontent.com/Wheemer/RF-Bridge-Home-Assistant/main/custom_components/rf_bridge/brand/header_logo.png#gh-light-mode-only" alt="RF Bridge" width="440">

<strong>Home Assistant integration for the modified Sonoff RF Bridge.</strong>

[![HACS Custom](https://img.shields.io/badge/HACS-CUSTOM-FD7E14?style=for-the-badge&logo=home-assistant&logoColor=white&labelColor=555555)](https://github.com/hacs/integration)
[![Home Assistant](https://img.shields.io/badge/HOME%20ASSISTANT-CUSTOM%20INTEGRATION-41BDF5?style=for-the-badge&logo=home-assistant&logoColor=white&labelColor=555555)](https://www.home-assistant.io/)
[![Latest release](https://img.shields.io/github/v/release/Wheemer/RF-Bridge-Home-Assistant?style=for-the-badge&logo=github&logoColor=white&label=INTEGRATION&labelColor=555555&color=22C55E)](https://github.com/Wheemer/RF-Bridge-Home-Assistant/releases/latest)
[![Validate](https://img.shields.io/github/actions/workflow/status/Wheemer/RF-Bridge-Home-Assistant/validate.yml?style=for-the-badge&logo=githubactions&logoColor=white&label=VALIDATE&labelColor=555555)](https://github.com/Wheemer/RF-Bridge-Home-Assistant/actions/workflows/validate.yml)

[Install](#install) · [Firmware](https://github.com/Wheemer/RFLink32-Sonoff-RF-Bridge) · [Hardware modification guide](https://github.com/Wheemer/RFLink32-Sonoff-RF-Bridge/blob/main/doc/sonoff_rf_bridge.md) · [Issues](https://github.com/Wheemer/RF-Bridge-Home-Assistant/issues)

</div>

---

RF Bridge connects Home Assistant to the modified Sonoff RF Bridge firmware through its local WebSocket API. It handles discovery, configuration, named command buttons, learned RF events, decoded RFLink sensor entities, diagnostics, and signed firmware updates.

## Install

[![Open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Wheemer&repository=RF-Bridge-Home-Assistant&category=integration)

1. In HACS, add `Wheemer/RF-Bridge-Home-Assistant` as an **Integration** repository.
2. Install **RF Bridge**.
3. Reload the existing RF Bridge config entry, or add the bridge when it is discovered.

## What It Provides

- Local WebSocket API transport to the bridge on port `8080`.
- Zeroconf discovery and config-flow setup.
- Named Home Assistant buttons for configured RF commands.
- One RF event entity for known commands and explicit learn captures.
- Normal sensor entities beneath RF Bridge for decoded RFLink measurement frames, including temperature, humidity, rain, wind, pressure, power, voltage, and related fields.
- Sensor entities are restored after reload and never created from raw captures or remote-button frames.
- A firmware update entity that consumes signed releases from the [firmware repository](https://github.com/Wheemer/RFLink32-Sonoff-RF-Bridge).

## Update Model

Integration and firmware updates are deliberately independent:

- HACS updates this integration without flashing the bridge.
- The **RF Bridge Firmware** update entity installs only signed firmware releases.

This prevents firmware releases from appearing as HACS integration updates and prevents integration fixes from requiring an OTA flash.

## Hardware And Firmware

This integration requires the focused firmware for the direct-hack modified Sonoff RF Bridge R2 v2.2. Firmware installation, hardware modification, and OTA guidance live in the [RF Bridge firmware repository](https://github.com/Wheemer/RFLink32-Sonoff-RF-Bridge).

## Credits

The firmware project is a focused fork of [RFLink32](https://github.com/cpainchaud/RFLink32), itself derived from RFLink-ESP and the original RFLink project. The RFLink Gateway license is retained in this repository.
