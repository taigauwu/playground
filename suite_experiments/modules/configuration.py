import tkinter as tk
import ttkbootstrap as ttk
from tkinter import filedialog, messagebox, scrolledtext
import webbrowser
import sys
from gui.base import BaseToolFrame
from gui.widgets import Tooltip

class ConfigurationSettingsFrame(BaseToolFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Configuration Settings")
        
        # Local variables to hold changes before saving
        self.theme_is_dark_local = tk.BooleanVar(value=self.controller.theme_is_dark.get())
        self.lastools_path_local = tk.StringVar(value=self.controller.lastools_path_var.get())
        self.classify_lidar_bat_path_local = tk.StringVar(value=self.controller.classify_lidar_bat_path_var.get())
        self.downloader_dest_path_local = tk.StringVar(value=self.controller.downloader_dest_path_var.get())
        self.pdal_path_local = tk.StringVar(value=self.controller.pdal_path_var.get())
        self.pdal_wrench_path_local = tk.StringVar(value=self.controller.pdal_wrench_path_var.get())
        self.rtklib_path_local = tk.StringVar(value=self.controller.rtklib_path_var.get())

        self.create_widgets()

    def create_widgets(self):
        self.content_frame.grid_columnconfigure(0, weight=1)

        # --- Theme Settings ---
        theme_frame = ttk.Labelframe(self.content_frame, text="Theme", padding=15, style="Info.TLabelframe")
        theme_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        self.theme_toggle = ttk.Checkbutton(
            theme_frame, variable=self.theme_is_dark_local,
            command=self._update_toggle_text, bootstyle="round-toggle"
        )
        self.theme_toggle.pack(side='left')
        self._update_toggle_text()

        # --- LAStools Settings ---
        lastools_frame = ttk.Labelframe(self.content_frame, text="LAStools", padding=15, style="Info.TLabelframe")
        lastools_frame.grid(row=1, column=0, sticky="ew", pady=10)
        lastools_frame.columnconfigure(1, weight=1)
        ttk.Label(lastools_frame, text="Bin Folder:").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        lastools_entry = ttk.Entry(lastools_frame, textvariable=self.lastools_path_local, width=50)
        lastools_entry.grid(row=0, column=1, sticky="ew")
        Tooltip(lastools_entry, "Path to the 'bin' directory inside your LAStools installation folder (e.g., C:\\LAStools\\bin).")
        ttk.Button(lastools_frame, text="Browse...", command=lambda: self.browse_path(self.lastools_path_local, False), bootstyle="secondary").grid(row=0, column=2, padx=(10, 0))

        # --- FLAI Settings ---
        flai_frame = ttk.Labelframe(self.content_frame, text="FLAI", padding=15, style="Info.TLabelframe")
        flai_frame.grid(row=2, column=0, sticky="ew", pady=10)
        flai_frame.columnconfigure(1, weight=1)
        ttk.Label(flai_frame, text="Batch File:").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        flai_entry = ttk.Entry(flai_frame, textvariable=self.classify_lidar_bat_path_local, width=50)
        flai_entry.grid(row=0, column=1, sticky="ew")
        Tooltip(flai_entry, "Path to the 'classify_lidar.bat' file used to run the FLAI classification tool.")
        ttk.Button(flai_frame, text="Browse...", command=lambda: self.browse_path(self.classify_lidar_bat_path_local, True), bootstyle="secondary").grid(row=0, column=2, padx=(10, 0))

        # --- PDAL Settings ---
        pdal_frame = ttk.Labelframe(self.content_frame, text="PDAL", padding=15, style="Info.TLabelframe")
        pdal_frame.grid(row=3, column=0, sticky="ew", pady=10)
        pdal_frame.columnconfigure(1, weight=1)
        
        ttk.Label(pdal_frame, text="PDAL Exe:").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        pdal_entry = ttk.Entry(pdal_frame, textvariable=self.pdal_path_local, width=50)
        pdal_entry.grid(row=0, column=1, sticky="ew")
        Tooltip(pdal_entry, "Path to the 'pdal.exe' executable or just 'pdal' if in PATH.")
        ttk.Button(pdal_frame, text="Browse...", command=lambda: self.browse_path(self.pdal_path_local, True, is_exe=True), bootstyle="secondary").grid(row=0, column=2, padx=(10, 0))

        ttk.Label(pdal_frame, text="Wrench Exe:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        pdal_wrench_entry = ttk.Entry(pdal_frame, textvariable=self.pdal_wrench_path_local, width=50)
        pdal_wrench_entry.grid(row=1, column=1, sticky="ew")
        Tooltip(pdal_wrench_entry, "Path to the 'pdal_wrench.exe' executable or just 'pdal_wrench' if in PATH.")
        ttk.Button(pdal_frame, text="Browse...", command=lambda: self.browse_path(self.pdal_wrench_path_local, True, is_exe=True), bootstyle="secondary").grid(row=1, column=2, padx=(10, 0))

        # --- Downloader Settings ---
        downloader_frame = ttk.Labelframe(self.content_frame, text="Dataset Downloader", padding=15, style="Info.TLabelframe")
        downloader_frame.grid(row=4, column=0, sticky="ew", pady=10)
        downloader_frame.columnconfigure(1, weight=1)
        ttk.Label(downloader_frame, text="Data Folder:").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        downloader_entry = ttk.Entry(downloader_frame, textvariable=self.downloader_dest_path_local, width=50)
        downloader_entry.grid(row=0, column=1, sticky="ew")
        Tooltip(downloader_entry, "The default directory where datasets will be downloaded.")
        ttk.Button(downloader_frame, text="Browse...", command=lambda: self.browse_path(self.downloader_dest_path_local, False), bootstyle="secondary").grid(row=0, column=2, padx=(10, 0))
        
        # --- RTKLib Settings ---
        rtk_frame = ttk.Labelframe(self.content_frame, text="RTKLib (demo5)", padding=15, style="Info.TLabelframe")
        rtk_frame.grid(row=5, column=0, sticky="ew", pady=10)
        rtk_frame.columnconfigure(1, weight=1)
        ttk.Label(rtk_frame, text="Bin Folder:").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        rtk_entry = ttk.Entry(rtk_frame, textvariable=self.rtklib_path_local, width=50)
        rtk_entry.grid(row=0, column=1, sticky="ew")
        Tooltip(rtk_entry, "Path to the 'bin' directory of RTKLib (containing convbin.exe, rtkplot.exe, etc.).")
        ttk.Button(rtk_frame, text="Browse...", command=lambda: self.browse_path(self.rtklib_path_local, False), bootstyle="secondary").grid(row=0, column=2, padx=(10, 0))

        # --- Action Buttons ---
        action_frame = ttk.Frame(self.content_frame)
        action_frame.grid(row=6, column=0, sticky="ew", pady=20)
        action_frame.grid_columnconfigure(0, weight=1)
        action_frame.grid_columnconfigure(2, weight=1)
        
        button_container = ttk.Frame(action_frame)
        button_container.grid(row=0, column=1)
        
        save_btn = ttk.Button(button_container, text="Save and Exit", command=self.save_and_exit, bootstyle="primary")
        save_btn.pack(side="left", padx=(0, 5))
        Tooltip(save_btn, "Save the current settings to config.json and return to the main menu.")
        about_button = ttk.Button(button_container, text="About", command=self.show_about_dialog, bootstyle="info-outline")
        about_button.pack(side="left", padx=(5, 0))
        Tooltip(about_button, "Show application details and documentation links.")

    def show_about_dialog(self):
        about_window = tk.Toplevel(self)
        about_window.title("About Lidar Utility Suite")
        about_window.transient(self)
        about_window.grab_set()
        
        # Simple about text since __doc__ might not be available in the same way
        about_text = """
        Lidar Utility Suite v2.2.3
        
        A combined GUI for Point Cloud Utilities.
        
        Functionalities:
        1. Configuration Settings
        2. Dataset Downloader
        3. FLAI Classification
        4. GCP CSV Transformation
        5. Georeferencing
        6. Header Assignment
        7. Las2las Utility
        8. PDAL Classification Pipeline
        9. Point Cloud Scaling
        10. Split & Merge
        """
        
        container = ttk.Frame(about_window, padding=20)
        container.pack(fill="both", expand=True)
        text_widget = scrolledtext.ScrolledText(container, wrap=tk.WORD, height=15, width=60)
        text_widget.insert(tk.END, about_text)
        text_widget.config(state="disabled")
        text_widget.pack(pady=(0, 15), fill="both", expand=True)
        
        link_frame = ttk.Frame(container)
        link_frame.pack()
        ttk.Label(link_frame, text="For more details, visit the guide:").pack(side="left")
        manual_link = ttk.Label(link_frame, text="Guide/Manual Link", foreground="blue", cursor="hand2")
        manual_link.pack(side="left", padx=5)
        manual_link.bind("<Button-1>", lambda e: webbrowser.open("https://coda.io/d/Lidar_dRjeI0n92t3/Lidar-Point-Cloud-Utility-Suite_suX8oekO#_luPHeDFC"))
        
        ttk.Button(container, text="OK", command=about_window.destroy, bootstyle="primary").pack(pady=(15, 0))
        
        # Center the dialog
        self.update_idletasks()
        app_width, app_height = self.winfo_width(), self.winfo_height()
        app_x, app_y = self.winfo_rootx(), self.winfo_rooty()
        dialog_width, dialog_height = about_window.winfo_width(), about_window.winfo_height()
        x = app_x + (app_width // 2) - (dialog_width // 2)
        y = app_y + (app_height // 2) - (dialog_height // 2)
        about_window.geometry(f"+{x}+{y}")

    def _update_toggle_text(self):
        if self.theme_is_dark_local.get():
            self.theme_toggle.config(text="Dark Mode 🌙") 
        else:
            self.theme_toggle.config(text="Light Mode ☀️")

    def browse_path(self, var, is_file, is_exe=False):
        if is_file:
            if is_exe:
                filetypes = [("Executable files", "*.exe"), ("Batch files", "*.bat"), ("All files", "*.*")]
            else:
                filetypes = [("Batch files", "*.bat"), ("All files", "*.*")]
            path = filedialog.askopenfilename(filetypes=filetypes)
        else:
            path = filedialog.askdirectory()
        if path:
            var.set(path)

    def save_and_exit(self):
        # Update the global variables in the controller
        self.controller.theme_is_dark.set(self.theme_is_dark_local.get())
        self.controller.lastools_path_var.set(self.lastools_path_local.get())
        self.controller.classify_lidar_bat_path_var.set(self.classify_lidar_bat_path_local.get())
        self.controller.downloader_dest_path_var.set(self.downloader_dest_path_local.get())
        self.controller.pdal_path_var.set(self.pdal_path_local.get())
        self.controller.pdal_wrench_path_var.set(self.pdal_wrench_path_local.get())
        self.controller.rtklib_path_var.set(self.rtklib_path_local.get())
        
        # Trigger the theme change immediately
        self.controller.toggle_theme() 
        
        # Save to JSON
        self.controller.save_config()
        
        messagebox.showinfo("Settings Saved", "Your configuration has been saved.")
        self.controller.show_frame("MainMenuFrame")