from scummypy.core import Engine
from scummypy.music import SongPool
from game_state import GameState

stage_size: tuple = (640, 480)
fps: int = 60
title: str = "Scummypy Demo"

start_room_id: int = 1

#Import Room logic...
import interface
import street
import goat
import flower
import menu

ROOMS: dict[int, tuple] = {
    # [Room.init func, Room Name, Song Pool]
    0: (interface.init, "interface"),
    1: (street.init, "street", SongPool(
            [8007, 8008], 
            single_song_loop=True, 
            immediate_playback=False
        )),
    2: (goat.init, "goat", SongPool(
            [8006, 8009], 
            single_song_loop=False, 
            immediate_playback=True,
            shuffle_pool=True,
        )),
    3: (flower.init, "flower"),
    4: (menu.init, "menu"),
}
#ROOM_NAMES: list = [
#   "interface",
#    "street",
#]

SOUND_CHANNELS: dict[str, int] = {
    'talkies': 0,
    'music': 1,
    'ambient': 2,
    'maxChannels': 80
}
MUSIC_TRACKS: dict[int, str] = {
    # songId: filename
    8006: "puttcircus3.mp3",
    8007: "intro.mp3",
    8008: "goestomoon.mp3",
    8009: "parkviewmix2a.mp3",
}      
TALKIES: dict[str, tuple] = {
    # talkie_id: (filename, text)
    "putt_0001": (
                    "putt_0001.flac",
                    "That's my gas gauge.",
                 ),
}      

def main():
    engine = Engine(stage_size, fps, title)
    engine.register_rooms(ROOMS)
    engine.register_soundChannels(SOUND_CHANNELS)
    engine.register_music(MUSIC_TRACKS)
    engine.register_talkies(TALKIES)
    engine.set_game_state(GameState())
    engine.game_state.set_flag("g_musicMuted", True)
    engine.main_loop(start_room_id)

if __name__ == "__main__":
    main()
