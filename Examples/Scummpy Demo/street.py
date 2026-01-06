import threading
import pygame
import time

from typing import Iterable
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

    enter_costume = Costume( Resources.load_room_costume("PUTT/int-left-enter") )
    room.entered_from = engine.game_state.get_flag("g_lastRoom")
    if room.entered_from == 2:  # from goat room
        enter_costume = Costume( Resources.load_room_costume("PUTT/int-right-enter") )

    engine.current_skipable = lambda eng: handlePuttAnimationEnd(room.putt, None, room)
    costume = enter_costume
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
    room.engine.current_skipable = None

    # print("handlePuttAnimationEnd", actor, event, room)
    #if actor is not None:
        #room.remove_actor(actor) 

    stat_costume = Costume( Resources.load_room_costume("PUTT/int-stat-left") )
    if room.entered_from == 2:  # from goat room
        stat_costume = Costume( Resources.load_room_costume("PUTT/int-stat-right") )

    costume = stat_costume
    actor.change_costume(costume)
    room.setup_clickpoint(actor, handleMainPuttClick)
    actor.costume.stop_layers("head", "lids", "eyes-normal", frame=None)

    #onBlinkCompletedFunc = lambda: onBlinkCompleted(room, room.engine)
    #threading.Timer(1, actor.blink, args=("player", onBlinkCompletedFunc)).start()
    #actor.blink("player", lambda: onBlinkCompleted(room, room.engine))  

def handleMainPuttClick(room, engine): 
    print("Putt clicked!")
    engine.say_line(["putt_0002", "putt_0003"], look_at="player")
    # print(_line_said.subtitle)

def onBlinkCompleted(room, engine):
    room.putt.costume.play_layer("head", 0)
    room.putt.costume.play_layer("eyes-player", 0)

def onExitToTrainClick(room, engine):
    print("Bye-Bye!")
    engine.hide_cursor(inputBlocked=True)

    exit_costume = Costume( Resources.load_room_costume("PUTT/int-left2right-exit") )
    if room.entered_from == 2:  # from goat room
        exit_costume = Costume( Resources.load_room_costume("PUTT/int-right2right-exit") )

    actor = room.putt
    costume = exit_costume
    actor.change_costume(costume)
    actor.costume.play()
    actor.add_event(
        ActorEvents.ANIMATION_END,
        onExitAnimationDone,
        room,
        2,
    )
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
    #engine.show_text("This stump looks like it was cut a long time ago. When do you think it was cut?", force_show=True)

    if not engine.game_state.get_flag("street_cu_on"):
        room.engine.current_skipable = lambda eng_self: hideCloseup(room, engine)
        engine.game_state.set_flag("street_cu_on", True) 
        bg = Resources.load_room_image(ROOM_PATH, "cu_left_bg.png").convert()
        engine.close_up(bg, True)
        costume = Costume( Resources.load_room_costume("PUTT/int-cu-stat") )
        room.putt.change_costume(costume)
        room.putt.costume.stop_layers("head", "lids", "eyes-normal", frame=None)
        room.close_up_timer = threading.Timer(0.4, handleCloseupStarted, args=(room, engine))
        room.close_up_timer.start()

    else:
        hideCloseup(room, engine)

def handleCloseupStarted(room, engine):
    print("handleCloseupStarted called")
    if engine.in_close_up == True:
        engine.say_line(["putt_0004", "putt_0006", "putt_0005"], on_done=lambda: handleCloseupEnded(room, engine))

def handleCloseupEnded(room, engine):
    room.close_up_timer = threading.Timer(1, hideCloseup, args=(room, engine))
    room.close_up_timer.start()

def hideCloseup(room, engine):
    room.close_up_timer.cancel()
    room.engine.current_skipable = None
    engine.game_state.set_flag("street_cu_on", False) 
    handlePuttAnimationEnd(room.putt, None, room)
    engine.hide_close_up()


def exit(room, exit_to:int=0, exit_actor=None, exit_ainm_frame="") -> None:
    engine = room.engine
    if exit_to is 0:
        return print("[room] Can't go there..")
    if exit_actor is None:
        return engine.change_room(exit_to)

    engine.change_room(exit_to)

def onExitAnimationDone(exit_actor, event, room, exit_to:int=0) -> None:
    room.engine.current_skipable = None
    engine = room.engine
    if exit_to is 0:
        return print("[room] Can't go there..")
    
    engine.change_room(exit_to)


def destroy(room, engine) -> None:
    print(f'Destroying {ROOM_NAME}')