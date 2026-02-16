# CS 1.6 Modded Server

## About

A Counter-Strike 1.6 Dedicated Server (HLDS) that is easy to deploy and update on Linux (Ubuntu) and Windows, with support for Google Cloud Platform.

Every time you want to boot the server, you should run `gcp.sh` (if on Google Cloud) or `install.sh` (on Linux) and it will ensure your OS is up to date, CS 1.6 is up to date, and pull down the latest patches from this mod (any updates that I push up).

Any changes you have made to the files in this mod will be overwritten so I have created a "[custom files](#custom-files)" folder where you mirror the contents of the `cstrike/` folder, and any files you want to tweak, you put in there in the same spot and they will always overwrite the mod's default files. Read more about it [here](#custom-files).

The simple quick setup:

1. [Create your firewall rules](#create-firewall-rule)
2. [Provision your server on Google Cloud](#create-instance) or [set up on Linux](#running-on-linux) or [Windows](#running-on-windows)
3. [SSH into server](#ssh-to-server) (if GCP)
4. [Install](#install-mod)
5. [Create your custom files for hostname, admins etc](#custom-files)
6. Ensure you have followed the steps for creating an [online server](#creating-an-online-server) or [LAN server](#creating-a-lan-server)

Your server should be up and running!

Getting up and running:

- [Running on Google Cloud](#running-on-google-cloud)
- [Running on Linux](#running-on-linux)
- [Running on Windows](#running-on-windows)

## Mods

| Mod | Version | Description |
|---|---|---|
| [Metamod-P](https://github.com/Bots-United/metamod-p) | 1.21p38 | Plugin loader for HLDS |
| [AMX Mod X](https://www.amxmodx.org/) | 1.9.0-git5259 | Server-side scripting framework |
| [GunGame](https://github.com/xLeviNx/GunGame) | 2.13c | Turbo GunGame — level through weapons by getting kills |
| [CSDM Sake](https://github.com/s4ke/CSDMsake) | 1.1e | Deathmatch with instant respawn and weapon menus |
| [CS PugMod](https://github.com/SmileYzn/CS_PugMod-Archive) | 3.0.0 | Competitive PUG system (ready-up, map vote, knife round, LO3) |
| [Advanced Quake Sounds](https://github.com/ClaudiuHKS/AdvancedQuakeSounds) | 8.0 | Multikill announcer sounds |
| [RockTheVote Custom](https://forums.alliedmods.net/showthread.php?t=207493) | 1.8 | Players can vote to change the map early |
| [Kreedz (xPaw)](https://github.com/xPaw/AMXX-Plugins/tree/master/plugins/Kreedz) | 1.0 | KZ timer, checkpoints, hook, leaderboards, anti-cheat |
| [uSurf](http://forums.alliedmods.net/showthread.php?t=16418) | 5.2 | Surf management (checkpoints, timer, bunnyhop, semiclip) |

All mod binaries are committed to the repo in `cstrike/`. Linux `.so` and Windows `.dll` binaries have different filenames so they coexist in the same directories.

## Game modes

The server starts in **vanilla** mode with only core plugins active (admin system, damage stats). Use the server console or RCON to switch modes — each mode automatically changes to an appropriate map:

| Mode | Command | Description | Maps |
|---|---|---|---|
| Vanilla (default) | `exec vanilla.cfg` | Standard CS 1.6 with admin menu and damage stats | Standard maps (de_dust2, de_inferno, etc.) |
| GunGame | `exec gg.cfg` | Turbo GunGame — reversed weapon order (best to worst), instant respawn, knife steals a level | Custom GunGame maps (gg_simpsons, gg_buzz, etc.) |
| Deathmatch | `exec dm.cfg` | Instant respawn FFA with weapon menu, Quake Sounds | Custom aim/fy maps (aim_map, fy_iceworld, etc.) |
| Competitive (PUG) | `exec comp.cfg` | PugMod — players `.ready` up, vote map, pick teams, knife round, Live on 3 | Standard + custom competitive maps |
| KZ (Kreedz) | `exec kz.cfg` | Kreedz climbing — timer, checkpoints, hook, noclip, leaderboards | KZ maps (kz_longjumps2, bkz_goldbhop, etc.) |
| Surf | `exec surf.cfg` | Surf — checkpoints, timer, bunnyhop, auto-jump, semiclip, godmode | Surf maps (surf_ski_2, surf_egypt, etc.) |

### Changing modes

Via RCON or server console:
```
rcon exec gg.cfg
```

The mode config will automatically change the map. The mode persists across map rotations until you switch to a different mode.

### Custom overrides per mode

Each mode config executes a `custom_*.cfg` at the end for your overrides (hostname, extra settings, etc.):

| Mode | Custom file |
|---|---|
| All modes (server start) | `custom_server.cfg` |
| GunGame | `custom_gg.cfg` |
| Deathmatch | `custom_dm.cfg` |
| Competitive (PUG) | `custom_comp.cfg` |
| Vanilla | `custom_vanilla.cfg` |
| KZ (Kreedz) | `custom_kz.cfg` |
| Surf | `custom_surf.cfg` |

See [Custom files](#custom-files) for details on how to use these.

## Admin setup

Admins and moderators are configured in `cstrike/addons/amxmodx/configs/users.ini`. To add yourself, find your SteamID (e.g. via [steamid.io](https://steamid.io/)) and add a line:

```
"STEAM_0:0:12345" "" "abcdefghijklmnopqrstu" "ce"
```

- **Admin flags** (`abcdefghijklmnopqrstu`): Full access including immunity
- **Moderator flags** (`bcdefghijklmnopqrstu`): Everything except immunity

### Admin commands

Open console (`~` key) and type these commands:

**Menus:**

| Command | Description |
|---|---|
| `amxmodmenu` | Main admin menu (players, maps, cvars, commands) |
| `amx_cmdmenu` | Command menu (game modes, restart round, friendly fire) |

**Player management (console):**

| Command | Description |
|---|---|
| `amx_kick <name or #id> [reason]` | Kick a player |
| `amx_ban <name or #id> <minutes> [reason]` | Ban a player (0 = permanent) |
| `amx_unban <steamid or ip>` | Unban a player |
| `amx_slay <name or #id>` | Kill a player |
| `amx_slap <name or #id> [damage]` | Slap a player |
| `amx_who` | Show connected players and admin status |
| `amx_last` | Show last disconnected players |

**Server management (console):**

| Command | Description |
|---|---|
| `amx_map <mapname>` | Change map immediately |
| `amx_votemap <map1> <map2> [map3] [map4]` | Start a map vote |
| `amx_cvar <cvar> [value]` | Get or set a server variable |
| `amx_rcon <command>` | Execute an RCON command |
| `amx_pause` | Pause/unpause the game |
| `amx_plugins` | List loaded plugins |

**Chat commands (say in chat):**

| Command | Description |
|---|---|
| `say amx_nextmap <mapname>` | Set the next map |

### Player commands

Players can type these in chat (press `Y`):

| Command | Description |
|---|---|
| `say /rank` | Show your rank on the server |
| `say /top15` | Show the top 15 players |
| `say /statsme` | Show your personal stats |
| `say /hp` | Show who killed you and their remaining HP |
| `say timeleft` | Show time remaining on current map |
| `say thetime` | Show current server time |
| `say nextmap` | Show the next map in rotation |
| `say currentmap` | Show the current map name |
| `say /me` | Display your stats to all players |
| `say rtv` | Rock the vote — vote to change the map early |

**KZ mode commands:**

| Command | Description |
|---|---|
| `say /cp` | Save a checkpoint |
| `say /gc` | Teleport to last checkpoint |
| `say /stuck` | Teleport to previous checkpoint |
| `say /start` | Teleport to start position |
| `say /timer` | Toggle timer display |
| `say /pause` | Pause your timer and freeze |
| `say /unpause` | Resume playing |
| `say /noclip` | Toggle noclip (fly through walls) |
| `say /hook` | Toggle grappling hook |
| `say /spec` | Toggle spectator mode |
| `say /invis` | Toggle player invisibility |

**Surf mode commands:**

| Command | Description |
|---|---|
| `say /checkpoint` | Save a checkpoint |
| `say /gocheck` | Teleport to last checkpoint |
| `say /timer` | Toggle speed timer |
| `say /respawn` | Respawn at map start |
| `say /surfhelp` | Show surf help MOTD |

## Developer setup

### Updating mod binaries

If you need to update the mod framework binaries (Metamod, AMX Mod X, etc.), run the download script:

```bash
bash download-mods.sh
```

This downloads all framework binaries (Linux `.so` + Windows `.dll`) into `cstrike/`, then you commit the results to git. The install/update scripts just pull the repo zip - no runtime downloads needed.

### Compiling plugins

AMX Mod X plugins are written as `.sma` source files and compiled to `.amxx` bytecode. The compiler (`amxxpc`) is included in the AMX Mod X download.

**Docker (recommended — works on any OS including macOS ARM64):**
```bash
docker run --rm --platform linux/386 \
  -v "$PWD/cstrike/addons/amxmodx:/amxmodx" \
  -w /amxmodx/scripting \
  debian:bullseye-slim \
  ./amxxpc myplugin.sma -o../plugins/myplugin.amxx
```

The `amxxpc` compiler is a Linux x86 binary, so Docker is the easiest way to run it from macOS or Windows without WSL.

**Linux (native):**
```bash
cd cstrike/addons/amxmodx/scripting
./amxxpc myplugin.sma -o../plugins/myplugin.amxx
```

**Windows:**
```cmd
cd cstrike\addons\amxmodx\scripting
amxxpc.exe myplugin.sma -o..\plugins\myplugin.amxx
```

The `-o` flag specifies where to output the compiled `.amxx` file. Plugin source files (`.sma`) go in `scripting/`, compiled plugins (`.amxx`) go in `plugins/`.

Both compilers live in `cstrike/addons/amxmodx/scripting/` — `amxxpc` (Linux) and `amxxpc.exe` (Windows).

## Custom files

Any changes you have made to the files in this mod will be overwritten when the update scripts are run. I have created a folder `/custom_files/` in the root of the project, where you mirror the contents of the `cstrike/` folder, and any files you want to tweak, you put in there in the same spot and they will always overwrite the mod's default files.

You can see an example of what custom files look like in the `/custom_files_example/` directory.

### Custom config overrides

The easiest way to customize your server is through the `custom_*.cfg` files. Each mode config (`gg.cfg`, `dm.cfg`, etc.) executes its corresponding custom config at the end, so your settings always take priority.

To use them, copy the files from `custom_files_example/` to `custom_files/`:

```bash
cp -r custom_files_example/* custom_files/
```

Then edit the files in `custom_files/` to your liking. For example, to set your server hostname per mode:

| File | Example content |
|---|---|
| `custom_files/custom_server.cfg` | `hostname "My Server"` |
| `custom_files/custom_gg.cfg` | `hostname "My Server GunGame"` |
| `custom_files/custom_dm.cfg` | `hostname "My Server Deathmatch"` |
| `custom_files/custom_comp.cfg` | `hostname "My Server PUG"` |
| `custom_files/custom_vanilla.cfg` | `hostname "My Server"` |
| `custom_files/custom_kz.cfg` | `hostname "My Server KZ"` |
| `custom_files/custom_surf.cfg` | `hostname "My Server Surf"` |

The `custom_files/` folder persists across server updates. The install scripts automatically merge its contents into `cstrike/`.

You can override the custom files folder name with the `CUSTOM_FOLDER` environment variable (Linux/GCP) or the `custom_folder` setting in `win.ini` (Windows).

## Creating an online server

If you are hosting an online server, you need to create a Steam [Game Server Login Token](https://steamcommunity.com/dev/managegameservers) using Game ID `90`. Your server will not be visible in the server browser without this. Put this value in the `STEAM_ACCOUNT` environment variable.

Make sure you [port forward](https://portforward.com/router.htm) on your router TCP/UDP: `27015` and UDP: `27020` (HLTV) so players can connect from the internet.

## Creating a LAN server

**Linux:** Set `sv_lan 1` in your `custom_files/custom_server.cfg`.

**Windows:** Uncomment `sv_lan=1` in `win.ini`.

## Environment variables

Key | Default value | What is it
--- | --- | ---
`RCON_PASSWORD` | `changeme` | Remote console password to control server
`STEAM_ACCOUNT` | `` | [Game Server Login Token](https://steamcommunity.com/dev/managegameservers) (Game ID: 90) required for online servers
`SERVER_PASSWORD` | `` | Optional server password for private servers
`MOD_URL` | `https://github.com/kus/cs2-modded-server/archive/refs/heads/cs1.6.zip` | The zip for mod files to download and extract
`PORT` | `27015` | Server port
`MAXPLAYERS` | `32` | Max player limit
`MAP` | `de_dust2` | Starting map
`SYS_TICRATE` | `128` | Server tick rate
`DUCK_DOMAIN` | `` | [Duck DNS](https://www.duckdns.org/) domain for free dynamic DNS
`DUCK_TOKEN` | `` | [Duck DNS](https://www.duckdns.org/) access token
`CUSTOM_FOLDER` | `custom_files` | Folder for your custom file overrides

### Windows settings (win.ini)

| Key | Default | Description |
|---|---|---|
| `ip_internet` | `1.1.1.1` | Your public IP address |
| `custom_folder` | `custom_files` | Custom files folder |
| `rcon_password` | `changeme` | RCON password |
| `server_password` | *(commented out)* | Server join password |
| `sv_lan` | *(commented out)* | Set to `1` for LAN server |
| `cs16_players` | `32` | Max players |
| `cs16_port` | `27015` | Server port |
| `cs16_map` | `de_dust2` | Starting map |
| `cs16_ticrate` | `128` | Server tick rate |

## Running on Google Cloud

### Create firewall rule
```
gcloud compute firewall-rules create cs16 \
--allow tcp:27015-27020,udp:27015-27020
```

### Create instance

Ensure you have all the settings for your [environment variables](#environment-variables).

```
gcloud beta compute instances create <instance-name> \
--maintenance-policy=TERMINATE \
--project=<project> \
--zone=australia-southeast1-c \
--machine-type=e2-medium \
--network-tier=PREMIUM \
--metadata=RCON_PASSWORD=changeme,STEAM_ACCOUNT=changeme,MOD_URL=https://github.com/kus/cs2-modded-server/archive/refs/heads/cs1.6.zip,startup-script="echo \"Delaying for 30 seconds...\" && sleep 30 && cd / && /gcp.sh" \
--no-restart-on-failure \
--scopes=https://www.googleapis.com/auth/devstorage.read_only,https://www.googleapis.com/auth/compute.readonly,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/servicecontrol,https://www.googleapis.com/auth/service.management.readonly,https://www.googleapis.com/auth/trace.append \
--tags=cs16 \
--image-family=ubuntu-2204-lts \
--image-project=ubuntu-os-cloud \
--boot-disk-size=30GB \
--boot-disk-type=pd-standard \
--boot-disk-device-name=<instance-name>
```

Note: CS 1.6 is much lighter than CS:GO/CS2. An `e2-medium` instance is sufficient (2 vCPU, 4GB RAM). You only need ~30GB disk space.

### SSH to server
```
gcloud compute ssh <instance-name> \
--zone=australia-southeast1-c
```

### Install mod
```
sudo su
cd / && curl --silent --output "gcp.sh" "https://raw.githubusercontent.com/kus/cs2-modded-server/refs/heads/cs1.6/gcp.sh" && chmod +x gcp.sh && bash gcp.sh
```

If the installation has paused for a long time, restart the server and do it again. Note that HLDS (App ID 90) sometimes requires multiple SteamCMD runs to fully download - the install script handles this automatically.

### Stop server
```
gcloud compute instances stop <instance-name> \
--zone australia-southeast1-c
```

### Start server
```
gcloud compute instances start <instance-name> \
--zone australia-southeast1-c
```

### Delete server
```
gcloud compute instances delete <instance-name> \
--zone australia-southeast1-c
```

### Turn VM off at 3:30AM every day

SSH into the VM, switch to root `sudo su`, open crontab `nano /etc/crontab` and append:

```
30 3    * * *   root    shutdown -h now
```

## Running on Linux

Make sure you have **10GB free space**.

Ensure you have all the settings for your [environment variables](#environment-variables).

* **If setting up internet server:**

   Set environment variable `STEAM_ACCOUNT` to your [Game Server Login Token](https://steamcommunity.com/dev/managegameservers) (Game ID: 90)

   Make sure you [port forward](https://portforward.com/router.htm) on your router TCP/UDP: `27015` and UDP: `27020` so players can connect from the internet.

* **If setting up LAN server:**

   No GSLT needed. Set `sv_lan 1` in `custom_files/custom_server.cfg`.

```
sudo su
export RCON_PASSWORD="changeme"
export STEAM_ACCOUNT=""
export SERVER_PASSWORD=""
export PORT="27015"
export MAXPLAYERS="32"
export MAP="de_dust2"
cd / && curl --silent --output "install.sh" "https://raw.githubusercontent.com/kus/cs2-modded-server/refs/heads/cs1.6/install.sh" && chmod +x install.sh && bash install.sh
```

When the server starts, you can connect via the game console: `connect <your-ip>:27015`

## Running on Windows

Make sure you have **10GB free space**.

[Download this repo](https://github.com/kus/cs2-modded-server/archive/refs/heads/cs1.6.zip) and extract it to where you want your server (i.e. `C:\Server\cs16-modded-server`). All the following instructions will use this as the root.

Create a folder `steamcmd` and [download SteamCMD](https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip) and extract it inside `steamcmd` so you should have `\steamcmd\steamcmd.exe`.

Open `\win.ini` and configure your settings:
- Set `rcon_password` to your desired RCON password
- Set `ip_internet` to your [public IP](http://checkip.amazonaws.com/) (for internet servers)
- Uncomment `sv_lan=1` for LAN servers
- Uncomment `server_password` for private servers

* **If setting up internet server:**

   Create a [Game Server Login Token](https://steamcommunity.com/dev/managegameservers) with Game ID `90` and add `sv_setsteamaccount "YOUR_TOKEN"` to your `custom_files/custom_server.cfg`.

   Make sure you [port forward](https://portforward.com/router.htm) on your router TCP/UDP: `27015` and UDP: `27020` so players can connect from the internet.

* **If setting up LAN server:**

   Uncomment `sv_lan=1` in `win.ini`.

Run `win.bat`

Accept both Private and Public connections on Windows Firewall.

## FAQ

### How do I connect to RCON remotely?

Use [HLSW](http://www.hlsw.net/) or any RCON tool. Connect to `<IP>:27015` and enter your RCON password.

### How do I add bots?

To add bots to a Counter-Strike 1.6 dedicated server, you must use server-side modifications, as the base game does not include a native bot system for dedicated servers.

### The server won't show in the server browser

Make sure you have a valid [Game Server Login Token](https://steamcommunity.com/dev/managegameservers) set via the `STEAM_ACCOUNT` environment variable or `sv_setsteamaccount` in your custom_server.cfg.

[PodBot MM](https://github.com/APGRoboCop/podbot_mm): The most common choice for dedicated servers. It works through Metamod and is highly configurable. [Guide](https://forums.alliedmods.net/showthread.php?t=220798#Installation)

### SteamCMD fails to download all files

HLDS (App ID 90) has a known bug where it requires multiple SteamCMD runs to fully download all files. The Linux install scripts handle this automatically by running `app_update 90 validate` multiple times. On Windows, `win.bat` also runs SteamCMD with retry logic.

## References

- [Valve HLDS Documentation](https://developer.valvesoftware.com/wiki/Half-Life_Dedicated_Server)
- [SteamCMD Documentation](https://developer.valvesoftware.com/wiki/SteamCMD)

## License

See `LICENSE` for more details.
