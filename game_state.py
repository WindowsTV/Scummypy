class GameState:
    def __init__(self):
        self.flags = {
            "g_DEBUG": False,
            "g_interfaceVisible": False,
            "g_roomVisible": True,
            "g_cursorVisible": True,
            "g_lastRoom": -1,
            "g_lastCursor": None,
            "g_currentCursor": None,
            "g_itemOnCursor": None,
        }
        self.inventory = []

    def set_flag(self, name, value=True):
        self.flags[name] = value

    def get_flag(self, name, default=False):
        return self.flags.get(name, default)
    
    def add_item_to_inventory(self, item_id, value=True):
        self.inventory[item_id] = value

    def is_item_in_inventory(self, name, default=False):
        pass        