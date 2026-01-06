import pygame
import threading

from typing import Callable

class ActorEvents:
    ANIMATION_END = pygame.USEREVENT + 100
    ACTOR_UPDATE = pygame.USEREVENT + 101

class Actor(pygame.sprite.Sprite):
    def __init__(self, actor_id=None, costume=None, pos=(0, 0), name=None, room=None, actor_can_flap_while_change=False):
        super().__init__()

        if actor_id is None:
            raise ValueError("[actor.py] Actor requires an Actor ID")
        
        if costume is None:
            raise ValueError("[actor.py] Actor requires a Costume")
        
        self.room = room
        self.engine = room.engine if room is not None else None
        self.actor_id = actor_id
        self.costume = costume
        self.costume.actor = self
        if name is not None:
            self.__name__ = name
        self.pos = pygame.math.Vector2(pos)

        self.image = costume.image
        self.rect = self.image.get_rect()
        self.mask = pygame.mask.from_surface(self.image)
        self._update_rect_from_regpoint()

        self.blink_required_before_flap = True
        self.currently_looking_at = "normal"
        self.flapping_mouth = False
        self.actor_can_flap_while_change = actor_can_flap_while_change

        # event registry: { event_type : [ (callback, (arg1,arg2,...)), ... ] }
        self._event_handlers = {}
        
        if self.actor_can_flap_while_change == False:
            data = dict(update_type="new", actor_id=self.actor_id)
            pygame.event.post(pygame.event.Event(ActorEvents.ACTOR_UPDATE, data))

    def change_costume(self, new_costume):
        print(f"[actor.py] change_costume('{new_costume}')")

        self.clear_all_events()

        if not self.actor_can_flap_while_change:
            data = dict(update_type="change", actor_id=self.actor_id)
            pygame.event.post(pygame.event.Event(ActorEvents.ACTOR_UPDATE, data))

        self.costume = new_costume
        self.costume.actor = self

        self.image = self.costume.image
        self.rect = self.image.get_rect()
        self.mask = pygame.mask.from_surface(self.image)

        self._update_rect_from_regpoint()


    def get_valid_look_at(self, eye_state: str="normal"):
        if ('eyes-'+ eye_state) not in self.costume.layer_sheets:
            eye_state = "normal"

        # print(f"[actor.py] get_valid_look_at() -> '{eye_state}'")
        return eye_state

    def look_at(self, eye_state: str="normal"):
        print(f"[actor.py] look_at(eyes='{eye_state}')")
        if ('eyes-'+ eye_state) not in self.costume.layer_sheets:
            print(f"[actor.py] look_at(): no eyes layer for '{eye_state}'")
            return
        self.currently_looking_at = eye_state
        
        for layer in self.costume.layer_sheets:
            if layer.startswith("eyes-") and layer != ("eyes-" + eye_state):
                self.costume.set_layer_hidden(layer, True)

        if ("eyes-" + eye_state) in self.costume.layer_sheets:
            self.costume.set_layer_hidden("eyes-" + eye_state, False)
            self.costume.stop_layer("eyes-" + eye_state)


    def blink(self, look_at_state: str="normal", after_blink: Callable|None=None):
        # print(f"[actor.py] blink()")
        self.currently_looking_at = self.get_valid_look_at(look_at_state)
        
        if ('lids') not in self.costume.layer_sheets:
            self.look_at(look_at_state)
            return False
        
        self.costume.set_layer_hidden("lids", False)
        self.costume.stop_layer("lids")
        self.costume.play_layer("lids", "lids")

        # register handler (preferably once; see below)
        self.add_event(ActorEvents.ANIMATION_END, self.handleBlinkAnimationEnd, look_at_state, after_blink)

        self.look_at(look_at_state)
        return True
        # threading.Timer(0.1, self.look_at, args=(look_at_state,)).start()

    def handleBlinkAnimationEnd(
            self, 
            actor, 
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

    def flap_mouth(self, audio_handle, audio_end_callback: Callable=lambda:None):
        # print(f"[actor.py] flap_mouth('{audio_handle}')")
        self.flapping_mouth = True

        on_end_callables = lambda: (
            self.stop_mouth_flap(self, {}), 
            audio_end_callback()
        )
        #audio_handle.on_end_cb = lambda: self.stop_mouth_flap(self, {})            
        audio_handle.on_end_cb = on_end_callables            
        self.costume.play_layer("head", 0)
        self.costume.play_layer("eyes-"+self.currently_looking_at, 0)

    def stop_mouth_flap(self, actor, event_data, do_blink: bool=True):
        print(f"[actor.py] stop_mouth_flap()")
        self.flapping_mouth = False
        
        self.costume.stop_layer("head", 0)
        self.costume.stop_layer("eyes-"+self.currently_looking_at, 0)

        #onBlinkCompletedFunc = lambda: self.handleBlinkAnimationEnd(self, {"layer_name": "lids"})
        if do_blink == True:
            if self.currently_looking_at != "normal":
                self.blink("normal")
        else:
            self.look_at("normal")
        
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

    def remove_all_events(self, event_type):
        """Remove all handlers for the given event type."""
        if event_type in self._event_handlers:
            del self._event_handlers[event_type]

    def clear_all_events(self):
        """Remove all event handlers for all event types."""
        self._event_handlers.clear()

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

    def collidepoint(self, pos):       
        x = pos[0] - self.rect.x
        y = pos[1] - self.rect.y

        # Avoid index error
        if 0 <= x < self.rect.width and 0 <= y < self.rect.height:
            return self.mask.get_at((x, y))
        return False

    def colliderect(self, *args):
        return self.rect.colliderect(*args)

    def collide(self, *args):
        return self.rect.collide(*args)

    def contains(self, *args):
        return self.rect.contains(*args)

    def clip(self, *args):
        return self.rect.clip(*args)

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
