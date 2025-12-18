import threading
import pygame
import time

import scummypy.resources as Resources
from scummypy.room import Room
from scummypy.sprite import Sprite
from scummypy.actor import Actor, ActorEvents
from scummypy.costume import Costume
from scummypy import audio
from scummypy.cursors import Cursors


ROOM_NAME: str = __name__
ROOM_PATH: str = ROOM_NAME+"/"

def init(engine) -> Room:
    print("init", ROOM_NAME, "with debug enabled:", engine.DEBUG)

    bg = Resources.load_room_image(ROOM_PATH, "bg.jpg").convert()

    room = Room(engine, ROOM_NAME, bg)

    # attach script hooks as plain Python functions
    room.enter = lambda: enter(room, engine)
    room.destroy = lambda: destroy(room, engine)

    return room


def enter(room, engine) -> None:
    print("Entered", ROOM_NAME, Resources.ROOM_PATH)
    engine.game_state.set_flag("g_interfaceVisible", False) 

    # print(f'{ROOM_NAME} says at enter() g_lastRoom is {engine.game_state.get_flag("g_lastRoom")}')
    # print(f'{ROOM_NAME} says at enter() g_previousRooms is {engine.game_state.get_flag("g_previousRooms")}')

    #create_hotspot(left, top, width, height, onClick):
    exit_to = engine.game_state.get_flag("g_currentRoom")
    onExitHotspotClicked = lambda *_ : exit(room, exit_to)
    exitHotspot = room.create_hotspot(left=569, top=13, width=58, height=63)
    room.setup_clickpoint(exitHotspot, onExitHotspotClicked, Cursors.NEDeep)

    onMenuToggleClicked = lambda *_ : menuItemToggle(room, engine, "subtitles")
    subtitlesHotspot = room.create_hotspot(left=154, top=142, width=326, height=51)
    room.setup_clickpoint(subtitlesHotspot, onMenuToggleClicked)

    onMenuToggleClicked = lambda *_ : menuItemToggle(room, engine, "music")
    musicHotspot = room.create_hotspot(left=154, top=222, width=326, height=51)
    room.setup_clickpoint(musicHotspot, onMenuToggleClicked)

    onMenuSingleClicked = lambda *_ : menuItemSingle(room, engine, "restartGame")
    restartGameHotspot = room.create_hotspot(left=154, top=303, width=326, height=51)
    room.setup_clickpoint(restartGameHotspot, onMenuSingleClicked)

def menuItemToggle(room, engine, toggle_name:str = "") -> None:
    print(f"Toggling menu item: {toggle_name}")
    if toggle_name == "music":
        engine.toggle_music()
    elif toggle_name == "subtitles":
        engine.toggle_screen_text()

def menuItemSingle(room, engine, action_name:str = "") -> None:
    print(f"Single menu item: {action_name}")
    if action_name == "restartGame":
        engine.restart_game()

def exit(room, exit_to:int=0, exit_actor=None, exit_ainm_frame="") -> None:
    engine = room.engine
    if not isinstance(exit_to, int):
        return print(f"[room] exit_to must be int, got {type(exit_to).__name__}")
    
    if exit_to <= 0 or exit_to is None:
        return print("[room] Can't go there..")
    
    # print(f'{ROOM_NAME} says at exit() g_lastRoom is {engine.game_state.get_flag("g_lastRoom")}')
    engine.game_state.set_flag("g_interfaceVisible", True) 
    engine.change_room(exit_to, skip_enter_func=True)

def onExitAnimationDone(exit_actor, event, room, exit_to:int=0) -> None:
    engine = room.engine
    if exit_to is 0:
        return print("[room] Can't go there..")
    
    engine.change_room(exit_to)


def destroy(room, engine) -> None:
    print(f'Destroying {ROOM_NAME}')

    # Override the g_lastRoom to set the stat animation correctly
    prev_rooms = engine.game_state.get_flag("g_previousRooms") or []
    last_room_for_stat_animation = prev_rooms[-1] if prev_rooms else None
    engine.game_state.set_flag("g_lastRoom", last_room_for_stat_animation)
    