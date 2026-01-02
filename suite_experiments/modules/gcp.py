import tkinter as tk
import ttkbootstrap as ttk
from tkinter import filedialog, messagebox
import threading
import pandas as pd
import os
import re
from gui.base import BaseToolFrame
from gui.widgets import Tooltip

class GCPTransformFrame(BaseToolFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "DJI Terra 7-parameter CSV Generator")
        self.input_file_var = tk.StringVar()
        self.unit_display_var = tk.StringVar(value="US Survey Feet")
        self.UNIT_MAP = {"Meters": "meters", "US Survey Feet": "us-ft", "International Feet": "intl-ft"}
        self.is_processing = False
        self.create_widgets()
        self.input_file_var.trace_add("write", self._check_run_button_state)
        self.unit_display_var.trace_add("write", self._check_run_button_state)

    def create_widgets(self):
        self.content_frame.grid_columnconfigure(0, weight=1)
        input_frame = ttk.Labelframe(self.content_frame, text="1. Select Input and Parameters", padding=15, style="Info.TLabelframe"); input_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10)); input_frame.columnconfigure(1, weight=1)
        ttk.Label(input_frame, text="Input GCP File (.csv):").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=10)
        entry_button_frame = ttk.Frame(input_frame); entry_button_frame.grid(row=0, column=1, columnspan=2, sticky="ew"); entry_button_frame.columnconfigure(0, weight=1)
        gcp_entry = ttk.Entry(entry_button_frame, textvariable=self.input_file_var)
        gcp_entry.grid(row=0, column=0, sticky="ew")
        Tooltip(gcp_entry, "Select the input GCP file. It must contain specific columns like 'WGS84 Latitude', 'Elevation', etc.")
        gcp_browse = ttk.Button(entry_button_frame, text="Browse...", command=self.browse_csv_file, bootstyle="secondary")
        gcp_browse.grid(row=0, column=1, padx=(10, 0))
        Tooltip(gcp_browse, "Browse for the GCP file.")
        ttk.Label(input_frame, text="Preferred Elevation Unit:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=10)
        unit_combo = ttk.Combobox(input_frame, textvariable=self.unit_display_var, values=list(self.UNIT_MAP.keys()), state="readonly")
        unit_combo.grid(row=1, column=1, sticky="w")
        Tooltip(unit_combo, "Select the unit for the final 'Elevation2' column in the output file.")
        run_frame = ttk.Labelframe(self.content_frame, text="2. Run Process", padding=10, style="Info.TLabelframe"); run_frame.grid(row=1, column=0, sticky="ew", pady=10)
        self.run_container = ttk.Frame(run_frame); self.run_container.pack(fill='x')
        self.run_button = ttk.Button(self.run_container, text="Run CSV Generator", command=self.start_transformation_thread, bootstyle="primary", state="disabled"); self.run_button.pack(side='left', ipady=5, padx=(0, 10))
        Tooltip(self.run_button, "Generate the 7-parameter CSV file required by DJI Terra.")
        self.progress = ttk.Progressbar(self.run_container, orient="horizontal", length=300, mode="determinate", bootstyle="primary"); self.progress.pack(side="left", padx=5)
        
        reset_frame = ttk.Frame(self.content_frame)
        reset_frame.grid(row=2, column=0, sticky="e", pady=(10,0))
        reset_btn = ttk.Button(reset_frame, text="Reset All", command=self.reset_ui, bootstyle="secondary-outline")
        reset_btn.pack()
        Tooltip(reset_btn, "Clear all inputs.")

    def reset_ui(self):
        self.input_file_var.set("")
        self.unit_display_var.set("US Survey Feet")
        self.controller.log_frame.log("GCP Transformation tool has been reset.")

    def _check_run_button_state(self, *args):
        if self.is_processing: return
        self.run_button.config(state="normal" if os.path.isfile(self.input_file_var.get()) and self.unit_display_var.get() else "disabled")

    def browse_csv_file(self):
        filepath = filedialog.askopenfilename(title="Select a GCP CSV File", filetypes=(("CSV files", "*.csv"), ("All files", "*.*")))
        if filepath: self.input_file_var.set(filepath)

    def set_processing_state(self, is_processing):
        self.is_processing = is_processing
        # This tool is very fast and doesn't run an external process,
        # so we only manage the run button's state locally.
        if is_processing:
            self.run_button.config(text="Processing...", state="disabled")
            self.progress.config(mode="indeterminate"); self.progress.start()
        else:
            self.run_button.config(text="Run CSV Generator", state="normal")
            self.progress.stop(); self.progress.config(mode="determinate", value=0)
        self._check_run_button_state()

    def start_transformation_thread(self):
        if self.is_processing: return

        input_path = self.input_file_var.get()
        if not input_path:
            messagebox.showwarning("Input Missing", "Please select an input CSV file.")
            return

        directory, filename = os.path.split(input_path)
        base, _ = os.path.splitext(filename)
        output_path = os.path.join(directory, f"{base}_7param.csv")

        self.set_processing_state(True)
        self.controller.log_frame.log(f"\n{'='*20}\n--- [GCP TRANSFORM] Starting CSV Generation ---\n{'='*20}")
        
        selected_unit_internal = self.UNIT_MAP[self.unit_display_var.get()]
        
        thread = threading.Thread(
            target=self.run_transformation,
            args=(input_path, output_path, selected_unit_internal),
            daemon=True,
            name="GCP_Transform"
        )
        thread.start()

    def on_transformation_complete(self, is_success, message):
        """Handles UI updates after the GCP transformation is complete."""
        self.set_processing_state(False)
        if is_success:
            messagebox.showinfo("Success", message)
        else:
            messagebox.showerror("Error", message)

    def run_transformation(self, input_csv, output_csv, preferred_unit):
        log = self.controller.log_frame.log
        is_success = False
        message = ""
        try:
            log(f"Reading input file: {os.path.basename(input_csv)}")
            df = pd.read_csv(input_csv, dtype=str)
            log("Sanitizing numeric columns...")
            cols_to_sanitize = ['WGS84 Latitude', 'WGS84 Longitude', 'Elevation', 'Easting/Longitude', 'Northing/Latitude']
            for col in cols_to_sanitize:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: re.sub(r'[^0-9.-]', '', str(x)))
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                else: raise KeyError(f"Required column '{col}' is missing.")
            original_rows = len(df)
            df.dropna(subset=cols_to_sanitize, inplace=True)
            if len(df) < original_rows: log(f"Warning: Dropped {original_rows - len(df)} rows due to invalid numeric data.")
            log("Sanitization complete.")
            CONVERSION_FACTORS = {"meters": 1.0, "us-ft": 3.280833438333123, "intl-ft": 3.2808}
            conversion_factor = CONVERSION_FACTORS[preferred_unit]
            log(f"Using unit '{preferred_unit}' with conversion factor {conversion_factor}")
            df_transformed = pd.DataFrame()
            df_transformed['Name'] = df['Name']
            df_transformed['WGS84 Latitude'] = df['WGS84 Latitude']
            df_transformed['WGS84 Longitude'] = df['WGS84 Longitude']
            df_transformed['Elevation1'] = df['Elevation'] if conversion_factor == 1.0 else df['Elevation'] / conversion_factor
            df_transformed['Easting/Longitude'] = df['Easting/Longitude']
            df_transformed['Northing/Latitude'] = df['Northing/Latitude']
            df_transformed['Elevation2'] = df['Elevation']
            df_transformed = df_transformed[['Name', 'WGS84 Latitude', 'WGS84 Longitude', 'Elevation1', 'Easting/Longitude', 'Northing/Latitude', 'Elevation2']]
            log("Columns rearranged and Elevation1 calculated.")
            df_transformed.to_csv(output_csv, index=False, header=False)
            log(f"Successfully saved transformed file to: {os.path.basename(output_csv)}")
            
            is_success = True
            message = f"GCP file transformed successfully!\n\nOutput saved to:\n{os.path.basename(output_csv)}"
        except Exception as e:
            log(f"An error occurred: {e}")
            is_success = False
            message = f"An error occurred:\n{e}"
        finally:
            self.after(0, self.on_transformation_complete, is_success, message)