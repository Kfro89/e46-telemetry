#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOT'
Usage: enable_can0.sh [up|down]

- Temporarily bring SocketCAN up or down at 500000 bps.
- For permanent overlay config, see README.
EOT
}

ACTION="${1:-up}"
BITRATE=500000

case "$ACTION" in
  up)
    sudo ip link set can0 up type can bitrate "$BITRATE"
    ip -details link show can0 || true
    ;;
  down)
    sudo ip link set can0 down || true
    ;;
  *)
    usage
    exit 1
    ;;

esac
