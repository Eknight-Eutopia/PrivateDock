class ShopStreetService:
    def __init__(self):
        self._goods: dict[int, list[dict]] = {}

    def get_goods(self, commander_id: int) -> list[dict]:
        return self._goods.get(commander_id, [])

    def purchase(self, commander_id: int, goods_id: int) -> bool:
        goods = self._goods.get(commander_id, [])
        for g in goods:
            if g.get("id") == goods_id and g.get("buy_count", 0) > 0:
                g["buy_count"] -= 1
                return True
        return False
