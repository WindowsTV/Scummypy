import json
import pygame

from .actor import ActorEvents

class Costume:
    def __init__(self, image_path: str, json_path: str):
        self.actor = lambda: None
        self.sprite_sheet = pygame.image.load(image_path).convert_alpha()

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Sheet framerate (frames per second), like CreateJS
        self.framerate = data.get("framerate", 24)

        self.frames: list[pygame.Surface] = []
        self.reg_points: list[tuple[int, int]] = []

        # frames: [x, y, w, h, imageIndex, regX, regY]
        for fx, fy, fw, fh, imageIndex, regX, regY in data["frames"]:
            frame_surf = pygame.Surface((fw, fh), pygame.SRCALPHA)
            frame_surf.blit(self.sprite_sheet, (0, 0), (fx, fy, fw, fh))
            self.frames.append(frame_surf)
            self.reg_points.append((regX, regY))

        self.animations = data["animations"]
        self.current_anim: str | None = None
        self.current_frame_idx: int = 0
        self._frame_time: float = 0.0  # time accumulated in this frame

    def play(self, name: str):
        """Start playing an animation by name."""
        if self.current_anim != name:
            self.current_anim = name
            self.current_frame_idx = 0
            self._frame_time = 0.0

    def update(self, dt: float):
        """Advance animation based on elapsed time (dt in seconds)."""
        if self.current_anim is None:
            return

        anim = self.animations[self.current_anim]

        # Relative playback speed: 1 = normal, 2 = double, 0.5 = half
        speed = anim.get("speed", 1.0)

        frames = anim["frames"]
        if not frames or speed <= 0 or self.framerate <= 0:
            return

        # How long each frame should last (seconds)
        frame_duration = 1.0 / (self.framerate * speed)

        self._frame_time += dt

        while self._frame_time >= frame_duration:
            self._frame_time -= frame_duration
            self._advance_frame()

    def _advance_frame(self):
        anim = self.animations[self.current_anim]
        frames = anim["frames"]
        num_frames = len(frames)

        next_anim = anim.get("next", None)

        # Not at last frame yet → just advance
        if self.current_frame_idx + 1 < num_frames:
            self.current_frame_idx += 1
            return

        ended_anim = self.current_anim
        end_frame = num_frames - 1

        # Decide next animation/frame
        if next_anim is None:
            self.current_frame_idx = 0
        elif next_anim is False:
            self.current_frame_idx = end_frame
        elif isinstance(next_anim, str):
            self.play(next_anim)
        else:
            self.current_frame_idx = 0

        # Build event payload
        data = {
            "animation_type": "actor",
            "animation": ended_anim,
            "end_frame": end_frame,
            "actor": self.actor,
        }

        # Fire per-actor listeners
        if self.actor:
            self.actor._fire_event(ActorEvents.ANIMATION_END, **data)

        # Also post a global pygame event
        pygame.event.post(
            pygame.event.Event(ActorEvents.ANIMATION_END, **data)
        )

    @property
    def image(self) -> pygame.Surface:
        if self.current_anim is None:
            return self.frames[0]
        anim = self.animations[self.current_anim]
        frame_index = anim["frames"][self.current_frame_idx]
        return self.frames[frame_index]

    @property
    def reg_point(self) -> tuple[int, int]:
        """Return the (regX, regY) for the current frame."""
        if self.current_anim is None:
            return self.reg_points[0]
        anim = self.animations[self.current_anim]
        frame_index = anim["frames"][self.current_frame_idx]
        return self.reg_points[frame_index]
