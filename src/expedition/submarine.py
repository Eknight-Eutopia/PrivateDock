class SubmarineExpedition:
    def __init__(self):
        self._expeditions: list[dict] = []

    def get_info(self) -> list[dict]:
        return self._expeditions
