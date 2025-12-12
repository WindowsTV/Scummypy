from __future__ import annotations

from scummypy.core import Engine
from game_state import GameState
# from scummypy.music import SongPool  # uncomment when you add room music pools

stage_size: tuple[int, int] = (640, 480)
fps: int = 60
title: str = "Scummypy Demo"
start_room_id: int = 1

# ROOMS format:
# room_id: (init_fn, room_name, optional_music_pool)
# optional_music_pool:
#   SongPool(song_ids=[int...], single_song_loop=False, immediate_playback=False, shuffle_pool=False)
#   or None
ROOMS: dict[int, tuple] = {
    # 0: ( interface.init, "interface", None ),
}

SOUND_CHANNELS = {
    "talkies": 0,
    "music": 1,
    "ambient": 2,
    "maxChannels": 80,
}

# song_id
# filename (path resolution handled by your resource loader/music system)
MUSIC_TRACKS: dict[int, str] = {
    # 8008: "street_theme.ogg",
}

def main() -> None:
    engine = Engine(stage_size, fps, title)
    engine.set_game_state(GameState())
    engine.register_rooms(ROOMS)
    engine.register_soundChannels(SOUND_CHANNELS)
    engine.register_music(MUSIC_TRACKS)
    engine.main_loop(start_room_id)

if __name__ == "__main__":
    main()
