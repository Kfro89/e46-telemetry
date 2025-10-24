#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
UNIT_SRC="$REPO_DIR/systemd/e46-can-udp.service"
UNIT_DST="/etc/systemd/system/e46-can-udp.service"

if [[ ! -f "$REPO_DIR/config/config.yaml" ]]; then
  echo "[INFO] config/config.yaml not found; copying example..."
  cp "$REPO_DIR/config/config.example.yaml" "$REPO_DIR/config/config.yaml"
  echo "[INFO] Please edit $REPO_DIR/config/config.yaml before enabling the service."
fi

sudo sed \
  -e "s|__REPO_DIR__|$REPO_DIR|g" \
  "$UNIT_SRC" | sudo tee "$UNIT_DST" >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable --now e46-can-udp

sleep 1
sudo systemctl status --no-pager e46-can-udp || true
