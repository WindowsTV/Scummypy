from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .audio import AudioManager

import random

NEW_SONG_NOW = -1
STOP_MUSIC = 0
RESET_POOL = -1

@dataclass
class SongPool:
    song_ids: list
    single_song_loop: bool=False      # Set to True when song_ids has only one song and you want to loop it
    immediate_playback: bool=False      # Set to True when you want to start the music from the song_ids always. Otherwise the pool will start after the current song.
    shuffle_pool: bool=False

@dataclass
class Song:
    id: int
    filename: str      # e.g. "street_theme.ogg"

@dataclass
class MusicSystem:
    """
    High-level SCUMM-style music controller.

    - Uses AudioManager to actually play files.
    - Keeps track of current song and song pools.
    - Exposes methods similar to the SCUMM macros:
        - start_song(song_id)
        - start_next_song_now()
        - kill_music()
        - save/restore_preferred_pool()
    """
    audio: AudioManager
    _current_handle = None
    song_table: Dict[int, Song]      # song_id -> Song
    standard_pool: List[int] = field(default_factory=list)
    preferred_pool: Optional[List[int]] = None

    _preferred_pool_save: Optional[List[int]] = None
    _current_pool: List[int] = field(default_factory=list)
    _current_index: int = 0
    _current_song_id: int = STOP_MUSIC
    _last_song_id: int = STOP_MUSIC

    music_channel: int = -1


    def __post_init__(self):
        # If no explicit standard pool was given, use all song ids
        if not self.standard_pool:
            self.standard_pool = sorted(self.song_table.keys())
        # Start with the standard pool
        self._current_pool = list(self.standard_pool)
    
    # --- pool management (SCUMM-like) ---

    def use_standard_pool(self) -> None:
        """Switch back to the standard song pool."""
        self._current_pool = list(self.standard_pool)
        self._current_index = -1

    def set_preferred_pool(self, song_ids: List[int]) -> None:
        """Replace the preferred pool with a new list of song IDs."""
        self.preferred_pool = list(song_ids)
        self._current_pool = self.preferred_pool
        self._current_index = -1

    def save_preferred_pool(self) -> None:
        """
        SAVE_PREFERRED_SONG_POOL equivalent:
        Remember the current preferred pool and clear it.
        """
        self._preferred_pool_save = self.preferred_pool
        self.preferred_pool = None
        self.use_standard_pool()

    def restore_preferred_pool(self) -> None:
        """
        RESTORE_PREFERRED_SONG_POOL equivalent:
        Restore previously saved preferred pool.
        """
        if self._preferred_pool_save is not None:
            self.preferred_pool = self._preferred_pool_save
            self._preferred_pool_save = None
            self._current_pool = self.preferred_pool
            self._current_index = -1

    def shuffle_pool(self, pool_to_shuffle) -> None:
        if type(pool_to_shuffle) is list:
            random.shuffle(pool_to_shuffle)

    # --- core operations (macros) ---

    def start_song(self, song_id: int, loop: bool = False) -> None:
        """
        START_SONG behavior:
        - STOP_MUSIC (0)  -> stop all music.
        - NEW_SONG_NOW (-1) -> play next song in current pool.
        - positive id -> play that exact song id.
        """
        if song_id == STOP_MUSIC:
            self.kill_music()
            self._current_index = -1
            return

        if song_id == NEW_SONG_NOW:
            self._play_next_in_pool()
            return

        # play specific song id
        if self._current_handle:
            self.kill_music()

        self._play_song_by_id(song_id, loop)

    def start_song_pool(self) -> None:
        pass

    def start_next_song_now(self) -> None:
        """
        START_NEXT_SONG_NOW behavior:
        Same as start_song(NEW_SONG_NOW).
        """
        self.start_song(NEW_SONG_NOW)

    def kill_music(self, soft_kill=False) -> None:
        """
        KILL_MUSIC behavior:
        Stop all background music.
        """
                    
        if self._current_handle:
            if soft_kill is False:
                self._last_song_id = self._current_song_id
                self._current_song_id = STOP_MUSIC
                self._current_handle.on_end_cb = lambda: None
            self._current_handle.stop()
            print("[music.py] kill_music()", self._current_handle.on_end_cb.__name__)
        

    # --- internal helpers ---

    def _play_next_in_pool(self) -> None:
        # print("[music.py] _play_next_in_pool()")
        if not self._current_pool:
            # no songs in pool, just stop
            self.kill_music()
            return
        
        pool_len = len(self._current_pool)
        # If pool has only one song, unavoidable repeat.
        if pool_len == 1:
            next_id = self._current_pool[0]
            self._current_index = 0
            self._play_song_by_id(next_id)
            return
        
        attempts = 0
        next_id = self._current_song_id

        while next_id == self._current_song_id and attempts < pool_len:
            self._current_index = (self._current_index + 1) % pool_len
            next_id = self._current_pool[self._current_index]
            attempts += 1

        # If we tried pool_len times and still got the same id,
        # the pool is effectively all the same song; just play it.
        self._play_song_by_id(next_id)

    def _play_song_by_id(self, song_id: int, loop: bool = False) -> None:
        song = self.song_table.get(song_id)
        if not song:
            self.kill_music()
            return

        filename = song.filename
        filepath = "assets/audio/music/" + filename
        sound = self.audio.load(filepath)
        self._current_handle = self.audio.play(sound, filename, self.music_channel, loop)

        self._current_handle.on_end_cb = self.start_next_song_now
        # print("[music.py] set on_end_cb to", self._current_handle.on_end_cb.__name__)

        self._last_song_id = int(self._current_song_id)
        self._current_song_id = song_id
        print("[music.py] _play_song_by_id() > _current_song_id=", self._current_song_id,"& _last_song_id=", self._last_song_id)

    @property
    def current_song_id(self) -> int:
        return self._current_song_id
