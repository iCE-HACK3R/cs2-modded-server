#!/usr/bin/env bash

# Variables
user="steam"
INSTALL_DIR="/home/${user}/cs16"
IP="0.0.0.0"
PUBLIC_IP=$(dig +short myip.opendns.com @resolver1.opendns.com)
CUSTOM_FILES="${CUSTOM_FOLDER:-custom_files}"
PORT="${PORT:-27015}"
MAXPLAYERS="${MAXPLAYERS:-32}"
MAP="${MAP:-de_dust2}"
SYS_TICRATE="${SYS_TICRATE:-128}"

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

# Download latest stop script
curl --silent --output "stop.sh" "https://raw.githubusercontent.com/kus/cs2-modded-server/refs/heads/cs1.6/stop.sh" && chmod +x stop.sh

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
	# Fallback for older systems where lib32gcc-s1 doesn't exist
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
MAX_ATTEMPTS=5
for i in $(seq 1 $MAX_ATTEMPTS); do
	echo "SteamCMD attempt $i of $MAX_ATTEMPTS..."
	/steamcmd/steamcmd.sh +login anonymous \
		+force_install_dir ${INSTALL_DIR} \
		+app_update 90 validate \
		+quit
	if [ "$?" -eq "0" ]; then
		echo "SteamCMD attempt $i completed."
	fi
done

cd /home/${user}

echo "Downloading mod files..."
MOD_URL="${MOD_URL:-https://github.com/kus/cs2-modded-server/archive/refs/heads/cs1.6.zip}"
wget --quiet "${MOD_URL}" -O cs16-mod.zip
unzip -o -qq cs16-mod.zip
cp -rlf cs2-modded-server-cs1.6/cstrike/ ${INSTALL_DIR}/cstrike/
cp -R cs2-modded-server-cs1.6/custom_files/ ${INSTALL_DIR}/custom_files/
cp -R cs2-modded-server-cs1.6/custom_files_example/ ${INSTALL_DIR}/custom_files_example/
rm -rf cs2-modded-server-cs1.6 cs16-mod.zip

echo "Merging in custom files from ${CUSTOM_FILES}"
if [ -d "${INSTALL_DIR}/${CUSTOM_FILES}" ]; then
	cp -RT ${INSTALL_DIR}/${CUSTOM_FILES}/ ${INSTALL_DIR}/cstrike/
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
