class ArenaShopService:
    def __init__(self):
        self._offers: list[dict] = []

    def get_offers(self) -> list[dict]:
        return self._offers

    def refresh(self):
        pass
