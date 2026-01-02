import tkinter as tk
import ttkbootstrap as ttk
from gui.widgets import Tooltip

FONT_FAMILY = "Segoe UI"

class BaseToolFrame(ttk.Frame):
    def __init__(self, parent, controller, title, **kwargs):
        """Sets the general layout of each section/page."""
        
        super().__init__(parent, **kwargs)
        self.controller = controller
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        header_frame = ttk.Frame(self, padding=(10, 10))
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)
        
        self.back_button = ttk.Button(header_frame, text="‹ Main Menu", bootstyle="light", command=lambda: controller.show_frame("MainMenuFrame"))
        self.back_button.grid(row=0, column=0, sticky="w")
        Tooltip(self.back_button, "Return to the main tool selection menu.")
        
        self.title_label = ttk.Label(header_frame, text=title, font=(FONT_FAMILY, 18, "bold"))
        self.title_label.grid(row=1, column=0, sticky="w", pady=(10, 0))

        self.content_frame = ttk.Frame(self, padding=(20, 10))
        self.content_frame.grid(row=1, column=0, sticky="nsew")