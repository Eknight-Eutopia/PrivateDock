# PrivateDock — Implementation Status

PrivateDock covers most of the core game systems, but not all of them. This page lists what
you can expect to actually work, so you don't go looking for a feature that isn't there yet.

| Status | Meaning |
| :--- | :--- |
| **Works** | Implemented and tested in game. |
| **Should work** | Implemented, but not yet confirmed in game. |
| **Partly** | The main part works; some pieces are missing. |
| **Doesn't work** | Not implemented — the feature is not usable. |

This list is maintained by hand and may lag slightly behind the code.

---

## Works

### Account & login
Gateway handshake, server list, joining a server, character creation and onboarding. The EN
client is the one that is supported.

### Lobby & Secretary
Secretaries (including the "random secretary" display), skins, attire & style, and secretary
affinity.

### Commander Handbook
Rookie and Guide missions with real milestone gating and continuous progress tracking — pages
unlock as you actually complete their sub-tasks. The third (tech) tab unlocks together with
the Shipyard.

> Some sub-missions depend on systems that aren't in yet (META Lab, Private
> Quarters, Operation Siren), so those particular missions cannot be finished for now.

### Dock & Fleets
Ship locks, favourites, oath, skins, and surface / submarine fleet management.

### Equipment & Augment Modules (SP Weapons)
Gear enhancement, crafting, disassembling, and augment modules. The Gear Lab (equipment
transform in the Technology screen) works, including the full transform chains.

### Depot
Item inventory, materials, equipment boxes, designs and consumables.

### Tactical Classes
Skill training with tactical skill books, including live timers.

### Dorm (Backyard)
Two floors, furniture and theme templates, ship resting, food buffs, comfort, and continuous
EXP accrual.

### Fleet Technology
Faction tech points.

### Missions
Daily, weekly and main-campaign missions.

### Main Campaign
Chapters 1–4 including Hard stages: grid movement, enemy fleets, ambushes, boss spawns, star
rewards, Clearing Mode, and submarine support.

### Exercise (PvP)
Opponents are bots only — there are no live players. Tier promotions, rank-up reward mails,
merit currency, and season resets.

### Daily Raids & Commissions
Daily escort and tactical challenge stages with fast sweep, plus urgent and daily commission
dispatch.

### Shops
Munitions / General, Medal, Fragment and Charge shop packs. The weekly and monthly free supply
packs are granted; **real-money purchases are not supported**.

### Others
High-Efficiency Combat Logistics Plan, Public Guild, and the Mailbox.

---

## Partly

### Juustagram
Works, but a number of entries have no content yet.

### Construction
Light, Heavy and Special pools, medal exchange and ship retirement work. Wishing Well and the
build event are inactive for now — see _Deferred_ below.

### Operation Siren (World)
Only a small part is present; the full map / zone / fleet loop is not implemented.

### Admin web API
Optional and **off by default**. Server status, permissions, chapter state, player data and
shop routes work; user management, registration, exchange codes and similar routes are not
implemented.

---

## Should work (not yet tested in game)

- **Research Academy & Shipyard** — the PR/DR dock and research projects are implemented, but
  no ship has actually been produced through it yet.
- **War Archives & Remaster**

---

## Doesn't work

- **Operational Handover** — stage clears are not registered yet
- **Island Planner**
- **Private Quarters** (3D dorm)
- **Project Identity**
- **Cat Lodge** (Meowfficers)
- **META Lab**
- **Guild** — only Public Guild is available
- **Challenge Mode**

---

## Deferred & limitations

- **Build event / Wishing Well** — deferred until the next official EN build event, so the
  server's response can be aligned with it. Standard construction is unaffected.
- **Real-money purchases** are not supported — there is no payment processing.
- **Tests** are not part of this repository yet.
