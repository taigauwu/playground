import tkinter as tk
import ttkbootstrap as ttk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import os
import re
import requests
from gui.base import BaseToolFrame
from gui.widgets import Tooltip
from utils.projections import get_published_from_local, get_published_from_epsg
from utils.files import get_laz_output_filename
from core.execution import _execute_pdal_pipeline
import webbrowser
from utils.projections import get_published_from_local, get_published_from_epsg, validate_and_format_wkt

# Constants
FONT_FAMILY = "Segoe UI"

class HeaderToolFrame(BaseToolFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Assign/Update Point Cloud Header")
        self.crs_type, self.single_file_path, self.folder_path_display = tk.StringVar(value="local"), tk.StringVar(), tk.StringVar()
        self.current_unit_display = tk.StringVar()
        self.desired_unit_display = tk.StringVar()
        self.slug_id, self.local_string, self.epsg_code, self.crs_name_var = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.files_list = []
        self.is_processing = False
        self.batch_mode = tk.BooleanVar(value=False)
        self.UNIT_MAP_DISPLAY = {"Meters": "meters", "US Survey Feet": "us-ft", "International Feet": "ft"}
        self.create_widgets()
        self.update_ui_for_crs_type()
        
        self.single_file_path.trace_add("write", self._check_run_button_state)
        self.folder_path_display.trace_add("write", self._check_run_button_state)
        self.desired_unit_display.trace_add("write", self._check_run_button_state)
        self.current_unit_display.trace_add("write", self._check_run_button_state)
        self.local_string.trace_add("write", self._check_run_button_state)
        self.epsg_code.trace_add("write", self._check_run_button_state)
        self.crs_type.trace_add("write", self._check_run_button_state)

    def _check_run_button_state(self, *args):
        if self.is_processing: return
        
        if self.batch_mode.get():
            files_ok = bool(self.files_list)
        else:
            files_ok = os.path.isfile(self.single_file_path.get())

        crs_ok = False
        type_ = self.crs_type.get()
        
        if type_ == "local":
            crs_ok = bool(self.local_string.get() and self.desired_unit_display.get())
        elif type_ == "published":
            crs_ok = bool(self.epsg_code.get().isdigit() and self.current_unit_display.get() and self.desired_unit_display.get())
        elif type_ == "wkt": # <--- NEW
            # Check if text widget exists and has content
            if hasattr(self, 'wkt_input_text'):
                content = self.wkt_input_text.get("1.0", "end-1c").strip()
                crs_ok = bool(content)

        self.run_button.config(state="normal" if files_ok and crs_ok else "disabled")

    def _toggle_input_mode(self):
        is_batch = self.batch_mode.get()
        self.single_file_frame.grid_remove() if is_batch else self.single_file_frame.grid()
        self.folder_frame.grid() if is_batch else self.folder_frame.grid_remove()
        self._check_run_button_state()

    def create_widgets(self):
        self.content_frame.grid_columnconfigure(0, weight=1)

        input_container = ttk.Labelframe(self.content_frame, text="1. Select Input", padding=10, style="Info.TLabelframe")
        input_container.grid(row=0, column=0, sticky="ew")
        input_container.columnconfigure(1, weight=1)

        batch_toggle = ttk.Checkbutton(input_container, text="Batch Mode (Process entire folder)", variable=self.batch_mode, command=self._toggle_input_mode, bootstyle="round-toggle")
        batch_toggle.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        Tooltip(batch_toggle, "Check this to process all .laz files in a selected folder. Uncheck to process a single file.")

        self.single_file_frame = ttk.Frame(input_container)
        self.single_file_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        self.single_file_frame.columnconfigure(1, weight=1)
        ttk.Label(self.single_file_frame, text="Input point cloud file (.laz/.las):").grid(row=0, column=0, sticky="w", padx=(0,10))
        ttk.Entry(self.single_file_frame, textvariable=self.single_file_path, state="readonly").grid(row=0, column=1, sticky="ew")
        ttk.Button(self.single_file_frame, text="Browse...", command=self.browse_single_file, bootstyle="secondary").grid(row=0, column=2, padx=(5,0))

        self.folder_frame = ttk.Frame(input_container)
        self.folder_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        self.folder_frame.columnconfigure(1, weight=1)
        ttk.Label(self.folder_frame, text="Input folder with .laz/.las files:").grid(row=0, column=0, sticky="w", padx=(0,10))
        ttk.Entry(self.folder_frame, textvariable=self.folder_path_display, state="readonly").grid(row=0, column=1, sticky="ew")
        ttk.Button(self.folder_frame, text="Browse...", command=self.browse_folder, bootstyle="secondary").grid(row=0, column=2, padx=(5,0))

        self.folder_frame.grid_remove()

        options_frame = ttk.Labelframe(self.content_frame, text="2. Define Coordinate System", padding=10, style="Info.TLabelframe")
        options_frame.grid(row=1, column=0, sticky="ew", pady=10)
        options_frame.grid_columnconfigure(0, weight=1)
        
        options_container = ttk.Frame(options_frame)
        options_container.grid(row=0, column=0, sticky="ew")
        options_container.grid_columnconfigure(1, weight=1)
        
        radio_frame = ttk.Frame(options_container)
        radio_frame.grid(row=0, column=0, sticky="n", padx=(0, 20), pady=5)
        
        rb_local = ttk.Radiobutton(radio_frame, text="Local (Proj)", variable=self.crs_type, value="local", command=self.update_ui_for_crs_type)
        rb_local.pack(anchor="w", pady=2)
        
        rb_pub = ttk.Radiobutton(radio_frame, text="Published (EPSG)", variable=self.crs_type, value="published", command=self.update_ui_for_crs_type)
        rb_pub.pack(anchor="w", pady=2)
        
        # NEW BUTTON HERE
        rb_wkt = ttk.Radiobutton(radio_frame, text="Paste WKT", variable=self.crs_type, value="wkt", command=self.update_ui_for_crs_type)
        rb_wkt.pack(anchor="w", pady=2)

        self.param_frame = ttk.Frame(options_container)
        self.param_frame.grid(row=0, column=1, sticky="nsew")
        
        self.wkt_frame = ttk.Labelframe(self.content_frame, text="Retrieved WKT (for verification)", padding=10, style="Info.TLabelframe")
        self.wkt_frame.grid(row=2, column=0, sticky="ew")
        self.wkt_frame.grid_columnconfigure(0, weight=1)
        self.wkt_text_display = scrolledtext.ScrolledText(self.wkt_frame, wrap=tk.WORD, height=6, font=("Courier New", 9))
        self.wkt_text_display.grid(row=0, column=0, sticky="ew")
        self.wkt_text_display.config(state="disabled")
        self.wkt_frame.grid_remove()
        
        action_frame = ttk.Labelframe(self.content_frame, text="3. Run Process", padding=10, style="Info.TLabelframe")
        action_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        run_container = ttk.Frame(action_frame)
        run_container.grid(row=0, column=0, sticky="w")
        self.run_button = ttk.Button(run_container, text="Run Header Update", command=self.start_processing_thread, bootstyle="primary", state="disabled")
        self.run_button.pack(side="left", padx=(0, 10))
        Tooltip(self.run_button, "Execute the PDAL pipeline to assign the new Coordinate Reference System to the file.")
        self.progress = ttk.Progressbar(run_container, orient="horizontal", length=300, mode="determinate", bootstyle="primary")
        self.progress.pack(side="left")

        reset_frame = ttk.Frame(self.content_frame)
        reset_frame.grid(row=4, column=0, sticky="e", pady=(10,0))
        
        self.stop_button = ttk.Button(reset_frame, text="Stop Process", command=lambda: self.controller.terminate_frame_process(self), bootstyle="secondary", state="disabled")
        self.stop_button.pack(side="left", padx=(0, 5))
        Tooltip(self.stop_button, "Forcefully stop the current running process.")

        reset_btn = ttk.Button(reset_frame, text="Reset All", command=self.reset_ui, bootstyle="secondary-outline")
        reset_btn.pack(side="left")
        Tooltip(reset_btn, "Clear all inputs and selections in this tool.")
    
    def update_ui_for_crs_type(self):
        self.wkt_frame.grid_remove()
        for widget in self.param_frame.winfo_children(): widget.destroy()
        
        if self.crs_type.get() == "local": 
            self.create_local_widgets()
        elif self.crs_type.get() == "published": 
            self.create_published_widgets()
        elif self.crs_type.get() == "wkt":  # <--- NEW
            self.create_wkt_widgets()
            
        self._check_run_button_state()

    def create_local_widgets(self):
        self.param_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(self.param_frame, text="Project Slug ID (Optional):").grid(row=0, column=0, sticky="w", padx=(0, 10))
        slug_frame = ttk.Frame(self.param_frame)
        slug_frame.grid(row=0, column=1, sticky="ew")
        slug_entry = ttk.Entry(slug_frame, textvariable=self.slug_id, width=25)
        slug_entry.pack(side="left", padx=(0, 10))
        Tooltip(slug_entry, "Optional: Enter the project's PQ Slug ID to easily find its proj string.")
        slug_btn = ttk.Button(slug_frame, text="Open in Browser", command=self.open_slug_link, bootstyle="secondary")
        slug_btn.pack(side="left")
        Tooltip(slug_btn, "Open the coordinate system database in a web browser, filtered by the entered Slug ID.")
        
        ttk.Label(self.param_frame, text="Enter Proj String:").grid(row=1, column=0, sticky="nw", padx=(0, 10), pady=(10, 0))
        proj_text = scrolledtext.ScrolledText(self.param_frame, height=3, width=8, wrap=tk.WORD, font=(FONT_FAMILY, 9))
        proj_text.grid(row=1, column=1, sticky="ew", pady=(10, 0))
        Tooltip(proj_text, "Enter the proj4 string for the local coordinate system.")
        proj_text.bind("<<Modified>>", lambda e: self.on_text_modified(e, proj_text, self.local_string))
        self.local_string.trace_add("write", lambda *args: self.on_stringvar_modified(*args, widget=proj_text, stringvar=self.local_string))

        self.create_units_widget_local(2)

    def on_text_modified(self, event, widget, stringvar):
        content = widget.get("1.0", "end-1c")
        if content != stringvar.get():
            stringvar.set(content)
        widget.edit_modified(False)

    def on_stringvar_modified(self, *args, widget, stringvar):
        content = stringvar.get()
        if content != widget.get("1.0", "end-1c"):
            widget.delete("1.0", tk.END)
            widget.insert("1.0", content)

    def create_published_widgets(self):
        self.param_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(self.param_frame, text="Enter EPSG Code:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        epsg_entry_frame = ttk.Frame(self.param_frame)
        epsg_entry_frame.grid(row=0, column=1, sticky="ew")
        epsg_entry = ttk.Entry(epsg_entry_frame, textvariable=self.epsg_code, width=15)
        epsg_entry.pack(side="left")
        Tooltip(epsg_entry, "Enter the numerical EPSG code for the published coordinate system.")
        self.check_button = ttk.Button(epsg_entry_frame, text="Check", command=self.start_crs_name_fetch_thread, bootstyle="secondary")
        self.check_button.pack(side="left", padx=(10, 0))
        Tooltip(self.check_button, "Fetch and display the name of the CRS from epsg.io for the entered code.")
        ttk.Label(self.param_frame, text="CRS Name:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(5, 0))
        ttk.Label(self.param_frame, textvariable=self.crs_name_var, wraplength=400, justify="left").grid(row=1, column=1, sticky="w", pady=(5, 0))
        self.create_units_widget_published(2)

    def create_units_widget_local(self, grid_row):
        ttk.Label(self.param_frame, text="Units:").grid(row=grid_row, column=0, sticky="w", padx=(0, 10), pady=(10, 0))
        units_combo = ttk.Combobox(self.param_frame, textvariable=self.desired_unit_display, values=list(self.UNIT_MAP_DISPLAY.keys()), state="readonly")
        units_combo.grid(row=grid_row, column=1, sticky="w", pady=(10, 0))
        Tooltip(units_combo, "Select the measurement unit for the coordinate system (e.g., Meters, US Survey Feet).")

    def create_units_widget_published(self, start_row):
        ttk.Label(self.param_frame, text="Current Unit:").grid(row=start_row, column=0, sticky="w", padx=(0, 10), pady=(10, 0))
        current_unit_combo = ttk.Combobox(self.param_frame, textvariable=self.current_unit_display, values=list(self.UNIT_MAP_DISPLAY.keys()), state="readonly")
        current_unit_combo.grid(row=start_row, column=1, sticky="w", pady=(10, 0))
        Tooltip(current_unit_combo, "The unit of the coordinate system fetched from EPSG.io (usually Meters).")

        ttk.Label(self.param_frame, text="Desired Unit:").grid(row=start_row + 1, column=0, sticky="w", padx=(0, 10), pady=(10, 0))
        desired_unit_combo = ttk.Combobox(self.param_frame, textvariable=self.desired_unit_display, values=list(self.UNIT_MAP_DISPLAY.keys()), state="readonly")
        desired_unit_combo.grid(row=start_row + 1, column=1, sticky="w", pady=(10, 0))
        Tooltip(desired_unit_combo, "The target unit to convert the coordinate system to.")

    def browse_single_file(self):
        path = filedialog.askopenfilename(title="Select a Lidar file", filetypes=[("Lidar Files", "*.laz *.las"), ("All files", "*.*")])
        if path:
            self.single_file_path.set(path)
        self._check_run_button_state()

    def browse_folder(self):
        directory = filedialog.askdirectory(title="Select a folder with Lidar files")
        if directory:
            laz_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith(('.laz', '.las'))]
            if laz_files:
                self.files_list = laz_files
                self.folder_path_display.set(f"{len(laz_files)} file(s) found in '{os.path.basename(directory)}'")
            else:
                self.files_list.clear()
                self.folder_path_display.set("No .laz/.las files found in selected folder.")
                messagebox.showwarning("No Files Found", "The selected folder does not contain any .laz or .las files.")
        else:
            self.files_list.clear()
            self.folder_path_display.set("")
        self._check_run_button_state()

    def open_slug_link(self):
        slug = self.slug_id.get().strip()
        if not slug: return messagebox.showwarning("Missing Info", "Please enter a Project Slug ID.")
        webbrowser.open(f"https://app.prpellr.com/admin/coordinates/localsitecalibration/?q-l=on&q=project.slug_id+%3D+%22{slug}%22")

    def start_crs_name_fetch_thread(self):
        self.check_button.config(state="disabled")
        self.crs_name_var.set("Fetching...")
        threading.Thread(target=self._fetch_crs_name_worker, daemon=True, name="EPSG_Fetch").start()

    def _fetch_crs_name_worker(self):
        try:
            epsg_code = self.epsg_code.get().strip()
            if not epsg_code.isdigit():
                self.crs_name_var.set("Invalid EPSG code.")
                return
            response = requests.get(f"https://epsg.io/{epsg_code}.wkt", timeout=10)
            response.raise_for_status()
            wkt_string = response.text
            match = re.search(r'^(?:PROJCS|GEOGCS|GEOCCS|VERT_CS|COMPD_CS)\["([^"]+)"', wkt_string, re.IGNORECASE)
            if match: self.crs_name_var.set(match.group(1))
            elif "error" in wkt_string.lower(): self.crs_name_var.set(f"EPSG:{epsg_code} not found.")
            else: self.crs_name_var.set("Could not parse CRS name.")
        except requests.exceptions.RequestException:
            self.crs_name_var.set("Error connecting to EPSG.io.")
        finally:
            self.after(0, self.check_button.config, {'state': 'normal'})
            self.after(0, self._check_run_button_state)
    
    def set_processing_state(self, is_processing):
        self.is_processing = is_processing
        if is_processing:
            self.run_button.config(text="Processing...", state="disabled")
            self.progress.config(mode="indeterminate")
            self.progress.start()
            self.stop_button.config(state="normal")
        else:
            self.run_button.config(text="Run Header Update")
            self.progress.stop()
            self.progress.config(mode="determinate")
            self.progress['value'] = 0
            self._check_run_button_state()
            self.stop_button.config(state="disabled")

    def start_processing_thread(self):
        if self.is_processing: return
        self.controller.log_frame.log(f"\n{'='*20}\n--- [HEADER ASSIGN] Starting Process ---\n{'='*20}")
        self.set_processing_state(True)
        threading.Thread(target=self.run_processing, daemon=True, name="Header_Update").start()

    def reset_ui(self):
        for var in [self.single_file_path, self.folder_path_display, self.epsg_code, self.local_string, self.slug_id, self.current_unit_display, self.desired_unit_display, self.crs_name_var]: var.set("")
        self.files_list.clear()
        self.batch_mode.set(False)
        self._toggle_input_mode()
        self.crs_type.set("local")
        self.progress['value'] = 0
        self.update_ui_for_crs_type()
        self.controller.log_frame.log("Header Assignment tool has been reset.")

    def on_processing_complete(self, status, message):
        """Handles UI updates after the header processing is complete."""
        self.set_processing_state(False)
        if status == "success":
            messagebox.showinfo("Success", message)
            self.reset_ui()
        elif status == "warning":
            messagebox.showwarning("Warning", message)
        elif status == "error" and not self.controller.was_terminated:
            messagebox.showerror("Error", message)
        self.controller.was_terminated = False # Reset flag

    def run_processing(self):
        status = "error"
        message = ""
        try:
            if self.batch_mode.get():
                files_to_process = self.files_list
                if not files_to_process:
                    raise ValueError("Batch mode is on, but no folder is selected or the folder is empty.")
            else:
                single_file = self.single_file_path.get()
                if not os.path.isfile(single_file):
                    raise ValueError("Please select a valid input LAZ file.")
                files_to_process = [single_file]

            crs_type = self.crs_type.get()

            # LOGIC SWITCH
            if crs_type == 'local':
                units_internal = self.UNIT_MAP_DISPLAY[self.desired_unit_display.get()]
                wkt_srs = get_published_from_local(self.local_string.get().strip(), units_internal)
            elif crs_type == 'published':
                current_unit = self.UNIT_MAP_DISPLAY[self.current_unit_display.get()]
                desired_unit = self.UNIT_MAP_DISPLAY[self.desired_unit_display.get()]
                wkt_srs = get_published_from_epsg(int(self.epsg_code.get().strip()), current_unit, desired_unit)
            elif crs_type == 'wkt': # <--- NEW BLOCK
                raw_wkt = self.wkt_input_text.get("1.0", "end-1c").strip()
                wkt_srs = validate_and_format_wkt(raw_wkt)

            self.after(0, self.show_wkt, wkt_srs)
            
            total_files = len(files_to_process)
            all_success = True

            for i, las_path in enumerate(files_to_process):
                self.controller.log_frame.log(f"\n({i+1}/{total_files}) Processing: {os.path.basename(las_path)}")
                try:
                    output_path = get_laz_output_filename(las_path, '_header')
                    pipeline = [
                        {"type": "readers.las", "filename": las_path}, 
                        {
                            "type": "writers.las", 
                            "filename": output_path, 
                            "a_srs": wkt_srs, 
                            "minor_version": 2, 
                            "dataformat_id": 3, 
                            "forward": "all"
                        }
                    ]
                    
                    log_message = f"> Executing PDAL header pipeline...\n  Input: {os.path.basename(las_path)}\n  Output: {os.path.basename(output_path)}\n"
                    _execute_pdal_pipeline(pipeline, self.controller.log_frame, log_message, controller=self.controller, frame_instance=self)
                    
                except Exception as file_error:
                    all_success = False
                    if self.controller.was_terminated:
                        self.controller.log_frame.log(f"    --- Process for {os.path.basename(las_path)} was terminated by user. ---")
                        break
                    self.controller.log_frame.log(f"    --- ERROR processing {os.path.basename(las_path)}: {file_error} ---")

            if self.controller.was_terminated:
                status = "terminated"
                message = "Process was terminated by the user."
            elif all_success:
                status = "success"
                message = f"Header update complete for all {total_files} file(s)!"
            else:
                status = "warning"
                message = "Process finished, but one or more files failed. Check the log for details."
            
        except Exception as e:
            if not self.controller.was_terminated:
                status = "error"
                message = f"A critical error occurred:\n{e}"
        finally:
            self.after(0, self.on_processing_complete, status, message)

    def show_wkt(self, wkt_string):
        self.wkt_frame.grid()
        self.wkt_text_display.config(state="normal")
        self.wkt_text_display.delete(1.0, tk.END)
        self.wkt_text_display.insert(tk.END, wkt_string)
        self.wkt_text_display.config(state="disabled")
    
    def create_wkt_widgets(self):
        self.param_frame.grid_columnconfigure(0, weight=1)
        ttk.Label(self.param_frame, text="Paste WKT String:").grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        self.wkt_input_text = scrolledtext.ScrolledText(self.param_frame, height=8, width=50, wrap=tk.WORD, font=("Segoe UI", 9))
        self.wkt_input_text.grid(row=1, column=0, sticky="ew")
        Tooltip(self.wkt_input_text, "Paste the full Well-Known Text (WKT) string here. It will be automatically formatted for LAS compatibility.")
        
        # Bind key release to check valid state
        self.wkt_input_text.bind("<KeyRelease>", lambda e: self._check_run_button_state())