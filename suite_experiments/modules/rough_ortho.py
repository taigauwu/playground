import tkinter as tk
import ttkbootstrap as ttk
from tkinter import filedialog, messagebox
import threading
import os
from pathlib import Path

# External dependencies
try:
    import rasterio
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False

from gui.base import BaseToolFrame
from gui.widgets import Tooltip
from core.execution import _execute_pdal_pipeline

class RoughOrthoFrame(BaseToolFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Rough Ortho Generator")
        
        self.input_file_var = tk.StringVar()
        self.folder_path_var = tk.StringVar()
        self.resolution_var = tk.StringVar(value="0.25")
        self.batch_mode = tk.BooleanVar(value=False)
        self.files_list = []
        self.is_processing = False
        
        self.create_widgets()
        self.input_file_var.trace_add("write", self._check_run_state)
        self.folder_path_var.trace_add("write", self._check_run_state)

    def create_widgets(self):
        self.content_frame.grid_columnconfigure(0, weight=1)

        # --- 1. Input Selection ---
        input_frame = ttk.Labelframe(self.content_frame, text="1. Select Input", padding=15, style="Info.TLabelframe")
        input_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)

        # Batch Toggle
        batch_toggle = ttk.Checkbutton(input_frame, text="Batch Mode (Process entire folder)", variable=self.batch_mode, command=self._toggle_input_mode, bootstyle="round-toggle")
        batch_toggle.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        # Single File Input
        self.single_file_frame = ttk.Frame(input_frame)
        self.single_file_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        self.single_file_frame.columnconfigure(1, weight=1)
        ttk.Label(self.single_file_frame, text="Input LAZ File:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        entry = ttk.Entry(self.single_file_frame, textvariable=self.input_file_var, state="readonly")
        entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        btn = ttk.Button(self.single_file_frame, text="Browse...", command=self.browse_file, bootstyle="secondary")
        btn.grid(row=0, column=2, sticky="e")

        # Folder Input
        self.folder_frame = ttk.Frame(input_frame)
        self.folder_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        self.folder_frame.columnconfigure(1, weight=1)
        ttk.Label(self.folder_frame, text="Input Folder:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        folder_entry = ttk.Entry(self.folder_frame, textvariable=self.folder_path_var, state="readonly")
        folder_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        folder_btn = ttk.Button(self.folder_frame, text="Browse...", command=self.browse_folder, bootstyle="secondary")
        folder_btn.grid(row=0, column=2, sticky="e")
        self.folder_frame.grid_remove()

        # --- 2. Parameters ---
        param_frame = ttk.Labelframe(self.content_frame, text="2. Parameters", padding=15, style="Info.TLabelframe")
        param_frame.grid(row=1, column=0, sticky="ew", pady=10)
        
        ttk.Label(param_frame, text="Resolution:").pack(side="left", padx=(0, 10))
        res_entry = ttk.Entry(param_frame, textvariable=self.resolution_var, width=10)
        res_entry.pack(side="left")
        Tooltip(res_entry, "Pixel size in the output GeoTIFF (e.g., 0.25).")

        # --- 3. Run ---
        run_frame = ttk.Labelframe(self.content_frame, text="3. Run Process", padding=10, style="Info.TLabelframe")
        run_frame.grid(row=2, column=0, sticky="ew", pady=10)
        
        self.run_button = ttk.Button(run_frame, text="Generate Rough Ortho", command=self.start_process, bootstyle="primary", state="disabled")
        self.run_button.pack(side="left", padx=(0, 10))
        
        self.progress = ttk.Progressbar(run_frame, orient="horizontal", length=300, mode="determinate", bootstyle="primary")
        self.progress.pack(side="left")

        # --- Footer ---
        reset_frame = ttk.Frame(self.content_frame)
        reset_frame.grid(row=3, column=0, sticky="e", pady=(10,0))
        self.stop_button = ttk.Button(reset_frame, text="Stop Process", command=lambda: self.controller.terminate_frame_process(self), bootstyle="secondary", state="disabled")
        self.stop_button.pack(side="left", padx=(0, 5))
        ttk.Button(reset_frame, text="Reset", command=self.reset_ui, bootstyle="secondary-outline").pack(side="left")

        if not HAS_RASTERIO:
            messagebox.showerror("Missing Dependencies", "Required library 'rasterio' is missing. Please install it to use this tool.")
            self.run_button.config(text="Deps Missing", state="disabled")

    def _toggle_input_mode(self):
        is_batch = self.batch_mode.get()
        self.single_file_frame.grid_remove() if is_batch else self.single_file_frame.grid()
        self.folder_frame.grid() if is_batch else self.folder_frame.grid_remove()
        self._check_run_state()

    def browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("LAZ files", "*.laz *.las")])
        if path: self.input_file_var.set(path)

    def browse_folder(self):
        directory = filedialog.askdirectory()
        if directory:
            files = [os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith(('.laz', '.las'))]
            if files:
                self.files_list = files
                self.folder_path_var.set(f"{len(files)} file(s) found in '{os.path.basename(directory)}'")
            else:
                self.files_list = []
                self.folder_path_var.set("No .laz files found.")
        self._check_run_state()

    def _check_run_state(self, *args):
        if self.is_processing: return
        
        if self.batch_mode.get():
            files_ok = bool(self.files_list)
        else:
            files_ok = os.path.isfile(self.input_file_var.get())
            
        if HAS_RASTERIO and files_ok:
            self.run_button.config(state="normal")
        else:
            self.run_button.config(state="disabled")

    def reset_ui(self):
        self.input_file_var.set("")
        self.folder_path_var.set("")
        self.files_list = []
        self.resolution_var.set("0.25")
        self.batch_mode.set(False)
        self._toggle_input_mode()

    def set_processing_state(self, is_processing):
        self.is_processing = is_processing
        if is_processing:
            self.run_button.config(text="Processing...", state="disabled")
            self.progress.config(mode="indeterminate")
            self.progress.start()
            self.stop_button.config(state="normal")
        else:
            self.run_button.config(text="Generate Rough Ortho")
            self.progress.stop()
            self.progress.config(mode="determinate", value=0)
            self._check_run_state()
            self.stop_button.config(state="disabled")

    def start_process(self):
        if self.is_processing: return
        self.controller.log_frame.log(f"\n{'='*20}\n--- [ROUGH ORTHO] Starting Process ---\n{'='*20}")
        self.set_processing_state(True)
        threading.Thread(target=self.run_logic, daemon=True, name="RoughOrtho").start()

    def on_complete(self, success, message):
        self.set_processing_state(False)
        if success:
            messagebox.showinfo("Success", message)
        elif message and not self.controller.was_terminated:
            messagebox.showerror("Error", message)
        self.controller.was_terminated = False

    def run_logic(self):
        log = self.controller.log_frame.log
        success = False
        msg = ""

        try:
            if self.batch_mode.get():
                files_to_process = self.files_list
            else:
                files_to_process = [self.input_file_var.get()]

            reso = float(self.resolution_var.get())
            total_files = len(files_to_process)
            
            for i, input_path_str in enumerate(files_to_process):
                log(f"\n({i+1}/{total_files}) Processing: {os.path.basename(input_path_str)}")
                
                input_path = Path(input_path_str)
                base_name = input_path.stem
                output_dir = input_path.parent
                
                # Define outputs
                red_tif = output_dir / f"{base_name}_red.tif"
                green_tif = output_dir / f"{base_name}_green.tif"
                blue_tif = output_dir / f"{base_name}_blue.tif"
                final_ortho = output_dir / f"{base_name}_roughortho.tif"

                # 1. Generate Band TIFs using PDAL
                for band_name, out_tif in [("Red", red_tif), ("Green", green_tif), ("Blue", blue_tif)]:
                    pipeline = [
                        str(input_path),
                        {
                            "type": "writers.gdal",
                            "filename": str(out_tif),
                            "resolution": reso,
                            "dimension": band_name,
                            "data_type": "uint16_t",
                            "output_type": "mean",
                            "radius": 0.15
                        }
                    ]
                    _execute_pdal_pipeline(pipeline, self.controller.log_frame, f"  > Extracting {band_name} band...", self.controller, self)

                # 2. Merge into RGB using Rasterio
                log(f"  > Merging bands into {final_ortho.name}...")
                with rasterio.open(red_tif) as src_r:
                    meta = src_r.meta.copy()
                    r_data = src_r.read(1)
                with rasterio.open(green_tif) as src_g:
                    g_data = src_g.read(1)
                with rasterio.open(blue_tif) as src_b:
                    b_data = src_b.read(1)

                meta.update(count=3, driver='GTiff')
                
                with rasterio.open(final_ortho, 'w', **meta) as dst:
                    dst.write(r_data, 1)
                    dst.write(g_data, 2)
                    dst.write(b_data, 3)

                # 3. Cleanup
                log("  > Cleaning up intermediate files...")
                for f in [red_tif, green_tif, blue_tif]:
                    try:
                        os.remove(f)
                    except OSError:
                        pass
                
                log(f"  > Success: {final_ortho.name}")

            success = True
            msg = f"Rough Orthos generated for {total_files} file(s)!"

        except Exception as e:
            if not self.controller.was_terminated:
                log(f"Error: {e}")
                msg = str(e)
        finally:
            self.after(0, self.on_complete, success, msg)