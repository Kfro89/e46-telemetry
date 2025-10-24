#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E46 PT-CAN → Telemetry (UDP)
- Reads SocketCAN (can0), decodes with cantools from e46.dbc (if provided)
- Normalizes key signals and emits aggregated JSON over UDP at fixed rate
- Falls back to manual decoders for critical channels if a DBC mapping is missing

Deps:
  python-can, cantools, PyYAML
"""

import argparse
import json
import os
import socket
import sys
import time
import signal
from typing import Dict, Any, Optional, List

import can

try:
    import cantools  # type: ignore
except Exception:
    cantools = None  # type: ignore

try:
    import yaml  # PyYAML
except Exception as e:
    print("[FATAL] PyYAML is required. Did you install requirements.txt?", file=sys.stderr)
    raise


# -----------------------------
# Manual decoders (common E46 frames)
# -----------------------------

def _u8(b: int) -> int:
    return b & 0xFF


def decode_manual(can_id: int, data: bytes) -> Dict[str, float]:
    """Return partial dict of normalized signals for known E46 frames.
    Mappings are based on common community references; validate on your car.
    - 0x316: RPM
    - 0x329: Coolant temp (C), TPS (%)
    - 0x545: Oil temp (C)
    """
    out: Dict[str, float] = {}

    if can_id == 0x316 and len(data) >= 4:
        # RPM = ((B4 * 256) + B3) / 6.4
        b3 = _u8(data[2]); b4 = _u8(data[3])
        rpm = ((b4 * 256) + b3) / 6.4
        out["rpm"] = float(rpm)

    if can_id == 0x329:
        # Coolant C = (B2 * 0.75) - 48.373
        if len(data) >= 2:
            b2 = _u8(data[1])
            coolant_c = (b2 * 0.75) - 48.373
            out["coolant_c"] = float(coolant_c)
        # TPS % = (B6 / 255) * 100
        if len(data) >= 6:
            b6 = _u8(data[5])
            tps_pct = (b6 / 255.0) * 100.0
            out["tps_pct"] = float(tps_pct)

    if can_id == 0x545 and len(data) >= 5:
        # OilTemp C = B5 - 48.373
        b5 = _u8(data[4])
        oil_temp_c = b5 - 48.373
        out["oil_temp_c"] = float(oil_temp_c)

    return out


# -----------------------------
# Canonicalization
# -----------------------------

CANONICAL_KEYS = {
    "rpm": ["RPM", "Engine_RPM", "engine_rpm", "rpm", "N_ENG"],
    "coolant_c": [
        "EngineTemp",
        "CoolantTemp",
        "coolant_temp",
        "coolant_c",
        "TEMP_ENG",
    ],
    "oil_temp_c": ["OilTemp", "oil_temp_c", "oil_temp", "TOIL_CAN"],
    "tps_pct": [
        "TPS",
        "Throttle",
        "throttle_pct",
        "tps_pct",
        "TPS_CAN",
        "TPS_VIRT_CRU_CAN",
    ],
    "vehicle_speed_kph": ["VehicleSpeed", "Speed", "vehicle_speed", "speed_kph"],
    "fuel_pct": ["FuelLevel", "fuel_level", "fuel_pct"],
    "engine_running": ["engine_running", "LV_ERU_CAN"],
    "brake_switch": ["brake_switch", "LV_BS"],
    "check_engine_lamp": ["check_engine_lamp", "LV_MIL"],
    "coolant_overheat_lamp": ["coolant_overheat_lamp", "LV_TEMP_ENG"],
    "sport_button_state": ["sport_button_state", "STATE_SOF_CAN"],
}


def canonicalize(decoded: Dict[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    lower = {k.lower(): decoded[k] for k in decoded}
    for canon, candidates in CANONICAL_KEYS.items():
        for name in candidates:
            v = lower.get(name.lower())
            if isinstance(v, (int, float)):
                out[canon] = float(v)
                break
    return out


# -----------------------------
# Config merge
# -----------------------------

DEFAULTS = {
    "interface": "can0",
    "dbc": "",
    "host": None,
    "port": None,
    "rate_hz": 10.0,
    "print": False,
    "filters": [],  # list of IDs (int or hex strings)
}


def load_config(path: Optional[str], cli: Dict[str, Any]) -> Dict[str, Any]:
    cfg = DEFAULTS.copy()
    if path:
        with open(path, "r", encoding="utf-8") as f:
            file_cfg = yaml.safe_load(f) or {}
        cfg.update(file_cfg)
    # CLI overrides
    for k, v in cli.items():
        if v is not None:
            cfg[k] = v
    # Normalize filters
    filt: List[int] = []
    for it in cfg.get("filters", []) or []:
        if isinstance(it, str):
            filt.append(int(it, 16) if it.lower().startswith("0x") else int(it))
        else:
            filt.append(int(it))
    cfg["filters"] = filt
    return cfg


# -----------------------------
# Main
# -----------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="E46 PT-CAN to UDP telemetry")
    ap.add_argument("--config", help="Path to YAML config")
    ap.add_argument("--interface")
    ap.add_argument("--dbc")
    ap.add_argument("--host")
    ap.add_argument("--port", type=int)
    ap.add_argument("--rate_hz", type=float)
    ap.add_argument("--print", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config, {
        "interface": args.interface,
        "dbc": args.dbc,
        "host": args.host,
        "port": args.port,
        "rate_hz": args.rate_hz,
        "print": args.print,
    })

    if not cfg.get("host") or not cfg.get("port"):
        print("[FATAL] host and port are required (via config or CLI)", file=sys.stderr)
        return 2

    # UDP target
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = (cfg["host"], int(cfg["port"]))

    # Load DBC if available
    db = None
    if cantools and cfg.get("dbc"):
        try:
            db = cantools.database.load_file(cfg["dbc"])  # type: ignore
            print(f"[INFO] Loaded DBC: {cfg['dbc']} with {len(db.messages)} messages")
        except Exception as e:
            print(f"[WARN] Failed to load DBC ({cfg['dbc']}): {e}")
            db = None
    else:
        if not cantools:
            print("[WARN] cantools unavailable; using manual decoders only")
        else:
            print("[WARN] No DBC provided; using manual decoders only")

    # SocketCAN bus
    bus = can.interface.Bus(channel=cfg["interface"], bustype="socketcan")

    # Optional kernel filters
    if cfg.get("filters"):
        bus.set_filters([{"can_id": fid & 0x7FF, "can_mask": 0x7FF} for fid in cfg["filters"]])
        print(f"[INFO] Applied kernel filters: {[hex(x) for x in cfg['filters']]}")

    # Aggregate last-known values and emit at fixed cadence
    last: Dict[str, Any] = {}
    period = 1.0 / float(cfg.get("rate_hz", 10.0)) if float(cfg.get("rate_hz", 10.0)) > 0 else 0.1
    next_emit = time.monotonic() + period
    running = True

    def _stop(signum, frame):
        nonlocal running
        running = False

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _stop)

    while running:
        msg = bus.recv(timeout=0.05)
        now = time.time()

        if msg is not None and not msg.is_error_frame:
            merged: Dict[str, Any] = {}
            # DBC first
            if db:
                try:
                    decoded = db.decode_message(msg.arbitration_id, bytes(msg.data))
                    merged.update(decoded)
                except Exception:
                    pass
            # Manual fallback
            manual = decode_manual(msg.arbitration_id, bytes(msg.data))
            merged.update(manual)

            if merged:
                canon = canonicalize(merged)
                canon["_can_id"] = int(msg.arbitration_id)
                canon["_ts"] = now
                last.update(canon)

        if time.monotonic() >= next_emit:
            payload = {k: v for k, v in last.items() if not k.startswith("_")}
            if payload:
                pkt = json.dumps({
                    "ts": now,
                    "src": "e46-ms43",
                    "payload": payload,
                }).encode("utf-8")
                try:
                    udp.sendto(pkt, dest)
                except Exception as e:
                    print(f"[WARN] UDP send failed: {e}", file=sys.stderr)
                if cfg.get("print"):
                    print(pkt.decode("utf-8"))
            next_emit += period

    bus.shutdown()
    udp.close()
    print("[INFO] stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
