[日本語版](README-jp.md)
# EEW Alert HA

This Home Assistant integration is a fork of
[EEW Alert for Home Assistant](https://github.com/kotarou2211/ha-eew-alert).

The original integration uses Chromecast to display warning images and control lights and locks when an alert is issued. This fork removes all Chromecast-related functionality and instead publishes the alert as a Home Assistant event. This allows users to control devices and perform other actions using their own Home Assistant automations.

Directly connects to the [P2P Earthquake Information WebSocket](https://www.p2pquake.net) and receives Earthquake Early Warning (EEW) messages (code 556).

No MQTT broker or external container is required; everything runs within Home Assistant.

## Features

- Direct connection to the P2P Earthquake Information WebSocket (no additional middleware required)
- Minimum seismic intensity threshold and target prefectures can be configured through the Config Flow
- Training and test messages can be ignored
- Provides a "Test" button for testing event handling

## Installation

### Via HACS (Custom Repository)

1. Go to HACS → Integrations → menu in the upper-right corner → Custom repositories
2. Add the URL of this repository and select `Integration` as the category
3. Search for `EEW Alert HA` and install it
4. Restart Home Assistant

### Manual Installation

1. Copy `custom_components/eew_alert_ha` into the `config/custom_components/` directory of your Home Assistant installation
2. Restart Home Assistant

## Configuration

Go to Home Assistant → Settings → Devices & services → Add Integration,
search for `EEW Alert HA`, and follow the instructions.

Main configuration options:

| Option | Description |
|---|---|
| Minimum seismic intensity | An event is generated when an EEW meeting or exceeding this intensity is received |
| Target prefectures | If specified, the seismic intensity in the specified prefectures is used for evaluation. Multiple prefectures can be selected. If none are specified, the maximum seismic intensity nationwide is used |
| Ignore training/test messages | When enabled, training and test messages from P2P Earthquake Information are ignored |

## Event Details

When an EEW alert is received, the following Home Assistant event is generated.

The `scale` value is the seismic intensity multiplied by 10:

| scale | Seismic intensity |
|---:|---|
| 10 | 1 |
| 20 | 2 |
| 30 | 3 |
| 40 | 4 |
| 45 | 5 Lower |
| 50 | 5 Upper |
| 55 | 6 Lower |
| 60 | 6 Upper |
| 70 | 7 |

Example:

```yaml
event_type: eew_alert_triggered
data:
  id: test
  scale: 50
  label: 5強
  hypocenter: テスト震源
  prefs:
    - pref: 東京都
      scale: 50
  origin: LOCAL
```

The `prefs` field contains the predicted seismic intensity for each configured target prefecture.

## Testing

Press the `Test` button to generate a trigger using dummy data without receiving an actual message from the WebSocket.

To test the entire receiving pipeline (WebSocket reception → parsing → event generation), temporarily disable the `Ignore training/test messages` option and wait for a training or test message periodically transmitted by P2P Earthquake Information.

## Features Removed from the Original Repository

- Chromecast / Google Cast support
- Automatic light control when an alert is issued
- Automatic lock control when an alert is issued
- Presence-based filtering
- Seismic intensity map generation

## Prerequisites

None. No Chromecast, MQTT broker, external container, or other additional software is required.

## License

MIT License

## Disclaimer

This software is an unofficial community-developed tool and is not a replacement for the official Earthquake Early Warning systems operated by the Japan Meteorological Agency or other official organizations.

The authors assume no responsibility for any damage or loss resulting from malfunctions, delays, inaccuracies, or other issues with this software.

[日本語版](README-jp.md)
