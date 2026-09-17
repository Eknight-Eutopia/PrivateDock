# PrivateDock Installation & Setup Guide

This guide walks you through setting up, configuring, and running **PrivateDock**, as well as connecting the Azur Lane EN client.

---

## Table of Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Running](#running)
4. [Connecting the Client](#connecting-the-client)
5. [Configuration Reference](#configuration-reference)
6. [Admin API](#admin-api)
7. [Troubleshooting](#troubleshooting)

---

## Requirements

Before you begin, ensure you have the following software and components installed:

- **Python**: Version **3.12** or higher.
  - Download from [python.org](https://www.python.org/downloads/).
  - Ensure `python` and `pip` are added to your system `PATH`.
- **Operating System**:
  - **Windows**: 10 / 11 / Server (run terminal as Administrator to bind port 80).
  - **Linux**: Ubuntu 22.04+, Debian 12+, Arch Linux, etc.
  - **Android**: Supported via Termux (for running the server directly on a phone).
- **Elevated Privileges**:
  - Port 80 is a privileged port. You will need Administrator privileges (Windows) or root / `CAP_NET_BIND_SERVICE` permissions (Linux) to bind port 80.
- **Game Client & Data**:
  - Official Azur Lane EN Android client (stock APK; root is not required on the client device for normal gameplay unless using on-device hosts redirection like AdAway).
  - Unpacked client Lua scripts: [AzurLaneTools/AzurLaneLuaScripts](https://github.com/AzurLaneTools/AzurLaneLuaScripts) (branch `main`). The server extracts its game configurations and templates from the `EN/` subfolder.
- **Git**: For cloning repositories.

---

## Installation

### 1. Recommended Directory Layout

It is recommended to organize your workspace with the server repository and unpacked Lua repository as siblings:

```text
AzurLane/
├── PrivateDock/       # PrivateDock server repository
│   ├── configurations/       # Server configuration files (server.json)
│   ├── data/                 # Converted JSON game data (generated)
│   ├── db/                   # Default SQLite database directory
│   ├── scripts/              # Data conversion and utility scripts
│   └── src/                  # Server source code
└── AzurLaneLuaScripts/       # Unpacked client Lua data
    └── EN/                   # English region data (sharecfg, gamecfg, sharecfgdata)
```

Clone both repositories:

```bash
git clone https://github.com/Forlorn01/PrivateDock.git
git clone https://github.com/AzurLaneTools/AzurLaneLuaScripts.git
```

### 2. Set Up Python Virtual Environment

Navigate to the `PrivateDock` folder and create a virtual environment:

```bash
cd PrivateDock
python -m venv .venv
```

Activate the virtual environment:

- **Windows (PowerShell)**:
  ```powershell
  .venv\Scripts\Activate.ps1
  ```
- **Windows (Command Prompt)**:
  ```cmd
  .venv\Scripts\activate.bat
  ```
- **Linux / macOS**:
  ```bash
  source .venv/bin/activate
  ```

### 3. Install Dependencies

Install the required runtime dependencies:

```bash
pip install -r requirements.txt
```

### 4. Convert Client Lua Data to JSON

PrivateDock loads game templates (ships, items, activities, shops, chapters) from JSON files in `data/EN/`. Run the conversion script to generate these files from `AzurLaneLuaScripts/EN`:

```bash
python scripts/convert_lua_to_json.py
```

By default, the script looks for `../AzurLaneLuaScripts/EN` and outputs to `data/EN`. If your files are stored in a different location, specify the custom paths:

```bash
python scripts/convert_lua_to_json.py --input "C:\path\to\AzurLaneLuaScripts" --output "data" --region EN
```

Command-line options for the converter:
- `--input <DIR>`: Root folder of unpacked Lua scripts (default: sibling `AzurLaneLuaScripts`).
- `--output <DIR>`: Target directory for converted JSON data (default: `data`).
- `--region <NAME>`: Region subfolder to convert (default: `EN`).
- `--workers <N>`: Worker processes for parallel conversion (`0` = auto/CPU count, `1` = sequential).

### 5. Database Setup

PrivateDock supports both **SQLite** and **PostgreSQL**.

- **SQLite (Default & Recommended)**:
  - Zero manual setup required.
  - On the first server launch, PrivateDock automatically creates `db/privatedock.db`, applies all database migrations, and seeds the initial game data (items, ships, configurations) from `data/EN/`.
- **PostgreSQL (Optional)**:
  - If you prefer PostgreSQL, create a database (e.g. `privatedock`) and set the DSN and schema in `configurations/server.json`:
    ```json
    "database": {
      "driver": "postgres",
      "dsn": "postgres://postgres:password@localhost:5432/privatedock?sslmode=disable",
      "schema_name": "privatedock"
    }
    ```

---

## Running

### Configure Server IP Address

Before the first launch, open `configurations/server.json` and set `servers[0].ip` to the address the game client will use to reach this machine:

```json
{
  "privatedock": {
    "bind_address": "0.0.0.0",
    "port": 80,
    "name": "Private Dock"
  },
  "servers": [
    {
      "id": 1,
      "name": "Private Dock",
      "ip": "192.168.0.100",
      "port": 80
    }
  ]
}
```

> [!IMPORTANT]
> Both values ship as `127.0.0.1`, which only works when the client runs on the same machine as the server — for example an emulator with ADB port forwarding.
> For a phone, a tablet, or an emulator on its own virtual network adapter you must change **both**:
> - `servers[0].ip` — the address handed to the client, e.g. `192.168.0.100`;
> - `privatedock.bind_address` — set it to `0.0.0.0`. While it is `127.0.0.1` the server listens on loopback only and never sees connections coming from other devices, no matter what `servers[0].ip` says.

### Command-Line Arguments

The server accepts several optional command-line flags:

| Flag | Short | Default | Description |
| :--- | :---: | :---: | :--- |
| `--config <PATH>` | | `configurations/server.json` | Path to JSON server configuration file |
| `--no-api` | | `false` | Disable the embedded FastAPI REST API server (port 2289) |
| `--reseed` | `-s` | `false` | Force a full re-seed of game data from `data/` into the database |
| `--adb` | `-a` | `false` | Start background ADB watcher to parse live client Unity/Lua logs |
| `--flush-logcat` | `-f` | `false` | Flush device logcat buffer before starting ADB watcher |
| `--restart` | `-r` | `false` | Automatically restart the Azur Lane game client via ADB on startup |

### Usage Examples

- **Standard Launch**:
  ```bash
  python -m src
  ```
- **Custom Config File**:
  ```bash
  python -m src --config configurations/my_server.json
  ```
- **Force Reseed Database After Updating Game Data**:
  ```bash
  python -m src -s
  ```
- **Run With Live ADB Logcat Monitoring**:
  ```bash
  python -m src --adb --flush-logcat
  ```

### Starting the Server

Run the server from the root of the `PrivateDock` directory:

```bash
# Windows (Run terminal as Administrator to allow port 80 binding):
python -m src
```

> [!NOTE]
> The embedded Admin API ships **disabled** (`"api": {"enabled": false}`), so `python -m src` starts only the game server and nothing listens on port 2289. Set `api.enabled` to `true` if you want it — see [Admin API](#admin-api). The `--no-api` flag does the opposite: it suppresses the API for a single run without touching the config.

---

## Connecting the Client

### 1. Redirect Client Traffic

Redirect `blhxusgate.yo-star.com` to your server LAN IP address using one of the following methods:

#### Method A: Hosts File / AdAway (Device or Emulator)

**With root** — edit `/system/etc/hosts` directly, or let [AdAway](https://adaway.org/) write it for you:
1. Install AdAway and grant it root access.
2. Add a redirection entry:
   ```text
   <YOUR_SERVER_LAN_IP> blhxusgate.yo-star.com
   ```
   *(Example: `192.168.0.100 blhxusgate.yo-star.com`)*
3. Apply changes and restart the game.

**Without root** — AdAway also has a VPN-based mode. It starts a local VPN, intercepts DNS queries and answers them itself, so an entry pointing at your server works like a hosts line without touching the system:
1. Install AdAway and pick the VPN-based method during setup.
2. Add the same entry, making sure it is created as a **redirect** to your LAN IP and not as a blocked host.
3. Start the AdAway VPN service, then launch the game.

> [!NOTE]
> The VPN-based mode has not been verified with this client yet. Two things to watch: a rule added as *blocked* is answered with an empty DNS response, so the client simply fails to connect — it has to be a redirect rule; and some games refuse to start while a VPN is active. If either bites, fall back to Method B or C.

#### Method B: Local DNS Server (No Root Required)
If your client device is not rooted:
1. Configure a DNS rewrite rule on your local router, Pi-hole, or AdGuard Home:
   - Domain: `blhxusgate.yo-star.com`
   - Target IP: `<YOUR_SERVER_LAN_IP>`
2. Point your phone/tablet DNS settings to that DNS server.

#### Method C: HTTP Proxy / Redirection Tool
Configure an HTTP proxy or iptables on your network to redirect port 80 traffic for `blhxusgate.yo-star.com` to `<YOUR_SERVER_LAN_IP>:80`.

### 2. Login

PrivateDock replaces the game gateway, **not** the account service. The stock client still performs its login against the official Yostar service, so you need a valid account there before the client will talk to your server:

- **Your existing account** — sign in the way you normally would.
- **An unnamed (guest) account** — the client can also create an account that is not bound to an e-mail address or to any third-party login. Use this if you would rather not involve your main account.

> [!IMPORTANT]
> Either way, the login itself is handled by the official servers: the client contacts them directly over the internet and only afterwards connects to your gateway. The client device therefore needs internet access for the login step, even though everything after it runs against your PrivateDock instance.

What reaches PrivateDock is only the numeric account id (`arg2`) that the client presents at the gateway — your credentials are never sent to it:

- The id is mapped to a local commander in the `yostarus_maps` table. Only that id is stored, nothing else about the account.
- **First login from a given account** — no commander exists yet, so the client asks for a commander name and a starter ship, and PrivateDock creates the record.
- **Later logins with the same account** — resume the same commander. Every account keeps its own separate progress on the same server, so switching accounts is a way to start fresh without wiping the database.

---

## Configuration Reference

The main configuration file is located at `configurations/server.json`.

### Reference Table

| Section | Key | Type | Default | Description |
| :--- | :--- | :---: | :---: | :--- |
| **`privatedock`** | `bind_address` | string | `"127.0.0.1"` | Network interface IP to bind to. Ships as loopback-only; set `0.0.0.0` to accept connections from other devices |
| | `port` | integer | `80` | Gateway TCP listening port (standard game port is 80) |
| | `name` | string | `"Private Dock"` | Server instance display name |
| | `require_private_clients` | boolean | `false` | Whether to restrict connections to private client builds |
| | `maintenance` | boolean | `false` | If `true`, advertises maintenance status to incoming clients |
| **`servers`** | `id` | integer | `1` | Server entry identifier |
| | `name` | string | `"Private Dock"` | Server name displayed on the in-game server selection screen |
| | `ip` | string | `"127.0.0.1"` | Gateway IP address sent to client for game connection |
| | `port` | integer | `80` | Gateway port sent to client for game connection |
| | `proxy_ip` | string | `null` | Optional external proxy IP |
| | `proxy_port` | integer | `null` | Optional external proxy port |
| **`database`** | `driver` | string | `"sqlite"` | Database engine (`"sqlite"` or `"postgres"`) |
| | `path` | string | `"db/privatedock.db"` | SQLite database file path relative to repository root |
| | `dsn` | string | `""` | Full connection URI (e.g. `postgres://user:pass@host:5432/db`) |
| | `schema_name` | string | `"privatedock"` | Target schema name for PostgreSQL |
| **`region`** | `default` | string | `"EN"` | Game client region (`"EN"`, `"JP"`, `"CN"`, `"TW"`, `"KR"`) |
| **`create_player`** | `skip_onboarding` | boolean | `false` | If `true`, skips prologue missions and intro battles |
| | `name_blacklist` | array | `[]` | List of disallowed commander names |
| | `name_illegal_pattern` | string | `""` | Regex pattern matching forbidden characters in names |
| **`api`** | `enabled` | boolean | `false` | Whether to start the embedded FastAPI REST API server. Disabled in the shipped configuration |
| | `port` | integer | `2289` | HTTP port for REST API |
| | `environment` | string | `"development"` | API environment mode (`"development"` or `"production"`) |
| | `cors_origins` | array | `["*"]` | Allowed CORS origins for browser access |
| **`auth`** | `disable_auth` | boolean | `false` | If `true`, disables authentication checks on API routes |
| | `session_ttl_seconds` | integer | `86400` | Web admin session lifetime in seconds (1 day) |
| | `cookie_name` | string | `"privatedock_admin_session"` | Session cookie identifier |
| **`logs`** | `max_age_days` | integer | `14` | Delete `.log` files older than this many days at startup (`<= 0` disables the rule) |
| | `max_total_mb` | integer | `30` | Then delete the oldest logs until the `logs/` directory is below this size in MB (`<= 0` disables the rule) |

---

## Admin API

PrivateDock includes an embedded REST API built with FastAPI. It is **disabled** in the shipped `configurations/server.json` (`api.enabled: false`) because the game server does not need it — nothing listens on port 2289 until you turn it on.

- **Address**: `http://localhost:2289/` (configurable via `api.port` in `server.json`).
- **Swagger Documentation**: Interactive OpenAPI documentation is accessible in your browser at:
  ```text
  http://localhost:2289/docs
  ```
- **Current Status**:
  - System health, server status, permission policies, and challenge routes are active.
  - User management endpoints (`/api/v1/admin/users`) and web frontend dashboard are currently work in progress (`not implemented`).
- **Disabling the API**:
  - If you do not need the HTTP API service, run the server with `--no-api` or set `"api": {"enabled": false}` in `server.json`.

---

## Troubleshooting

### 1. Port 80 Permission Denied (`PermissionError` / `[Errno 13]`)

- **Cause**: Binding to ports below 1024 requires administrator/root privileges on most operating systems.
- **Solution**:
  - **Windows**: Right-click your terminal application (PowerShell or Command Prompt) and select **Run as administrator**.
  - **Linux**: Run with `sudo` or grant port binding capability to the Python executable:
    ```bash
    sudo setcap 'cap_net_bind_service=+ep' $(readlink -f $(which python3))
    ```

### 2. Port 80 Already in Use (`[Errno 10048]` or `[Errno 98]`)

- **Cause**: Another service is already listening on port 80.
- **Diagnostics & Solution**:
  - **Windows**:
    ```powershell
    netstat -ano | findstr :80
    ```
    Identify the PID in the rightmost column, then inspect the process:
    ```powershell
    tasklist /fi "pid eq <PID>"
    ```
    Common culprits on Windows:
    - IIS / World Wide Web Publishing Service: Stop it via `net stop w3svc`.
    - Skype, Apache, or Nginx.
    - Another local proxy or traffic-capture tool you may have left running.
  - **Linux**:
    ```bash
    sudo ss -tulpn | grep :80
    ```
    Stop the occupying service (`systemctl stop apache2` or `nginx`).

### 3. Client Stuck on "Loading..." or Connection Error

- **Verify Server LAN IP**: Check that `servers[0].ip` in `configurations/server.json` is set to your machine's actual LAN IP address (e.g. `192.168.0.100`). The shipped default `127.0.0.1` only works when the client runs on the same machine, so a phone or a separate emulator will not connect until this is changed.
- **Firewall Settings**: Ensure inbound TCP traffic on port 80 (and port 2289 if using the API) is allowed by your server's firewall (e.g. Windows Defender Firewall or Linux `ufw`).
- **Verify Connectivity From Client Device**: Open a web browser on the client phone/tablet and navigate to `http://<YOUR_SERVER_LAN_IP>/`. The connection should be accepted (or reset), confirming network reachability.
- **DNS / Hosts Check**: Ensure your hosts redirection on the client resolves `blhxusgate.yo-star.com` directly to your server IP.

### 4. Client Errors & Debugging via ADB

When the game client behaves unexpectedly without showing a server-side error, inspect the client's internal Unity and Lua logcat logs:

1. Enable **USB Debugging** on the Android device or emulator.
2. Connect via ADB:
   ```bash
   adb devices
   ```
3. Stream Unity and game logs:
   ```bash
   adb logcat -s Unity
   ```
4. Or use PrivateDock's built-in ADB watcher:
   ```bash
   python -m src --adb --flush-logcat
   ```
Client-side Lua errors and stack traces will be printed directly, helping identify any data mismatches or missing packet fields.
