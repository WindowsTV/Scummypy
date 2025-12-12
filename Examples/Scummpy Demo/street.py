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

    bg = Resources.load_room_image(ROOM_PATH, "bg.png").convert()

    room = Room(engine, ROOM_NAME, bg)

    # attach script hooks as plain Python functions
    room.enter = lambda: enter(room, engine)
    room.destroy = lambda: destroy(room, engine)

    return room


def enter(room, engine) -> None:
    print("Entered", ROOM_NAME)
    engine.game_state.set_flag("g_interfaceVisible", True) 

    #engine.start_song(8008, loop=True)

    #create_hotspot(left, top, width, height, onClick):
    exitToTrainHotspot = room.create_hotspot(420, 42, 146, 132, onExitToTrainClick)
    room.setup_clickpoint(exitToTrainHotspot, onExitToTrainClick, Cursors.NEDeep)

    exitToFakeRoom = room.create_hotspot(18, 152, 76, 188)
    room.setup_clickpoint(exitToFakeRoom, onExitToFakeRoom, Cursors.WEST)

    #create_hotspot(left, top, width, height, onClick):
    rockHotspot = room.create_hotspot(316, 230, 54, 40, onRockClick)
    room.setup_clickpoint(rockHotspot, onRockClick)

    stumpHotspot = room.create_hotspot(left=561, top=222, width=80, height=56)
    room.stumpClickpoint = room.setup_clickpoint(stumpHotspot, onStumpClick)

    fireworks_img = Resources.load_room_image(ROOM_PATH, "sprite_fireworks.png")
    sprite_fireworks = Sprite(fireworks_img, (0, 0))
    room.add_sprite(sprite_fireworks, "sprite_fireworks")
    room.setup_clickpoint(sprite_fireworks, makeARock)   

    if engine.game_state.get_flag("street_madeARock") is True:
        makeARock(room, engine)

def onExitToTrainClick(room, engine):
    print("Bye-Bye!")
    engine.toggle_cursor_visible()

    engine.change_room(2)

def onExitToFakeRoom(room, engine):
    engine.toggle_cursor_visible()
    
    currentVisible = engine.game_state.get_flag("g_interfaceVisible")
    if currentVisible is True:
        engine.hide_interface()
    else:
        engine.show_interface()

    #engine.game_state.set_flag("g_interfaceVisible", not currentVisible) 
    # later: open close-up room, show dialog, etc.

def makeARock(room, engine):
    rock_img = Resources.load_room_image(ROOM_PATH, "rock-obstacle-pixelated.png")
    rock_sprite=None

    if not room.sprite_exists("rock_sprite"):
        rock_sprite = Sprite(rock_img, (0, 0))
        room.add_sprite(rock_sprite, "rock_sprite")
        room.rock_sprite.x += 100
        engine.game_state.set_flag("street_madeARock", True) 
    else:
        engine.game_state.set_flag("street_madeARock", False) 
        room.remove_sprite(room.rock_sprite)
        
    print(room.sprites)


def onRockClick(room, engine):
    print("rock clicked!", engine.music._current_handle.on_end_cb.__name__)

    #engine.start_song(8008, loop=True)
    engine.music.kill_music(soft_kill=True)

def onStumpClick(room, engine):
    print("[street.py]", engine.actor_table)

def exit(room, exit_to:int=0, exit_actor=None, exit_ainm_frame="") -> None:
    engine = room.engine
    if exit_to is 0:
        return print("[room] Can't go there..")
    if exit_actor is None:
        return engine.change_room(exit_to)

    engine.change_room(exit_to)

def destroy(room, engine) -> None:
    print(f'Destroying {ROOM_NAME}')