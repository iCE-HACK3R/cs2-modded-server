#!/usr/bin/env bash

# download-mods.sh
# One-time script to download all mod framework binaries and plugins.
# Run this locally, then commit the resulting cstrike/ files to git.
#
# Usage: bash download-mods.sh
#
# Downloads:
#   - Metamod-P 1.21p38 (Linux + Windows)
#   - AMX Mod X 1.9.0-git5259 base + cstrike (Linux + Windows)
#   - GunGame 2.13c
#   - CSDM 2.1.2
#   - Advanced Quake Sounds 8.0
#   - CS_PugMod 2.0.6 (competitive PUG system)
#
# Linux .so and Windows .dll binaries have different filenames so they
# coexist in the same directories. No separate windows/ folder needed.

set -euo pipefail

# Download a file
download() {
    local dest="$1"
    local url="$2"
    if ! curl -sSL -o "$dest" "$url"; then
        echo "  ERROR: Failed to download $url"
        return 1
    fi
}

# Download and verify it's a binary archive (not HTML)
download_archive() {
    local dest="$1"
    local url="$2"
    download "$dest" "$url"
    local filetype
    filetype=$(file -b "$dest")
    if echo "$filetype" | grep -qi "html"; then
        echo "  ERROR: Download returned HTML instead of archive: $url"
        head -c 200 "$dest"
        echo ""
        rm -f "$dest"
        return 1
    fi
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CSTRIKE_DIR="${SCRIPT_DIR}/cstrike"
TMP_DIR="${SCRIPT_DIR}/tmp_mods"

echo "============================================"
echo "CS 1.6 Mod Framework Downloader"
echo "============================================"
echo ""
echo "This will download all mod binaries into:"
echo "  cstrike/  (Linux .so + Windows .dll + cross-platform configs)"
echo ""

# Clean up any previous tmp
rm -rf "${TMP_DIR}"
mkdir -p "${TMP_DIR}"

# Ensure target dirs exist
mkdir -p "${CSTRIKE_DIR}/addons/metamod/dlls"
mkdir -p "${CSTRIKE_DIR}/addons/amxmodx"

# Back up our custom configs before AMX Mod X overwrites them
CONFIGS_DIR="${CSTRIKE_DIR}/addons/amxmodx/configs"
mkdir -p "${TMP_DIR}/saved_configs"
for f in plugins.ini users.ini amxx.cfg; do
    if [ -f "${CONFIGS_DIR}/$f" ]; then
        cp "${CONFIGS_DIR}/$f" "${TMP_DIR}/saved_configs/$f"
    fi
done

# ============================================
# 1. METAMOD-P 1.21p38
# ============================================
echo "[1/6] Downloading Metamod-P 1.21p38..."

METAMOD_URL="https://github.com/Bots-United/metamod-p/releases/download/v1.21p38/metamod_i686_linux_win32-1.21p38.tar.xz"
download_archive "${TMP_DIR}/metamod-p.tar.xz" "${METAMOD_URL}"
mkdir -p "${TMP_DIR}/metamod-p"
tar -xJf "${TMP_DIR}/metamod-p.tar.xz" -C "${TMP_DIR}/metamod-p"
cp "${TMP_DIR}/metamod-p/metamod.dll" "${CSTRIKE_DIR}/addons/metamod/dlls/"
cp "${TMP_DIR}/metamod-p/metamod.so" "${CSTRIKE_DIR}/addons/metamod/dlls/"
echo "  -> Linux: metamod.so"
echo "  -> Windows: metamod.dll"

# ============================================
# 2. AMX MOD X 1.9.0-git5259 (base + cstrike)
# ============================================
echo "[2/6] Downloading AMX Mod X 1.9.0-git5259..."

AMXX_VERSION="1.9"
AMXX_BUILD="5259"
AMXX_BASE_URL="https://www.amxmodx.org/amxxdrop/${AMXX_VERSION}"

# Linux base
AMXX_BASE_LINUX="${AMXX_BASE_URL}/amxmodx-${AMXX_VERSION}.0-git${AMXX_BUILD}-base-linux.tar.gz"
download_archive "${TMP_DIR}/amxx-base-linux.tar.gz" "${AMXX_BASE_LINUX}"
mkdir -p "${TMP_DIR}/amxx-base-linux"
tar -xzf "${TMP_DIR}/amxx-base-linux.tar.gz" -C "${TMP_DIR}/amxx-base-linux"
cp -R "${TMP_DIR}/amxx-base-linux/addons/amxmodx/"* "${CSTRIKE_DIR}/addons/amxmodx/"
echo "  -> Linux base extracted"

# Linux cstrike addon
AMXX_CSTRIKE_LINUX="${AMXX_BASE_URL}/amxmodx-${AMXX_VERSION}.0-git${AMXX_BUILD}-cstrike-linux.tar.gz"
download_archive "${TMP_DIR}/amxx-cstrike-linux.tar.gz" "${AMXX_CSTRIKE_LINUX}"
mkdir -p "${TMP_DIR}/amxx-cstrike-linux"
tar -xzf "${TMP_DIR}/amxx-cstrike-linux.tar.gz" -C "${TMP_DIR}/amxx-cstrike-linux"
cp -R "${TMP_DIR}/amxx-cstrike-linux/addons/amxmodx/"* "${CSTRIKE_DIR}/addons/amxmodx/"
echo "  -> Linux cstrike addon extracted"

# Windows base (DLLs + compiler go into same cstrike/ dirs alongside .so files)
AMXX_BASE_WIN="${AMXX_BASE_URL}/amxmodx-${AMXX_VERSION}.0-git${AMXX_BUILD}-base-windows.zip"
download_archive "${TMP_DIR}/amxx-base-win.zip" "${AMXX_BASE_WIN}"
mkdir -p "${TMP_DIR}/amxx-base-win"
unzip -o -qq "${TMP_DIR}/amxx-base-win.zip" -d "${TMP_DIR}/amxx-base-win"
find "${TMP_DIR}/amxx-base-win/addons/amxmodx/dlls" -name "*.dll" -exec cp {} "${CSTRIKE_DIR}/addons/amxmodx/dlls/" \;
find "${TMP_DIR}/amxx-base-win/addons/amxmodx/modules" -name "*.dll" -exec cp {} "${CSTRIKE_DIR}/addons/amxmodx/modules/" \;
# Copy Windows compiler for AQS compilation
find "${TMP_DIR}/amxx-base-win/addons/amxmodx/scripting" -name "amxxpc*" -exec cp {} "${CSTRIKE_DIR}/addons/amxmodx/scripting/" \;
echo "  -> Windows base DLLs + compiler extracted"

# Windows cstrike addon
AMXX_CSTRIKE_WIN="${AMXX_BASE_URL}/amxmodx-${AMXX_VERSION}.0-git${AMXX_BUILD}-cstrike-windows.zip"
download_archive "${TMP_DIR}/amxx-cstrike-win.zip" "${AMXX_CSTRIKE_WIN}"
mkdir -p "${TMP_DIR}/amxx-cstrike-win"
unzip -o -qq "${TMP_DIR}/amxx-cstrike-win.zip" -d "${TMP_DIR}/amxx-cstrike-win"
if [ -d "${TMP_DIR}/amxx-cstrike-win/addons/amxmodx/dlls" ]; then
    find "${TMP_DIR}/amxx-cstrike-win/addons/amxmodx/dlls" -name "*.dll" -exec cp {} "${CSTRIKE_DIR}/addons/amxmodx/dlls/" \;
fi
if [ -d "${TMP_DIR}/amxx-cstrike-win/addons/amxmodx/modules" ]; then
    find "${TMP_DIR}/amxx-cstrike-win/addons/amxmodx/modules" -name "*.dll" -exec cp {} "${CSTRIKE_DIR}/addons/amxmodx/modules/" \;
fi
echo "  -> Windows cstrike DLLs extracted"

# ============================================
# 3. GUNGAME 2.13c
# ============================================
echo "[3/6] Downloading GunGame 2.13c..."

GUNGAME_URL="https://github.com/xLeviNx/GunGame/releases/download/release/gg_213c_full.zip"
download_archive "${TMP_DIR}/gungame.zip" "${GUNGAME_URL}"
mkdir -p "${TMP_DIR}/gungame"
unzip -o -qq "${TMP_DIR}/gungame.zip" -d "${TMP_DIR}/gungame"

# GunGame zip contains gg_213c_full/ subdirectory with addons/ and sound/
GG_ROOT=$(find "${TMP_DIR}/gungame" -maxdepth 2 -type d -name "addons" | head -1 | xargs dirname)
if [ -n "$GG_ROOT" ] && [ -d "$GG_ROOT/addons" ]; then
    cp -R "$GG_ROOT/addons/amxmodx/"* "${CSTRIKE_DIR}/addons/amxmodx/"
    echo "  -> GunGame plugins, configs, and lang extracted"
    # Copy sound files (sound/gungame/*.wav)
    if [ -d "$GG_ROOT/sound" ]; then
        cp -R "$GG_ROOT/sound" "${CSTRIKE_DIR}/"
        echo "  -> GunGame sounds extracted"
    fi
else
    # Fallback: find and copy files individually
    find "${TMP_DIR}/gungame" -name "*.amxx" -exec cp {} "${CSTRIKE_DIR}/addons/amxmodx/plugins/" \;
    find "${TMP_DIR}/gungame" -name "*.sma" -exec cp {} "${CSTRIKE_DIR}/addons/amxmodx/scripting/" \;
    find "${TMP_DIR}/gungame" -name "gungame.txt" -exec cp {} "${CSTRIKE_DIR}/addons/amxmodx/data/lang/" \;
    find "${TMP_DIR}/gungame" -name "gungame.cfg" -exec cp {} "${CSTRIKE_DIR}/addons/amxmodx/configs/" \;
    mkdir -p "${CSTRIKE_DIR}/sound/gungame"
    find "${TMP_DIR}/gungame" -name "*.wav" -exec cp {} "${CSTRIKE_DIR}/sound/gungame/" \;
    echo "  -> GunGame extracted (fallback)"
fi

# ============================================
# 4. CSDMsake (Deathmatch - pure Pawn, no native module)
# ============================================
echo "[4/6] Downloading CSDMsake..."

CSDMSAKE_BASE="https://raw.githubusercontent.com/s4ke/CSDMsake/master"
mkdir -p "${CSTRIKE_DIR}/addons/amxmodx/scripting"
for sma in csdmsake.sma csdmsake_equip.sma csdmsake_spawn.sma csdmsake_fixes.sma csdmsake_display.sma spawn_editor.sma; do
    download "${CSTRIKE_DIR}/addons/amxmodx/scripting/$sma" "${CSDMSAKE_BASE}/$sma"
done
echo "  -> CSDMsake source downloaded (compile .sma files separately and commit .amxx)"

# ============================================
# 5. ADVANCED QUAKE SOUNDS 8.0
# ============================================
echo "[5/6] Downloading Advanced Quake Sounds 8.0..."

AQS_BASE="https://github.com/ClaudiuHKS/AdvancedQuakeSounds/releases/download/v8.0"

# Download sound files (the main asset - quake announcer WAVs)
download_archive "${TMP_DIR}/aqs-sound.zip" "${AQS_BASE}/sound.zip"
mkdir -p "${TMP_DIR}/aqs-sound"
unzip -o -qq "${TMP_DIR}/aqs-sound.zip" -d "${TMP_DIR}/aqs-sound"

# Download plugin source and config
download "${TMP_DIR}/AQS.sma" "${AQS_BASE}/AQS.sma"
download "${TMP_DIR}/AQS.ini" "${AQS_BASE}/AQS.ini"

# Copy sound files
if [ -d "${TMP_DIR}/aqs-sound/sound" ]; then
    cp -R "${TMP_DIR}/aqs-sound/sound" "${CSTRIKE_DIR}/"
else
    mkdir -p "${CSTRIKE_DIR}/sound/quake"
    find "${TMP_DIR}/aqs-sound" \( -name "*.wav" -o -name "*.mp3" \) -exec cp {} "${CSTRIKE_DIR}/sound/quake/" \;
fi

# Copy source to scripting
mkdir -p "${CSTRIKE_DIR}/addons/amxmodx/scripting"
cp "${TMP_DIR}/AQS.sma" "${CSTRIKE_DIR}/addons/amxmodx/scripting/"

# Copy ini config
mkdir -p "${CSTRIKE_DIR}/addons/amxmodx/configs"
cp "${TMP_DIR}/AQS.ini" "${CSTRIKE_DIR}/addons/amxmodx/configs/"

echo "  -> Advanced Quake Sounds extracted (compile AQS.sma separately and commit AQS.amxx)"

# ============================================
# 6. CS_PUGMOD 2.0.6 (Competitive PUG system)
# ============================================
echo "[6/6] Downloading CS_PugMod 2.0.6..."

PUGMOD_BASE="https://raw.githubusercontent.com/SmileYzn/CS_PugMod-Archive/master/addons/amxmodx"

# Source files
for sma in PugAdmin.sma PugAux.sma PugConfigs.sma PugCore.sma PugFlood.sma PugLO3.sma PugMenus.sma PugReady.sma PugWarmup.sma; do
    download "${CSTRIKE_DIR}/addons/amxmodx/scripting/$sma" "${PUGMOD_BASE}/scripting/$sma"
done
echo "  -> PugMod source files downloaded"

# Include files
for inc in PugCS.inc PugCore.inc PugMenus.inc PugStocks.inc; do
    download "${CSTRIKE_DIR}/addons/amxmodx/scripting/include/$inc" "${PUGMOD_BASE}/scripting/include/$inc"
done
echo "  -> PugMod include files downloaded"

# Language files
for lang in PugAdmin.txt PugAux.txt PugCore.txt PugMenus.txt PugReady.txt; do
    download "${CSTRIKE_DIR}/addons/amxmodx/data/lang/$lang" "${PUGMOD_BASE}/data/lang/$lang"
done
echo "  -> PugMod lang files downloaded"

echo "  -> PugMod extracted (compile .sma files separately and commit .amxx)"

# ============================================
# RESTORE CUSTOM CONFIGS
# ============================================
echo ""
echo "Restoring custom configs (overwritten by AMX Mod X defaults)..."
for f in plugins.ini users.ini amxx.cfg; do
    if [ -f "${TMP_DIR}/saved_configs/$f" ]; then
        cp "${TMP_DIR}/saved_configs/$f" "${CONFIGS_DIR}/$f"
        echo "  -> Restored $f"
    fi
done

# ============================================
# CLEANUP
# ============================================
echo ""
echo "Cleaning up temp files..."
rm -rf "${TMP_DIR}"

echo ""
echo "============================================"
echo "Done! All files downloaded to cstrike/"
echo ""
echo "Next steps:"
echo "  1. Review the downloaded files"
echo "  2. Commit everything to git"
echo "  3. The install.sh/win.bat will overlay these"
echo "============================================"
