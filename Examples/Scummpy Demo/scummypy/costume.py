import json
from dataclasses import dataclass
from typing import Optional, Any

import pygame

from .actor import ActorEvents


# -----------------------------
# LayerSheet = sprite data only
# -----------------------------
class LayerSheet:
    def __init__(self, sheet: pygame.Surface, layer_json: dict):
        self.sprite_sheet = sheet.convert_alpha()
        self.frames: list[pygame.Surface] = []
        self.reg_points: list[tuple[int, int]] = []
        self.frame_meta: list[dict | None] = []
        self.animations: dict[str, dict] = layer_json.get("animations", {})

        for frame in layer_json.get("frames", []):
            fx, fy, fw, fh, imageIndex, regX, regY = frame[:7]
            meta = frame[7] if len(frame) > 7 else None

            surf = pygame.Surface((fw, fh), pygame.SRCALPHA)
            surf.blit(self.sprite_sheet, (0, 0), (fx, fy, fw, fh))
            self.frames.append(surf)
            self.reg_points.append((regX, regY))
            self.frame_meta.append(meta)

    def get_frame_raw(self, raw_idx: int) -> tuple[Optional[pygame.Surface], tuple[int, int]]:
        if not self.frames:
            return None, (0, 0)
        i = max(0, min(int(raw_idx), len(self.frames) - 1))
        return self.frames[i], self.reg_points[i]

    def get_frame_anim(self, anim_name: str, anim_idx: int) -> tuple[Optional[pygame.Surface], tuple[int, int], int]:
        """
        Returns (image, reg_point, sheet_frame_index_used)
        """
        if not self.frames:
            return None, (0, 0), 0

        anim = self.animations.get(anim_name)
        if not anim:
            return self.frames[0], self.reg_points[0], 0

        frames_list = anim.get("frames", [])
        if not frames_list:
            return self.frames[0], self.reg_points[0], 0

        i = max(0, min(int(anim_idx), len(frames_list) - 1))
        sheet_idx = int(frames_list[i])
        sheet_idx = max(0, min(sheet_idx, len(self.frames) - 1))
        return self.frames[sheet_idx], self.reg_points[sheet_idx], sheet_idx


# -----------------------------
# Shared timeline state model
# -----------------------------
@dataclass
class TimelineState:
    mode: str = "raw"                 # "raw" or "anim"
    raw_idx: int = 0                  # index into sheet frames
    anim_name: Optional[str] = None   # animation name
    anim_idx: int = 0                 # index into anim["frames"]
    t: float = 0.0                    # time accumulator
    loops: bool = False
    paused: bool = False


@dataclass
class LayerState(TimelineState):
    is_hidden: bool = False
    event_fired: bool = False


# -----------------------------
# Costume
# -----------------------------
class Costume:
    def __init__(self, image_path_or_tuple: str | tuple, json_path: str = ""):
        self.actor = None
        self._paused = False

        # Mode flags
        self._layered = False

        # Single-sheet data
        self.sprite_sheet: Optional[pygame.Surface] = None
        self.frames: list[pygame.Surface] = []
        self.reg_points: list[tuple[int, int]] = []
        self.animations: dict[str, dict] = {}
        self.timeline = TimelineState()
        self.framerate: float = 24.0

        # Layered data
        self.layer_defs: dict[str, dict] = {}
        self.layer_sheets: dict[str, LayerSheet] = {}
        self.layer_order: list[str] = []
        self.base_layer_name: Optional[str] = None
        self._layer_state: dict[str, LayerState] = {}

        # ---------------- load ----------------
        if not json_path and isinstance(image_path_or_tuple, tuple):
            sheet_surface, data, layer_images_src = image_path_or_tuple

            base_url_detected = data.get("base_url", None)
            if base_url_detected is not None:
                self.setup_layers(data, layer_images_src)
                return

            self.sprite_sheet = sheet_surface
            self._load_single(data)
            return

        # explicit paths
        image_path = image_path_or_tuple  # type: ignore[assignment]
        if not isinstance(image_path, str):
            raise TypeError("image_path_or_tuple must be a str path when json_path is provided")

        self.sprite_sheet = pygame.image.load(image_path).convert_alpha()
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._load_single(data)

    # ---------- Single-sheet loading ----------
    def _load_single(self, data: dict) -> None:
        self._layered = False
        self.framerate = float(data.get("framerate", 24))

        if self.sprite_sheet is None:
            raise RuntimeError("Costume sprite_sheet is not loaded (None)")

        self.frames.clear()
        self.reg_points.clear()

        for fx, fy, fw, fh, imageIndex, regX, regY in data.get("frames", []):
            frame_surf = pygame.Surface((fw, fh), pygame.SRCALPHA)
            frame_surf.blit(self.sprite_sheet, (0, 0), (fx, fy, fw, fh))
            self.frames.append(frame_surf)
            self.reg_points.append((regX, regY))

        self.animations = data.get("animations", {})
        self.timeline = TimelineState()

    # ---------- Layered loading ----------
    def setup_layers(self, data: dict, layer_images_src: dict[str, pygame.Surface]) -> None:
        self._layered = True
        self.framerate = float(data.get("framerate", 24))
        self.layer_defs = data.get("layers", {})

        self.layer_sheets.clear()
        self.layer_order.clear()
        self._layer_state.clear()

        for layer_name, layer in self.layer_defs.items():
            if not isinstance(layer, dict):
                continue
            if layer.get("src"):
                continue

            images = layer.get("images", [])
            if not images:
                continue

            img_name = images[0]
            sheet = layer_images_src.get(img_name)
            if sheet is None:
                continue

            self.layer_sheets[layer_name] = LayerSheet(sheet, layer)
            self.layer_order.append(layer_name)

        self.base_layer_name = "body" if "body" in self.layer_sheets else (self.layer_order[0] if self.layer_order else None)

        for layer_name in self.layer_order:
            is_hidden = bool(self.layer_defs[layer_name].get("isHidden", False))
            self._layer_state[layer_name] = LayerState(is_hidden=is_hidden)

    # -----------------------------
    # Public controls (single sheet)
    # -----------------------------
    def play(self, play_at: str | int | None = None) -> None:
        """
        Single-sheet control:
          - None/int => raw timeline
          - str      => animation timeline
        """
        if self._layered:
            # layered costumes should use play_layer()/play_all_layers()
            self._paused = False
            return

        self._paused = False
        self.timeline.t = 0.0
        self.timeline.paused = False

        if play_at is None or isinstance(play_at, int):
            self.timeline.mode = "raw"
            self.timeline.anim_name = None
            self.timeline.anim_idx = 0
            self.timeline.raw_idx = self._clamp(play_at or 0, 0, len(self.frames) - 1)
            return

        if play_at not in self.animations:
            raise KeyError(f"Unknown animation '{play_at}'. Available: {list(self.animations.keys())}")

        self.timeline.mode = "anim"
        self.timeline.anim_name = play_at
        self.timeline.anim_idx = 0
        self.timeline.raw_idx = 0

    def stop(self, frame: Optional[int] = None) -> None:
        if self._layered:
            self._paused = True
            return

        self._paused = True
        self.timeline.paused = True
        self.timeline.t = 0.0

        if frame is not None:
            self.timeline.mode = "raw"
            self.timeline.anim_name = None
            self.timeline.anim_idx = 0
            self.timeline.raw_idx = self._clamp(frame, 0, len(self.frames) - 1)

    # -----------------------------
    # Public controls (layered)
    # -----------------------------
    def play_layer(self, layer_name: str, play_at: str | int | None = None) -> None:
        sheet = self.layer_sheets.get(layer_name, None)
        if sheet is None:
            return
        
        st = self._layer_state[layer_name]

        st.paused = False
        st.t = 0.0
        st.event_fired = False 
        
        # raw
        if play_at is None or isinstance(play_at, int):
            st.mode = "raw"
            st.anim_name = None
            st.anim_idx = 0
            st.raw_idx = self._clamp(play_at or 0, 0, len(sheet.frames) - 1)
            return

        # anim
        if play_at not in sheet.animations:
            raise KeyError(f"Layer '{layer_name}' unknown anim '{play_at}'. Available: {list(sheet.animations.keys())}")

        st.mode = "anim"
        st.anim_name = play_at
        st.anim_idx = 0

        # keep raw_idx synced to current anim frame for meta/offsets/debug
        first = sheet.animations[play_at].get("frames", [0])[0]
        st.raw_idx = self._clamp(int(first), 0, len(sheet.frames) - 1)

    def stop_layer(self, layer_name: str, frame: Optional[int] = None) -> None:
        sheet = self.layer_sheets.get(layer_name, None)
        if sheet is None:
            return
        
        st = self._layer_state[layer_name]

        st.paused = True
        st.t = 0.0

        if frame is not None:
            st.mode = "raw"
            st.anim_name = None
            st.anim_idx = 0
            st.raw_idx = self._clamp(frame, 0, len(sheet.frames) - 1)
    
    def stop_layers(self, *layer_names: str, frame: Optional[int] = None) -> None:
        for layer_name in layer_names:
            self.stop_layer(layer_name, frame)

    def play_all_layers(self, play_at: str | int | None = None) -> None:
        for name in self.layer_order:
            self.play_layer(name, play_at)

    def set_layer_hidden(self, layer_name: str, hidden: bool) -> None:
        if layer_name in self._layer_state:
            self._layer_state[layer_name].is_hidden = hidden
            
    # -----------------------------
    # Update
    # -----------------------------
    def update(self, dt: float) -> None:
        if self._paused:
            return

        if self._layered:
            self._update_layers(dt)
        else:
            self._update_single(dt)

    def _update_single(self, dt: float) -> None:
        if self.timeline.paused:
            return
        if not self.frames or self.framerate <= 0:
            return

        frames_list, speed, next_anim = self._resolve_single_timeline()
        if not frames_list or speed <= 0:
            return

        frame_duration = 1.0 / (self.framerate * speed)
        self.timeline.t += dt

        while self.timeline.t >= frame_duration:
            self.timeline.t -= frame_duration
            self._step_timeline_single(frames_list, next_anim)

    def _resolve_single_timeline(self) -> tuple[list[int], float, Any]:
        if self.timeline.mode == "anim" and self.timeline.anim_name:
            anim = self.animations.get(self.timeline.anim_name, {})
            return anim.get("frames", []), float(anim.get("speed", 1.0)), anim.get("next", None)
        return list(range(len(self.frames))), 1.0, None

    def _step_timeline_single(self, frames_list: list[int], next_anim: Any) -> None:
        # RAW MODE
        if self.timeline.mode == "raw":
            if self.timeline.raw_idx + 1 < len(frames_list):
                self.timeline.raw_idx += 1
            else:
                if getattr(self.timeline, "loops", True):
                    self.timeline.raw_idx = 0
                else:
                    # freeze on last frame (common behavior)
                    self.timeline.raw_idx = len(frames_list) - 1
                    self.timeline.paused = True
                    # optional: fire end for raw too
                    self._fire_anim_end(animation_type="actor", animation=None, end_frame=self.timeline.raw_idx)
            return  # <-- IMPORTANT

        # ANIM MODE
        if self.timeline.anim_idx + 1 < len(frames_list):
            self.timeline.anim_idx += 1
            return

        # ended anim
        ended = self.timeline.anim_name
        end_frame = len(frames_list) - 1
        self._fire_anim_end(animation_type="actor", animation=ended, end_frame=end_frame)

        if next_anim is None:
            if getattr(self.timeline, "loops", True):
                self.timeline.anim_idx = 0
            else:
                self.timeline.anim_idx = end_frame
                self.timeline.paused = True
        elif next_anim is False:
            self.timeline.anim_idx = end_frame
            self.timeline.paused = True
        elif isinstance(next_anim, str):
            self.play(next_anim)
        else:
            self.timeline.anim_idx = 0

    def _update_layers(self, dt: float) -> None:
        if self.framerate <= 0:
            return

        for layer_name in self.layer_order:
            sheet = self.layer_sheets[layer_name]
            st = self._layer_state[layer_name]

            if st.paused:
                continue
            if not sheet.frames:
                continue

            frames_list, speed, next_anim = self._resolve_layer_timeline(sheet, st)
            if not frames_list or speed <= 0:
                continue

            frame_duration = 1.0 / (self.framerate * speed)
            st.t += dt

            while st.t >= frame_duration:
                st.t -= frame_duration
                self._step_timeline_layer(layer_name, sheet, st, frames_list, next_anim)

    def _resolve_layer_timeline(self, sheet: LayerSheet, st: LayerState) -> tuple[list[int], float, Any]:
        if st.mode == "anim" and st.anim_name and st.anim_name in sheet.animations:
            anim = sheet.animations[st.anim_name]
            return anim.get("frames", []), float(anim.get("speed", 1.0)), anim.get("next", None)

        # fallback to raw
        st.mode = "raw"
        st.anim_name = None
        st.anim_idx = 0
        return list(range(len(sheet.frames))), 1.0, None

    def _step_timeline_layer(self, layer_name: str, sheet: LayerSheet, st: LayerState,
                            frames_list: list[int], next_anim: Any) -> None:
        if st.mode == "raw":
            st.raw_idx = (st.raw_idx + 1) % len(frames_list)
            return

        end_frame = len(frames_list) - 1

        # Normal advance
        if st.anim_idx < end_frame:
            st.anim_idx += 1
            st.raw_idx = self._clamp(int(frames_list[st.anim_idx]), 0, len(sheet.frames) - 1)
            return

        # We are ON the last frame and another tick happened -> now it's "ended"
        if st.event_fired is False:
            self._fire_anim_end(
                animation_type="layer",
                animation=st.anim_name,
                end_frame=end_frame,
                layer_name=layer_name,
                layer=sheet,
            )
        st.event_fired = True

        # Decide what happens next
        if next_anim is None:
            st.anim_idx = 0
        elif next_anim is False:
            st.anim_idx = end_frame
            st.paused = True
        elif isinstance(next_anim, str) and next_anim in sheet.animations:
            st.anim_name = next_anim
            st.anim_idx = 0
        else:
            st.anim_idx = 0

        st.raw_idx = self._clamp(int(frames_list[st.anim_idx]), 0, len(sheet.frames) - 1)

    # -----------------------------
    # Rendering helpers
    # -----------------------------
    @property
    def image(self) -> pygame.Surface:
        if self._layered:
            img, _ = self._compose_layers()
            return img
        return self._single_image()

    @property
    def reg_point(self) -> tuple[int, int]:
        if self._layered:
            _, rp = self._compose_layers()
            return rp
        return self._single_reg_point()

    def _single_image(self) -> pygame.Surface:
        if not self.frames:
            return pygame.Surface((1, 1), pygame.SRCALPHA)

        if self.timeline.mode == "raw":
            return self.frames[self._clamp(self.timeline.raw_idx, 0, len(self.frames) - 1)]

        # anim mode
        if not self.timeline.anim_name:
            return self.frames[0]

        anim = self.animations.get(self.timeline.anim_name, {})
        frames_list = anim.get("frames", [])
        if not frames_list:
            return self.frames[0]

        i = self._clamp(self.timeline.anim_idx, 0, len(frames_list) - 1)
        sheet_idx = self._clamp(int(frames_list[i]), 0, len(self.frames) - 1)
        return self.frames[sheet_idx]

    def _single_reg_point(self) -> tuple[int, int]:
        if not self.reg_points:
            return (0, 0)

        if self.timeline.mode == "raw":
            i = self._clamp(self.timeline.raw_idx, 0, len(self.reg_points) - 1)
            return self.reg_points[i]

        if not self.timeline.anim_name:
            return self.reg_points[0]

        anim = self.animations.get(self.timeline.anim_name, {})
        frames_list = anim.get("frames", [])
        if not frames_list:
            return self.reg_points[0]

        i = self._clamp(self.timeline.anim_idx, 0, len(frames_list) - 1)
        sheet_idx = self._clamp(int(frames_list[i]), 0, len(self.reg_points) - 1)
        return self.reg_points[sheet_idx]

    def _compose_layers(self) -> tuple[pygame.Surface, tuple[int, int]]:
        if not self.layer_sheets or not self.layer_order:
            return pygame.Surface((1, 1), pygame.SRCALPHA), (0, 0)

        parts: list[tuple[str, pygame.Surface, int, int]] = []

        for layer_name in self.layer_order:
            st = self._layer_state.get(layer_name)
            sheet = self.layer_sheets.get(layer_name)
            if not st or not sheet or st.is_hidden:
                continue

            if st.mode == "anim" and st.anim_name:
                img, (regX, regY), _ = sheet.get_frame_anim(st.anim_name, st.anim_idx)
            else:
                img, (regX, regY) = sheet.get_frame_raw(st.raw_idx)

            if img is None:
                continue
            parts.append((layer_name, img, regX, regY))

        if not parts:
            return pygame.Surface((1, 1), pygame.SRCALPHA), (0, 0)

        left = min(-regX for (_, _, regX, _) in parts)
        top = min(-regY for (_, _, _, regY) in parts)
        right = max(-regX + img.get_width() for (_, img, regX, _) in parts)
        bottom = max(-regY + img.get_height() for (_, img, _, regY) in parts)

        w = int(right - left)
        h = int(bottom - top)
        out = pygame.Surface((w, h), pygame.SRCALPHA)

        # offsets from base layer meta (uses base layer *raw_idx* which is always synced)
        x_offset = 0
        y_offset = 0
        if self.base_layer_name and self.base_layer_name in self.layer_sheets:
            base_sheet = self.layer_sheets[self.base_layer_name]
            base_state = self._layer_state.get(self.base_layer_name)
            if base_state:
                base_idx = self._clamp(base_state.raw_idx, 0, len(base_sheet.frame_meta) - 1)
                meta = base_sheet.frame_meta[base_idx]
                if isinstance(meta, dict):
                    rel = meta.get("relativeOffsets")
                    if rel and len(rel) >= 2:
                        x_offset, y_offset = int(rel[0]), int(rel[1])

        for layer_name, img, regX, regY in parts:
            x = int((-regX) - left)
            y = int((-regY) - top)

            if self.base_layer_name and layer_name != self.base_layer_name:
                out.blit(img, (x + x_offset, y + y_offset))
            else:
                out.blit(img, (x, y))

        composite_reg = (int(-left), int(-top))
        return out, composite_reg

    # -----------------------------
    # Utilities
    # -----------------------------
    def _fire_anim_end(self, **data: Any) -> None:
        # print(f"[costume.py] _fire_anim_end(): data={data}")
        if self.actor:
            self.actor._fire_event(ActorEvents.ANIMATION_END, **data)
        pygame.event.post(pygame.event.Event(ActorEvents.ANIMATION_END, **data))

    @staticmethod
    def _clamp(v: int, lo: int, hi: int) -> int:
        if hi < lo:
            return lo
        return max(lo, min(int(v), int(hi)))
