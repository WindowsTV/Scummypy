class GameState:
    def __init__(self, flags=None):
        if flags is None:
            self.flags = {
                "g_DEBUG": False,
                "g_interfaceVisible": False,
                "g_roomVisible": True,
                "g_lastRoom": -1,
                "g_currentRoom": -1,
                "g_cursorVisible": True,
                "g_lastCursor": None,
                "g_currentCursor": None,
                "g_itemOnCursor": None,
                "g_screenTextEnabled": True,
                "g_musicMuted": False,
                "g_talkiesMuted": False,
                "g_soundsMuted": False,
            }
        else:
            self.flags = flags.copy()  # <- key line
        self.inventory = []

    def set_flag(self, name, value=True):
        self.flags[name] = value

    def get_flag(self, name, default=None):
        return self.flags.get(name, default)
    
    def add_item_to_inventory(self, item_id, value=True):
        self.inventory[item_id] = value

    def is_item_in_inventory(self, name, default=False):
        pass        