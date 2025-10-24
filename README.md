# e46-can-udp

Reads BMW E46 (MS43) PT‑CAN with SocketCAN, decodes messages using a DBC (with manual fallbacks for key signals), and publishes normalized telemetry as UDP JSON at a fixed rate.

## Features
- SocketCAN input (e.g., `can0 @ 500000`)
- `cantools` DBC decoding + manual fallback for RPM, coolant temp, oil temp, throttle
- Normalized keys (e.g., `rpm`, `coolant_c`, `oil_temp_c`, `tps_pct`, `vehicle_speed_kph`, `fuel_pct`)
- UDP JSON output at fixed rate (default 10 Hz)
- `systemd` unit for auto‑start on boot

## Hardware assumptions
- Raspberry Pi + CAN HAT (MCP2515/TJA1050 or PiCAN) wired to BMW E46 PT‑CAN twisted pair
- PT‑CAN bitrate: **500000**

## Quick start

```bash
# On the Pi
sudo apt update
sudo apt install -y git python3-pip can-utils

# Clone your repo (replace with your URL)
cd ~
git clone <YOUR_REPO_URL> e46-can-udp
cd e46-can-udp

# Python deps
pip3 install -r requirements.txt

# Copy example config and edit
cp config/config.example.yaml config/config.yaml
nano config/config.yaml   # set host, port, dbc path, etc.

# (Optional) Bring up SocketCAN immediately (temporary until reboot)
sudo ./scripts/enable_can0.sh up

# Run
python3 ./src/e46_can_udp.py --config ./config/config.yaml --print
```

## SocketCAN setup (permanent)
Edit `/boot/config.txt` and add the overlay for your HAT (example for MCP2515 @ 16 MHz on `spi0.0`, interrupt GPIO 25):

```ini
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25
```

Reboot, then:
```bash
sudo ip link set can0 up type can bitrate 500000
candump can0   # verify frames with ignition on
```

## DBC file
-A curated MS43 PT-CAN DBC is included at `./dbc/e46.dbc` (see file header for provenance and supported signals).
  Copy or adjust as you validate additional channels on your vehicle.
- If you prefer to fetch an alternative mapping, `./scripts/fetch_e46_dbc.sh` remains available to download a community DBC into `./dbc/`.
- Signals differ slightly by trim/year; validate on your car. Manual fallbacks cover common channels.

## Systemd install

```bash
sudo ./scripts/install_systemd.sh
# Follow prompts; the script will write a unit with your repo path and enable it.

# Logs
journalctl -u e46-can-udp -f
```

## Telemetry output format
At 10 Hz by default, the service sends a single JSON packet per tick via UDP:

```json
{
  "ts": 1735087654.12,
  "src": "e46-ms43",
  "payload": {
    "rpm": 2478.1,
    "coolant_c": 92.4,
    "oil_temp_c": 95.6,
    "tps_pct": 18.0,
    "vehicle_speed_kph": 43.2
  }
}
```

## Development
- Lint on PR via GitHub Actions (`.github/workflows/ci.yml`).
- Minimal deps: `python-can`, `cantools`, `PyYAML`.

## License
MIT (see `LICENSE`).
