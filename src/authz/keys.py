# role names
RoleAdmin = "admin"
RolePlayer = "player"

# permission keys
PermAdminAuthz = "admin.authz"
PermAdminUsers = "admin.users"
PermAdminPermission = "admin.permission_policy"
PermPlayers = "players"
PermGameData = "game_data"
PermShop = "shop"
PermNotices = "notices"
PermExchangeCodes = "exchange_codes"
PermActivities = "activities"
PermJuustagram = "juustagram"
PermServer = "server"
PermMeResources = "me.resources"
PermMeShips = "me.ships"
PermMeItems = "me.items"
PermMeSkins = "me.skins"


def known_permissions() -> dict[str, str]:
    return {
        PermAdminAuthz: "Manage roles and permissions",
        PermAdminUsers: "Manage staff accounts",
        PermAdminPermission: "Manage permission policy",
        PermPlayers: "Manage player accounts",
        PermGameData: "Manage game data",
        PermShop: "Manage shop offers",
        PermNotices: "Manage notices",
        PermExchangeCodes: "Manage exchange codes",
        PermActivities: "Manage activities",
        PermJuustagram: "Manage Juustagram",
        PermServer: "Manage server",
        PermMeResources: "Self resources read/update",
        PermMeShips: "Give ships to self",
        PermMeItems: "Give items to self",
        PermMeSkins: "Give skins to self",
    }
