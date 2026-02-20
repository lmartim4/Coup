
class Player:

    def __init__(self, name: str, influences: list):
        self.name = name
        self.influences = influences          # cartas na mão
        self.revealed_influences = []        # cartas reveladas (viradas na mesa)
        self.coins = 2
