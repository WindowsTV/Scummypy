import pygame

import scummypy.resources as Resources
from scummypy.room import Room
from scummypy.actor import Actor, ActorEvents
from scummypy.costume import Costume
from scummypy import audio

ROOM_NAME: str = __name__

def init(engine) -> Room:
    print("init", ROOM_NAME, "with debug enabled:", engine.DEBUG)

    bg = Resources.load_image("interface/", "interface_bg.bmp").convert()
    bg.set_colorkey((173, 0, 173))

    bg_rect = bg.get_rect()
    bg_rect.y = 349

    room = Room(engine, ROOM_NAME, bg, bg_rect)

    # attach script hooks as plain Python functions
    room.enter = lambda: enter(room, engine)
    room.destroy = lambda: destroy(room, engine)
    room.initiated = True

    return room


# ---------- SCRIPTS (plain functions) ----------

def enter(room, engine) -> None:
    print("Setup Interface...")
    room.entered = True

    gasGaugeHotspot = room.create_hotspot(5, 394, 42, 50)
    room.setup_clickpoint(gasGaugeHotspot, onGasGaugeClick)

    hornHotspot = room.create_hotspot(102, 408, 42, 50)
    room.hornClickpoint = room.setup_clickpoint(hornHotspot, onHornClick)

    speedHotspot = room.create_hotspot(left=198, top=376, width=84, height=62)
    room.speedClickpoint = room.setup_clickpoint(speedHotspot, onSpeedClick)

    radioHotspot = room.create_hotspot(left=200, top=442, width=93, height=32)
    room.radioClickpoint = room.setup_clickpoint(radioHotspot, onRadioClick)

def onGasGaugeClick(room, engine):
    _current_handle = engine.play_talkie("putt_0001.flac")
    print("I think I need some gas..")

def onHornClick(room, engine):
    print("Heather go beep")
    room.disable_clickpoint(room.hornClickpoint)
    
    _current_handle = engine.play_sound("sfx_pp_horn.mp3")
    _current_handle.on_end_cb = lambda: onHornAfter(room, engine)
    
    #actor: radio
    if not room.sprite_exists("int-horn"):
        inv_costume = Costume(
            "assets/interface/inventory.png",
            "assets/interface/inventory.json",
        )
        # Actor(actor_id=None, costume=None, name=None, pos=(0, 0), room=None)
        hornActor = Actor(room.get_next_actor_id(), inv_costume)
        hornActor.costume.sprite_sheet.set_colorkey((203, 123, 199))
        hornActor.costume.play("inv-horn-beep")
        hornActor.add_event(
            ActorEvents.ANIMATION_END,
            handleEvent,
            room,
            room.hornClickpoint
        )
        room.add_actor(hornActor, "int-horn")

def handleEvent(actor, event, room, clickpoint=None):
    # print("actor:", actor)
    # print("animation ended:", event["animation"])
    # print("end frame:", event["end_frame"])
    room.remove_actor(actor)
    if clickpoint is not None: room.enable_clickpoint(clickpoint)
    #room.radioHotspot.disabled = False

def onHornAfter(room, engine):
    print("She did go beep...")

def onSpeedClick(room, engine):
    print("Speedy..")
    room.disable_clickpoint(room.speedClickpoint)

    _current_handle = engine.play_sound("sfx_inv_rev.mp3")

    costume = Costume(
        "assets/interface/inventory.png",
        "assets/interface/inventory.json",
    )
    # Actor(actor_id=None, costume=None, name=None, pos=(0, 0), room=None)
    actor = Actor(room.get_next_actor_id(), costume)
    actor.costume.play("inv-speedometer")
    actor.add_event(
        ActorEvents.ANIMATION_END,
        handleEvent,
        room,
        room.speedClickpoint
    )
    room.add_actor(actor, "int-speed")


def onRadioClick(room, engine):    
    print("Gee, maybe I should say something here.")
    room.disable_clickpoint(room.radioClickpoint)

    handle = engine.play_sound("sfx_inv_radio_static.mp3", 3)
    
    scheduler = engine.register_audioEvents(handle)
    scheduler.add_event(1000, int_audio_scheduled_event, room, engine, handle)

    if not room.sprite_exists("radio"):
        inv_costume = Costume(
            "assets/interface/inventory.png",
            "assets/interface/inventory.json",
        )
        radioActor = Actor(room.get_next_actor_id(), inv_costume)
        radioActor.costume.play("inv-radio-talking")
        radioActor.add_event(
            ActorEvents.ANIMATION_END,
            handleEvent,
            room,
            room.radioClickpoint
        )
        room.add_actor(radioActor, "radio")


def int_audio_scheduled_event(room, engine, audioHandler=lambda:None) -> None:
    print("int_audio_scheduled_event()", room.ROOM_NAME)

def destroy(room, engine) -> None:
    print(f'Destroying{ROOM_NAME}')
