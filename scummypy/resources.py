import os
import pygame

ASSETS_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

def _join(*parts):
    return os.path.join(ASSETS_ROOT, *parts)

def load_image(*path_parts):
    path = _join(*path_parts)
    return pygame.image.load(path).convert_alpha()

def load_room_image(room: str, img: str):
    return load_image("rooms", room, img)

def load_sound(*path_parts):
    path = _join(*path_parts)
    return pygame.mixer.Sound(path)
