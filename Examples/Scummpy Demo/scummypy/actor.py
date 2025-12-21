import pygame
import threading

from typing import Callable

class ActorEvents:
    ANIMATION_END = pygame.USEREVENT + 100

class Actor(pygame.sprite.Sprite):
    def __init__(self, actor_id=None, costume=None, pos=(0, 0), name=None, room=None):
        super().__init__()

        if actor_id is None:
            raise ValueError("[actor.py] Actor requires an Actor ID")
        
        if costume is None:
            raise ValueError("[actor.py] Actor requires a Costume")
        
        self.room = room
        self.actor_id = actor_id
        self.costume = costume
        self.costume.actor = self
        if name is not None:
            self.__name__ = name
        self.pos = pygame.math.Vector2(pos)

        self.image = costume.image
        self.rect = self.image.get_rect()
        self._update_rect_from_regpoint()

        # event registry: { event_type : [ (callback, (arg1,arg2,...)), ... ] }
        self._event_handlers = {}

    def look_at(self, eye_state: str="normal"):
        print(f"[actor.py] look_at(eyes='{eye_state}')")
        if ('eyes-'+ eye_state) not in self.costume.layer_sheets:
            print(f"[actor.py] look_at(): no eyes layer for '{eye_state}'")
            return
        
        for layer in self.costume.layer_sheets:
            if layer.startswith("eyes-") and layer != ("eyes-" + eye_state):
                self.costume.set_layer_hidden(layer, True)

        if ("eyes-" + eye_state) in self.costume.layer_sheets:
            self.costume.set_layer_hidden("eyes-" + eye_state, False)
            self.costume.stop_layer("eyes-" + eye_state)


    def blink(self, look_at_state: str="normal", after_blink: Callable|None=None):
        # print(f"[actor.py] blink()")
        if ('lids') not in self.costume.layer_sheets:
            print(f"[actor.py] blink(): No lids layer for blink")
            return
        
        self.add_event(
            ActorEvents.ANIMATION_END,
            self.handleBlinkAnimationEnd,
            look_at_state,
            after_blink,
        )
        self.costume.play_layer("lids", "lids")
        self.look_at(look_at_state)
        # threading.Timer(0.1, self.look_at, args=(look_at_state,)).start()

    def handleBlinkAnimationEnd(self, actor, 
                                event_data, 
                                look_at_state: str = "normal",
                                after_blink: Callable|None = None
                                ):
        print("[actor.py] handleBlinkAnimationEnd()")

        if event_data.get("layer_name") == "lids":
            self.costume.set_layer_hidden("lids", True)
            self.remove_event(ActorEvents.ANIMATION_END, self.handleBlinkAnimationEnd)

            if after_blink is not None:
                after_blink()

    def add_event(self, event_type, callback, *user_args):
        """Register a callback for a specific ActorEvents type."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append((callback, user_args))

    def remove_event(self, event_type, callback):
        """Remove all handlers for an event type using the given callback."""
        handlers = self._event_handlers.get(event_type)
        if not handlers:
            return

        cb_self = getattr(callback, "__self__", None)
        cb_func = getattr(callback, "__func__", callback)

        new_handlers = []
        for cb, args in handlers:
            h_self = getattr(cb, "__self__", None)
            h_func = getattr(cb, "__func__", cb)

            # keep only those that don't match
            if not (h_self is cb_self and h_func is cb_func):
                new_handlers.append((cb, args))

        if new_handlers:
            self._event_handlers[event_type] = new_handlers
        else:
            del self._event_handlers[event_type]


    def _fire_event(self, event_type, **event_data):
        """Internal: trigger all registered callbacks for this actor."""
        handlers = self._event_handlers.get(event_type, [])
        if not handlers:
            return

        # Iterate over a snapshot so handlers can remove themselves safely
        for callback, user_args in list(handlers):
            callback(self, event_data, *user_args)


    # --- Positioning code ---
    def _update_rect_from_regpoint(self):
        rx, ry = self.costume.reg_point
        self.rect.topleft = (self.pos.x - rx, self.pos.y - ry)

    def update(self, dt: float):
        self.costume.update(dt)
        self.image = self.costume.image
        self._update_rect_from_regpoint()

    def destroy(self):
        """
        Remove this actor from its room and clean up resources.
        """

        # Remove from sprite groups
        self.kill()   # removes from ALL pygame groups the actor belongs to

        # Clear event listeners
        self._event_handlers.clear()

        # Tell the costume it no longer has an actor
        if hasattr(self.costume, "actor") and self.costume.actor is self:
            self.costume.actor = None

        # Clear the costume reference entirely
        #self.costume = None

        # print(f"[Actor] Destroyed: {self.actor_id} - {self.__name__}")

    @property
    def x(self): return self.pos.x
    @x.setter
    def x(self, v):
        self.pos.x = v
        self._update_rect_from_regpoint()

    @property
    def y(self): return self.pos.y
    @y.setter
    def y(self, v):
        self.pos.y = v
        self._update_rect_from_regpoint()
