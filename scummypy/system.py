import tkinter as tk
from tkinter import simpledialog
from tkinter import commondialog
from tkinter import messagebox

class InputDialog(simpledialog.Dialog):
    def __init__(self, parent, title: str, message: str):
        self.message = message
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        # Make window non-resizable and, on Windows, remove max/min
        self.resizable(False, False)
        try:
            self.attributes("-toolwindow", True)  # Windows-only hint
        except tk.TclError:
            pass

        label = tk.Label(master, text=self.message)
        label.pack(padx=10, pady=(10, 5))

        self.entry_var = tk.StringVar()
        entry = tk.Entry(master, textvariable=self.entry_var)
        entry.pack(padx=10, pady=(0, 10))

        return entry  # initial focus

    def apply(self):
        self.result = self.entry_var.get()
