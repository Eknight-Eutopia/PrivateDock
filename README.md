# PrivateDock

**PrivateDock** is a high-performance private server emulator for the mobile game [Azur Lane](https://en.wikipedia.org/wiki/Azur_Lane), written in Python 3.12+ with `asyncio`. It targets official EN Android clients and allows playing with a stock, unmodified game client.

---

## Features

PrivateDock implements most of the core game systems.

Already works:
- Secretary, Juustagram
- Dock, Fleets (incl. submarines), Equipment, Meowfficers
- Ships Build (with custom max orders), Requisition, Retire
- Shops, Missions, Handbook, Tactical Classes, Dorm, Fleet Technology, Research Academy, Shipyard
- Main Campaign, War Archives, Daily Raids, Exercises

For a per-system breakdown of what
works, what is only partly covered, and what is not implemented yet, see the
**[Implementation Status](docs/STATUS.md)** page.

---

## Quick Start

For full installation and configuration instructions, see the **[Installation Guide](docs/INSTALL.md)**.

1. **Prerequisites**: Python 3.12+, Azur Lane EN client, and [AzurLaneLuaScripts](https://github.com/AzurLaneTools/AzurLaneLuaScripts).
2. **Clone & Install Dependencies**:
   ```bash
   git clone https://github.com/AzurLaneTools/AzurLaneLuaScripts.git
   git clone https://github.com/Forlorn01/PrivateDock.git
   cd PrivateDock
   python -m venv .venv
   # Windows:
   .venv\Scripts\Activate.ps1
   # Linux / macOS:
   source .venv/bin/activate

   pip install -r requirements.txt
   ```
3. **Convert Game Data**:
   ```bash
   python scripts/convert_lua_to_json.py
   ```
4. **Configure Server**:
   Edit `configurations/server.json` and set `servers[0].ip` to your machine's LAN IP address.
5. **Run**:
   ```bash
   # Windows (Run PowerShell as Administrator to bind port 80):
   python -m src
   ```

---

## Architecture Highlights

- **Asynchronous Event Loop**: Built on Python `asyncio` for high concurrency and low latency.
- **Dynamic Protobuf Engine**: Dynamic generation of 1,700+ protobuf message types from binary descriptors without requiring compiled `.py` proto stubs.
- **Dual Database Backends**:
  - **SQLite** (default): Zero-configuration file-based database (`db/privatedock.db`), ideal for local or single-player setups.
  - **PostgreSQL**: Production-grade engine with asynchronous connection pooling via `asyncpg`.
  - Built-in SQL dialect translation layer and automated migrations.
- **Stock Client Compatibility**: Works with the unmodified EN client via DNS/hosts redirection.

---

## Thanks & Credits

- [AzurLaneTools](https://github.com/AzurLaneTools) for providing the unpacked client Lua scripts in [AzurLaneLuaScripts](https://github.com/AzurLaneTools/AzurLaneLuaScripts).
- [Molly](https://github.com/ggmolly) for [Belfast](https://github.com/ggmolly/belfast), which served as the original Go server foundation.