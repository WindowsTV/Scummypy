import pygame

class ActorEvents:
    ANIMATION_END = pygame.USEREVENT + 100

class Actor(pygame.sprite.Sprite):
    def __init__(self, actor_id=None, costume=None, pos=(0, 0), name=None, room=None):
        super().__init__()

        if actor_id is None:
            raise ValueError("[actor.py] Actor requires an Actor ID")
        
        if costume is None:
            raise ValueError("[actor.py] Actor requires a Costume")
        
        self.actor_id = actor_id
        self.costume = costume
        self.costume.actor = self
        if name is not None:
            self.__name__ = name
        self.pos = pygame.math.Vector2(pos)
        self.room = room

        self.image = costume.image
        self.rect = self.image.get_rect()
        self._update_rect_from_regpoint()

        # event registry: { event_type : [ (callback, (arg1,arg2,...)), ... ] }
        self._event_handlers = {}

    def add_event(self, event_type, callback, *user_args):
        """Register a callback for a specific ActorEvents type."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append((callback, user_args))

    def _fire_event(self, event_type, **event_data):
        """Internal: trigger all registered callbacks for this actor."""
        handlers = self._event_handlers.get(event_type, [])
        if not handlers:
            return

        for callback, user_args in handlers:
            # CALLBACK CALL CONTRACT:
            # callback(actor, event_data, *user_args)
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
