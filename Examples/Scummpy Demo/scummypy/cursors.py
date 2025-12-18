import pygame
import scummypy.resources as Resources

class Cursors:
    @staticmethod
    def HCursor(filename: str, hotspot=(0, 0)) -> pygame.cursors.Cursor | None:
        name=filename
        surf = Resources.load_image(f"cursors/{filename}")

        # Validate hotspot is inside surface bounds and image size is reasonable
        try:
            w, h = surf.get_size()
            hx, hy = hotspot

            if not (isinstance(hx, int) and isinstance(hy, int)):
                raise ValueError("[cursor.py] hotspot arg must be integers")

            if not (0 <= hx < w and 0 <= hy < h):
                raise ValueError(f"[cursor.py] hotspot {hotspot} outside image bounds {w}x{h}")

            # Windows/SDL can fail for very large cursors; limit to a sensible size
            MAX_CURSOR_DIM = 64
            if w > MAX_CURSOR_DIM or h > MAX_CURSOR_DIM:
                raise ValueError(f"[cursor.py] cursor image too large: {w}x{h}")

            cursor = pygame.cursors.Cursor(hotspot, surf)
            return cursor

        except Exception as e:
            # Fall back to a system cursor to avoid CreateIconIndirect errors on Windows
            try:
                print(f"[cursor.py] HCursor: falling back to system cursor for {filename}: {e}")
                return pygame.cursors.Cursor(pygame.SYSTEM_CURSOR_ARROW)
            except Exception:
                # Last resort: return None (caller should handle None)
                return None

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
