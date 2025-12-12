import pygame
import scummypy.resources as Resources

class Cursors:
    @staticmethod
    def HCursor(filename: str, hotspot=(0, 0)) -> pygame.cursors.Cursor:
        name=filename
        surf = Resources.load_image(f"cursors/{filename}")
        cursor = pygame.cursors.Cursor(hotspot, surf)
        return cursor

    HIGHLIGHT = None
    NORMAL = None
    NWDeep = None
    #NORTH
    NEDeep = None
    #EAST
    EShallow = None
    #SOUTH
    WEST = None

    #BACK TO NORTH

    @classmethod
    def load_all(cls):
        cls.HIGHLIGHT = cls.HCursor("hw_cursorHighlight.png")
        cls.NORMAL   = cls.HCursor("hw_cursorNormal.png")
        cls.NWDeep   = cls.HCursor("hw_cursorNWDeep.png", (0, 0))
        cls.NEDeep   = cls.HCursor("hw_cursorNEDeep.png", (30, 0))
        cls.EShallow   = cls.HCursor("hw_cursorEShallow.png", (22, 16))
        cls.WEST   = cls.HCursor("hw_cursorWest.png", (0, 14))
