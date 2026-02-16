#!/usr/bin/env bash

# download-maps.sh
# Downloads popular custom CS 1.6 maps for various game modes.
# Stock maps (de_dust2, de_inferno, etc.) are already included with HLDS.
# Run this locally, then commit the resulting cstrike/maps/ files to git.
#
# Usage: bash download-maps.sh [mode...]
#
# Examples:
#   bash download-maps.sh           # Download all modes
#   bash download-maps.sh gg dm     # Download only GunGame and Deathmatch maps
#   bash download-maps.sh awp surf  # Download only AWP and Surf maps
#
# Available modes: gg dm comp aim awp surf kz deathrun zombie hns knife
#
# Source: csboost.eu (direct BSP downloads, HTTP 200 = found, 302 = missing)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAPS_DIR="${SCRIPT_DIR}/cstrike/maps"
BASE_URL="https://www.csboost.eu/downloads/maps"

mkdir -p "${MAPS_DIR}"

TOTAL=0
OK=0
FAIL=0
SKIP=0
FAILED_MAPS=()

download_map() {
    local map="$1"
    local bsp="${map}.bsp"
    TOTAL=$((TOTAL + 1))

    if [ -f "${MAPS_DIR}/${bsp}" ]; then
        SKIP=$((SKIP + 1))
        return
    fi

    local url="${BASE_URL}/${bsp}"
    local http_code
    http_code=$(curl -sI -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")

    if [ "$http_code" = "200" ]; then
        if curl -sL -o "${MAPS_DIR}/${bsp}" "$url" 2>/dev/null; then
            echo "  OK  ${bsp}"
            OK=$((OK + 1))
        else
            echo "  FAIL ${bsp} (download error)"
            rm -f "${MAPS_DIR}/${bsp}"
            FAIL=$((FAIL + 1))
            FAILED_MAPS+=("$map")
        fi
    else
        echo "  MISS ${bsp} (HTTP ${http_code})"
        FAIL=$((FAIL + 1))
        FAILED_MAPS+=("$map")
    fi
}

# ==========================================================================
# MAP LISTS BY GAME MODE
# ==========================================================================

maps_gg() {
    echo ""
    echo "[GunGame] Downloading maps..."
    for map in \
        gg_simpsons \
        gg_buzz \
        gg_mini_dust2 \
        gg_dusty \
        gg_fy_simpsons \
        gg_fy_inferno \
        gg_mini_inferno \
        gg_arena \
        gg_playground \
        gg_crossfire \
        gg_camper \
        gg_aztec_pool \
    ; do
        download_map "$map"
    done
}

maps_dm() {
    echo ""
    echo "[Deathmatch] Downloading maps..."
    for map in \
        aim_map \
        aim_ak-colt \
        aim_headshot \
        aim_map_usp \
        aim_deagle5 \
        fy_iceworld \
        fy_pool_day \
        fy_snow \
        aim_aztec \
        aim_sk_ak_m4 \
        aim_map_pro \
        aim_deagle \
    ; do
        download_map "$map"
    done
}

maps_comp() {
    echo ""
    echo "[Competitive] Downloading custom maps (stock maps already in HLDS)..."
    for map in \
        de_cpl_mill \
        de_tuscan \
        de_clan1_mill \
        de_cpl_fire \
        de_season \
        de_contra \
        de_forge \
        de_cache \
        de_mirage \
        de_russka \
        de_cpl_strike \
        de_lite \
    ; do
        download_map "$map"
    done
}

maps_awp() {
    echo ""
    echo "[AWP] Downloading maps..."
    for map in \
        awp_india \
        awp_map \
        awp_city \
        awp_dust \
        awp_aztec \
        awp_ruins \
        awp_rats3 \
        awp_metro \
        awp_assault \
        awp_snow_india \
        awp_map2 \
        awp_l337sk337 \
    ; do
        download_map "$map"
    done
}

maps_surf() {
    echo ""
    echo "[Surf] Downloading maps..."
    for map in \
        surf_ski_2 \
        surf_ski_5 \
        surf_ninja \
        surf_simpsons_final \
        surf_egypt \
        surf_legendary \
        surf_ice \
        surf_iceday \
        surf_city \
        surf_green \
        surf_10x_reloaded \
        surf_sand \
    ; do
        download_map "$map"
    done
}

maps_kz() {
    echo ""
    echo "[KZ / Kreedz Climbing] Downloading maps..."
    for map in \
        kz_longjumps2 \
        kz_longjumps3 \
        kz_megabhop \
        bkz_goldbhop \
        kz_hopez \
        kz_hop \
        kz_kzdk_covebhop \
        kz_dalai_rats \
        kz_climbers_b01 \
        kz_man_bhop \
        kz_colors \
        kz_synergy_x2 \
    ; do
        download_map "$map"
    done
}

maps_deathrun() {
    echo ""
    echo "[Deathrun] Downloading maps..."
    for map in \
        deathrun_temple \
        deathrun_arctic \
        deathrun_poolday \
        deathrun_forest \
        deathrun_ice \
        deathrun_jigsaw \
        deathrun_cartoon \
        deathrun_horror \
        deathrun_extreme \
        deathrun_starwars \
        deathrun_projetocs \
        deathrun_skills \
    ; do
        download_map "$map"
    done
}

maps_zombie() {
    echo ""
    echo "[Zombie] Downloading maps..."
    for map in \
        zm_ice_attack \
        zm_dust2 \
        zm_lila_panic \
        zm_infantry \
        zm_beach \
        zm_foda \
        zm_ice_attack3 \
        zm_deko2 \
        zm_3rooms \
        zm_dust_world \
        zm_ice_attack2 \
        zm_fdust2x2 \
    ; do
        download_map "$map"
    done
}

maps_hns() {
    echo ""
    echo "[Hide and Seek] Downloading maps..."
    for map in \
        hns_floppytown \
        hns_floppytown_pro \
        hns_village \
        hns_bronx \
        hns_snowtown \
        hns_building_xnet \
        hns_snowhill \
        hns_midtown \
        hns_earthward \
        hns_poolday \
        hns_tyo \
        hns_gtgcity \
    ; do
        download_map "$map"
    done
}

maps_knife() {
    echo ""
    echo "[Knife Arena] Downloading maps..."
    for map in \
        ka_acer_2 \
        ka_roadwars_v2 \
        ka_trainfight \
        ka_leyna \
        ka_spires \
        ka_hell2 \
        ka_kungfuhustle \
        ka_underbelly \
        ka_survival \
        ka_killbox \
        ka_loco \
        ka_street \
    ; do
        download_map "$map"
    done
}

# ==========================================================================
# MAIN
# ==========================================================================

ALL_MODES=(gg dm comp awp surf kz deathrun zombie hns knife)

echo "============================================"
echo "CS 1.6 Custom Map Downloader"
echo "============================================"
echo ""
echo "Source: ${BASE_URL}"
echo "Target: ${MAPS_DIR}"
echo ""

if [ $# -eq 0 ]; then
    MODES=("${ALL_MODES[@]}")
else
    MODES=("$@")
fi

for mode in "${MODES[@]}"; do
    case "$mode" in
        gg|gungame)    maps_gg ;;
        dm|deathmatch) maps_dm ;;
        comp|competitive) maps_comp ;;
        awp)           maps_awp ;;
        surf)          maps_surf ;;
        kz|kreedz)     maps_kz ;;
        deathrun)      maps_deathrun ;;
        zombie|zm)     maps_zombie ;;
        hns)           maps_hns ;;
        knife|ka)      maps_knife ;;
        *)
            echo "Unknown mode: $mode"
            echo "Available: ${ALL_MODES[*]}"
            exit 1
            ;;
    esac
done

echo ""
echo "============================================"
echo "Results: ${OK} downloaded, ${SKIP} skipped (exist), ${FAIL} not found"
echo "============================================"

if [ ${#FAILED_MAPS[@]} -gt 0 ]; then
    echo ""
    echo "Maps not available on csboost.eu (source manually):"
    for m in "${FAILED_MAPS[@]}"; do
        echo "  - ${m}"
    done
    echo ""
    echo "Alternative sources:"
    echo "  https://gamebanana.com/mods/cats/5474"
    echo "  https://www.gamemodd.com/cs/maps/"
    echo "  https://www.17buddies.rocks"
fi
