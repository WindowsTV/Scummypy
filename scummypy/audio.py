import time
import pygame

class AudioEventScheduler:
    """
    Fires callbacks when audio position reaches given timestamps.
    get_pos_ms is a function that returns the current playback position in ms.
    """    
    def __init__(self, audioHandle, get_pos_ms=None):
        self.handle = audioHandle
        self.get_pos_ms = audioHandle.get_position_ms
        # [time_ms, cb, args, kwargs, fired]
        self.events = []
        self.finished = False   # we'll use this for engine cleanup

        self.handle.audioEventScheduler = self


    def add_event(self, time_ms, callback, *args, **kwargs):
        self.events.append([time_ms, callback, args, kwargs, False])

    def clear_events(self):
        self.events = []
        self.finished = True

    def update(self):
        if self.finished:
            return

        pos = self.get_pos_ms()
        if pos == -100:
            return self.clear_events()
        
        remaining = []

        for t, cb, args, kwargs, fired in self.events:
            if not fired and pos >= t:
                try:
                    cb(*args, **kwargs)
                    fired = True
                except Exception as ex:
                    print("Error in audio callback", cb.__name__, ":", ex)

            if not fired:
                remaining.append([t, cb, args, kwargs, fired])

        self.events = remaining

        # If there are no more events, we can mark this as done
        if not self.events:
            self.finished = True



class AudioHandle:
    """Wrapper around a playing sound so callers can stop it and query logical position."""
    def __init__(self, channel: pygame.mixer.Channel, sound: pygame.mixer.Sound):
        self.channel = channel
        self.sound = sound
        self.identity = ""
        self.on_end_cb = lambda: None

        self._start_time:float = -100
        self._paused = False
        self._pause_time = 0.0  # perf_counter() at pause

        self.audioEventScheduler = None

    def set_identity(self, _identity):
        self.identity = _identity

    def play(self, loop: bool = False):
        self._start_time = time.perf_counter()
        self._paused = False
        self._pause_time = 0.0
        self.channel.play(self.sound, loops=-1 if loop else 0)

    def stop(self):
        if self.channel:
            self.channel.stop()
        self._start_time = -100

    def is_playing(self):
        if self._start_time == -100 or self.channel is None:
            return False

        ch = self.channel
        if not ch.get_busy():
            return False

        # If pygame is playing a different Sound on this channel now,
        # treat this handle as stopped.
        cur_sound = ch.get_sound()
        if cur_sound is not self.sound:
            self._start_time = -100  # poison so get_position_ms returns -100
            return False

        return True

    def pause(self):
        if not self._paused and self.channel.get_busy():
            self._paused = True
            self._pause_time = time.perf_counter()
            self.channel.pause()

    def resume(self):
        if self._paused:
            # shift start_time forward so total elapsed stays correct
            delta = time.perf_counter() - self._pause_time
            self._start_time += delta
            self._paused = False
            self.channel.unpause()

    def get_position_ms(self) -> float:
        """Logical position in ms since play(), for lip sync / events."""
        if self._start_time == -100:
            return -100
        if not self.is_playing():
            return -100

        if self._paused:
            elapsed = self._pause_time - self._start_time
        else:
            elapsed = time.perf_counter() - self._start_time

        return elapsed * 1000.0


class AudioManager:
    """
    Ultra-thin audio wrapper.
    - loads Audio.
    - plays Audio.
    - stops Audio.
    """
    SOUND_END = pygame.USEREVENT + 1

    def __init__(self, num_channels: int = 20):
        print(f'[audio.py] AudioManager(num_channels={num_channels})')
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.set_num_channels(num_channels)

        # Pre-allocate channels for deterministic behavior
        self.channels = [pygame.mixer.Channel(i) for i in range(num_channels)]

        # Sounds cache
        self.cache = {}
        self.sounds_playing: list[AudioHandle] = []

    def load(self, filepath: str) -> pygame.mixer.Sound:
        """Load (and cache) a sound file."""
        if filepath not in self.cache:
            self.cache[filepath] = pygame.mixer.Sound(filepath)
        return self.cache[filepath]

    def play(self, sound: pygame.mixer.Sound, filename, soundChannel: int, loop: bool = False) -> AudioHandle:
        if soundChannel != -1 and self.channels[soundChannel]:
            channel = self.channels[soundChannel]      # << always honor explicit channel
        else:
            channel = pygame.mixer.find_channel()

        if channel is None:
            channel = self.channels[-1]

        # 2. Remove any old handles tied to this channel (music or sfx)
        to_keep = []
        for h in self.sounds_playing:
            if h.channel is channel:
                if h.audioEventScheduler:
                    h.audioEventScheduler.clear_events()
                pass
            else:
                to_keep.append(h)
        self.sounds_playing = to_keep

        # 3. Create new handle
        handle = AudioHandle(channel, sound)
        handle.set_identity(filename)
        handle.play(loop=loop)
        channel.set_endevent(self.SOUND_END)

        self.sounds_playing.append(handle)
        return handle

    
    def on_audio_end(self):
        """Remove handles whose channel has stopped, then trigger callbacks.

        Important: callbacks (like music auto-advance) may create NEW handles.
        We reset self.sounds_playing first so new handles are preserved.
        """

        # Take a snapshot of the current handles
        old_handles = list(self.sounds_playing)

        # Start a fresh list; callbacks may append new handles to this.
        self.sounds_playing = []
        survivors = self.sounds_playing

        for handle in old_handles:
            # print("[audio.py] on_audio_end() sound playing", handle.identity)
            if handle.is_playing():
                survivors.append(handle)
            else:
                # Just ended: call its callback if any
                cb = handle.on_end_cb
                if cb is not None:
                    try:
                        print("[audio.py] on_end_cb() for=", handle.identity)
                        cb()
                    except Exception as e:
                        print("[audio.py] Error during on_end_cb:", e)
        # No reassignment needed; survivors *is* self.sounds_playing

    def find_by_identity(self, identity: str) -> list[AudioHandle]:
        return [h for h in self.sounds_playing if h.identity == identity]

    def find_by_channel_index(self, idx: int) -> AudioHandle | None:
        ch = self.channels[idx]
        for h in self.sounds_playing:
            if h.channel is ch:
                return h
        return None

    def stop_all(self):
        """Stop everything playing."""
        pygame.mixer.stop()

    def stop_all_but(self, channel_id_to_ignore=-1):
        """Stop every channel EXCEPT the one passed in."""

        if channel_id_to_ignore == -1:
            return
        
        channel_to_ignore = self.channels[channel_id_to_ignore]
        if channel_to_ignore is None:
            return        
        
        for ch in self.channels:
            if ch is channel_to_ignore:
                continue
            ch.stop()

