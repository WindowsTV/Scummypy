import threading
import time
from unittest import result
import pygame
import traceback

from dataclasses import dataclass


import scummypy.resources as Resources
from .cursors import Cursors
from .actor import ActorEvents
from .audio import AudioHandle, AudioManager, AudioEventScheduler
from .music import MusicSystem, Song
from .system import ask_yes_no, ask_ok_cancel

class Engine:
    def __init__(self, screen_size=(640, 480), fps=60, title="Scummpy"):
        pygame.init()
        self.screen = pygame.display.set_mode(screen_size)
        pygame.display.set_caption(title)

        self.DEBUG: bool = False
        self.HOTSPOT_DRAWER_POINTS = [(None, None), (0, 0)]
        # pygame.key.set_repeat(80)

        self._main_thread_id = threading.get_ident()
        self._skip_dt_frames = 0
        self.clock = pygame.time.Clock()
        self.fps: int = fps
        self.title: str = title
        self.running: bool = False
        self.mouse_input_blocked: bool = False
        self.key_input_blocked: bool = False

        # [audio.py] SOUND_END = pygame.USEREVENT + 1
        self.SCREEN_TEXT_EVENT: int = pygame.USEREVENT + 3
        self.ENGINE_RESTART_EVENT = pygame.USEREVENT + 50
        # [actor.py] ANIMATION_END = pygame.USEREVENT + 100
        # [actor.py] ACTOR_UPDATE = pygame.USEREVENT + 101

        self.interface = None
        self.last_room = None
        self.current_room = None
        self.current_skipable = callable
        self.in_close_up = False
        self.room_registry = {}       # { "room_id": init(engine) }
        self.actor_table = {}
        self.sound_channels = {}
        self.audio_schedulers = []
        self._line_token_by_channel: dict[int, int] = {}
        self._line_queue_by_channel: dict[int, list] = {}
        self._line_active_by_channel: dict[int, bool] = {}
        self._line_on_done_by_channel: dict = {}
        self._current_actor_talking: int = -1
        Cursors.load_all()
        self.Cursors = Cursors

        self.screen_text = (None, None)

    def refocus_pygame(self):
        # Bring the Pygame window to the front
        #pygame.display.set_mode(self.screen.get_size())  # refreshes window handle

        # Force SDL window to focus
        pygame.event.post(pygame.event.Event(pygame.ACTIVEEVENT, gain=1, state=2))

        # On some window managers, we need an explicit focus command:
        try:
            if self.DEBUG and self.current_room:
                pass
                pygame.display.set_caption(f"{self.title} - room: {self.current_room.ROOM_NAME}")
            else:          
                pygame.display.set_caption(self.title)  # causes focus update
        except:
            pass

    def set_game_state(self, gameState):
        self.game_state = gameState
        if self.game_state:
            # Sometimes the DEBUG in core.py is not available to check in all Python files
            self.game_state.set_flag("g_DEBUG", self.DEBUG) 


    def register_rooms(self, room_table: dict, room_names: list | None = None):
        """room_table: {room_id: init(engine) -> Room}"""
        self.room_registry.update(room_table)
        
        # Quick fix for potential removal of room_names
        if room_names is None:
            room_names = []
       #if "interface" in room_names:
            #index = room_names.index('interface')
            #self.interface = self.room_registry[index]
            #print("[core.py]", self.interface)

        for room_id in self.room_registry:
            room_name = self.room_registry[room_id][1]
            if room_name == "interface":
                factory = self.room_registry[room_id]
                self.interface = factory[0](self)
                self.interface.enter()
                self.interface.screen = self.screen

        if self.DEBUG: 
            print("[core.py] room_table:", room_table)

    def register_soundChannels(self, sound_channels: dict):
        self.audio = AudioManager(sound_channels['maxChannels'])

        self.sound_channels = sound_channels

        if self.DEBUG: 
            print(f'[core.py] sound_channels:{sound_channels}')

    def register_music(self, song_table: dict):
        """music_table: {id: filename}"""

        for songId in song_table:
            song = song_table[songId]
            song_table[songId] = Song(songId, song)

        self.music = MusicSystem(
            audio=self.audio,
            song_table=song_table,
        )
        if self.sound_channels['music']:
            self.music.music_channel = self.sound_channels['music']

        if self.DEBUG: 
            print("[core.py] song_table:", song_table)

    def register_talkies(self, talkie_table: dict):
        """talkie_table: {id: (filename, text)}"""
        self.talkie_table = talkie_table

        if self.DEBUG: 
            print("[core.py] talkie_table:", talkie_table)

    def register_audioEvents(self, get_position_func=None):
        scheduler = AudioEventScheduler(get_position_func)
        self.audio_schedulers.append(scheduler)
        return scheduler

    def enter_modal_room(self, room_id: int):
        # 1) Suspend current WORLD room (do NOT destroy)
        if self.modal_room is not None:
            raise RuntimeError("Modal already active")

        if self.current_room is None:
            raise RuntimeError("No world room to suspend")

        self.suspended_world_room = self.current_room
        self.suspended_world_room_id = self.game_state.get_flag("g_currentRoom") or 0
        self.world_paused = True

        # optional: stop actor AI/ticks if your room update drives that
        # optional: stop SFX but keep music, up to you

        # 2) Load modal room as the ACTIVE displayed room
        factory = self.room_registry[room_id]
        Resources.ROOM_PATH = factory[1]
        self.modal_room = factory[0](self)
        self.modal_room_id = room_id

        # Route drawing/input to modal
        self.modal_room.screen = self.screen

        self.modal_room.enter()

        # Cursor reset
        self._handle_mouse_motion()

    def change_room(self, room_id: int, skip_enter_func: bool = False):

        if room_id is None or not isinstance(room_id, int):
            raise TypeError(f"room_id must be int, got {type(room_id).__name__}")

        if room_id <= 0:
            raise Exception("room_id can not be 0 or lower!")

        # --- flags: last room + rolling last-3 room history ---
        prev_room = int(self.game_state.get_flag("g_currentRoom"))  # int or None

        # previous room
        self.game_state.set_flag("g_lastRoom", prev_room)

        # rolling history (last 3, newest first)
        history = self.game_state.get_flag("g_previousRooms")
        if not isinstance(history, list):
            history = []

        if isinstance(prev_room, int):
            history.insert(0, int(prev_room))
            # remove duplicates while keeping order
            # history = list(dict.fromkeys(history))
            # keep only last 3
            history = history[:3]

        self.game_state.set_flag("g_previousRooms", history)

        # print(f'[core.py] g_lastRoom is {self.game_state.get_flag("g_lastRoom")}')
        # print(f'[core.py] g_previousRooms is {self.game_state.get_flag("g_previousRooms")}')

        if self.current_room is not None:
            if hasattr(self.current_room, "destroy"):
                self.current_room.destroy()

        self.clear_lines()
        self.audio.stop_all_but(self.music.music_channel)
        if screen_text := self.screen_text[0]:
            self.screen_text = (None, None)
            pygame.time.set_timer(self.SCREEN_TEXT_EVENT, 0)  # Stop the timer

        if self.interface:
            self.interface.remove_all_actors()
            self.interface.enable_all_clickpoints()

        factory = self.room_registry[room_id]
        Resources.ROOM_PATH = factory[1]
        self.current_room = factory[0](self)
        self.game_state.set_flag("g_currentRoom", room_id)
        self.current_skipable = None

        if hasattr(self.current_room, "enter"):
            self.current_room.enter()
            if skip_enter_func is True:
                if self.current_skipable and callable(self.current_skipable):
                    self.current_skipable(self)
                    self.current_skipable = None

        self.current_room.screen = self.screen

        # Run this once to reset the mouse cursor..
        self._handle_mouse_motion()

        try:
            song_ids = factory[2].song_ids
            single_song_loop = factory[2].single_song_loop
            immediate_playback = factory[2].immediate_playback
            shuffle_pool = factory[2].shuffle_pool

            if shuffle_pool is True:
                self.music.shuffle_pool(song_ids)

            self.music.set_preferred_pool(song_ids)

            if self.game_state.get_flag("g_musicMuted") is not True:
                if self.music._current_song_id <= 0:
                    self.music.start_next_song_now()
                elif immediate_playback is True:
                    if self.music._current_song_id not in self.music._current_pool:
                        self.music.start_next_song_now()

        except Exception:
            pass

        if self.DEBUG:
            pygame.display.set_caption(f"{self.title} - room: {self.current_room.ROOM_NAME}")

    def main_loop(self, start_room_id: int):
        if start_room_id:
            self.start_room_id = start_room_id
            if self.DEBUG: 
                print("[core.py] Start game in Room:", start_room_id)
            self.change_room(start_room_id)

        self.running = True

        while self.running:
            dt = self.clock.tick(self.fps) / 1000.0
            dt = min(dt, 1/30) # clamp to ~33ms (or 1/15 if you prefer)

            # If we just came back from a modal, ignore dt for a couple frames
            if self._skip_dt_frames > 0:
                dt = 0.0
                self._skip_dt_frames -= 1

            for scheduler in self.audio_schedulers:
                scheduler.update()
            self.audio_schedulers = [
                s for s in self.audio_schedulers
                if not s.finished
            ] # clean out finished ones

            for event in pygame.event.get():
                if event.type in (
                    getattr(pygame, "WINDOWFOCUSGAINED", -1),
                    getattr(pygame, "WINDOWFOCUSLOST", -1),
                    getattr(pygame, "WINDOWENTER", -1),
                    getattr(pygame, "WINDOWLEAVE", -1),
                ): 
                    pass # print("[WIN]", pygame.event.event_name(event.type), event)


                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == self.ENGINE_RESTART_EVENT:
                    print("[core.py] ENGINE_RESTART_EVENT received")

                    self.change_room(event.room_id)

                    # Reset timing so room enter animation doesn't fast-forward
                    self.clock.tick()
                    self._skip_dt_frames = 2

                    # Flush anything queued from the previous room/menu/dialog
                    pygame.event.clear()
                    break

                elif event.type == self.audio.SOUND_END:
                    print("[core.py] SOUND_END event received")
                    self.audio.on_audio_end()
                elif event.type == self.SCREEN_TEXT_EVENT:
                    print("[core.py] SCREEN_TEXT_EVENT event received")
                    self.screen_text = (None, None)
                    pygame.time.set_timer(self.SCREEN_TEXT_EVENT, 0)  # Stop the timer
                elif event.type == pygame.MOUSEMOTION:
                    self._handle_mouse_motion(event)
                elif event.type == ActorEvents.ACTOR_UPDATE:
                    if event.update_type is "new" or event.update_type is "change":
                        actor = self.actor_table.get(event.actor_id, None)
                        if actor is not None:
                            print(f'[core.py] ACTOR_UPDATE event received {event.update_type} for actor_id: {event.actor_id}')
                            if actor.actor_can_flap_while_change == False and self.is_actor_talking(actor_id=event.actor_id):
                                if self.in_close_up == False:
                                    self.stop_line(channel=0)
                else:
                    if not self.key_input_blocked:
                        if event.type == pygame.KEYDOWN:
                            self._handle_keydown(event)
                        if event.type == pygame.KEYUP:
                            self._handle_keyup(event)

                    if not self.mouse_input_blocked:                        
                        if self.current_room:
                            self.current_room.handle_event(event)
                        if self.interface:
                            self.interface.handle_event(event)

            if self.current_room:
                self.current_room.update(dt)
                self.current_room.draw(self.screen)

            if self.interface:
                if self.game_state.get_flag("g_interfaceVisible") is True:
                    self.interface.update(dt)
                    self.interface.draw(self.screen)   

            if self.screen_text[0] is not None:
                for surf, rect in self.screen_text:
                    self.screen.blit(surf, rect)

            pygame.display.flip()

        pygame.quit()

    def _handle_mouse_motion(self, event=None):
        isCursorVisible = self.game_state.get_flag("g_cursorVisible")
        pygame.mouse.set_visible(isCursorVisible)

        if event is not None:
            pos = event.pos
        else:
            pos =  pygame.mouse.get_pos()

        hover_cursor = None

        # 1. Room hover
        if self.current_room:
            room_cursor = self.current_room.get_hover_cursor(pos)
            if room_cursor is not None:
                hover_cursor = room_cursor

        # 2. Interface hover (takes priority, but only if it actually returns something)
        if self.interface and self.game_state.get_flag("g_interfaceVisible") is True:
            ui_cursor = self.interface.get_hover_cursor(pos)
            if ui_cursor is not None:
                hover_cursor = ui_cursor

        # 3. Decide final cursor
        if hover_cursor is not None:
            # hover_cursor can already be a pygame Cursor or a system cursor constant
            cursor = hover_cursor
        else:
            cursor = Cursors.NORMAL or pygame.SYSTEM_CURSOR_CROSSHAIR

        pygame.mouse.set_cursor(cursor)

    def _handle_keydown(self, event):
        print("[core.py] _handle_keydown()> unicode=", event.unicode, "key=", event.key)
        if event.key == 27 or event.key == 115: #Escape Key or S Key
            pygame.key.set_repeat(0)
            if self.current_skipable and callable(self.current_skipable):
                    self.current_skipable(self)
                    self.current_skipable = None
            else:
                print("[core.py] Escape Pressed - no skipable, do a stop-line")
                self.stop_line(channel=0)
        if event.key == 46: # Period Key
            self.skip_line(channel=0)
        if event.key == 1073742048: #CTRL Key
            pygame.key.set_repeat(80)

            pos =  pygame.mouse.get_pos()
            if self.HOTSPOT_DRAWER_POINTS[0] is (None, None):
                self.HOTSPOT_DRAWER_POINTS[0] = pos

            self.HOTSPOT_DRAWER_POINTS[1] = pos

            left = self.HOTSPOT_DRAWER_POINTS[0][0]
            top = self.HOTSPOT_DRAWER_POINTS[0][1]
            width = int(self.HOTSPOT_DRAWER_POINTS[1][0]) - left
            height = int(self.HOTSPOT_DRAWER_POINTS[1][1]) - top

            print(f'left={left}, top={top}, width={width}, height={height}')

            rect: pygame.Rect = pygame.Rect(0, 0, 100, 100)
            pygame.draw.rect(self.screen, "red", rect, width=2)

    def _handle_keyup(self, event):
        if event.key == 1073742048: #CTRL Key
            self.HOTSPOT_DRAWER_POINTS[0] = (None, None)
    
    def _debug_focus_snapshot(self, tag: str):
        try:
            focused = pygame.key.get_focused()
        except Exception:
            focused = None

        try:
            mouse_focused = pygame.mouse.get_focused()
        except Exception:
            mouse_focused = None

        pressed = None
        try:
            pressed = pygame.mouse.get_pressed(3)
        except Exception:
            pass

        print(
            f"[FOCUS] {tag} | key_focused={focused} mouse_focused={mouse_focused} "
            f"blocked(mouse={self.mouse_input_blocked}, key={self.key_input_blocked}) "
            f"pressed={pressed}"
        )

    def _debug_drain_events(self, n: int = 30, tag: str = ""):
        events = pygame.event.get()
        print(f"[EVENTS] drain tag={tag} count={len(events)}")
        for i, e in enumerate(events[:n]):
            name = pygame.event.event_name(e.type)
            extras = []
            if hasattr(e, "pos"):
                extras.append(f"pos={e.pos}")
            if hasattr(e, "button"):
                extras.append(f"button={e.button}")
            if hasattr(e, "key"):
                extras.append(f"key={e.key}")
            if hasattr(e, "gain"):
                extras.append(f"gain={getattr(e, 'gain', None)} state={getattr(e, 'state', None)}")
            print(f"  {i:02d}: {name} ({e.type}) {' '.join(extras)}")

    def prompt(
        self,
        *,
        prompt_type: str = "okcancel",
        title: str | None = None,
        message: str = "Are you sure?",
        pcallback=None,
        ncallback=None,
    ) -> bool:
        if title is None:
            title = self.title
        if prompt_type == "yesno":
            return ask_yes_no(self, title=title, message=message, pcallback=pcallback, ncallback=ncallback)
        elif prompt_type == "okcancel":
            return ask_ok_cancel(self, title=title, message=message, pcallback=pcallback, ncallback=ncallback)
        else:
            return False


    def hide_cursor(self, inputBlocked=False):
        self.game_state.set_flag("g_cursorVisible", False)
        #self.game_state.set_flag("g_inputDisabled", inputDisabled) 
        self.mouse_input_blocked = inputBlocked

        isCursorVisible = self.game_state.get_flag("g_cursorVisible")
        pygame.mouse.set_visible(isCursorVisible)
        pygame.display.flip()

    def show_cursor(self, inputBlocked=False):
        self.game_state.set_flag("g_cursorVisible", True) 
        #self.game_state.set_flag("g_inputDisabled", inputDisabled)
        self.mouse_input_blocked = inputBlocked

        isCursorVisible = self.game_state.get_flag("g_cursorVisible")
        pygame.mouse.set_visible(isCursorVisible)
        self._handle_mouse_motion()

        pygame.display.flip()

    def toggle_cursor_visible(self):
        isCursorVisible = self.game_state.get_flag("g_cursorVisible")
        if isCursorVisible is True:
            self.hide_cursor()
        else:
            self.show_cursor()

    def hide_interface(self, hideCursor=False):
        if self.interface:
            self.interface.remove_all_room_actors()
            self.interface.enable_all_clickpoints()
        
        self.game_state.set_flag("g_interfaceVisible", False)

        if hideCursor is True:
            self.hide_cursor()

    def show_interface(self, showCursor=True):
        self.game_state.set_flag("g_interfaceVisible", True)
        
        if showCursor is True:
            self.show_cursor()

    def close_up(self, bg, hideCursor=True):
        self.stop_line(channel=0)
        
        if self.interface:
            self.interface.remove_all_room_actors()
            self.interface.disable_all_clickpoints()
        if self.current_room:
            self.current_room.background = bg
            self.current_room.background_rect = bg.get_rect()
            self.current_room.hide_current_sprites()
        
        self.in_close_up = True
        self.game_state.set_flag("g_interfaceVisible", False)

        if hideCursor == True:
            self.hide_cursor(inputBlocked=True)

    def hide_close_up(self, showCursor=True):
        if self.interface:
            self.interface.enable_all_clickpoints()
        if self.current_room:
            self.current_room.background = self.current_room.restore_background
            self.current_room.background_rect = self.current_room.restore_background.get_rect()
            self.current_room.show_hidden_items()

        self.in_close_up = False
        self.game_state.set_flag("g_interfaceVisible", True)

        if showCursor == True:
            self.show_cursor(inputBlocked=False)

    def show_text(
        self,
        text: str,
        color: tuple = (255, 255, 255),
        duration: float = 0,
        position: tuple[int, int] = (4, 4),
        outline_px: int = 2,
        force_show: bool = False,
    ) -> None:
        if not text:
            return
        
        screen_text_enabled = self.game_state.get_flag("g_screenTextEnabled")
        if force_show is True:
            screen_text_enabled = True
            
        if screen_text_enabled != True:
            return

        if duration == 0:
            words = len(text.split())
            duration = max(1200, words * 300)

        font = pygame.font.SysFont("Arial Rounded MT Bold", 48, bold=False)
        fg = color
 
        outline = (0, 0, 0)

        max_width = self.screen.get_width() - position[0] - 8

        lines = self.wrap_text(text, font, max_width)

        y = position[1]
        rendered = []

        for line in lines:
            surf = self.render_text_outline(
                font,
                line,
                fg,
                outline,
                outline_px
            )
            rect = surf.get_rect(topleft=(position[0], y))
            rendered.append((surf, rect))
            y += font.get_height()

        self.screen_text = rendered

        for surf, rect in rendered:
            self.screen.blit(surf, rect)

        pygame.display.flip()
        if duration >= 0:
            pygame.time.set_timer(self.SCREEN_TEXT_EVENT, int(duration))

    def render_text_outline(
            self,
            font: pygame.font.Font,
            text: str,
            fg_color: tuple[int, int, int],
            outline_color: tuple[int, int, int] = (0, 0, 0),
            outline_px: int = 1
    ) -> pygame.Surface:
        text_surf = font.render(text, True, fg_color)

        w = text_surf.get_width() + outline_px * 2
        h = text_surf.get_height() + outline_px * 2

        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        # Draw outline
        for dx in range(-outline_px, outline_px + 1):
            for dy in range(-outline_px, outline_px + 1):
                if dx == 0 and dy == 0:
                    continue
                surf.blit(
                    font.render(text, True, outline_color),
                    (dx + outline_px, dy + outline_px)
                )

        # Draw main text
        surf.blit(text_surf, (outline_px, outline_px))
        return surf


    def wrap_text(self, text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        words = text.split(" ")
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            width, _ = font.size(test_line)

            if width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines
    
    def render_wrapped_outline_text(
            self,
            text: str,
            font: pygame.font.Font,
            max_width: int,
            fg_color=(255, 255, 255),
            outline_color=(0, 0, 0),
            outline_px=1
    ) -> list[pygame.Surface]:
        lines = self.wrap_text(text, font, max_width)

        surfaces = []
        for line in lines:
            surf = self.render_text_outline(
                font,
                line,
                fg_color,
                outline_color,
                outline_px
            )
            surfaces.append(surf)

        return surfaces
    
    def remove_text(self):
        self.screen_text = (None, None)
        pygame.time.set_timer(self.SCREEN_TEXT_EVENT, 0)  # Stop the timer
            
    def toggle_screen_text(self):
        screen_text_enabled = self.game_state.get_flag("g_screenTextEnabled")
        if screen_text_enabled == True:
            self.game_state.set_flag("g_screenTextEnabled", False)
            if self.screen_text[0] is not None:
                self.remove_text()
        else:
            self.game_state.set_flag("g_screenTextEnabled", True)

    def toggle_music(self):        
        music_muted = self.game_state.get_flag("g_musicMuted")
        if music_muted == True: 
            # Music is muted, so unmute and start playing
            self.game_state.set_flag("g_musicMuted", False)
            self.music.start_next_song_now()
        else:
            # Music is playing, so mute it
            self.game_state.set_flag("g_musicMuted", True)
            self.music.kill_music(soft_kill=False)

    def start_song(self, songId: int, loop: bool = False):
        if self.game_state.get_flag("g_musicMuted") is True:
            return
        self.music.start_song(songId, loop)

    def restart_game(self, start_room_id=None):
        """
        Fully restart the game:
        - Clears room, actors, UI, audio, and game state
        - Returns to the start room
        """
        if start_room_id is None:
            start_room_id = getattr(self, "start_room_id", None)
            if start_room_id is None:
                raise ValueError("restart_game requires a start_room_id (or Engine.start_room_id set).")

        # 1) Stop any timers (example: your caption timer)
        if hasattr(self, "SCREEN_TEXT_EVENT"):
            pygame.time.set_timer(self.SCREEN_TEXT_EVENT, 0)

        # 2) Clear UI / captions
        if hasattr(self, "screen_text"):
            self.screen_text = (None, None)

        # 3) Stop audio
        if hasattr(self, "audio"):
            music_muted = self.game_state.get_flag("g_musicMuted")
            print(f'[core.py] restart_game() music_muted={music_muted}')

            if music_muted == True: 
                self.audio.stop_all_but(self.music.music_channel)
            else:
                self.audio.stop_all()
    

        # 4) Clear actor table safely
        if hasattr(self, "actor_table"):
            # copy values so we can modify the dict while iterating
            for actor in list(self.actor_table.values()):
                actor.destroy()
            self.actor_table.clear()

        # 5) Let the current room clean itself up
        if self.current_room is not None:
            # if you have room.exit logic, call it
            if hasattr(self.current_room, "exit"):
                self.current_room.exit()
            if hasattr(self.current_room, "destroy"):
                print('[core.py] restart_game() destroying current room')
                self.current_room.destroy()

            # clear sprite groups if the room has them
            if hasattr(self.current_room, "actors"):
                self.current_room.actors.empty()
                self._current_actor_talking = -1

            if hasattr(self.current_room, "hotspots"):
                self.current_room.hotspots.clear()

            self.current_room = None

        # 6) Reset game state
        # If you use a GameState class, recreate it here.
        # Otherwise just clear the dict.
        if isinstance(self.game_state, dict):
            print('[core.py] restart_game() clearing game_state dict')
            self.game_state.clear()
        else:
            new_state = type(self.game_state)()
            for k in ("g_screenTextEnabled", "g_musicMuted", "g_talkiesMuted", "g_soundsMuted"):
                new_state.set_flag(k, self.game_state.get_flag(k))

            self.game_state = new_state

        # 7) Restart from the beginning
        pygame.event.post(pygame.event.Event(self.ENGINE_RESTART_EVENT, {"room_id": start_room_id}))
        #threading.Timer(0.1, self.change_room, args=(start_room_id,)).start()
        #self.change_room(start_room_id)


    @dataclass
    class TalkieResult:
        handle: AudioHandle
        subtitle: str | None
        
    def play_talkie(self, filename: str, soundChannel: int = 0, loop: bool = False, preload: bool = False):
        filepath = f"assets/audio/talkies/{filename}"
        sound = self.audio.load(filepath)
        if preload:
            return self.audio.preload_sound(sound, filename, soundChannel, loop)
        return self.audio.play(sound, filename, soundChannel, loop)

    def _next_line_token(self, channel: int) -> int:
        t = self._line_token_by_channel.get(channel, 0) + 1
        self._line_token_by_channel[channel] = t
        return t
    
    def say_line(self, key, *, color=(255,165,255), actor_id=1, look_at="normal",
                channel: int = 0, show_subtitles: bool = True, on_done=None) -> TalkieResult | None:
        # Remove any existing text first
        if self.screen_text[0] is not None:
            self.remove_text()

        self._current_actor_talking = actor_id
        
        # SEQUENCE MODE
        if isinstance(key, (list, tuple)):
            return self._say_line_sequence(
                key, # type: ignore
                color=color,
                actor_id=actor_id,
                look_at=look_at,
                channel=channel,
                show_subtitles=show_subtitles,
                on_done=on_done,
            )
        
        # SINGLE LINE MODE
        return self._say_one_line(
            key,
            color=color,
            actor_id=actor_id,
            look_at=look_at,
            channel=channel,
            show_subtitles=show_subtitles,
            token=self._next_line_token(channel),
            on_done=on_done,
        )
    
    def _say_line_sequence(
        self,
        items: list,
        *,
        color=(255,165,255),
        actor_id=1,
        look_at="normal",
        channel: int = 0,
        show_subtitles: bool = True,
        on_done=callable,
    ):
        # New token for the whole sequence (so skip cancels pending steps)
        token = self._next_line_token(channel)

        # Build a queue of "steps"
        # Steps are tuples: ("say", key, actor_id, look_at) or ("cmd", {...})
        queue: list[tuple] = []
        current_actor = actor_id
        current_look = look_at

        for it in items:
            if isinstance(it, str):
                queue.append(("say", it, current_actor, current_look))
            elif isinstance(it, dict):
                # command dicts
                if "changeTalker" in it:
                    current_actor = int(it["changeTalker"])
                if "look_at" in it:
                    current_look = str(it["look_at"])
                # you can add more commands later (pause, wait_ms, etc.)
            else:
                raise TypeError(f"Unsupported sequence item: {it} ({type(it).__name__})")

        # Store/replace queue for this channel
        self._line_queue_by_channel[channel] = queue
        self._line_active_by_channel[channel] = True
        self._line_on_done_by_channel[channel] = on_done

        def play_next():
            # If sequence was cancelled (skip / new say_line), stop.
            if self._line_token_by_channel.get(channel) != token:
                if on_done:
                    on_done()
                self._line_active_by_channel[channel] = False
                return

            q = self._line_queue_by_channel.get(channel, [])
            if not q:
                # Sequence complete
                self._line_active_by_channel[channel] = False
                if on_done:
                    on_done()
                return

            step = q.pop(0)
            self._line_queue_by_channel[channel] = q

            kind = step[0]
            if kind != "say":
                # (we’re not pushing cmd steps into queue in this version)
                return play_next()

            _, one_key, one_actor_id, one_look = step

            # Play ONE line, and when it ends, call play_next()
            self._say_one_line(
                one_key,
                color=color,
                actor_id=one_actor_id,
                look_at=one_look,
                channel=channel,
                show_subtitles=show_subtitles,
                token=token,
                on_done=play_next,
            )

        return play_next()

        # Return something predictable. You can return None or a small object.
        return None

    def _say_one_line(
        self,
        key: str,
        *,
        color=(255,165,255),
        actor_id=1,
        look_at="normal",
        channel: int = 0,
        show_subtitles: bool = True,
        token: int,
        on_done=None,   # called after audio finishes
    ):
        filename = key
        subtitle = None

        talkie_info = self.talkie_table.get(key)
        if talkie_info:
            filename, subtitle = talkie_info

        handle = self.play_talkie(filename, soundChannel=channel, loop=False, preload=False)

        def guarded_done():
            # Only run if this sequence is still current
            if self._line_token_by_channel.get(channel) != token:
                return
            # Clean text, then move on
            self.remove_text()
            if on_done:
                on_done()

        actor = self.actor_table.get(actor_id)
        if actor is None:
            handle.on_end_cb = guarded_done
            if show_subtitles and subtitle:
                self.show_text(subtitle, color=color, duration=-1)
            return self.TalkieResult(handle, subtitle)

        # If already flapping and need to change gaze, stop flap first
        if actor.flapping_mouth and actor.currently_looking_at != look_at:
            actor.stop_mouth_flap(self, {}, do_blink=False)

        def safe_play():
            if self._line_token_by_channel.get(channel) != token:
                return
            handle.play()

        if actor.blink_required_before_flap and actor.currently_looking_at != look_at:
            handle.pause()

            def on_blink_done():
                if self._line_token_by_channel.get(channel) != token:
                    if actor.flapping_mouth:
                        return
                    return actor.look_at("normal")

                # IMPORTANT: pass guarded_done so end triggers next line
                actor.flap_mouth(handle, guarded_done)
                safe_play()

            has_blinked = actor.blink(look_at, on_blink_done)
            if has_blinked is False:
                actor.flap_mouth(handle, guarded_done)
                safe_play()
        else:
            actor.flap_mouth(handle, guarded_done)

        if show_subtitles and subtitle:
            self.show_text(subtitle, color=color, duration=-1)

        return self.TalkieResult(handle, subtitle)


    def stop_line(self, channel: int = 0, invalidate_pending_cbs: bool = True):
        #queue = self._line_queue_by_channel.get(channel)
        #if not queue:
            #return
        
        # Invalidate any pending "resume" callbacks for this channel
        self._next_line_token(channel)
        self.audio.stop_channel(channel)
        self.remove_text()
        self._current_actor_talking = -1

    def skip_line(self, channel: int = 0):
        if not self._line_active_by_channel.get(channel):
            self.audio.stop_channel(channel)
            self.remove_text()
            return

        # Invalidate current audio callbacks
        token = self._next_line_token(channel)

        # Stop sound + visuals
        self.audio.stop_channel(channel)
        self.remove_text()

        # Stop actor animation
        queue = self._line_queue_by_channel.get(channel)
        if queue:
            _, _, actor_id, _ = queue[0]
            actor = self.actor_table.get(actor_id)
            if actor and actor.flapping_mouth:
                actor.stop_mouth_flap(self, {}, do_blink=False)

        # Advance using the SAME logic as normal flow
        self._advance_sequence(channel, token)

    def _advance_sequence(self, channel: int, token: int):
        # Sequence was cancelled
        if self._line_token_by_channel.get(channel) != token:
            self._line_active_by_channel[channel] = False
            return

        queue = self._line_queue_by_channel.get(channel, [])
        while queue:
            step = queue.pop(0)
            self._line_queue_by_channel[channel] = queue

            kind = step[0]

            def advance_sequence():
                self._advance_sequence(channel, token)

            if kind == "say":
                _, key, actor_id, look_at = step
                self._say_one_line(
                    key,
                    actor_id=actor_id,
                    look_at=look_at,
                    channel=channel,
                    token=token,
                    on_done=advance_sequence,
                )
                return  # wait for this say to finish

            else:
                # COMMAND STEP — execute immediately
                self._execute_command_step(step)
                continue

        # End of sequence
        self._line_active_by_channel[channel] = False
        self._finish_sequence(channel, token)
        
    def _execute_command_step(self, step: tuple):
        kind = step[0]

        if kind == "cmd":
            cmd = step[1]
            if "changeTalker" in cmd:
                self._current_actor_talking = int(cmd["changeTalker"])
            if "look_at" in cmd:
                actor = self.actor_table.get(self._current_actor_talking)
                if actor:
                    actor.look_at(cmd["look_at"])

    def _finish_sequence(self, channel: int, token: int):
        if self._line_token_by_channel.get(channel) != token:
            return

        self._line_active_by_channel[channel] = False

        on_done = self._line_on_done_by_channel.pop(channel, None)
        if callable(on_done):
            on_done()

    def clear_lines(self, channel: int = 0):
        if channel in self._line_queue_by_channel:
            del self._line_queue_by_channel[channel]
        self._current_actor_talking = -1

    def is_actor_in_talkie_queue(self, channel: int = 0, actor_id: int = 1) -> bool:
        # print(f"[core.py] is_actor_in_talkie_queue()> channel={channel}, actor_id={actor_id}")

        queue = self._line_queue_by_channel.get(channel)
        if not queue:
            return False

        token, line, queued_actor_id, eye_state = queue[0]
        if queued_actor_id == actor_id:
            return True
        
        return False
    
    def is_actor_talking(self, channel: int = 0, actor_id: int = 1) -> bool:
        if self._current_actor_talking == actor_id:
            return True
        
        return self.is_actor_in_talkie_queue(channel, actor_id)


    def play_sound(self, filename, soundChannel=-1, loop: bool = False):
        filepath = "assets/audio/sfx/" + filename
        sound = self.audio.load(filepath)
        return self.audio.play(sound, filename, soundChannel, loop)