import tkinter as tk
import ttkbootstrap as ttk
from tkinter import filedialog, messagebox
import threading
import os
import json
import tempfile
from pathlib import Path

# External dependencies (wrapped in try/except for safety)
try:
    import pandas as pd
    import laspy
    import rasterio
    import numpy as np
    import matplotlib
    matplotlib.use('Agg') # Force non-interactive backend for GUI safety
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource
    from mpl_toolkits.axes_grid1 import make_axes_locatable
    HAS_DEPS = True
except ImportError as e:
    HAS_DEPS = False
    MISSING_DEP_ERROR = str(e)

from gui.base import BaseToolFrame
from gui.widgets import Tooltip
from core.execution import _execute_pdal_pipeline

class DsmMapToolFrame(BaseToolFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "DSM & Stat Map Generator")
        
        self.input_file_var = tk.StringVar()
        self.unit_var = tk.StringVar(value="Meters")
        self.is_processing = False
        
        self.UNIT_LABELS = {
            "Meters": "Elevation (m)",
            "US Survey Foot": "Elevation (ft (US))",
            "International Foot": "Elevation (ft)"
        }

        self.create_widgets()
        self.input_file_var.trace_add("write", self._check_run_state)
        self.unit_var.trace_add("write", self._check_run_state)

    def create_widgets(self):
        self.content_frame.grid_columnconfigure(0, weight=1)

        # --- 1. Input Selection ---
        input_frame = ttk.Labelframe(self.content_frame, text="1. Select Input", padding=15, style="Info.TLabelframe")
        input_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)

        ttk.Label(input_frame, text="Input LAZ File:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        entry = ttk.Entry(input_frame, textvariable=self.input_file_var, state="readonly")
        entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        btn = ttk.Button(input_frame, text="Browse...", command=self.browse_file, bootstyle="secondary")
        btn.grid(row=0, column=2, sticky="e")

        # --- 2. Parameters ---
        param_frame = ttk.Labelframe(self.content_frame, text="2. Parameters", padding=15, style="Info.TLabelframe")
        param_frame.grid(row=1, column=0, sticky="ew", pady=10)
        
        ttk.Label(param_frame, text="Elevation Unit:").pack(side="left", padx=(0, 10))
        unit_combo = ttk.Combobox(param_frame, textvariable=self.unit_var, values=list(self.UNIT_LABELS.keys()), state="readonly", width=15)
        unit_combo.pack(side="left")
        Tooltip(unit_combo, "Select the unit for the elevation colorbar label.")

        # --- 3. Run ---
        run_frame = ttk.Labelframe(self.content_frame, text="3. Run Process", padding=10, style="Info.TLabelframe")
        run_frame.grid(row=2, column=0, sticky="ew", pady=10)
        
        self.run_button = ttk.Button(run_frame, text="Generate Maps", command=self.start_process, bootstyle="primary", state="disabled")
        self.run_button.pack(side="left", padx=(0, 10))
        
        self.progress = ttk.Progressbar(run_frame, orient="horizontal", length=300, mode="determinate", bootstyle="primary")
        self.progress.pack(side="left")

        # --- Footer ---
        reset_frame = ttk.Frame(self.content_frame)
        reset_frame.grid(row=3, column=0, sticky="e", pady=(10,0))
        self.stop_button = ttk.Button(reset_frame, text="Stop Process", command=lambda: self.controller.terminate_frame_process(self), bootstyle="secondary", state="disabled")
        self.stop_button.pack(side="left", padx=(0, 5))
        ttk.Button(reset_frame, text="Reset", command=self.reset_ui, bootstyle="secondary-outline").pack(side="left")

        if not HAS_DEPS:
            messagebox.showerror("Missing Dependencies", f"Required libraries (laspy, rasterio, matplotlib) are missing.\nError: {MISSING_DEP_ERROR}")
            self.run_button.config(text="Deps Missing", state="disabled")

    def browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("LAZ files", "*.laz")])
        if path: self.input_file_var.set(path)

    def _check_run_state(self, *args):
        if self.is_processing: return
        if HAS_DEPS and os.path.isfile(self.input_file_var.get()) and self.unit_var.get():
            self.run_button.config(state="normal")
        else:
            self.run_button.config(state="disabled")

    def reset_ui(self):
        self.input_file_var.set("")
        self.unit_var.set("Meters")

    def set_processing_state(self, is_processing):
        self.is_processing = is_processing
        if is_processing:
            self.run_button.config(text="Processing...", state="disabled")
            self.progress.config(mode="indeterminate")
            self.progress.start()
            self.stop_button.config(state="normal")
        else:
            self.run_button.config(text="Generate Maps")
            self.progress.stop()
            self.progress.config(mode="determinate", value=0)
            self._check_run_state()
            self.stop_button.config(state="disabled")

    def start_process(self):
        if self.is_processing: return
        self.controller.log_frame.log(f"\n{'='*20}\n--- [MAP GEN] Starting Generation ---\n{'='*20}")
        self.set_processing_state(True)
        threading.Thread(target=self.run_logic, daemon=True, name="Map_Generator").start()

    def on_complete(self, success, message):
        self.set_processing_state(False)
        if success:
            messagebox.showinfo("Success", message)
        elif message and not self.controller.was_terminated:
            messagebox.showerror("Error", message)
        self.controller.was_terminated = False

    # --- Logic Implementation ---

    def run_logic(self):
        log = self.controller.log_frame.log
        laz_path = self.input_file_var.get()
        unit_label = self.UNIT_LABELS[self.unit_var.get()]
        success = False
        msg = ""

        try:
            # 1. Stats
            log("Step 1/4: Calculating Z-statistics...")
            first_bin, last_bin = self._process_laz_stats(laz_path)
            if first_bin is None: raise ValueError("Failed to calculate valid Z-bins from file.")
            
            # 2. PDAL Pipeline
            log(f"Step 2/4: Running PDAL (Filter Z[{first_bin}:{last_bin}])...")
            dsm_path, stat_path = self._run_pdal(laz_path, first_bin, last_bin)
            
            # 3. Relief Map
            log("Step 3/4: Generating Shaded Relief Map...")
            base_name = Path(laz_path).stem
            output_dir = Path(laz_path).parent
            relief_out = output_dir / f"{base_name}_dsm_relief.png"
            self._create_shaded_relief(dsm_path, str(relief_out), unit_label)
            
            # 4. Count Map
            log("Step 4/4: Generating Count Map...")
            count_out = output_dir / f"{base_name}_stat_count.png"
            self._create_count_map(stat_path, str(count_out))
            
            success = True
            msg = f"Maps generated successfully!\n\nOutputs:\n{relief_out.name}\n{count_out.name}"
            log("\n--- Pipeline Complete! ---")

        except Exception as e:
            if not self.controller.was_terminated:
                log(f"Error: {e}")
                msg = str(e)
        finally:
            self.after(0, self.on_complete, success, msg)

    def _process_laz_stats(self, filepath):
        log = self.controller.log_frame.log
        try:
            with laspy.open(filepath, mode='r') as fh:
                las_data = fh.read()
            z_coords = las_data.z
            if len(z_coords) == 0: return None, None

            min_z, max_z = int(z_coords.min()), int(z_coords.max()) + 1
            z_bins = range(min_z, max_z + 1, 1)
            counts, _ = pd.cut(z_coords, bins=z_bins, include_lowest=True, right=False, retbins=True)
            counts = counts.value_counts().sort_index()
            
            bin_df = pd.DataFrame({'bin': [int(b.left) for b in counts.index], 'count': counts.values})
            filtered = bin_df[bin_df['count'] >= 100].reset_index(drop=True)
            
            if not filtered.empty:
                return filtered['bin'].iloc[0], filtered['bin'].iloc[-1]
            return None, None
        except Exception as e:
            log(f"Stats Error: {e}")
            return None, None

    def _run_pdal(self, laz_path, first, last):
        input_path = Path(laz_path)
        out_denoised = input_path.with_name(f"{input_path.stem}_denoised.laz")
        out_dsm = input_path.with_name(f"{input_path.stem}_dsm.tif")
        out_stat = input_path.with_name(f"{input_path.stem}_stat.tif")
        
        # Denoise
        pipeline_denoise = [
            str(input_path),
            {"type": "filters.range", "limits": f"Z[{first}:{last}]"},
            {"type": "filters.assign", "assignment": "Classification[:]=0"},
            {"type": "writers.las", "filename": str(out_denoised), "minor_version": "4"}
        ]
        _execute_pdal_pipeline(pipeline_denoise, self.controller.log_frame, "Denoising...", self.controller, self)
        
        # DSM
        pipeline_dsm = [
            str(out_denoised),
            {"type": "writers.gdal", "filename": str(out_dsm), "resolution": 1.0, "output_type": "max"}
        ]
        _execute_pdal_pipeline(pipeline_dsm, self.controller.log_frame, "Creating DSM TIF...", self.controller, self)

        # Stat
        pipeline_stat = [
            str(out_denoised),
            {"type": "writers.gdal", "filename": str(out_stat), "resolution": 1.0, "output_type": "min,count"}
        ]
        _execute_pdal_pipeline(pipeline_stat, self.controller.log_frame, "Creating Stat TIF...", self.controller, self)
        
        return str(out_dsm), str(out_stat)

    def _create_shaded_relief(self, dem_path, out_path, unit_label):
        with rasterio.open(dem_path) as src:
            elevation = src.read(1)
            elevation[elevation == src.nodata] = np.nan
        
        data_min, data_max = np.nanmin(elevation), np.nanmax(elevation)
        ls = LightSource(azdeg=315, altdeg=45)
        hillshade = ls.hillshade(elevation, vert_exag=1.1, dx=1.0, dy=1.0)

        fig, ax = plt.subplots(figsize=(12, 8))
        im = ax.imshow(elevation, cmap='gist_earth')
        ax.imshow(hillshade, cmap='gray', alpha=0.3)
        ax.axis('off')

        divider = make_axes_locatable(ax)
        cax = divider.append_axes("bottom", size="5%", pad=0.5)
        cbar = fig.colorbar(im, cax=cax, orientation='horizontal', label='')
        cbar.set_ticks([data_min, data_max])
        cbar.set_ticklabels([f'{data_min:.2f}', f'{data_max:.2f}'])
        cbar.ax.tick_params(labelsize=12)
        cbar.set_label(unit_label, fontsize=14, fontweight='bold')

        plt.tight_layout(pad=0)
        plt.savefig(out_path, dpi=300, bbox_inches='tight', pad_inches=0.2)
        plt.close(fig)

    def _create_count_map(self, tif_path, out_path):
        with rasterio.open(tif_path) as src:
            data = src.read(2).astype(float) # Band 2 is count
            if src.nodata is not None: data[data == src.nodata] = np.nan
            data[data == 0] = np.nan
            masked_data = np.ma.masked_invalid(data)

        if masked_data.count() == 0: return # Handle empty

        data_min, data_max = masked_data.min(), masked_data.max()
        
        fig, ax = plt.subplots(figsize=(12, 8))
        im = ax.imshow(masked_data, cmap='viridis')
        ax.axis('off')

        divider = make_axes_locatable(ax)
        cax = divider.append_axes("bottom", size="5%", pad=0.5)
        cbar = fig.colorbar(im, cax=cax, orientation='horizontal', label='')
        cbar.set_ticks([data_min, data_max])
        cbar.set_ticklabels([f'{int(data_min)}', f'{int(data_max)}'])
        cbar.ax.tick_params(labelsize=12)
        cbar.set_label("Count", fontsize=14, fontweight='bold')

        plt.tight_layout(pad=0)
        plt.savefig(out_path, dpi=300, bbox_inches='tight', pad_inches=0.2)
        plt.close(fig)