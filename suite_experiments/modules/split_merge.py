import tkinter as tk
import ttkbootstrap as ttk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import os
import re
import sys
import tempfile
import shutil
from gui.base import BaseToolFrame
from gui.widgets import Tooltip
from core.execution import _execute_las_command

class SplitMergeFrame(BaseToolFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Split/Merge Point Cloud Tiles")
        self.is_processing = False
        self.setup_variables()
        self.create_widgets()
        self._sync_axis_selection()
        self._check_run_button_state()

    def setup_variables(self):
        self.lastools_path_var = self.controller.lastools_path_var
        self.axis_var = tk.StringVar(value='Y')
        self.min_x_var, self.max_x_var = tk.StringVar(), tk.StringVar()
        self.min_y_var, self.max_y_var = tk.StringVar(), tk.StringVar()
        self.lasinfo_file_var = tk.StringVar()
        self.lasinfo_axis_var = tk.StringVar(value='y')
        self.lasinfo_bin_var = tk.StringVar(value="50")
        self.split_laz_file_var = tk.StringVar()
        self.split_num_tiles_var = tk.StringVar(value="2")
        self.buffer_size_var = tk.StringVar(value="200")
        self.merge_tiles_folder_var = tk.StringVar()
        self.split_y_axis_radio, self.split_x_axis_radio = None, None
        self.merge_y_axis_radio, self.merge_x_axis_radio = None, None
        
        self.split_laz_file_var.trace_add("write", self._check_run_button_state)
        self.merge_tiles_folder_var.trace_add("write", self._check_run_button_state)

    def _on_mousewheel(self, event, canvas):
        if sys.platform == "win32": canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif sys.platform == "darwin": canvas.yview_scroll(int(-1 * event.delta), "units")
        else:
            if event.num == 4: canvas.yview_scroll(-1, "units")
            elif event.num == 5: canvas.yview_scroll(1, "units")

    def _bind_mousewheel_recursively(self, widget, canvas):
        widget.bind("<MouseWheel>", lambda e, c=canvas: self._on_mousewheel(e, c))
        for child in widget.winfo_children():
            self._bind_mousewheel_recursively(child, canvas)
            
    def _sync_axis_selection(self):
        selected_axis = self.lasinfo_axis_var.get()
        if selected_axis: self.axis_var.set(selected_axis.upper())

    def _reset_all(self):
        self._reset_autopopulate()
        self.lasinfo_file_var.set("")
        self.lasinfo_axis_var.set('y')
        self.lasinfo_bin_var.set("50")
        self.split_num_tiles_var.set("2")
        self.buffer_size_var.set("200")
        self.merge_tiles_folder_var.set("")
        self.controller.log_frame.log("Split/Merge tool has been fully reset.")


    def _reset_autopopulate(self):
        for var in [self.min_x_var, self.max_x_var, self.min_y_var, self.max_y_var, self.split_laz_file_var]: var.set("")
        self.split_histo_text.delete(1.0, tk.END)
        self.merge_histo_text.delete(1.0, tk.END)
        for radio in [self.split_y_axis_radio, self.split_x_axis_radio, self.merge_y_axis_radio, self.merge_x_axis_radio]:
            if radio: radio.config(state="normal")
        self.controller.log_frame.log("Auto-populate fields have been reset.")
        self._check_run_button_state()

    def _check_run_button_state(self, *args):
        if self.is_processing: return
        try:
            current_tab = self.notebook.index(self.notebook.select())
            lastools_ok = os.path.isdir(self.lastools_path_var.get())
            if not lastools_ok:
                self.run_button.config(state="disabled")
                return
            if current_tab == 0: is_valid = os.path.isfile(self.split_laz_file_var.get())
            elif current_tab == 1: is_valid = os.path.isdir(self.merge_tiles_folder_var.get())
            else: is_valid = False
            self.run_button.config(state="normal" if is_valid else "disabled")
        except (tk.TclError, AttributeError): pass
            
    def create_widgets(self):
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)
        
        canvas = tk.Canvas(self.content_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview, bootstyle="round")
        scrollable_frame = ttk.Frame(canvas, padding="10")
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._bind_mousewheel_recursively(scrollable_frame, canvas)
        
        scrollable_frame.grid_columnconfigure(0, weight=1)
        scrollable_frame.grid_rowconfigure(0, weight=1)
        
        self.notebook = ttk.Notebook(scrollable_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew", pady=10)
        self.notebook.bind("<<NotebookTabChanged>>", self._check_run_button_state)
        
        split_tab, merge_tab = ttk.Frame(self.notebook, padding=10), ttk.Frame(self.notebook, padding=10)
        split_tab.grid_columnconfigure(0, weight=1)
        merge_tab.grid_columnconfigure(0, weight=1)
        self.notebook.add(split_tab, text='Split LAZ')
        self.notebook.add(merge_tab, text='Merge Tiles')
        
        self.create_split_widgets(split_tab)
        self.create_merge_widgets(merge_tab)
        
        run_frame = ttk.Labelframe(scrollable_frame, text="6. Run Process", padding=10, style="Info.TLabelframe")
        run_frame.grid(row=1, column=0, sticky="ew", pady=(10,0))

        run_container = ttk.Frame(run_frame)
        run_container.pack(anchor="w")
        self.run_button = ttk.Button(run_container, text="Run Process", bootstyle="primary", command=lambda: self.start_processing(self.notebook.index(self.notebook.select())), state="disabled")
        self.run_button.pack(side="left", padx=(0, 10))
        Tooltip(self.run_button, "Execute the selected process (Split or Merge).")
        
        self.progress = ttk.Progressbar(run_container, orient="horizontal", length=300, mode="determinate", bootstyle="primary")
        self.progress.pack(side="left", padx=10)

        reset_frame = ttk.Frame(scrollable_frame)
        reset_frame.grid(row=2, column=0, sticky="e", pady=(10,0))
        
        self.stop_button = ttk.Button(reset_frame, text="Stop Process", command=lambda: self.controller.terminate_frame_process(self), bootstyle="secondary", state="disabled")
        self.stop_button.pack(side="left", padx=(0, 5))
        Tooltip(self.stop_button, "Forcefully stop the current running process.")

        reset_btn = ttk.Button(reset_frame, text="Reset All", command=self._reset_all, bootstyle="secondary-outline")
        reset_btn.pack(side="left")
        Tooltip(reset_btn, "Reset all fields in both the Split and Merge tabs.")

    def _create_autopopulate_widgets(self, parent):
        info_frame = ttk.Labelframe(parent, text="1. Auto-populate from File (Optional)", padding=10, style="Info.TLabelframe")
        info_frame.columnconfigure(1, weight=1)
        
        self.create_path_entry(info_frame, "Input source point cloud file (.laz):", self.lasinfo_file_var, 0, True)
        
        histo_frame = ttk.Frame(info_frame)
        histo_frame.grid(row=1, column=0, columnspan=3, sticky="w", pady=5)
        ttk.Label(histo_frame, text="Histogram Axis:").pack(side=tk.LEFT, padx=(0,10))
        rb_y = ttk.Radiobutton(histo_frame, text="Y", variable=self.lasinfo_axis_var, value='y', command=self._sync_axis_selection); rb_y.pack(side=tk.LEFT); Tooltip(rb_y, "Generate histogram based on Y-axis distribution.")
        rb_x = ttk.Radiobutton(histo_frame, text="X", variable=self.lasinfo_axis_var, value='x', command=self._sync_axis_selection); rb_x.pack(side=tk.LEFT, padx=10); Tooltip(rb_x, "Generate histogram based on X-axis distribution.")
        ttk.Label(histo_frame, text="Bin Size:").pack(side=tk.LEFT, padx=(20,10))
        bin_entry = ttk.Entry(histo_frame, textvariable=self.lasinfo_bin_var, width=10); bin_entry.pack(side=tk.LEFT); Tooltip(bin_entry, "The size of each bin for the histogram calculation.")
        button_frame = ttk.Frame(info_frame)
        button_frame.grid(row=2, column=0, columnspan=3, pady=10)
        auto_pop_btn = ttk.Button(button_frame, text="Run & Auto-Populate", command=self.start_lasinfo_processing, bootstyle="info")
        auto_pop_btn.pack(side=tk.LEFT, padx=5)
        Tooltip(auto_pop_btn, "Run lasinfo on the selected file to automatically fill in the project boundaries and histogram data below.")
        reset_auto_btn = ttk.Button(button_frame, text="Reset", command=self._reset_autopopulate, bootstyle="secondary")
        reset_auto_btn.pack(side=tk.LEFT, padx=5)
        Tooltip(reset_auto_btn, "Clear the auto-populated fields.")
        return info_frame
        
    def create_split_widgets(self, parent):
        self._create_autopopulate_widgets(parent).grid(row=0, column=0, sticky="ew", pady=(0, 15))
        axis_frame, self.split_y_axis_radio, self.split_x_axis_radio = self.create_axis_selection(parent)
        axis_frame.grid(row=1, column=0, sticky="ew", pady=5)
        self.create_boundaries_inputs(parent).grid(row=2, column=0, sticky="ew", pady=5)
        core_frame = ttk.Labelframe(parent, text="4. Core Settings", padding=10, style="Info.TLabelframe")
        core_frame.grid(row=3, column=0, sticky="ew", pady=5)
        core_frame.columnconfigure(1, weight=1)
        core_frame.columnconfigure(3, weight=1)
        ttk.Label(core_frame, text="Buffer Size:").grid(row=0, column=0, sticky="w", padx=5)
        buffer_entry = ttk.Entry(core_frame, textvariable=self.buffer_size_var); buffer_entry.grid(row=0, column=1, sticky="ew", padx=(5,10)); Tooltip(buffer_entry, "The overlap size between adjacent tiles to prevent data gaps.")
        ttk.Label(core_frame, text="Number of Tiles:").grid(row=0, column=2, sticky="w", padx=5)
        num_tiles_entry = ttk.Entry(core_frame, textvariable=self.split_num_tiles_var); num_tiles_entry.grid(row=0, column=3, sticky="ew", padx=5); Tooltip(num_tiles_entry, "The desired number of output tiles to split the file into.")
        paths_frame = ttk.Labelframe(parent, text="5. Input File for Splitting", padding=10, style="Info.TLabelframe")
        paths_frame.grid(row=4, column=0, sticky="ew", pady=5)
        paths_frame.columnconfigure(1, weight=1)
        self.create_path_entry(paths_frame, "Input point cloud file (.laz):", self.split_laz_file_var, 0, True)
        histo_frame = ttk.Labelframe(parent, text="6. Raw Histogram Data", padding=10, style="Info.TLabelframe")
        histo_frame.grid(row=5, column=0, sticky="ew", pady=5)
        histo_frame.grid_columnconfigure(0, weight=1)
        histo_frame.grid_rowconfigure(0, weight=1)
        self.split_histo_text = scrolledtext.ScrolledText(histo_frame, wrap=tk.WORD, height=8, font=('Courier New', 9))
        self.split_histo_text.grid(row=0, column=0, sticky="nsew")
        Tooltip(self.split_histo_text, "Raw histogram data used to calculate tile boundaries. Auto-populated from Step 1.")

    def create_merge_widgets(self, parent):
        self._create_autopopulate_widgets(parent).grid(row=0, column=0, sticky="ew", pady=(0, 15))
        axis_frame, self.merge_y_axis_radio, self.merge_x_axis_radio = self.create_axis_selection(parent)
        axis_frame.grid(row=1, column=0, sticky="ew", pady=5)
        self.create_boundaries_inputs(parent).grid(row=2, column=0, sticky="ew", pady=5)
        paths_frame = ttk.Labelframe(parent, text="4. Input Folder", padding=10, style="Info.TLabelframe")
        paths_frame.grid(row=3, column=0, sticky="ew", pady=5)
        paths_frame.columnconfigure(1, weight=1)
        self.create_path_entry(paths_frame, "Classified Tiles Folder:", self.merge_tiles_folder_var, 0, False)
        histo_frame = ttk.Labelframe(parent, text="5. Raw Histogram Data (Must match original)", padding=10, style="Info.TLabelframe")
        histo_frame.grid(row=4, column=0, sticky="ew", pady=5)
        histo_frame.grid_columnconfigure(0, weight=1)
        histo_frame.grid_rowconfigure(0, weight=1)
        self.merge_histo_text = scrolledtext.ScrolledText(histo_frame, wrap=tk.WORD, height=8, font=('Courier New', 9))
        self.merge_histo_text.grid(row=0, column=0, sticky="nsew")
        Tooltip(self.merge_histo_text, "Raw histogram data used to correctly clip buffers during merge. Must match the data from the original split.")

    def create_axis_selection(self, parent):
        axis_frame = ttk.Labelframe(parent, text="2. Axis to Process", padding=10, style="Info.TLabelframe")
        y_radio = ttk.Radiobutton(axis_frame, text="Y-Axis", variable=self.axis_var, value='Y')
        y_radio.pack(side=tk.LEFT, padx=10)
        Tooltip(y_radio, "Process the point cloud along the Y-axis (North-South).")
        x_radio = ttk.Radiobutton(axis_frame, text="X-Axis", variable=self.axis_var, value='X')
        x_radio.pack(side=tk.LEFT, padx=10)
        Tooltip(x_radio, "Process the point cloud along the X-axis (East-West).")
        return axis_frame, y_radio, x_radio

    def create_boundaries_inputs(self, parent):
        bounds_frame = ttk.Labelframe(parent, text="3. Overall Project Boundaries", padding=10, style="Info.TLabelframe")
        bounds_frame.columnconfigure((1, 3), weight=1)
        ttk.Label(bounds_frame, text="Min X:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Entry(bounds_frame, textvariable=self.min_x_var).grid(row=0, column=1, sticky="ew", padx=(0,5))
        ttk.Label(bounds_frame, text="Max X:").grid(row=0, column=2, sticky="w", padx=5)
        ttk.Entry(bounds_frame, textvariable=self.max_x_var).grid(row=0, column=3, sticky="ew")
        ttk.Label(bounds_frame, text="Min Y:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(bounds_frame, textvariable=self.min_y_var).grid(row=1, column=1, sticky="ew", pady=5, padx=(0,5))
        ttk.Label(bounds_frame, text="Max Y:").grid(row=1, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(bounds_frame, textvariable=self.max_y_var).grid(row=1, column=3, sticky="ew", pady=5)
        return bounds_frame

    def create_path_entry(self, parent, label, var, row, is_file):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=2)
        entry = ttk.Entry(parent, textvariable=var)
        entry.grid(row=row, column=1, sticky="ew", pady=2, padx=5)
        button = ttk.Button(parent, text="Browse...", command=lambda: self.browse_path(var, is_file), bootstyle="secondary")
        button.grid(row=row, column=2, sticky="e", padx=5, pady=2)
        Tooltip(entry, f"Path to the input {'file' if is_file else 'folder'}.")
        Tooltip(button, f"Browse for the input {'file' if is_file else 'folder'}.")

    def browse_path(self, var, is_file):
        if is_file: path = filedialog.askopenfilename(filetypes=[("LAZ files", "*.laz")])
        else: path = filedialog.askdirectory()
        if path: var.set(path)

    def set_processing_state(self, is_processing):
        self.is_processing = is_processing
        if is_processing:
            self.run_button.config(text="Processing...", state="disabled")
            self.progress.config(mode="indeterminate")
            self.progress.start()
            self.stop_button.config(state="normal")
        else:
            self.run_button.config(text="Run Process")
            self.progress.stop()
            self.progress.config(mode="determinate")
            self.progress['value'] = 0
            self._check_run_button_state()
            self.stop_button.config(state="disabled")

    def start_lasinfo_processing(self):
        if self.is_processing: return
        self.controller.log_frame.log(f"\n{'='*20}\n--- [SPLIT/MERGE] Starting lasinfo Process ---\n{'='*20}")
        self.set_processing_state(True)
        threading.Thread(target=self.run_lasinfo_process, daemon=True, name="LAStools_Info").start()

    def start_processing(self, selected_tab_index):
        if self.is_processing: return

        # 1. Fetch values on Main Thread
        if selected_tab_index == 0:
            ui_values = self.get_split_ui_values()
            target_function = self.run_split_process
            thread_name = "Split_Process"
        else:
            ui_values = self.get_merge_ui_values()
            target_function = self.run_merge_process
            thread_name = "Merge_Process"

        # ... Log setup ...
        process_name = 'Split' if selected_tab_index == 0 else 'Merge'
        self.controller.log_frame.log(f"\n{'='*20}\n--- [SPLIT/MERGE] Starting {process_name} Process ---\n{'='*20}")
        self.set_processing_state(True)

        # 2. Pass values to the thread
        threading.Thread(target=target_function, args=(ui_values,), daemon=True, name=thread_name).start()
    
    def on_lasinfo_complete(self, is_success, error_message):
        self.set_processing_state(False)
        if is_success:
            messagebox.showinfo("Success", "lasinfo process complete. Fields have been auto-populated.")
        else:
            if not self.controller.was_terminated:
                messagebox.showerror("Error", f"An error occurred during lasinfo process:\n{error_message}")
            self.controller.was_terminated = False

    def on_process_complete(self, process_name, is_success):
        self.set_processing_state(False)
        if is_success:
            messagebox.showinfo("Success", f"{process_name} process complete!")
        else:
            if not self.controller.was_terminated:
                 messagebox.showerror("Error", f"An error occurred during the {process_name} process. Please check the log.")
            self.controller.was_terminated = False
            
    def run_lasinfo_process(self):
        is_success = False
        error_message = ""
        try:
            log = self.controller.log_frame.log
            laz_file, lastools_path = self.lasinfo_file_var.get(), self.lastools_path_var.get()
            axis, bin_size = self.lasinfo_axis_var.get(), self.lasinfo_bin_var.get()
            lasinfo_path = os.path.join(lastools_path, "lasinfo64.exe")
            if not os.path.exists(lasinfo_path):
                raise FileNotFoundError(f"lasinfo64.exe not found. Please check the LAStools path in Configuration. Expected at: {lasinfo_path}")
            if not os.path.exists(laz_file):
                raise FileNotFoundError(f"Source LAZ file for auto-populate not found.")
            
            command = [lasinfo_path, "-i", laz_file, "-histo", axis, bin_size]
            
            full_report = _execute_las_command(command, self.controller.log_frame, controller=self.controller, frame_instance=self)

            self.auto_populate_fields(full_report)
            if full_report:
                try:
                    report_filename = os.path.join(os.path.dirname(laz_file), f"{os.path.splitext(os.path.basename(laz_file))[0]}_info_{axis}.txt")
                    log(f"\n--- Saving full report to file ---")
                    with open(report_filename, 'w', encoding='utf-8') as f: f.write(full_report)
                    log(f"    SUCCESS: Report saved to '{report_filename}'")
                except Exception as e:
                    log(f"    WARNING: Could not save report file. Error: {e}")
            log("\n--- lasinfo Process Complete ---")
            is_success = True
        except Exception as e:
            if not self.controller.was_terminated:
                self.controller.log_frame.log(f"\nAN ERROR OCCURRED: {e}")
                error_message = str(e)
        finally:
            self.after(0, self.on_lasinfo_complete, is_success, error_message)

    def auto_populate_fields(self, report_text):
        log = self.controller.log_frame.log
        log("\n--- Auto-populating fields ---")
        min_match = re.search(r"min x y z:\s+(-?[\d\.]+)\s+(-?[\d\.]+)", report_text)
        max_match = re.search(r"max x y z:\s+(-?[\d\.]+)\s+(-?[\d\.]+)", report_text)
        if min_match and max_match:
            self.min_x_var.set(min_match.group(1)); self.min_y_var.set(min_match.group(2))
            self.max_x_var.set(max_match.group(1)); self.max_y_var.set(max_match.group(2))
            log("    SUCCESS: Min/Max boundaries populated.")
        else: log("    WARNING: Could not find Min/Max boundaries in the report.")
        histogram_lines = [line.strip() for line in report_text.split('\n') if line.strip().startswith("bin [")]
        if histogram_lines:
            histogram_block = "\n".join(histogram_lines)
            self.split_histo_text.delete(1.0, tk.END); self.split_histo_text.insert(tk.END, histogram_block)
            self.merge_histo_text.delete(1.0, tk.END); self.merge_histo_text.insert(tk.END, histogram_block)
            log("    SUCCESS: Histogram data populated.")
        else: log("    WARNING: Could not find histogram data in the report.")
        self.split_laz_file_var.set(self.lasinfo_file_var.get())
        log("    SUCCESS: Split LAZ input file path populated.")
        log("    Disabling 'Axis to Process' to prevent mismatches. Use 'Reset' to re-enable.")
        for radio in [self.split_y_axis_radio, self.split_x_axis_radio, self.merge_y_axis_radio, self.merge_x_axis_radio]:
            if radio: radio.config(state="disabled")

    def run_split_process(self, ui_values):
        log = self.controller.log_frame.log
        is_success = False
        try:
            # UNPACK arguments passed from main thread (instead of calling self.get_split_ui_values())
            axis, _, _, _, _, buffer_size, num_tiles, laz_file, lastools_path, histo_data = ui_values
            out_folder = os.path.join(os.path.dirname(laz_file), f"Split_{axis}_{num_tiles}_Tiles")
            log("Step 1: Preparing environment and validating inputs...")
            las2las = os.path.join(lastools_path, "las2las.exe")
            if not os.path.exists(las2las):
                raise FileNotFoundError(f"las2las.exe not found. Please check the LAStools path in Configuration. Expected at: {las2las}")
            if not os.path.exists(laz_file):
                raise FileNotFoundError("Input LAZ file for splitting not found.")
            os.makedirs(out_folder, exist_ok=True)
            log(f"    Output folder: {out_folder}")
            log("Step 2: Calculating tile boundaries from histogram data...")
            histogram = self.parse_histogram_data(histo_data)
            if not histogram: raise ValueError("Could not parse histogram data.")
            min_coord, max_coord = histogram[0]['start'], histogram[-1]['end']
            total_points = sum(item['count'] for item in histogram)
            log(f"    Total points calculated: {total_points:,}")
            points_per_tile = total_points // num_tiles
            log(f"    Target points per tile: ~{points_per_tile:,}")
            tile_boundaries, cumulative_points, tile_num = [], 0, 1
            for bin_data in histogram:
                cumulative_points += bin_data['count']
                if cumulative_points >= (points_per_tile * tile_num) and tile_num < num_tiles:
                    log(f"    Tile {tile_num} ends at {axis}-coordinate: {bin_data['end']}")
                    tile_boundaries.append(bin_data['end']); tile_num += 1
            log(f"Step 3: Splitting file into {num_tiles} buffered tiles...")
            base_filename = os.path.splitext(os.path.basename(laz_file))[0]
            last_max = min_coord
            for i, current_max in enumerate(tile_boundaries + [max_coord]):
                min_orig, max_orig = last_max, current_max
                min_buf = min_orig if i == 0 else min_orig - (buffer_size / 2)
                max_buf = max_orig if i == num_tiles - 1 else max_orig + (buffer_size / 2)
                out_filename = os.path.join(out_folder, f"{base_filename}_{axis}_tile{i + 1}.laz")
                log(f"Processing Tile {i + 1}: {axis}-range [{min_buf:.2f} to {max_buf:.2f}]")
                command = [las2las, "-i", laz_file, "-o", out_filename, f"-keep_{axis.lower()}", str(min_buf), str(max_buf), "-olaz"]
                _execute_las_command(command, self.controller.log_frame, controller=self.controller, frame_instance=self)
                log(f"    SUCCESS: Created {os.path.basename(out_filename)}")
                last_max = current_max
            log("Step 4: Creating buffer zone WKT files...")
            self.create_wkt_files(tile_boundaries, buffer_size, out_folder, base_filename, axis)
            log("\nSplit Process Complete!")
            is_success = True
        except Exception as e:
            if not self.controller.was_terminated:
                log(f"\nAN ERROR OCCURRED: {e}")
            is_success = False
        finally:
            self.after(0, self.on_process_complete, "Split", is_success)

    def create_wkt_files(self, boundaries, buffer, folder, basename, axis):
        log = self.controller.log_frame.log
        min_x, max_x, min_y, max_y = float(self.min_x_var.get()), float(self.max_x_var.get()), float(self.min_y_var.get()), float(self.max_y_var.get())
        for i, b in enumerate(boundaries):
            b_min, b_max = b - (buffer / 2), b + (buffer / 2)
            wkt_file = os.path.join(folder, f"{basename}_buffer_zone_{axis}_{i + 1}.wkt")
            if axis == 'Y': wkt = f"POLYGON(({min_x} {b_max}, {max_x} {b_max}, {max_x} {b_min}, {min_x} {b_min}, {min_x} {b_max}))"
            else: wkt = f"POLYGON(({b_max} {max_y}, {b_max} {min_y}, {b_min} {min_y}, {b_min} {max_y}, {b_max} {max_y}))"
            with open(wkt_file, 'w') as f: f.write(wkt)
            log(f"    SUCCESS: Created {os.path.basename(wkt_file)}")

    def run_merge_process(self):
        log = self.controller.log_frame.log
        is_success = False
        try:
            axis, _, _, _, _, tiles_folder, lastools_path, histo_data = self.get_merge_ui_values()
            log(f"--- Starting Merge Process on {axis}-axis ---")
            log("Step 1: Preparing environment and calculating boundaries...")
            las2las, lasmerge = os.path.join(lastools_path, "las2las.exe"), os.path.join(lastools_path, "lasmerge.exe")
            if not os.path.exists(las2las) or not os.path.exists(lasmerge):
                raise FileNotFoundError(f"las2las.exe or lasmerge.exe not found. Check LAStools path in Configuration.")
            if not os.path.exists(tiles_folder): raise FileNotFoundError("Classified tiles folder not found.")
            sorted_tiles = sorted([f for f in os.listdir(tiles_folder) if f.lower().endswith('.laz')], key=lambda f: int(re.findall(r'\d+', f)[-1]))
            num_tiles = len(sorted_tiles)
            if num_tiles == 0: raise ValueError("No .laz files found in the specified folder.")
            log(f"    Detected {num_tiles} tiles to merge.")
            temp_dir = tempfile.mkdtemp(prefix="clipped_tiles_")
            log(f"    Temporary folder created at: {temp_dir}")
            histogram = self.parse_histogram_data(histo_data)
            if not histogram: raise ValueError("Could not parse histogram data.")
            min_coord, max_coord = (float(self.min_y_var.get()), float(self.max_y_var.get())) if axis == 'Y' else (float(self.min_x_var.get()), float(self.max_x_var.get()))
            total_points = sum(item['count'] for item in histogram)
            points_per_tile = total_points // num_tiles
            tile_boundaries, cumulative_points, tile_num = [], 0, 1
            for bin_data in histogram:
                cumulative_points += bin_data['count']
                if cumulative_points >= (points_per_tile * tile_num) and tile_num < num_tiles:
                    tile_boundaries.append(bin_data['end']); tile_num += 1
            log("    Tile boundaries calculated from histogram.")
            log("Step 2: Clipping individual tiles...")
            all_boundaries = [min_coord] + tile_boundaries + [max_coord]
            base_filename = os.path.commonprefix(sorted_tiles).rsplit('_', 2)[0] if sorted_tiles else "merged_file"
            log(f"    Base filename detected as: {base_filename}")
            clipped_files = []
            for i in range(num_tiles):
                min_orig, max_orig = all_boundaries[i], all_boundaries[i+1]
                input_tile = os.path.join(tiles_folder, sorted_tiles[i])
                clipped_tile = os.path.join(temp_dir, f"clipped_{i + 1}.laz")
                log(f"Clipping '{os.path.basename(input_tile)}' to range [{min_orig:.2f} to {max_orig:.2f}]")
                _execute_las_command([las2las, "-i", input_tile, f"-keep_{axis.lower()}", str(min_orig), str(max_orig), "-o", clipped_tile, "-olaz"], self.controller.log_frame, controller=self.controller, frame_instance=self)
                clipped_files.append(clipped_tile)
            log("Step 3: Merging clipped tiles...")
            final_output = os.path.join(tiles_folder, f"{base_filename}_merged_{axis}.laz")
            merge_cmd = [lasmerge, "-i"] + clipped_files + ["-o", final_output, "-olaz"]
            log(f"    Final output will be: {os.path.basename(final_output)}")
            _execute_las_command(merge_cmd, self.controller.log_frame, controller=self.controller, frame_instance=self)
            shutil.rmtree(temp_dir)
            log("    SUCCESS: Merged file created and temporary files deleted.")
            log("\nMerge Process Complete!")
            is_success = True
        except Exception as e:
            if not self.controller.was_terminated:
                log(f"\nAN ERROR OCCURRED: {e}")
            is_success = False
        finally:
            self.after(0, self.on_process_complete, "Merge", is_success)
    
    def get_split_ui_values(self):
        try:
            buffer_size = int(self.buffer_size_var.get())
            num_tiles = int(self.split_num_tiles_var.get())
        except ValueError:
            raise ValueError("Buffer Size and Number of Tiles must be valid integers.")
        
        return (self.axis_var.get(), float(self.min_x_var.get()), float(self.max_x_var.get()), float(self.min_y_var.get()), float(self.max_y_var.get()), buffer_size, num_tiles, self.split_laz_file_var.get(), self.lastools_path_var.get(), self.split_histo_text.get(1.0, tk.END))

    def get_merge_ui_values(self):
        return (self.axis_var.get(), float(self.min_x_var.get()), float(self.max_x_var.get()), float(self.min_y_var.get()), float(self.max_y_var.get()), self.merge_tiles_folder_var.get(), self.lastools_path_var.get(), self.merge_histo_text.get(1.0, tk.END))

    def parse_histogram_data(self, raw_data):
        parsed = []
        for line in raw_data.strip().split('\n'):
            match = re.search(r"\[(-?[\d\.]+),(-?[\d\.]+)[\)\]]\s+has\s+(\d+)", line.strip())
            if match: parsed.append({'start': float(match.group(1)), 'end': float(match.group(2)), 'count': int(match.group(3))})
        return parsed