# system.py
from __future__ import annotations

import threading
import pygame


def ask_yes_no(
    engine,
    *,
    title: str = "Confirm",
    message: str = "Are you sure?",
    pcallback=None,
    ncallback=None,
) -> bool:
    """Blocking Yes/No dialog (Tk) that safely pauses pygame input and restores focus."""
    _ensure_main_thread(engine)

    _begin_modal(engine)

    result: bool = False
    root = None
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        try:
            root.update_idletasks()
            root.update()
        except Exception:
            pass

        result = bool(messagebox.askyesno(title, message, parent=root))

        if result:
            if callable(pcallback):
                pcallback(result)
        else:
            if callable(ncallback):
                ncallback(result)

        return result

    finally:
        try:
            if root is not None:
                root.destroy()
        except Exception:
            pass

        _end_modal(engine)


def ask_ok_cancel(
    engine,
    *,
    title: str = "Confirm",
    message: str = "Continue?",
    pcallback=None,
    ncallback=None,
) -> bool:
    """Blocking OK/Cancel dialog (Tk). Returns True for OK, False for Cancel."""
    _ensure_main_thread(engine)

    _begin_modal(engine)

    result: bool = False
    root = None
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        try:
            root.update_idletasks()
            root.update()
        except Exception:
            pass

        result = bool(messagebox.askokcancel(title, message, parent=root))

        if result:
            if callable(pcallback):
                pcallback(result)
        else:
            if callable(ncallback):
                ncallback(result)

        return result

    finally:
        try:
            if root is not None:
                root.destroy()
        except Exception:
            pass

        _end_modal(engine)


# -------------------------
# Internal helpers
# -------------------------

def _ensure_main_thread(engine) -> None:
    # If you stored _main_thread_id on engine, enforce it
    main_id = getattr(engine, "_main_thread_id", None)
    if main_id is not None and threading.get_ident() != main_id:
        raise RuntimeError("Tk prompts must be called from the main pygame thread")


def _begin_modal(engine) -> None:
    engine.mouse_input_blocked = True
    engine.key_input_blocked = True
    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)


def _end_modal(engine) -> None:
    # Flush any clicks/keys that happened while dialog was up
    pygame.event.clear([
        pygame.MOUSEMOTION,
        pygame.MOUSEBUTTONDOWN,
        pygame.MOUSEBUTTONUP,
        pygame.KEYDOWN,
        pygame.KEYUP,
        pygame.TEXTINPUT,
        pygame.MOUSEWHEEL,
    ])

    # Bring focus back to pygame window
    if hasattr(engine, "refocus_pygame"):
        engine.refocus_pygame()

    # Prevent huge dt spike after blocking dialog
    try:
        engine.clock.tick()
        engine._skip_dt_frames = 2
    except Exception:
        pass

    # Restore input & cursor
    engine.mouse_input_blocked = False
    engine.key_input_blocked = False
    if hasattr(engine, "show_cursor"):
        engine.show_cursor(inputBlocked=False)
