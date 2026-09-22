#!/bin/bash
set -e

# Detect architecture and ensure correct binary is in place
ARCH=$(uname -m)
TUNNEL_DIR="/opt/wipter/resources/wipter-tunnel/wipter-tunnel_0.1.0_linux"
mkdir -p "$TUNNEL_DIR"

if [ "$ARCH" = "x86_64" ]; then
    if [ -f "/opt/wipter/resources/bin/wipter-tunnel-x86_64" ]; then
        cp -f /opt/wipter/resources/bin/wipter-tunnel-x86_64 "$TUNNEL_DIR/wipter-tunnel"
    fi
elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    if [ -f "/opt/wipter/resources/bin/wipter-tunnel-arm64" ]; then
        cp -f /opt/wipter/resources/bin/wipter-tunnel-arm64 "$TUNNEL_DIR/wipter-tunnel"
    fi
fi

chmod +x "$TUNNEL_DIR/wipter-tunnel" 2>/dev/null || true

# Generate unique random machine-id for each container
if [ -f /proc/sys/kernel/random/uuid ]; then
    cat /proc/sys/kernel/random/uuid | tr -d '-' > /etc/machine-id 2>/dev/null || true
fi

# Ensure user data dir exists
mkdir -p "${WIPTER_USER_DATA:-/root/.config/wipter-app}"

# If credentials don't exist in mounted volume, copy template
if [ ! -f "${WIPTER_USER_DATA:-/root/.config/wipter-app}/secure-credentials.json" ] && [ -f "/opt/wipter/config-template/secure-credentials.json" ]; then
    cp -f "/opt/wipter/config-template/secure-credentials.json" "${WIPTER_USER_DATA:-/root/.config/wipter-app}/"
fi

exec "$@"
