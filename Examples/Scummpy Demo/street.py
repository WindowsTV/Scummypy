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

    bg = Resources.load_room_image(ROOM_PATH, "bg.png").convert()

    room = Room(engine, ROOM_NAME, bg)

    # attach script hooks as plain Python functions
    room.enter = lambda: enter(room, engine)
    room.destroy = lambda: destroy(room, engine)

    engine.game_state.set_flag("g_interfaceVisible", True) 

    #create_hotspot(left, top, width, height, onClick):
    exitToTrainHotspot = room.create_hotspot(420, 42, 146, 132, onExitToTrainClick)
    room.setup_clickpoint(exitToTrainHotspot, onExitToTrainClick, Cursors.NEDeep)

    exitToFakeRoom = room.create_hotspot(18, 152, 76, 188)
    room.setup_clickpoint(exitToFakeRoom, onExitToFakeRoom, Cursors.WEST)

    #create_hotspot(left, top, width, height, onClick):
    rockHotspot = room.create_hotspot(316, 230, 54, 40, onRockClick)
    room.setup_clickpoint(rockHotspot, onRockClick)

    stumpHotspot = room.create_hotspot(left=561, top=222, width=80, height=56)
    room.setup_clickpoint(stumpHotspot, onStumpClick)

    fireworks_img = Resources.load_room_image(ROOM_PATH, "sprite_fireworks.png")
    sprite_fireworks = Sprite(fireworks_img, (0, 0))
    room.add_sprite(sprite_fireworks, "sprite_fireworks")
    room.setup_clickpoint(sprite_fireworks, makeARock)   

    if engine.game_state.get_flag("street_madeARock") is True:
        makeARock(room, engine)

    return room


def enter(room, engine) -> None:
    print(f'[{ROOM_NAME}.py] Entered!')

    room.entered_from = engine.game_state.get_flag("g_lastRoom")
    if room.entered_from == 2:  # from goat room
        print(f'[street.py] you came from the Goat!')

    engine.current_skipable = lambda eng: handlePuttAnimationEnd(room.putt, None, room)
    costume = Costume( Resources.load_room_costume("PUTT/int-left-enter") )
    # Actor(actor_id=None, costume=None, name=None, pos=(0, 0), room=None)
    actor = Actor(room.get_next_actor_id(), costume)
    actor.costume.play()
    actor.add_event(
        ActorEvents.ANIMATION_END,
        handlePuttAnimationEnd,
        room, # Arg 3
    )
    room.add_actor(actor, "putt")

def handlePuttAnimationEnd(actor, event, room):
    pass
    print("handlePuttAnimationEnd", actor, event, room)
    if actor is not None:
        room.remove_actor(actor) 

    costume = Costume( Resources.load_room_costume("PUTT/pai-stat") )
    # Actor(actor_id=None, costume=None, name=None, pos=(0, 0), room=None)
    actor = Actor(room.get_next_actor_id(), costume)
    # actor.costume.play()
    room.add_actor(actor, "putt")
    actor.costume.stop_layer("head")
    actor.costume.stop_layer("lids")
    #actor.look_at("player")
    actor.costume.stop_layer("eyes-normal")

    onBlinkCompletedFunc = lambda: onBlinkCompleted(room, room.engine)
    threading.Timer(1, actor.blink, args=("player", onBlinkCompletedFunc)).start()
    #actor.blink("player", lambda: onBlinkCompleted(room, room.engine))  

def onBlinkCompleted(room, engine):
    room.putt.costume.play_layer("head", 0)
    room.putt.costume.play_layer("eyes-player", 0)

def onExitToTrainClick(room, engine):
    print("Bye-Bye!")
    engine.hide_cursor(inputBlocked=True)

    #engine.change_room(2)
    room.remove_actor(room.putt)

    costume = Costume( Resources.load_room_costume("PUTT/int-left2right-exit") )
    actor = Actor(room.get_next_actor_id(), costume)
    actor.costume.play()
    actor.add_event(
        ActorEvents.ANIMATION_END,
        onExitAnimationDone,
        room,
        2,
    )
    room.add_actor(actor, "putt")
    engine.current_skipable = lambda eng: onExitAnimationDone(actor, None, room, 2)

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
    print("rock clicked!")

    #engine.start_song(8008, loop=True)
    engine.music.kill_music(soft_kill=True)

def onStumpClick(room, engine):
    print("[street.py]", engine.actor_table)
    engine.show_text("This stump looks like it was cut a long time ago. When do you think it was cut?")

def exit(room, exit_to:int=0, exit_actor=None, exit_ainm_frame="") -> None:
    engine = room.engine
    if exit_to is 0:
        return print("[room] Can't go there..")
    if exit_actor is None:
        return engine.change_room(exit_to)

    engine.change_room(exit_to)

def onExitAnimationDone(exit_actor, event, room, exit_to:int=0) -> None:
    engine = room.engine
    if exit_to is 0:
        return print("[room] Can't go there..")
    
    engine.change_room(exit_to)


def destroy(room, engine) -> None:
    print(f'Destroying {ROOM_NAME}')