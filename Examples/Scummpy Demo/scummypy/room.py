import pygame

from .cursors import Cursors
from .actor import ActorEvents

class Room:
    ROOM_NAME: str = __name__
    screen = lambda: None

    def __init__(
                    self, 
                    engine, 
                    room_name: str, 
                    background_surface: pygame.Surface,
                    background_rect: pygame.Rect | None = None
                 ):
        self.engine = engine
        self.ROOM_NAME = room_name
        self.visible = True
        self.background = background_surface
        # use passed-in rect or default to (0, 0)
        self.background_rect = background_rect or self.background.get_rect(topleft=(0, 0))

        self.actors = pygame.sprite.LayeredUpdates()
        self.sprites = pygame.sprite.LayeredUpdates()
        self.hotspots = []  # list of (pygame.Rect, callback)

        # these can be overridden/assigned by room scripts
        # e.g. room.enter = lambda: enter(room, engine)
        self.enter = lambda: self.fake_enter()
        self.entered = False
        self.destroy = lambda: None
        self.initiated = False

    def fake_enter(self, room=None, engine=None):
        return None

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)
        elif event.type == ActorEvents.ANIMATION_END:
            if event.animation_type is "actor":
                pass


    def get_hover_cursor(self, pos):
        for rect, callback, hoverCursor, disabled in self.hotspots:
            if rect.collidepoint(pos):
                if disabled is True:
                    return Cursors.NORMAL
                else:
                    return hoverCursor or pygame.SYSTEM_CURSOR_CROSSHAIR
        return None

    def _handle_click(self, pos):
        for rect, callback, _, disabled in self.hotspots:
            if rect.collidepoint(pos):
                if disabled is not True:
                    callback(self, self.engine)
                break

    def update(self, dt: float):
            self.actors.update(dt)
            self.sprites.update(dt)

    def draw(self, screen):
        if self.engine.game_state.get_flag("g_roomVisible") is True:
            screen.blit(self.background, self.background_rect)

        self.actors.draw(screen)
        self.sprites.draw(screen)

        # DEBUG: draw hotspot rectangles
        if self.engine.DEBUG:
            for rect, _, _, disabled in self.hotspots:
                if type(rect) is pygame.rect.Rect:
                    pygame.draw.rect(screen, "red", rect, width=2)

    def room_has(self, item_to_check) -> bool:
        if hasattr(self, item_to_check):
            return True
        return False

    def create_hotspot(self, left: int, top: int, width: int, height: int, onClick=None):
        """
            create_hotspot() will only make the rectangle.
            In you Room logic call setup_clickpoint() to draw to the stage
            & setup the click action.
            left: Rect Left
            top: Rect top
            width: Rect width
            height: Rect height
        """

        rect: pygame.Rect = pygame.Rect(left, top, width, height)
        #setattr(rect, "disabled", False)

        #hotspot = self.hotspots.append((rect, onClick))
        return rect

    def setup_clickpoint(self, clickable, onClick, hoverCursor=None):
        if hoverCursor is None:
            hoverCursor = Cursors.HIGHLIGHT

        clickpoint = [clickable, onClick, hoverCursor, False]
        self.hotspots.append(clickpoint)

        return clickpoint
        #room.hotspots.append((mailbox_rect, on_click_mailbox))

    def disable_clickpoint(self, clickable=None):
        if clickable is None:
            print("[room.py] No clickable to be disabled..")
            return

        rect_to_check = clickable[0]

        for hotspot in self.hotspots:   # hotspot is a list: [rect, callback, cursor, disabled]
            rect, callback, hoverCursor, disabled = hotspot
            
            if rect_to_check is rect:
                hotspot[3] = True
                break
        # Check if is over the (any) hotspot
        self.engine._handle_mouse_motion()
        
    def enable_clickpoint(self, clickable=None):
        """Enable a single hotspot given the clickable record (e.g. from create_clickpoint)."""
        if clickable is None:
            print("[room.py] No clickable to be enabled..")
            return

        rect_to_check = clickable[0]

        for hotspot in self.hotspots:
            rect, callback, hoverCursor, disabled = hotspot
            if rect_to_check is rect:       # same Rect object
                hotspot[3] = False          # disabled -> False (enabled)
                break

        # Re-evaluate cursor hover after enabling
        self.engine._handle_mouse_motion()


    def enable_all_clickpoints(self):
        """Enable ALL hotspots in this room."""
        if not self.hotspots:
            return

        for hotspot in self.hotspots:
            # hotspot = [rect, callback, hoverCursor, disabled]
            hotspot[3] = False  # mark as enabled

        # Re-evaluate cursor hover after enabling all
        self.engine._handle_mouse_motion()


    def add_sprite(self, sprite, spriteName):
        sprite.__name__= spriteName
        self.sprites.add(sprite)
        setattr(self, spriteName, sprite)

    def sprite_exists(self, spriteName) -> bool:
        return self.room_has(spriteName)

    def remove_sprite(self, sprite, spriteName=None):
        if sprite:
            delattr(self, sprite.__name__)  
            self.sprites.remove(sprite)

    def get_next_actor_id(self):
        if not self.engine.actor_table:
            return 1  # or 1, depending on your game
        return max(self.engine.actor_table.keys()) + 1

    def add_actor(self, actor, actor_name):
        actor.__name__= actor_name
        # store in ID table
        self.engine.actor_table[actor.actor_id] = actor

        self.actors.add(actor)
        
        setattr(self, actor_name, actor)
    
    def remove_actor_by_id(self, actor_id):
        actor = self.engine.actor_table.get(actor_id)
        if not actor:
            return

        self.remove_actor(actor)

    def remove_actor(self, actor):
        if actor:
            delattr(self, actor.__name__) 

            del self.engine.actor_table[actor.actor_id] 

            self.actors.remove(actor)
            actor.destroy()

    def remove_all_room_actors(self):
        actors = list(self.actors)  # snapshot
        for actor in actors:
            self.remove_actor(actor)

    def remove_all_actors(self):
        actor_ids = list(self.engine.actor_table.keys())  # snapshot

        for actor_id in actor_ids:
            actor = self.engine.actor_table.get(actor_id)
            if actor is not None:
                self.remove_actor(actor)


