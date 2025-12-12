import pygame
import tkinter as tk
from tkinter import simpledialog
from tkinter import commondialog
from tkinter import messagebox
from .system import InputDialog


import scummypy.resources as Resources
from .cursors import Cursors
from .actor import ActorEvents
from .audio import AudioManager, AudioEventScheduler
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
        pygame.key.set_repeat(80)

        self.clock = pygame.time.Clock()
        self.fps: int = fps
        self.title: str = title
        self.running: bool = False
        self.input_blocked: bool = False

        self.interface = None
        self.current_room = None
        self.room_registry = {}       # { "room_id": init(engine) }
        self.actor_table = {}
        self.sound_channels = {}
        self.audio_schedulers = []
        Cursors.load_all()
        self.Cursors = Cursors

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

    def register_audioEvents(self, get_position_func=None):
        scheduler = AudioEventScheduler(get_position_func)
        self.audio_schedulers.append(scheduler)
        return scheduler

    def change_room(self, room_id: int):
        if room_id <= 0:
            raise Exception("Room ID can not be 0 or lower!")

        if self.current_room is not None:
            if hasattr(self.current_room, "destroy"):
                self.current_room.destroy()

        self.audio.stop_all_but(self.music.music_channel)

        if self.interface:
            self.interface.remove_all_actors()
            self.interface.enable_all_clickpoints()

        factory = self.room_registry[room_id]
        self.current_room = factory[0](self)
        self.current_room.enter()
        self.current_room.screen = self.screen

        # Run this once to reset the mouse cursor..
        self._handle_mouse_motion()

        try:
            song_ids = factory[2].song_ids
            single_song_loop = factory[2].single_song_loop
            immediate_playback = factory[2].immediate_playback
            shuffle_pool = factory[2].shuffle_pool

            print("[core.py] change_room()> b4 shuffle=", song_ids)
            if shuffle_pool is True:
                self.music.shuffle_pool(song_ids)
                print("[core.py] change_room()> after shuffle=", song_ids)
            
            self.music.set_preferred_pool(song_ids)
            #print("[core.py] self.music._current_song_id =", self.music._current_song_id)
            
            if self.music._current_song_id <= 0:
                self.music.start_next_song_now()
            elif immediate_playback is True:
                if self.music._current_song_id not in self.music._current_pool:
                    self.music.start_next_song_now()

        except Exception as err:
            pass


        if self.DEBUG:
            pygame.display.set_caption(f"{self.title} - room: {self.current_room.ROOM_NAME}")


    def main_loop(self, start_room_id: int):
        if start_room_id:
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
                elif event.type == pygame.MOUSEMOTION:
                    self._handle_mouse_motion(event)
                else:
                    if not self.input_blocked:
                        if event.type == pygame.KEYDOWN:
                            self._handle_keydown(event)
                        if event.type == pygame.KEYUP:
                            self._handle_keyup(event)
                            
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
        #print("[core.py] _handle_keydown()> unicode=", event.unicode, "key=", event.key)
        if event.key == 1073742048: #CTRL Key
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
        self.input_blocked = True
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
            self.refocus_pygame()

        return msg_response


    def hide_cursor(self, inputBlocked=False):
        self.game_state.set_flag("g_cursorVisible", False)
        #self.game_state.set_flag("g_inputDisabled", inputDisabled) 
        self.input_blocked = inputBlocked

        isCursorVisible = self.game_state.get_flag("g_cursorVisible")
        pygame.mouse.set_visible(isCursorVisible)
        pygame.display.flip()

    def show_cursor(self, inputBlocked=False):
        self.game_state.set_flag("g_cursorVisible", True) 
        #self.game_state.set_flag("g_inputDisabled", inputDisabled)
        self.input_blocked = inputBlocked

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

    def start_song(self, songId: int, loop: bool = False):
        self.music.start_song(songId, loop)

    def play_talkie(self, filename, soundChannel=0, loop: bool = False):
        filepath = "assets/audio/talkies/" + filename
        sound = self.audio.load(filepath)
        return self.audio.play(sound, filename, soundChannel, loop)
    
    def play_sound(self, filename, soundChannel=-1, loop: bool = False):
        filepath = "assets/audio/sfx/" + filename
        sound = self.audio.load(filepath)
        return self.audio.play(sound, filename, soundChannel, loop)