import tkinter as tk
import ttkbootstrap as ttk
from tkinter import filedialog, messagebox
import threading
import os
from gui.base import BaseToolFrame
from gui.widgets import Tooltip
# Import the logic function directly from the internal module
from modules.smrf_logic import run_smrf_workflow

class LocalSMRFFrame(BaseToolFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Local SMRF")
        self.is_processing = False

        # --- Input Variables ---
        self.input_cloud_var = tk.StringVar()
        self.input_polygon_var = tk.StringVar()
        
        # --- SMRF Parameter Variables ---
        self.slope_var = tk.StringVar(value="0.05")
        self.threshold_var = tk.StringVar(value="0.1")
        self.cell_var = tk.StringVar(value="1.0")
        self.window_var = tk.StringVar(value="9")
        
        self.create_widgets()

        # --- Trace variables to update run button state ---
        self.input_cloud_var.trace_add("write", self._check_run_button_state)
        self.input_polygon_var.trace_add("write", self._check_run_button_state)

    def create_widgets(self):
        self.content_frame.grid_columnconfigure(0, weight=1)

        # --- 1. Input Files ---
        io_settings = ttk.Labelframe(self.content_frame, text="1. Input Files", padding=15, style="Info.TLabelframe")
        io_settings.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        io_settings.columnconfigure(1, weight=1)

        # Input Cloud
        ttk.Label(io_settings, text="Input Cloud (.laz/.las):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        cloud_frame = ttk.Frame(io_settings)
        cloud_frame.grid(row=0, column=1, sticky="ew")
        cloud_frame.columnconfigure(0, weight=1)
        cloud_entry = ttk.Entry(cloud_frame, textvariable=self.input_cloud_var)
        cloud_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        Tooltip(cloud_entry, "Select the input point cloud file (.laz or .las).")
        cloud_btn = ttk.Button(cloud_frame, text="Browse...", command=self.browse_cloud, bootstyle="secondary")
        cloud_btn.grid(row=0, column=1, padx=(5, 0))
        
        # Input Polygon
        ttk.Label(io_settings, text="Input Polygon (.shp):").grid(row=1, column=0, sticky="w", padx=5, pady=(10, 5))
        poly_frame = ttk.Frame(io_settings)
        poly_frame.grid(row=1, column=1, sticky="ew", pady=(10, 0))
        poly_frame.columnconfigure(0, weight=1)
        poly_entry = ttk.Entry(poly_frame, textvariable=self.input_polygon_var)
        poly_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        Tooltip(poly_entry, "Select the input shapefile polygon for clipping and classification.")
        poly_btn = ttk.Button(poly_frame, text="Browse...", command=self.browse_polygon, bootstyle="secondary")
        poly_btn.grid(row=0, column=1, padx=(5, 0))

        # --- 2. SMRF Parameters ---
        smrf_settings = ttk.Labelframe(self.content_frame, text="2. SMRF Parameters", padding=15, style="Info.TLabelframe")
        smrf_settings.grid(row=1, column=0, sticky="ew", pady=10)
        smrf_settings.columnconfigure((1, 3), weight=1)

        ttk.Label(smrf_settings, text="Slope:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        slope_entry = ttk.Entry(smrf_settings, textvariable=self.slope_var, width=10)
        slope_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        Tooltip(slope_entry, "SMRF Slope (e.g., 0.05)")

        ttk.Label(smrf_settings, text="Threshold:").grid(row=0, column=2, sticky="w", padx=15, pady=5)
        thresh_entry = ttk.Entry(smrf_settings, textvariable=self.threshold_var, width=10)
        thresh_entry.grid(row=0, column=3, sticky="ew", padx=5, pady=5)
        Tooltip(thresh_entry, "SMRF Threshold (e.g., 0.1)")

        ttk.Label(smrf_settings, text="Cell Size:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        cell_entry = ttk.Entry(smrf_settings, textvariable=self.cell_var, width=10)
        cell_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        Tooltip(cell_entry, "SMRF Cell size (e.g., 1.0)")

        ttk.Label(smrf_settings, text="Window Size:").grid(row=1, column=2, sticky="w", padx=15, pady=5)
        window_entry = ttk.Entry(smrf_settings, textvariable=self.window_var, width=10)
        window_entry.grid(row=1, column=3, sticky="ew", padx=5, pady=5)
        Tooltip(window_entry, "SMRF Window Size (e.g., 9 or 145)")

        # --- 3. Run Process ---
        run_frame = ttk.Labelframe(self.content_frame, text="3. Run Process", padding=10, style="Info.TLabelframe")
        run_frame.grid(row=2, column=0, sticky="ew", pady=10)
        run_container = ttk.Frame(run_frame)
        run_container.pack(anchor="w")
        
        self.run_button = ttk.Button(run_container, text="Run Local SMRF", command=self.start_processing_thread, bootstyle="primary", state="disabled")
        self.run_button.pack(side="left", padx=(0, 10))
        Tooltip(self.run_button, "Execute the full inside/outside SMRF classification script.")
        
        self.progress = ttk.Progressbar(run_container, orient="horizontal", length=300, mode="determinate", bootstyle="primary")
        self.progress.pack(side="left")

        # --- 4. Reset/Stop ---
        reset_frame = ttk.Frame(self.content_frame)
        reset_frame.grid(row=3, column=0, sticky="e", pady=(10,0))
        
        self.stop_button = ttk.Button(reset_frame, text="Stop Process", command=lambda: self.controller.terminate_frame_process(self), bootstyle="secondary", state="disabled")
        self.stop_button.pack(side="left", padx=(0, 5))
        Tooltip(self.stop_button, "Forcefully stop the current running process.")

        reset_btn = ttk.Button(reset_frame, text="Reset All", command=self.reset_ui, bootstyle="secondary-outline")
        reset_btn.pack(side="left")
        Tooltip(reset_btn, "Clear all inputs and selections in this tool.")

    def browse_cloud(self):
        path = filedialog.askopenfilename(filetypes=[("Lidar Files", "*.laz *.las"), ("All files", "*.*")])
        if path:
            self.input_cloud_var.set(path)

    def browse_polygon(self):
        path = filedialog.askopenfilename(filetypes=[("Shapefiles", "*.shp"), ("All files", "*.*")])
        if path:
            self.input_polygon_var.set(path)

    def reset_ui(self):
        self.input_cloud_var.set("")
        self.input_polygon_var.set("")
        self.slope_var.set("0.05")
        self.threshold_var.set("0.1")
        self.cell_var.set("1.0")
        self.window_var.set("9")
        self.controller.log_frame.log("Local SMRF tool has been reset.")
        self._check_run_button_state()

    def _check_run_button_state(self, *args):
        if self.is_processing:
            return
        files_ok = os.path.isfile(self.input_cloud_var.get()) and os.path.isfile(self.input_polygon_var.get())
        self.run_button.config(state="normal" if files_ok else "disabled")

    def set_processing_state(self, is_processing):
        self.is_processing = is_processing
        if is_processing:
            self.run_button.config(text="Processing...", state="disabled")
            self.progress.config(mode="indeterminate")
            self.progress.start()
            self.stop_button.config(state="normal")
        else:
            self.run_button.config(text="Run Local SMRF")
            self.progress.stop()
            self.progress.config(mode="determinate", value=0)
            self._check_run_button_state()
            self.stop_button.config(state="disabled")

    def start_processing_thread(self):
        if self.is_processing:
            return
            
        # --- Validation ---
        try:
            float(self.slope_var.get())
            float(self.threshold_var.get())
            float(self.cell_var.get())
            int(self.window_var.get())
        except ValueError as e:
            messagebox.showerror("Invalid Parameter", f"One of the SMRF parameters is not a valid number.\n\n{e}")
            return
            
        self.set_processing_state(True)
        self.controller.log_frame.log(f"\n{'='*20}\n--- [Local SMRF] Starting Process ---\n{'='*20}")
        
        # Start the logic in a thread
        threading.Thread(target=self.run_local_smrf_logic, daemon=True, name="LocalSMRF").start()

    def on_process_complete(self, is_success, message):
        """Handles UI updates after the process is complete."""
        self.set_processing_state(False)
        if is_success:
            messagebox.showinfo("Success", message)
        elif message and not self.controller.was_terminated:
            messagebox.showerror("Error", message)
        self.controller.was_terminated = False # Reset flag

    def run_local_smrf_logic(self):
        is_success = False
        message = ""
        try:
            # --- 1. Get all inputs ---
            input_cloud = self.input_cloud_var.get()
            input_polygon = self.input_polygon_var.get()
            
            slope = float(self.slope_var.get())
            threshold = float(self.threshold_var.get())
            cell = float(self.cell_var.get())
            window = int(self.window_var.get())
            
            # Get executable paths from controller/config
            pdal_exe = self.controller.pdal_path_var.get() or "pdal"
            pdal_wrench_exe = self.controller.pdal_wrench_path_var.get() or "pdal_wrench"
            
            # --- 2. Run the imported workflow ---
            # We pass the controller's log function as the callback so the logic can print to the GUI
            final_output = run_smrf_workflow(
                input_cloud, input_polygon, slope, threshold, cell, window,
                pdal_exe, pdal_wrench_exe,
                log_callback=self.controller.log_frame.log
            )
            
            is_success = True
            message = f"Local SMRF processing complete!\nOutput: {os.path.basename(final_output)}"
            
        except Exception as e:
            if not self.controller.was_terminated:
                message = f"An error occurred: {e}"
            is_success = False
        finally:
            self.after(0, self.on_process_complete, is_success, message)