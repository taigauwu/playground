import tkinter as tk
import ttkbootstrap as ttk
import sys
import subprocess

# Import Core Logic
from core.config import load_settings, save_settings

# Import GUI Components
from gui.main_menu import MainMenuFrame
from gui.widgets import OperationLogFrame

# Import Modules
# We import these directly now that the files exist.
from modules.georeference import GeoreferenceFrame
from modules.header import HeaderToolFrame
from modules.scaling import ScaleToolFrame
from modules.split_merge import SplitMergeFrame
from modules.classification import ClassificationFrame
from modules.configuration import ConfigurationSettingsFrame
from modules.gcp import GCPTransformFrame
from modules.las2las import Las2lasFrame
from modules.downloader import DownloaderFrame
from modules.local_smrf import LocalSMRFFrame 
from modules.dsm_viz import DsmMapToolFrame
from modules.rough_ortho import RoughOrthoFrame
from modules.ppk import GNSSFrame

FONT_FAMILY = "Segoe UI"

class App(ttk.Window):
    def __init__(self):
        super().__init__(themename="solar")
        
        # --- Application State ---
        self.theme_name_var = tk.StringVar()
        self.theme_is_dark = tk.BooleanVar()
        
        # Paths
        self.lastools_path_var = tk.StringVar()
        self.classify_lidar_bat_path_var = tk.StringVar()
        self.downloader_dest_path_var = tk.StringVar()
        self.pdal_path_var = tk.StringVar()
        self.pdal_wrench_path_var = tk.StringVar()
        self.rtklib_path_var = tk.StringVar()
        
        # Process Management
        self.running_processes = {}
        self.was_terminated = False

        # --- Setup UI ---
        self.title("LiDAR Utility Suite v2.2.3")
        self.current_tool_frame = None
        self.style.configure('TLabelframe.Label', font=(FONT_FAMILY, 11, "bold"))
        
        # Load Configuration
        self.load_preferences() 
        self.style.theme_use(self.theme_name_var.get())

        # Event Bindings
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Grid Layout
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # --- Initialize Frames ---
        self.frames = {}
        
        # List of all Frame classes to instantiate
        frame_classes = [
            MainMenuFrame, 
            GeoreferenceFrame, 
            HeaderToolFrame, 
            ScaleToolFrame, 
            SplitMergeFrame, 
            ClassificationFrame, 
            ConfigurationSettingsFrame, 
            GCPTransformFrame, 
            Las2lasFrame, 
            DownloaderFrame,
            DsmMapToolFrame,
            RoughOrthoFrame,
            GNSSFrame,
            LocalSMRFFrame
        ]

        for F in frame_classes:
            frame = F(parent=self, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # --- Operation Log ---
        self.log_frame_container = ttk.Frame(self)
        self.log_frame_container.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.log_frame = OperationLogFrame(self.log_frame_container, self)
        self.log_frame.pack(fill="x", expand=True)
        self.log_frame_container.grid_remove()
        
        # Start on Main Menu
        self.show_frame("MainMenuFrame")

    def toggle_theme(self):
        """Switches between the light ('yeti') and dark ('solar') themes."""
        if self.theme_is_dark.get():
            self.theme_name_var.set("solar")
        else:
            self.theme_name_var.set("yeti")
        
        self.style.theme_use(self.theme_name_var.get())
        self.save_config()

    def load_preferences(self):
        """Loads saved user settings using the core config module"""
        config = load_settings()
        
        self.lastools_path_var.set(config["lastools_path"])
        self.classify_lidar_bat_path_var.set(config["classify_lidar_bat_path"])
        self.downloader_dest_path_var.set(config["downloader_dest_path"])
        self.theme_name_var.set(config["theme_name"])
        self.pdal_path_var.set(config.get("pdal_path", ""))
        self.pdal_wrench_path_var.set(config.get("pdal_wrench_path", ""))
        self.rtklib_path_var.set(config.get("rtklib_path", ""))
        
        self.theme_is_dark.set(self.theme_name_var.get() == "solar")

    def save_config(self):
        """Saves the current settings using the core config module"""
        config_data = {
            "lastools_path": self.lastools_path_var.get(),
            "classify_lidar_bat_path": self.classify_lidar_bat_path_var.get(),
            "downloader_dest_path": self.downloader_dest_path_var.get(),
            "theme_name": self.theme_name_var.get(),
            "pdal_path": self.pdal_path_var.get(),
            "pdal_wrench_path": self.pdal_wrench_path_var.get(),
            "rtklib_path": self.rtklib_path_var.get()
        }
        save_settings(config_data)

    def on_closing(self):
        """Sets the behavior of the app when the application window is closed"""
        self.terminate_all_processes()
        self.save_config()
        self.destroy()

    def _resize_window(self):
        """Sets/resizes the window of each section."""
        if not self.current_tool_frame:
            return

        frame = self.current_tool_frame
        page_name = frame.__class__.__name__

        self.update_idletasks()

        if page_name == "MainMenuFrame":
            width = frame.winfo_reqwidth() + 60
            height = frame.winfo_reqheight() + 40
            self.geometry(f"{width}x{height}")
        elif page_name == "SplitMergeFrame":
            screen_height = self.winfo_screenheight()
            screen_width = self.winfo_screenwidth()
            width = max(frame.winfo_reqwidth() + 40, 850)
            height = screen_height - 100
            x_pos = (screen_width // 2) - (width // 2)
            self.geometry(f"{width}x{height}+{x_pos}+20")
        else:
            width = frame.winfo_reqwidth() + 60
            height = frame.winfo_reqheight() + 80

            if self.log_frame_container.winfo_viewable():
                height += 240

            self.geometry(f"{width}x{height}")

    def show_frame(self, page_name, title=None):
        """Handles the behavior when switching window/section/pages"""
        frame = self.frames[page_name]
        frame.tkraise()
        self.title(title if title else "LiDAR Utility Suite v2.2.3")

        if page_name == "MainMenuFrame":
            self.show_log(False)
        elif self.running_processes:
            self.show_log(True)

        self.update_idletasks() 
        self.current_tool_frame = frame

        self.after(10, self._resize_window)

    def show_sub_frame(self, page_name, sub_frame_class_name, title=None):
        """Shows a parent frame and then a specific tool within it."""
        self.show_frame(page_name, title)
        parent_frame = self.frames.get(page_name)
        if parent_frame and hasattr(parent_frame, 'show_sub_tool'):
            parent_frame.show_sub_tool(sub_frame_class_name, title)

    def show_log(self, show=True):
        """Controls the visibility of the Operation Log Frame at the bottom of the window"""
        is_visible = self.log_frame_container.winfo_viewable()

        if show and not is_visible:
            self.log_frame_container.grid()
        elif not show and is_visible:
            self.log_frame_container.grid_remove()

        self.after(10, self._resize_window)

    def terminate_frame_process(self, frame_instance):
        """Forcefully terminates the process associated with a specific tool frame."""
        process_to_kill = self.running_processes.get(frame_instance)
        if process_to_kill and process_to_kill.poll() is None:
            log = self.log_frame.log
            log("="*20)
            log("--- [SYSTEM] User requested process termination. ---")
            self.was_terminated = True
            try:
                if sys.platform == 'win32':
                    kill_command = ['taskkill', '/F', '/T', '/PID', str(process_to_kill.pid)]
                    subprocess.run(kill_command, check=False, creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    log(f"    > Successfully sent termination signal to process tree with PID: {process_to_kill.pid}")
                else:
                    process_to_kill.terminate()
                    log(f"    > Sent termination signal to process with PID: {process_to_kill.pid}")
                process_to_kill.wait(timeout=2)
            except Exception as e:
                log(f"    > Could not terminate the process cleanly: {e}")
            finally:
                if frame_instance in self.running_processes:
                    del self.running_processes[frame_instance]
                
                # Reset the specific frame's UI
                if hasattr(frame_instance, 'set_processing_state'):
                    frame_instance.set_processing_state(False)
                elif hasattr(frame_instance, 'set_ui_state'):
                    frame_instance.set_ui_state(False)

    def terminate_all_processes(self):
        """Terminates all currently running background processes before exiting."""
        if self.running_processes:
            log = self.log_frame.log
            log("="*20)
            log("--- [SYSTEM] Application closing. Terminating all background processes. ---")
            for frame in list(self.running_processes.keys()):
                self.terminate_frame_process(frame)