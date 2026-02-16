#!/usr/bin/env bash

# Removes everything: HLDS, SteamCMD, mods, and scripts.
# A clean slate. Re-run install.sh or start.sh to start over.
#
# As root (sudo su)
# cd / && curl --silent --output "cleanup.sh" "https://raw.githubusercontent.com/kus/cs2-modded-server/refs/heads/cs1.6/cleanup.sh" && chmod +x cleanup.sh && bash cleanup.sh

if [ "$EUID" -ne 0 ]; then
	echo "ERROR: Please run this script as root..."
	exit 1
fi

user="steam"
INSTALL_DIR="/home/${user}/cs16"

echo "Removing everything for a clean slate..."

# Stop any running server
echo "  Stopping server (if running)..."
if [ -f "/stop.sh" ]; then
	bash /stop.sh 2>/dev/null
fi

# Remove HLDS install
echo "  Removing HLDS (${INSTALL_DIR})..."
rm -rf ${INSTALL_DIR}

# Remove SteamCMD
echo "  Removing SteamCMD..."
rm -rf /steamcmd
rm -rf /root/.steam
rm -rf /root/Steam

# Remove scripts
echo "  Removing scripts..."
rm -f /install.sh
rm -f /start.sh
rm -f /stop.sh
rm -f /gcp.sh

echo "Clean slate. To start over:"
echo "  cd / && curl --silent --output \"install.sh\" \"https://raw.githubusercontent.com/kus/cs2-modded-server/refs/heads/cs1.6/install.sh\" && chmod +x install.sh && bash install.sh"

# Self-destruct
rm -f /cleanup.sh
