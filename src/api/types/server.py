from pydantic import BaseModel



class ConnectionDetail(BaseModel):
    hash: int = 0
    remote_addr: str = ""
    connected_at: str = ""
    commander_id: int = 0
    queue_max: int = 0
    queue_blocks: int = 0
    handler_errors: int = 0
    write_errors: int = 0



class ConnectionSummary(BaseModel):
    hash: int = 0
    remote_addr: str = ""
    connected_at: str = ""
    commander_id: int = 0



class ServerConfigResponse(BaseModel):
    bind_address: str = ""
    port: int = 0
    region: str = ""



class ServerConfigUpdate(BaseModel):
    bind_address: str = ""
    port: int = 0
    region: str = ""



class ServerMaintenanceResponse(BaseModel):
    enabled: bool = False



class ServerMaintenanceUpdate(BaseModel):
    enabled: bool = False



class ServerMetricsResponse(BaseModel):
    client_count: int = 0
    queue_max: int = 0
    queue_blocks: int = 0
    handler_errors: int = 0
    write_errors: int = 0
    packets_per_sec: float = 0.0



class ServerStatsResponse(BaseModel):
    client_count: int = 0



class ServerStatusResponse(BaseModel):
    name: str = ""
    commit: str = ""
    running: bool = False
    accepting: bool = False
    maintenance: bool = False
    uptime_sec: int = 0
    uptime_human: str = ""
    client_count: int = 0



class ServerUptimeResponse(BaseModel):
    uptime_sec: int = 0
    uptime_human: str = ""

