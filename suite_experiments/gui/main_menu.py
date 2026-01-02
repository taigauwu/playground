import tkinter as tk
import ttkbootstrap as ttk
from gui.widgets import Tooltip

FONT_FAMILY = "Segoe UI"

class MainMenuFrame(ttk.Frame):
    def __init__(self, parent, controller):
        """The main menu of the app"""
        super().__init__(parent)
        self.controller = controller
        
        self.grid_columnconfigure((0, 2), weight=1)
        self.grid_rowconfigure((0, 2), weight=1)

        content_container = ttk.Frame(self)
        content_container.grid(row=1, column=1, sticky='') 

        title = ttk.Label(content_container, text="LiDAR Utility Suite v2.2.3", font=(FONT_FAMILY, 24, "bold"))
        title.pack(pady=(20, 30), padx=50)

        # --- Grouped Button Layout ---
        button_container = ttk.Frame(content_container)
        button_container.pack(padx=10, pady=(0, 20), fill='x', expand=True)
        button_container.grid_columnconfigure((0, 1), weight=1, uniform="group1")

        groups = {
            "Download Tools": [
                {'text': "Dataset Downloader", 'frame': "DownloaderFrame", 'title': "Dataset Downloader"},
                {'text': "7-parameter CSV Generator", 'frame': "GCPTransformFrame", 'title': "DJI Terra 7-parameter CSV Generator"},
            ],
            "Georeferencing Tools": [
                {'text': "Scaling", 'frame': "ScaleToolFrame", 'title': "Scale Point Cloud"},
                {'text': "Georeferencing", 'frame': "GeoreferenceFrame", 'title': "Georeference Point Cloud"},
                {'text': "Assign/Update Header", 'frame': "HeaderToolFrame", 'title': "Assign/Update Point Cloud Header"},
            ],
            "Classification": [
                {'text': "PDAL", 'frame': "ClassificationFrame", 'sub_frame': "PipelineClassificationFrame", 'title': "PDAL Point Cloud Classification"},
                {'text': "FLAI", 'frame': "ClassificationFrame", 'sub_frame': "FlaiFrame", 'title': "FLAI Point Cloud Classification"},
                {'text': "Class Assign Reclassification", 'frame': "ClassificationFrame", 'sub_frame': "ManualReclassFrame", 'title': "Class Assign from Polygon Reclassification"},
                {'text': "Local SMRF", 'frame': "LocalSMRFFrame", 'title': "Local SMRF"},
            ],
            "Miscellaneous": [
                {'text': "LAS2LAS Utility", 'frame': "Las2lasFrame", 'title': "LAS2LAS Point Cloud Utility"},
                {'text': "Split/Merge Tiles", 'frame': "SplitMergeFrame", 'title': "Split/Merge Point Cloud Tiles"},
                {'text': "DSM & Stat Map Generator", 'frame': "DsmMapToolFrame", 'title': "DSM & Stat Map Generator"},
                {'text': "Rough Ortho Generator", 'frame': "RoughOrthoFrame", 'title': "Rough Ortho Generator"},
                {'text': "RTKLib Utilities", 'frame': "GNSSFrame", 'title': "GNSS Utilities (RTKLib)"},
            ]    
        }

        # Define the grid position for each group title
        grid_positions = {
            "Download Tools": (0, 0),
            "Georeferencing Tools": (0, 1),
            "GNSS Tools": (0, 2),
            "Classification": (1, 0),
            "Miscellaneous": (1, 1)
        }

        for group_title, buttons in groups.items():
            row, col = grid_positions[group_title]
            
            labelframe = ttk.Labelframe(button_container, text=group_title, padding=(15, 10), style="Info.TLabelframe")
            labelframe.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)
            
            # --- Centering Logic ---
            labelframe.grid_rowconfigure(0, weight=1)
            labelframe.grid_rowconfigure(2, weight=1)
            labelframe.grid_columnconfigure(0, weight=1)
            button_inner_container = ttk.Frame(labelframe)
            button_inner_container.grid(row=1, column=0)

            for button_info in buttons:
                command = None
                if 'sub_frame' in button_info:
                    command = lambda bi=button_info: controller.show_sub_frame(
                        bi['frame'],
                        bi['sub_frame'],
                        bi['title']
                    )
                else:
                    command = lambda bi=button_info: controller.show_frame(
                        bi['frame'],
                        bi['title']
                    )
                
                btn = ttk.Button(
                    button_inner_container,
                    text=button_info['text'],
                    bootstyle="secondary",
                    command=command
                )
                btn.pack(pady=6, ipady=8, fill='x')
                Tooltip(btn, f"Open the '{button_info['title']}' tool.")

        footer_frame = ttk.Frame(content_container)
        footer_frame.pack(fill='x', pady=(40, 0), padx=50)
        footer_frame.grid_columnconfigure(1, weight=1)

        self.theme_toggle = ttk.Checkbutton(
            footer_frame,
            variable=self.controller.theme_is_dark,
            command=self._on_theme_toggle,
            bootstyle="round-toggle"
        )
        self.theme_toggle.grid(row=0, column=0, sticky='w')
        self._update_toggle_text()
        Tooltip(self.theme_toggle, "Toggle between light and dark visual themes for the application.")

        self.settings_button = ttk.Button(
            footer_frame,
            text="⚙️ Configuration Settings",
            bootstyle="light",
            command=lambda: self.controller.show_frame("ConfigurationSettingsFrame", "Configuration Settings")
        )
        self.settings_button.grid(row=0, column=2, sticky='e')
        
        Tooltip(self.settings_button, "Configure paths to external tools (LAStools, FLAI) and change the application theme.")

    def _on_theme_toggle(self):
        self.controller.toggle_theme()
        self._update_toggle_text()

    def _update_toggle_text(self):
        if self.controller.theme_is_dark.get():
            self.theme_toggle.config(text="Dark Mode 🌙") 
        else:
            self.theme_toggle.config(text="Light Mode ☀️")