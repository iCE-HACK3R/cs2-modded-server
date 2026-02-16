#!/usr/bin/env bash

# Install
# As root (sudo su)
# cd / && curl --silent --output "start.sh" "https://raw.githubusercontent.com/kus/cs2-modded-server/refs/heads/cs1.6/start.sh" && chmod +x start.sh && bash start.sh

METADATA_URL="${METADATA_URL:-http://metadata.google.internal/computeMetadata/v1/instance/attributes}"

get_metadata () {
    if [ -z "$1" ]
    then
        local result=""
    else
        local result=$(curl -s "$METADATA_URL/$1?alt=text" -H "Metadata-Flavor: Google")
		if [[ $result == *"<!DOCTYPE html>"* ]]; then
			result=""
		fi
    fi

    echo $result
}

# Get meta data from GCP and set environment variables
META_RCON_PASSWORD=$(get_metadata RCON_PASSWORD)
META_MOD_URL=$(get_metadata MOD_URL)
META_PORT=$(get_metadata PORT)
META_MAXPLAYERS=$(get_metadata MAXPLAYERS)
META_MAP=$(get_metadata MAP)
META_SYS_TICRATE=$(get_metadata SYS_TICRATE)
export RCON_PASSWORD="${META_RCON_PASSWORD:-changeme}"
export STEAM_ACCOUNT="${STEAM_ACCOUNT:-$(get_metadata STEAM_ACCOUNT)}"
export MOD_URL="${META_MOD_URL:-https://github.com/kus/cs2-modded-server/archive/refs/heads/cs1.6.zip}"
export SERVER_PASSWORD="${SERVER_PASSWORD:-$(get_metadata SERVER_PASSWORD)}"
export PORT="${META_PORT:-27015}"
export MAXPLAYERS="${META_MAXPLAYERS:-32}"
export MAP="${META_MAP:-de_dust2}"
export SYS_TICRATE="${META_SYS_TICRATE:-128}"
export DUCK_DOMAIN="${DUCK_DOMAIN:-$(get_metadata DUCK_DOMAIN)}"
export DUCK_TOKEN="${DUCK_TOKEN:-$(get_metadata DUCK_TOKEN)}"
export CUSTOM_FOLDER="${CUSTOM_FOLDER:-$(get_metadata CUSTOM_FOLDER)}"

cd /

# Update DuckDNS with our current IP
if [ ! -z "$DUCK_TOKEN" ]; then
    echo url="http://www.duckdns.org/update?domains=$DUCK_DOMAIN&token=$DUCK_TOKEN&ip=$(dig +short myip.opendns.com @resolver1.opendns.com)" | curl -k -o /duck.log -K -
fi

# Variables
user="steam"
INSTALL_DIR="/home/${user}/cs16"
IP="0.0.0.0"
PUBLIC_IP=$(dig +short myip.opendns.com @resolver1.opendns.com)
CUSTOM_FILES="${CUSTOM_FOLDER:-custom_files}"
if [ -f /etc/os-release ]; then
	. /etc/os-release
	DISTRO_OS=$NAME
	DISTRO_VERSION=$VERSION_ID
elif type lsb_release >/dev/null 2>&1; then
	DISTRO_OS=$(lsb_release -si)
	DISTRO_VERSION=$(lsb_release -sr)
elif [ -f /etc/lsb-release ]; then
	. /etc/lsb-release
	DISTRO_OS=$DISTRIB_ID
	DISTRO_VERSION=$DISTRIB_RELEASE
elif [ -f /etc/debian_version ]; then
	DISTRO_OS=Debian
	DISTRO_VERSION=$(cat /etc/debian_version)
else
	DISTRO_OS=$(uname -s)
	DISTRO_VERSION=$(uname -r)
fi

# Check distrib
if ! command -v apt-get &> /dev/null; then
	echo "ERROR: OS distribution not supported... $DISTRO_OS $DISTRO_VERSION"
	exit 1
fi

# Check root
if [ "$EUID" -ne 0 ]; then
	echo "ERROR: Please run this script as root..."
	exit 1
fi

if [ -z "$PUBLIC_IP" ]; then
	echo "ERROR: Cannot retrieve your public IP address..."
	exit 1
fi

echo "Updating Operating System..."
apt update -y -q && apt upgrade -y -q >/dev/null
if [ "$?" -ne "0" ]; then
	echo "ERROR: Updating Operating System..."
	exit 1
fi

echo "Adding i386 architecture..."
dpkg --add-architecture i386 >/dev/null
if [ "$?" -ne "0" ]; then
	echo "ERROR: Cannot add i386 architecture..."
	exit 1
fi

echo "Installing required packages for $DISTRO_OS $DISTRO_VERSION..."
apt-get update -y -q >/dev/null
apt-get install -y -q curl wget screen nano file tar bzip2 gzip unzip hostname bsdmainutils util-linux ca-certificates binutils bc jq tmux lib32gcc-s1 lib32stdc++6 lib32z1 >/dev/null
if [ "$?" -ne "0" ]; then
	apt-get install -y -q curl wget screen nano file tar bzip2 gzip unzip hostname bsdmainutils util-linux ca-certificates binutils bc jq tmux lib32gcc1 lib32stdc++6 lib32z1 >/dev/null
	if [ "$?" -ne "0" ]; then
		echo "ERROR: Cannot install required packages..."
		exit 1
	fi
fi

echo "Checking $user user exists..."
getent passwd ${user} >/dev/null 2&>1
if [ "$?" -ne "0" ]; then
	echo "Adding $user user..."
	addgroup ${user} && \
	adduser --system --home /home/${user} --shell /bin/false --ingroup ${user} ${user} && \
	usermod -a -G tty ${user} && \
	mkdir -m 777 ${INSTALL_DIR} && \
	chown -R ${user}:${user} ${INSTALL_DIR}
	if [ "$?" -ne "0" ]; then
		echo "ERROR: Cannot add user $user..."
		exit 1
	fi
fi

echo "Checking steamcmd exists..."
if [ ! -d "/steamcmd" ]; then
	mkdir /steamcmd && cd /steamcmd
	wget https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz
	tar -xvzf steamcmd_linux.tar.gz
	mkdir -p /root/.steam/sdk32/
	ln -s /steamcmd/linux32/steamclient.so /root/.steam/sdk32/steamclient.so
fi

# CS 1.6 (HLDS, App ID 90) requires multiple SteamCMD runs to fully install
echo "Downloading/updating CS 1.6 (HLDS)..."
echo "Note: HLDS (App ID 90) may require multiple download attempts..."
STEAMCMD_ATTEMPT=0
while true; do
	STEAMCMD_ATTEMPT=$((STEAMCMD_ATTEMPT + 1))
	echo "SteamCMD attempt $STEAMCMD_ATTEMPT..."
	/steamcmd/steamcmd.sh +login anonymous \
		+force_install_dir ${INSTALL_DIR} \
		+app_update 90 validate \
		+quit
	if [ "$?" -eq "0" ]; then
		echo "SteamCMD update confirmed."
		break
	fi
	echo "SteamCMD reported an issue or incomplete update. Retrying in 5 seconds..."
	sleep 5
done

cd /home/${user}

echo "Merging in custom files from ${CUSTOM_FILES}"
if [ -d "${INSTALL_DIR}/${CUSTOM_FILES}" ]; then
	cp -RT ${INSTALL_DIR}/${CUSTOM_FILES}/ ${INSTALL_DIR}/cstrike/
fi

# Compile AQS (Advanced Quake Sounds) if .amxx doesn't exist yet
AMXXPC="${INSTALL_DIR}/cstrike/addons/amxmodx/scripting/amxxpc"
AQS_SMA="${INSTALL_DIR}/cstrike/addons/amxmodx/scripting/AQS.sma"
AQS_AMXX="${INSTALL_DIR}/cstrike/addons/amxmodx/plugins/AQS.amxx"
if [ -f "$AQS_SMA" ] && [ ! -f "$AQS_AMXX" ] && [ -x "$AMXXPC" ]; then
	echo "Compiling AQS.sma..."
	cd ${INSTALL_DIR}/cstrike/addons/amxmodx/scripting
	./amxxpc AQS.sma -o"$AQS_AMXX" 2>&1 || echo "WARNING: AQS compilation failed"
	cd /home/${user}
fi

chown -R ${user}:${user} ${INSTALL_DIR}

cd ${INSTALL_DIR}

# Build launch args with secrets passed as +args (override server.cfg)
LAUNCH_ARGS="+ip $IP +port $PORT +maxplayers $MAXPLAYERS +map $MAP +sys_ticrate $SYS_TICRATE"
[ ! -z "$RCON_PASSWORD" ] && LAUNCH_ARGS="$LAUNCH_ARGS +rcon_password $RCON_PASSWORD"
[ ! -z "$SERVER_PASSWORD" ] && LAUNCH_ARGS="$LAUNCH_ARGS +sv_password $SERVER_PASSWORD"

echo "Starting CS 1.6 server on $PUBLIC_IP:$PORT"
./hlds_run \
    -game cstrike \
    -console \
    $LAUNCH_ARGS
