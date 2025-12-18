import os
import json
import pygame

ASSETS_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
ROOM_PATH = ""

def _join(*parts):
    #print(f"_join()> ASSETS_ROOT={ASSETS_ROOT} & parts={parts}")
    sanitized = [str(p).lstrip('/\\') for p in parts]
    full_path = os.path.join(ASSETS_ROOT, *sanitized)
    #print(f"_join()> full_path={full_path}")
    return full_path

def load_image(*path_parts):
    path = _join(*path_parts)
    return pygame.image.load(path).convert_alpha()

def load_room_image(room: str, img: str):
    return load_image("rooms", room, img)

def load_room_costume(file_name: str):
    json_path = _join("rooms", ROOM_PATH, "cost", f"{file_name}.json")

    with open(json_path, "r", encoding="utf-8") as f:
        json_data:dict = json.load(f)
    
    layer_images_src = {}
    base_url = json_data.get("base_url", None)
    if base_url is not None:
        # Using the Costume JSON 
        image:pygame.Surface = pygame.Surface((0,0))  # placeholder
        layers = json_data.get("layers", {})

        # Some layers in the JSON can be empty strings (""), so guard for dicts
        for layer_name, layer in layers.items():
            if not isinstance(layer, dict):
                continue

            # If layer points to another JSON (src), we skip image loading here
            src_path = layer.get("src", None)
            if src_path is not None:
                continue

            layer_images = layer.get("images", {})
            for img_name in layer_images:
                layer_images_src[img_name] = (load_image("rooms", ROOM_PATH, "cost", base_url, f"{img_name}"))

    else:
        image:pygame.Surface = load_image("rooms", ROOM_PATH, "cost", f"{file_name}.png")

    return image, json_data, layer_images_src

def load_sound(*path_parts):
    path = _join(*path_parts)
    return pygame.mixer.Sound(path)

def load_music_track(*path_parts):
    path = _join(*path_parts)
    return pygame.mixer.Sound(path)
