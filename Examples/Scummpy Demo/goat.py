import pygame
import time

import scummypy.resources as Resources
from scummypy.room import Room
from scummypy.sprite import Sprite
from scummypy.actor import Actor
from scummypy.costume import Costume
from scummypy import audio
from scummypy.cursors import Cursors


ROOM_NAME: str = __name__
ROOM_PATH: str = ROOM_NAME+"/"

def init(engine) -> Room:
    print("init", ROOM_NAME, "with debug enabled:", engine.DEBUG)

    bg = Resources.load_room_image(ROOM_PATH, "bg.jpg").convert()

    room = Room(engine, ROOM_NAME, bg)

    #create_hotspot(left, top, width, height, onClick):
    exitToStreetRoom = room.create_hotspot(0, 178, 76, 192)
    room.setup_clickpoint(exitToStreetRoom, lambda *_: exit(room, 1), Cursors.WEST)

    exitToFlowerRoom = room.create_hotspot(left=579, top=245, width=60, height=96)
    # room.setup_clickpoint(exitToFlowerRoom,  lambda room, engine: exit(room, exit_to=3, exit_actor=None), Cursors.EShallow)
    room.setup_clickpoint(exitToFlowerRoom,  lambda *_: exit(room, exit_to=3, exit_actor=None), Cursors.EShallow)

    # attach script hooks as plain Python functions
    room.enter = lambda: enter(room, engine)
    room.destroy = lambda: destroy(room, engine)

    return room
    


def enter(room, engine) -> None:
    print("Entered", ROOM_NAME)
    engine.game_state.set_flag("g_interfaceVisible", True) 
    engine.show_cursor()

    room.entered_from = engine.game_state.get_flag("g_lastRoom")
    if room.entered_from == 1:
        print(f'[street.py] you came from the Street!')

    #engine.start_song(1, loop=True)

def onExitToStreetRoom(room, engine) -> None:
    print("Bye-Bye!")
    exit(room, exit_to=1)

def exit(room, exit_to:int=0, exit_actor=None, exit_ainm_frame="") -> None:
    engine = room.engine
    if exit_to is 0:
        return print("[room] Can't go there..")
    if exit_actor is None:
        return engine.change_room(exit_to)

    engine.change_room(exit_to)

def destroy(room, engine) -> None:
    print(f'Destroying {ROOM_NAME}')