from dataclasses import dataclass
import pygame
import tkinter as tk
from tkinter import simpledialog
from tkinter import commondialog
from tkinter import messagebox
from .system import InputDialog


import scummypy.resources as Resources
from .cursors import Cursors
from .actor import ActorEvents
from .audio import AudioHandle, AudioManager, AudioEventScheduler
from .music import MusicSystem, Song

class Engine:
    def __init__(self, screen_size=(640, 480), fps=60, title="Scummpy"):
        pygame.init()
        self.screen = pygame.display.set_mode(screen_size)
        pygame.display.set_caption(title)

        # ---- Tkinter hidden root ----
        self.tk_root = tk.Tk()
        self.tk_root.withdraw()   # Hide the main Tkinter window
        self.tk_root.attributes("-topmost", True)  # Dialogs appear on top

        self.DEBUG: bool = False
        self.HOTSPOT_DRAWER_POINTS = [(None, None), (0, 0)]
        # pygame.key.set_repeat(80)

        self.clock = pygame.time.Clock()
        self.fps: int = fps
        self.title: str = title
        self.running: bool = False
        self.mouse_input_blocked: bool = False
        self.key_input_blocked: bool = False

        # [audio.py] SOUND_END = pygame.USEREVENT + 1
        self.SCREEN_TEXT_EVENT: int = pygame.USEREVENT + 3
        # [actor.py] ANIMATION_END = pygame.USEREVENT + 100

        self.interface = None
        self.last_room = None
        self.current_room = None
        self.current_skipable = callable
        self.room_registry = {}       # { "room_id": init(engine) }
        self.actor_table = {}
        self.sound_channels = {}
        self.audio_schedulers = []
        Cursors.load_all()
        self.Cursors = Cursors

        self.screen_text = (None, None)

    def refocus_pygame(self):
        # Bring the Pygame window to the front
        pygame.display.set_mode(self.screen.get_size())  # refreshes window handle

        # Force SDL window to focus
        pygame.event.post(pygame.event.Event(pygame.ACTIVEEVENT, gain=1, state=6))

        # On some window managers, we need an explicit focus command:
        try:
            if self.DEBUG and self.current_room:
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

        if hasattr(self.current_room, "enter"):
            self.current_room.enter()
            if skip_enter_func is True:
                if self.current_skipable and callable(self.current_skipable):
                    self.current_skipable(self)

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

        # current room stays a single int
        self.game_state.set_flag("g_currentRoom", room_id)


    def main_loop(self, start_room_id: int):
        if start_room_id:
            self.start_room_id = start_room_id
            if self.DEBUG: 
                print("[core.py] Start game in Room:", start_room_id)
            self.change_room(start_room_id)

        self.running = True

        while self.running:
            dt = self.clock.tick(self.fps) / 1000.0  # seconds
            for scheduler in self.audio_schedulers:
                scheduler.update()
            self.audio_schedulers = [
                s for s in self.audio_schedulers
                if not s.finished
            ] # clean out finished ones

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == self.audio.SOUND_END:
                    self.audio.on_audio_end()
                elif event.type == self.SCREEN_TEXT_EVENT:
                    self.screen_text = (None, None)
                    pygame.time.set_timer(self.SCREEN_TEXT_EVENT, 0)  # Stop the timer
                elif event.type == pygame.MOUSEMOTION:
                    self._handle_mouse_motion(event)
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
        # print("[core.py] _handle_keydown()> unicode=", event.unicode, "key=", event.key)
        if event.key == 27 or event.key == 115: #Escape Key or S Key
            pygame.key.set_repeat(0)
            if self.current_skipable and callable(self.current_skipable):
                    self.current_skipable(self)
                    self.current_skipable = None
            else:
                print("[core.py] Escape Pressed - no skipable, do a stop-line")

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
    
    def show_prompt(self, promptType="input", title="Info", message="Unknown message"):
        # Block engine input while dialog is up
        self.mouse_input_blocked = True
        self.key_input_blocked = True

        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)

        msg_response = None
        try:
            if promptType in ("okay", "ok"):
                msg_response = messagebox.showinfo(title, message, parent=self.tk_root)

            elif promptType == "okCancel":
                msg_response = messagebox.askokcancel(title, message, parent=self.tk_root)

            elif promptType == "input":
                dialog = InputDialog(self.tk_root, title, message)
                msg_response = dialog.result

            elif promptType == "yesNo":
                msg_response = messagebox.askyesno(title, message, parent=self.tk_root)

            else:
                # Fallback to simple info
                msg_response = messagebox.showinfo(title, message, parent=self.tk_root)

        finally:
            # Flush any clicks/keys that happened while dialog was up
            pygame.event.clear()

            # Restore input & cursor
            self.show_cursor(inputBlocked=False)
            self.key_input_blocked = False
            self.refocus_pygame()

        return msg_response


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

    def show_text(
        self,
        text: str,
        color: tuple = (255, 255, 255),
        duration: float = 0,
        position: tuple[int, int] = (4, 4),
        outline_px: int = 2
    ) -> None:
        if not text:
            return
        
        screen_text_enabled = self.game_state.get_flag("g_screenTextEnabled")
        if screen_text_enabled != True:
            return

        if duration <= 0:
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
    def toggle_screen_text(self):
        screen_text_enabled = self.game_state.get_flag("g_screenTextEnabled")
        if screen_text_enabled == True:
            self.game_state.set_flag("g_screenTextEnabled", False)
            if self.screen_text[0] is not None:
                self.screen_text = (None, None)
                pygame.time.set_timer(self.SCREEN_TEXT_EVENT, 0)  # Stop the timer
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
        self.change_room(start_room_id)


    @dataclass
    class TalkieResult:
        handle: AudioHandle
        subtitle: str | None
        
    def play_talkie(self, filename: str, soundChannel: int = 0, loop: bool = False):
        filepath = f"assets/audio/talkies/{filename}"
        sound = self.audio.load(filepath)
        return self.audio.play(sound, filename, soundChannel, loop)

    def say_line(self, key: str, *, color=(255, 165, 255), channel: int = 0, show_subtitles: bool = True):
        # Defaults if no entry exists
        filename = key
        subtitle = None

        talkie_info = self.talkie_table.get(key)
        if talkie_info:
            filename, subtitle = talkie_info  # (audio_filename, subtitle_text)

        handle = self.play_talkie(filename, soundChannel=channel, loop=False)

        if show_subtitles and subtitle:
            self.show_text(subtitle, color=color)

        return self.TalkieResult(handle, subtitle)


    def play_sound(self, filename, soundChannel=-1, loop: bool = False):
        filepath = "assets/audio/sfx/" + filename
        sound = self.audio.load(filepath)
        return self.audio.play(sound, filename, soundChannel, loop)