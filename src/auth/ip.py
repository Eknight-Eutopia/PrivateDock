def normalize_ip(addr: str) -> str:
    if ":" in addr and addr.count(":") >= 2:
        if addr.startswith("["):
            idx = addr.rfind("]:")
            if idx != -1:
                return addr[1:idx]
        else:
            idx = addr.rfind(":")
            if idx != -1:
                return addr[:idx]
    return addr
