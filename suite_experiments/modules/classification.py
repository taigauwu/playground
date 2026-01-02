import tkinter as tk
import ttkbootstrap as ttk
from tkinter import filedialog, messagebox
import threading
import os
import sys
import tempfile
import json
from pathlib import Path
from gui.base import BaseToolFrame
from gui.widgets import Tooltip
from core.execution import _execute_command, _execute_pdal_pipeline
from utils.files import get_output_filename, get_laz_output_filename

# Constants
FONT_FAMILY = "Segoe UI"

# --- Helper Function for Manual Reclassification ---
def class_assign_from_polygon(input_laz_path, shp_file, log_widget, controller=None, frame_instance=None):
    """Reclassifies the point cloud using an input shapefile containing polygons with assigned Class"""
    suffix = f"_reclass"
    output_path = get_laz_output_filename(input_laz_path, suffix)

    pipeline = [
        {"type": "readers.las", "filename": input_laz_path},
        {
            "type":"filters.overlay",
            "dimension": "Classification",
            "datasource": shp_file,
            "column": "Class"
        },
        {
            "type": "writers.las",
            "filename": output_path,
            "minor_version": 2,
            "dataformat_id": 3,
            "forward": "all",
        }
    ]
    
    log_message = f"> Executing PDAL reclassification pipeline...\n  Input: {os.path.basename(input_laz_path)}\n  Shapefile: {os.path.basename(shp_file)}\n  Output: {os.path.basename(output_path)}\n"
    _execute_pdal_pipeline(pipeline, log_widget, log_message, controller=controller, frame_instance=frame_instance)

    return output_path

# --- Main Classification Frame (The Container) ---
class ClassificationFrame(BaseToolFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Point Cloud Classification")
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        main_pane = ttk.Frame(self.content_frame)
        main_pane.grid(row=0, column=0, sticky="nsew", pady=5)
        main_pane.grid_rowconfigure(0, weight=1)
        main_pane.grid_columnconfigure(0, weight=1)

        self.content_area = ttk.Frame(main_pane)
        self.content_area.grid(row=0, column=0, sticky="nsew")
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)

        self.tool_frames = {}
        
        # Initialize sub-frames
        # We pass 'self' (ClassificationFrame) to FlaiFrame so it can access parent methods if needed
        self.pipeline_frame = PipelineClassificationFrame(self.content_area, controller)
        self.flai_frame = FlaiFrame(self.content_area, controller, self)
        self.manual_frame = ManualReclassFrame(self.content_area, controller)

        self.tool_frames[PipelineClassificationFrame.__name__] = self.pipeline_frame
        self.tool_frames[FlaiFrame.__name__] = self.flai_frame
        self.tool_frames[ManualReclassFrame.__name__] = self.manual_frame

        for frame in self.tool_frames.values():
            frame.grid(row=0, column=0, sticky="nsew")

    def show_sub_tool(self, sub_frame_class_name, new_title=None):
        """Shows a specific tool frame and updates the title."""
        frame = self.tool_frames.get(sub_frame_class_name)
        if frame:
            if new_title:
                self.title_label.config(text=new_title)
            frame.tkraise()
        else:
            print(f"Error: Could not find sub-frame {sub_frame_class_name}")

# --- Sub-Frame 1: Manual Reclassification ---
class ManualReclassFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.input_laz_path = tk.StringVar()
        self.shp_file_path = tk.StringVar()
        self.is_processing = False
        self.create_widgets()
        
        self.input_laz_path.trace_add("write", self._check_run_button_state)
        self.shp_file_path.trace_add("write", self._check_run_button_state)

    def _check_run_button_state(self, *args):
        if self.is_processing: return
        laz_ok = os.path.isfile(self.input_laz_path.get())
        shp_ok = os.path.isfile(self.shp_file_path.get())
        self.run_button.config(state="normal" if laz_ok and shp_ok else "disabled")

    def create_widgets(self):
        self.grid_columnconfigure(0, weight=1)

        input_frame = ttk.Labelframe(self, text="1. Select Input Files", padding=10, style="Info.TLabelframe")
        input_frame.grid(row=0, column=0, sticky="ew")
        input_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(input_frame, text="Input point cloud file (.laz):").grid(row=0, column=0, sticky="w", padx=5, pady=10)
        laz_entry_frame = ttk.Frame(input_frame)
        laz_entry_frame.grid(row=0, column=1, columnspan=2, sticky="ew")
        laz_entry_frame.columnconfigure(0, weight=1)
        ttk.Entry(laz_entry_frame, textvariable=self.input_laz_path).grid(row=0, column=0, sticky="ew", padx=5)
        ttk.Button(laz_entry_frame, text="Browse...", command=self.browse_laz, bootstyle="secondary").grid(row=0, column=1, padx=5)

        ttk.Label(input_frame, text="Input reclassification shape file (.shp):").grid(row=1, column=0, sticky="w", padx=5, pady=10)
        shp_entry_frame = ttk.Frame(input_frame)
        shp_entry_frame.grid(row=1, column=1, columnspan=2, sticky="ew")
        shp_entry_frame.columnconfigure(0, weight=1)
        ttk.Entry(shp_entry_frame, textvariable=self.shp_file_path).grid(row=1, column=0, sticky="ew", padx=5)
        ttk.Button(shp_entry_frame, text="Browse...", command=self.browse_shp, bootstyle="secondary").grid(row=1, column=1, padx=5)

        run_frame = ttk.Labelframe(self, text="2. Run Process", padding=10, style="Info.TLabelframe")
        run_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        run_container = ttk.Frame(run_frame)
        run_container.grid(row=0, column=0, sticky="w", pady=5)

        self.run_button = ttk.Button(run_container, text="Run Reclassification", command=self.start_reclass_thread, bootstyle="primary", state="disabled")
        self.run_button.pack(side="left", padx=(0, 10))
        Tooltip(self.run_button, "Execute the reclassification process using the selected files.")
        self.progress = ttk.Progressbar(run_container, orient="horizontal", length=300, mode="determinate", bootstyle="primary")
        self.progress.pack(side="left")

        reset_frame = ttk.Frame(self)
        reset_frame.grid(row=2, column=0, sticky="e", pady=(10,0))
        
        self.stop_button = ttk.Button(reset_frame, text="Stop Process", command=lambda: self.controller.terminate_frame_process(self), bootstyle="secondary", state="disabled")
        self.stop_button.pack(side="left", padx=(0, 5))
        Tooltip(self.stop_button, "Forcefully stop the current running process.")

        reset_btn = ttk.Button(reset_frame, text="Reset All", command=self.reset_ui, bootstyle="secondary-outline")
        reset_btn.pack(side="left")
        Tooltip(reset_btn, "Clear all input fields.")

    def reset_ui(self):
        self.input_laz_path.set("")
        self.shp_file_path.set("")
        self.controller.log_frame.log("Manual Reclassification tool has been reset.")

    def browse_laz(self):
        path = filedialog.askopenfilename(filetypes=[("LAZ files", "*.laz")])
        if path: self.input_laz_path.set(path)

    def browse_shp(self):
        path = filedialog.askopenfilename(filetypes=[("Shapefiles", "*.shp"), ("All files", "*.*")])
        if path: self.shp_file_path.set(path)

    def set_processing_state(self, is_processing):
        self.is_processing = is_processing
        if is_processing:
            self.run_button.config(text="Processing...", state="disabled")
            self.progress.config(mode="indeterminate")
            self.progress.start()
            self.stop_button.config(state="normal")
        else:
            self.run_button.config(text="Run Reclassification")
            self.progress.stop()
            self.progress.config(mode="determinate", value=0)
            self._check_run_button_state()
            self.stop_button.config(state="disabled")

    def start_reclass_thread(self):
        if self.is_processing: return
        self.controller.log_frame.log(f"\n{'='*20}\n--- [MANUAL RECLASS] Starting Reclassification ---\n{'='*20}")
        self.set_processing_state(True)
        threading.Thread(target=self.run_reclassification, daemon=True, name="Manual_Reclass").start()

    def on_reclass_complete(self, is_success, message):
        self.set_processing_state(False)
        if is_success:
            messagebox.showinfo("Success", message)
        else:
            if not self.controller.was_terminated:
                messagebox.showerror("Error", message)
        self.controller.was_terminated = False

    def run_reclassification(self):
        is_success = False
        message = ""
        try:
            output_path = class_assign_from_polygon(self.input_laz_path.get(), self.shp_file_path.get(), self.controller.log_frame, controller=self.controller, frame_instance=self)
            is_success = True
            message = f"Reclassification complete!\nOutput saved to: {os.path.basename(output_path)}"
        except Exception as e:
            if not self.controller.was_terminated:
                is_success = False
                message = f"Reclassification Failed:\n{e}"
        finally:
            self.after(0, self.on_reclass_complete, is_success, message)

# --- Sub-Frame 2: Pipeline Classification ---
class PipelineClassificationFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.setup_variables()
        self.create_widgets()
        self._check_pipeline_run_buttons_state()
        
    def setup_variables(self):
        self.input_folder_var, self.denoised_file_var = tk.StringVar(), tk.StringVar()
        self.single_file_path_var = tk.StringVar()
        self.batch_mode_step1 = tk.BooleanVar(value=False)
        self.batch_mode_step3 = tk.BooleanVar(value=False)
        self.input_files_list = []
        self.input_files_list_step3 = []
        self.run_buttons, self.progress_bars = {}, {}
        self.stop_buttons = {}
        self.current_step, self.is_processing = None, False
        self.decimation_var = tk.StringVar(value="2")
        self.reso_var_step2 = tk.StringVar(value="US Feet (1.0)")
        self.window_var_step2 = tk.StringVar(value="103")
        self.reso_var_step3 = tk.StringVar(value="US Feet (1.0)")
        self.slope_var_step3 = tk.StringVar(value="0.05")
        self.window_var_step3 = tk.StringVar(value="25")
        self.threshold_var_step3 = tk.StringVar(value="0.20")

        self.single_file_path_var.trace_add("write", self._check_pipeline_run_buttons_state)
        self.input_folder_var.trace_add("write", self._check_pipeline_run_buttons_state)
        self.input_folder_var_step3 = tk.StringVar()
        self.input_folder_var_step3.trace_add("write", self._check_pipeline_run_buttons_state)
        self.denoised_file_var.trace_add("write", self._check_pipeline_run_buttons_state)

    def _check_pipeline_run_buttons_state(self, *args):
        if self.is_processing: return
        
        if self.batch_mode_step1.get():
            step1_ok = bool(self.input_files_list)
        else:
            step1_ok = os.path.isfile(self.single_file_path_var.get())

        if 1 in self.run_buttons: self.run_buttons[1].config(state="normal" if step1_ok else "disabled")
        
        step2_ok = os.path.isfile(self.denoised_file_var.get())
        if 2 in self.run_buttons: self.run_buttons[2].config(state="normal" if step2_ok else "disabled")
        
        if self.batch_mode_step3.get():
            step3_ok = bool(self.input_files_list_step3)
        else:
            step3_ok = os.path.isfile(self.denoised_file_var.get())
        
        if 3 in self.run_buttons: self.run_buttons[3].config(state="normal" if step3_ok else "disabled")

    def create_widgets(self):
        notebook = ttk.Notebook(self)
        notebook.grid(row=0, column=0, sticky="nsew")
        self.step1_frame = ttk.Frame(notebook, padding=20)
        self.step2_frame = ttk.Frame(notebook, padding=20)
        self.step3_frame = ttk.Frame(notebook, padding=20)
        notebook.add(self.step1_frame, text="STEP 1: Denoise")
        notebook.add(self.step2_frame, text="STEP 2: Test Parameters")
        notebook.add(self.step3_frame, text="STEP 3: Classify Points")
        self.create_step1_widgets(self.step1_frame)
        self.create_step2_widgets(self.step2_frame)
        self.create_step3_widgets(self.step3_frame)

    def create_path_entry(self, parent, label_text, text_variable):
        container = ttk.Frame(parent)
        container.pack(fill='x', expand=True, pady=5)
        
        label = ttk.Label(container, text=label_text)
        label.pack(side='top', anchor='w')

        entry_frame = ttk.Frame(container)
        entry_frame.pack(fill='x', expand=True)
        entry_frame.grid_columnconfigure(0, weight=1)

        entry = ttk.Entry(entry_frame, textvariable=text_variable)
        entry.grid(row=0, column=0, sticky="ew")
        
        browse_button = ttk.Button(
            entry_frame, text="Browse...", bootstyle="secondary",
            command=lambda tv=text_variable: self.browse_file(tv)
        )
        browse_button.grid(row=0, column=1, padx=(10, 0))
        return entry, browse_button

    def browse_file(self, text_variable, title='Select a Lidar File'):
        initial_dir = os.path.dirname(self.input_folder_var.get()) if self.input_folder_var.get() else os.getcwd()
        filepath = filedialog.askopenfilename(title=title, initialdir=initial_dir, filetypes=(("LAZ files", "*.laz"),))
        if filepath:
            text_variable.set(filepath)
            self.controller.log_frame.log(f"Selected file: {filepath}")

    def browse_folder_step1(self):
        directory = filedialog.askdirectory(title="Select a folder with LAZ files")
        if directory:
            laz_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith('.laz')]
            if laz_files:
                self.input_files_list = laz_files
                self.input_folder_var.set(f"{len(laz_files)} .laz files found in '{os.path.basename(directory)}'")
            else:
                self.input_files_list.clear()
                self.input_folder_var.set("No .laz files found in selected folder.")
                messagebox.showwarning("No Files Found", "The selected folder does not contain any .laz files.")
        else:
            self.input_files_list.clear()
            self.input_folder_var.set("")
        self._check_pipeline_run_buttons_state()
        
    def reset_ui(self):
        self.single_file_path_var.set("")
        self.input_folder_var.set("")
        self.input_files_list.clear()
        self.denoised_file_var.set("")
        self.input_folder_var_step3.set("")
        self.input_files_list_step3.clear()
        self.decimation_var.set("2")
        self.reso_var_step2.set("US Feet (1.0)")
        self.window_var_step2.set("103")
        self.reso_var_step3.set("US Feet (1.0)")
        self.slope_var_step3.set("0.05")
        self.window_var_step3.set("25")
        self.threshold_var_step3.set("0.20")
        self.batch_mode_step1.set(False)
        self.batch_mode_step3.set(False)
        self._toggle_input_mode_step1()
        self._toggle_input_mode_step3()
        self.controller.log_frame.log("PDAL Pipeline tool has been reset.")

    def _toggle_input_mode_step1(self):
        is_batch = self.batch_mode_step1.get()
        self.single_file_frame_step1.pack_forget() if is_batch else self.single_file_frame_step1.pack(fill='x')
        self.folder_frame_step1.pack(fill='x') if is_batch else self.folder_frame_step1.pack_forget()
        self._check_pipeline_run_buttons_state()

    def create_step1_widgets(self, parent):
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text="Denoise, DTM, and Stat Files Generator", font=(FONT_FAMILY, 14, "bold")).pack(anchor='w', pady=(0, 20))
        
        input_frame = ttk.Labelframe(parent, text="1. Select Input", padding=10, style="Info.TLabelframe")
        input_frame.pack(fill='x', pady=(0, 10))
        input_frame.columnconfigure(0, weight=1)

        batch_toggle = ttk.Checkbutton(input_frame, text="Batch Mode (Process entire folder)", variable=self.batch_mode_step1, command=self._toggle_input_mode_step1, bootstyle="round-toggle")
        batch_toggle.pack(anchor='w', pady=(0, 10))
        Tooltip(batch_toggle, "Check this to process all .laz files in a selected folder. Uncheck to process a single file.")
        
        self.single_file_frame_step1 = ttk.Frame(input_frame)
        self.single_file_frame_step1.pack(fill='x')
        entry_s, browse_s = self.create_path_entry(self.single_file_frame_step1, "Input georeferenced .laz file:", self.single_file_path_var)

        self.folder_frame_step1 = ttk.Frame(input_frame)
        self.folder_frame_step1.pack(fill='x')
        entry_f, browse_f = self.create_path_entry(self.folder_frame_step1, "Input folder with georeferenced .laz files:", self.input_folder_var)
        entry_f.config(state="readonly")
        browse_f.config(command=self.browse_folder_step1)
        self.folder_frame_step1.pack_forget()
        
        run_frame = ttk.Labelframe(parent, text="2. Run Process", padding=10, style="Info.TLabelframe")
        run_frame.pack(fill='x', pady=(10,0))
        run_container = ttk.Frame(run_frame)
        run_container.pack(anchor='w')
        self.run_buttons[1] = ttk.Button(run_container, text="Run Denoise", bootstyle="primary", command=lambda: self.start_run_process(1))
        self.run_buttons[1].pack(side='left', padx=(0, 10))
        Tooltip(self.run_buttons[1], "Run the denoising process and generate DSM/Stat raster files.")
        self.progress_bars[1] = ttk.Progressbar(run_container, orient="horizontal", length=300, mode="determinate", bootstyle="primary")
        self.progress_bars[1].pack(side='left')

        spacer = ttk.Frame(parent)
        spacer.pack(fill='both', expand=True)
        action_frame = ttk.Frame(parent)
        action_frame.pack(side='bottom', anchor='se')
        
        stop_btn = ttk.Button(action_frame, text="Stop Process", command=lambda: self.controller.terminate_frame_process(self), bootstyle="secondary", state="disabled")
        stop_btn.pack(side="left", padx=(0, 5))
        Tooltip(stop_btn, "Forcefully stop the current running process.")
        self.stop_buttons[1] = stop_btn
        
        reset_btn = ttk.Button(action_frame, text="Reset All", command=self.reset_ui, bootstyle="secondary-outline")
        reset_btn.pack(side="left")
        Tooltip(reset_btn, "Reset all steps and fields in the PDAL Pipeline tool.")

    def create_step2_widgets(self, parent):
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text="Test Parameters DTM Generator", font=(FONT_FAMILY, 14, "bold")).pack(anchor='w', pady=(0, 20))
        
        input_frame = ttk.Labelframe(parent, text="1. Select Input File", padding=10, style="Info.TLabelframe")
        input_frame.pack(fill='x', pady=(0, 10))
        self.create_path_entry(input_frame, "Input denoised LAZ file (from Step 1 or browse manually) (.laz):", self.denoised_file_var)
        
        params_frame = ttk.Labelframe(parent, text="2. Set the Parameters", padding=10, style="Info.TLabelframe")
        params_frame.pack(fill='x', pady=(10,0))
        params_frame.grid_columnconfigure((0, 1, 2), weight=1)

        ttk.Label(params_frame, text="Decimation Step:").grid(row=0, column=0, padx=(0,10), pady=5, sticky="w")
        deci_entry = ttk.Entry(params_frame, textvariable=self.decimation_var); deci_entry.grid(row=1, column=0, sticky="ew", padx=(0,10)); Tooltip(deci_entry, "The step used to thin the point cloud for faster testing (e.g., a value of 2 keeps every 2nd point).")
        ttk.Label(params_frame, text="Resolution (Reso):").grid(row=0, column=1, padx=(0,10), pady=5, sticky="w")
        reso_combo = ttk.Combobox(params_frame, textvariable=self.reso_var_step2, values=["US Feet (1.0)", "Meters (0.25)"], state="readonly"); reso_combo.grid(row=1, column=1, sticky="ew", padx=(0,10)); Tooltip(reso_combo, "The resolution of the output test DTM rasters.")
        ttk.Label(params_frame, text="Window Size:").grid(row=0, column=2, pady=5, sticky="w")
        win_entry = ttk.Entry(params_frame, textvariable=self.window_var_step2); win_entry.grid(row=1, column=2, sticky="ew"); Tooltip(win_entry, "The SMRF window size parameter to use for all test runs.")

        run_frame = ttk.Labelframe(parent, text="3. Run Process", padding=10, style="Info.TLabelframe")
        run_frame.pack(fill='x', pady=(10,0))
        run_container = ttk.Frame(run_frame)
        run_container.pack(anchor='w')
        self.run_buttons[2] = ttk.Button(run_container, text="Run Test Parameters", bootstyle="primary", command=lambda: self.start_run_process(2))
        self.run_buttons[2].pack(side='left', padx=(0, 10))
        Tooltip(self.run_buttons[2], "Run the test process, which generates multiple DTMs using different slope parameters.")
        self.progress_bars[2] = ttk.Progressbar(run_container, orient="horizontal", length=300, mode="determinate", bootstyle="primary")
        self.progress_bars[2].pack(side='left')

        spacer = ttk.Frame(parent)
        spacer.pack(fill='both', expand=True)
        action_frame = ttk.Frame(parent)
        action_frame.pack(side='bottom', anchor='se')

        stop_btn = ttk.Button(action_frame, text="Stop Process", command=lambda: self.controller.terminate_frame_process(self), bootstyle="secondary", state="disabled")
        stop_btn.pack(side="left", padx=(0, 5))
        Tooltip(stop_btn, "Forcefully stop the current running process.")
        self.stop_buttons[2] = stop_btn

        reset_btn = ttk.Button(action_frame, text="Reset All", command=self.reset_ui, bootstyle="secondary-outline")
        reset_btn.pack(side="left")
        Tooltip(reset_btn, "Reset all steps and fields in the PDAL Pipeline tool.")

    def create_step3_widgets(self, parent):
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text="Final Point Cloud Classification", font=(FONT_FAMILY, 14, "bold")).pack(anchor='w', pady=(0, 20))
        
        input_frame = ttk.Labelframe(parent, text="1. Select Input", padding=10, style="Info.TLabelframe")
        input_frame.pack(fill='x', pady=(0, 10))
        input_frame.columnconfigure(0, weight=1)

        batch_toggle_step3 = ttk.Checkbutton(input_frame, text="Batch Mode (Process entire folder)", variable=self.batch_mode_step3, command=self._toggle_input_mode_step3, bootstyle="round-toggle")
        batch_toggle_step3.pack(anchor='w', pady=(0, 10))
        Tooltip(batch_toggle_step3, "Check this to process all .laz files in a selected folder. Uncheck to process a single file.")

        self.single_file_frame_step3 = ttk.Frame(input_frame)
        self.single_file_frame_step3.pack(fill='x')
        self.create_path_entry(self.single_file_frame_step3, "Input denoised LAZ file (from Step 1 or browse manually):", self.denoised_file_var)

        self.folder_frame_step3 = ttk.Frame(input_frame)
        self.folder_frame_step3.pack(fill='x')
        entry_f, browse_f = self.create_path_entry(self.folder_frame_step3, "Input folder with denoised .laz files:", self.input_folder_var_step3)
        entry_f.config(state="readonly")
        browse_f.config(command=self.browse_folder_step3)
        self.folder_frame_step3.pack_forget()
        
        params_frame = ttk.Labelframe(parent, text="2. Set the Parameters", padding=10, style="Info.TLabelframe")
        params_frame.pack(fill='x', pady=(10,0))
        params_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ttk.Label(params_frame, text="Resolution (Reso):").grid(row=0, column=0, padx=(0,10), pady=5, sticky="w")
        reso_combo = ttk.Combobox(params_frame, textvariable=self.reso_var_step3, values=["US Feet (1.0)", "Meters (0.25)"], state="readonly"); reso_combo.grid(row=1, column=0, sticky="ew", padx=(0,10)); Tooltip(reso_combo, "The resolution for the final DTM created from the classified ground points.")
        ttk.Label(params_frame, text="Slope:").grid(row=0, column=1, padx=(0,10), pady=5, sticky="w")
        slope_entry = ttk.Entry(params_frame, textvariable=self.slope_var_step3); slope_entry.grid(row=1, column=1, sticky="ew", padx=(0,10)); Tooltip(slope_entry, "The SMRF slope parameter, chosen based on the results from Step 2.")
        ttk.Label(params_frame, text="Window Size:").grid(row=0, column=2, padx=(0,10), pady=5, sticky="w")
        win_entry = ttk.Entry(params_frame, textvariable=self.window_var_step3); win_entry.grid(row=1, column=2, sticky="ew", padx=(0,10)); Tooltip(win_entry, "The SMRF window size parameter for the final classification.")
        ttk.Label(params_frame, text="Threshold:").grid(row=0, column=3, pady=5, sticky="w")
        thresh_entry = ttk.Entry(params_frame, textvariable=self.threshold_var_step3); thresh_entry.grid(row=1, column=3, sticky="ew"); Tooltip(thresh_entry, "The SMRF elevation threshold parameter for the final classification.")

        run_frame = ttk.Labelframe(parent, text="3. Run Process", padding=10, style="Info.TLabelframe")
        run_frame.pack(fill='x', pady=(10,0))
        run_container = ttk.Frame(run_frame)
        run_container.pack(anchor='w')
        self.run_buttons[3] = ttk.Button(run_container, text="Run Classify Points", bootstyle="primary", command=lambda: self.start_run_process(3))
        self.run_buttons[3].pack(side='left', padx=(0, 10))
        Tooltip(self.run_buttons[3], "Run the final ground classification process using the specified parameters.")
        self.progress_bars[3] = ttk.Progressbar(run_container, orient="horizontal", length=300, mode="determinate", bootstyle="primary")
        self.progress_bars[3].pack(side='left')

        spacer = ttk.Frame(parent)
        spacer.pack(fill='both', expand=True)
        action_frame = ttk.Frame(parent)
        action_frame.pack(side='bottom', anchor='se')

        stop_btn = ttk.Button(action_frame, text="Stop Process", command=lambda: self.controller.terminate_frame_process(self), bootstyle="secondary", state="disabled")
        stop_btn.pack(side="left", padx=(0, 5))
        Tooltip(stop_btn, "Forcefully stop the current running process.")
        self.stop_buttons[3] = stop_btn

        reset_btn = ttk.Button(action_frame, text="Reset All", command=self.reset_ui, bootstyle="secondary-outline")
        reset_btn.pack(side="left")
        Tooltip(reset_btn, "Reset all steps and fields in the PDAL Pipeline tool.")

    def set_processing_state(self, is_processing):
        self.is_processing = is_processing
        progress_bar = self.progress_bars.get(self.current_step)
        
        active_stop_button = self.stop_buttons.get(self.current_step)

        if is_processing:
            for btn in self.run_buttons.values(): btn.config(state="disabled")
            if self.current_step in self.run_buttons:
                self.run_buttons[self.current_step].config(text="Processing...")
            if progress_bar:
                progress_bar.config(mode="indeterminate")
                progress_bar.start()
            if active_stop_button:
                active_stop_button.config(state="normal")
        else:
            if progress_bar:
                progress_bar.stop()
                progress_bar.config(mode="determinate", value=0)
            self.run_buttons[1].config(text="Run Denoise")
            self.run_buttons[2].config(text="Run Test Parameters")
            self.run_buttons[3].config(text="Run Classify Points")
            self._check_pipeline_run_buttons_state()
            for btn in self.stop_buttons.values():
                btn.config(state="disabled")

    def start_run_process(self, step_number):
        if self.is_processing: return
        self.current_step = step_number
        self.controller.log_frame.log(f"\n{'='*20}\n--- [PDAL PIPELINE] Starting Step {step_number} ---\n{'='*20}")
        self.set_processing_state(True)
        target_functions = {1: self.execute_step1_denoise, 2: self.execute_step2_test, 3: self.execute_step3_classify}
        target_function = target_functions.get(step_number)
        if target_function:
            threading.Thread(target=target_function, daemon=True, name=f"PDAL_Step_{step_number}").start()
    
    def _toggle_input_mode_step3(self):
        is_batch = self.batch_mode_step3.get()
        self.single_file_frame_step3.pack_forget() if is_batch else self.single_file_frame_step3.pack(fill='x')
        self.folder_frame_step3.pack(fill='x') if is_batch else self.folder_frame_step3.pack_forget()
        self._check_pipeline_run_buttons_state()

    def browse_folder_step3(self):
        directory = filedialog.askdirectory(title="Select a folder with denoised LAZ files")
        if directory:
            laz_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith('.laz')]
            if laz_files:
                self.input_files_list_step3 = laz_files
                self.input_folder_var_step3.set(f"{len(laz_files)} .laz files found in '{os.path.basename(directory)}'")
            else:
                self.input_files_list_step3.clear()
                self.input_folder_var_step3.set("No .laz files found in selected folder.")
                messagebox.showwarning("No Files Found", "The selected folder does not contain any .laz files.")
        else:
            self.input_files_list_step3.clear()
            self.input_folder_var_step3.set("")
        self._check_pipeline_run_buttons_state()

    # In a production app, this import logic should likely be in the 'utils' or 'core' package, 
    # but we keep it here for now as it's specific to the classification pipeline logic.
    try:
        import laspy
    except ImportError:
        laspy = None

    def _process_laz_file_stats(self, file_path):
        if not self.laspy:
             self.controller.log_frame.log("Error: 'laspy' is not installed. Cannot calculate stats.")
             return None, None

        log = self.controller.log_frame.log
        try:
            log("Reading LAZ file for statistics...")
            with self.laspy.open(file_path, mode='r') as file_handler: las_data = file_handler.read()
            z_coords = las_data.z
            min_z, max_z = int(z_coords.min()), int(z_coords.max()) + 1
            z_bins = range(min_z, max_z + 1, 1)
            counts, _ = pd.cut(z_coords, bins=z_bins, include_lowest=True, right=False, retbins=True)
            counts = counts.value_counts().sort_index()
            bin_df = pd.DataFrame({'bin': [int(b.left) for b in counts.index], 'count': counts.values})
            filtered_df = bin_df[bin_df['count'] >= 100].reset_index(drop=True)
            if not filtered_df.empty:
                first_bin, last_bin = filtered_df['bin'].iloc[0], filtered_df['bin'].iloc[-1]
                log(f"Automatically determined Z-Range: [{first_bin}, {last_bin}]")
                return first_bin, last_bin
            else:
                log("Warning: Filtered DataFrame is empty. Using full range.")
                return None, None
        except Exception as e:
            log(f"An error occurred during statistics processing: {e}")
            return None, None
            
    def on_pipeline_step_complete(self, step_number, is_success, message):
        """Handles UI updates after a pipeline step is complete."""
        self.set_processing_state(False)
        if is_success:
            if "failed" in message:
                messagebox.showwarning("Warning", message)
            else:
                messagebox.showinfo("Success", message)
        elif message and not self.controller.was_terminated:
            messagebox.showerror("Error", message)
        
        self.controller.was_terminated = False

    def execute_step1_denoise(self):
        log_frame = self.controller.log_frame
        is_success = False
        message = ""
        try:
            if self.batch_mode_step1.get():
                files_to_process = self.input_files_list
                if not files_to_process:
                    raise ValueError("Input folder not selected or is empty.")
            else:
                single_file = self.single_file_path_var.get()
                if not os.path.isfile(single_file):
                    raise ValueError("Please select a valid input LAZ file.")
                files_to_process = [single_file]
            
            total_files = len(files_to_process)
            if not files_to_process or not any(files_to_process):
                raise ValueError("No valid input files selected.")

            total_files = len(files_to_process)
            all_files_succeeded = True

            for i, input_path_str in enumerate(files_to_process):
                log_frame.log(f"\n--- ({i+1}/{total_files}) Processing: {os.path.basename(input_path_str)} ---")
                input_path = Path(input_path_str)
                first_bin, last_bin = self._process_laz_file_stats(input_path_str)
                range_filter = f"Z[{first_bin}:{last_bin}]" if first_bin is not None and last_bin is not None else "Z[:]"
                
                output_denoised_laz = input_path.with_name(f"{input_path.stem}_denoised.laz")
                output_dsm_tif = input_path.with_name(f"{input_path.stem}_dsm.tif")
                output_stat_tif = input_path.with_name(f"{input_path.stem}_stat.tif")

                try:
                    pipeline = [str(input_path), {"type": "filters.range", "limits": range_filter}, {"type": "filters.assign", "assignment": "Classification[:]=0"}, {"type": "writers.las", "filename": str(output_denoised_laz), "minor_version": "4"}]
                    _execute_pdal_pipeline(pipeline, log_frame, "Denoising...", controller=self.controller, frame_instance=self)
                    
                    pipeline = [str(output_denoised_laz), {"type": "writers.gdal", "filename": str(output_dsm_tif), "resolution": 1.0, "output_type": "max"}]
                    _execute_pdal_pipeline(pipeline, log_frame, "Creating DSM...", controller=self.controller, frame_instance=self)
                    
                    pipeline = [str(output_denoised_laz), {"type": "writers.gdal", "filename": str(output_stat_tif), "resolution": 1.0, "output_type": "min,count"}]
                    _execute_pdal_pipeline(pipeline, log_frame, "Creating STAT...", controller=self.controller, frame_instance=self)
                except Exception as file_error:
                    all_files_succeeded = False
                    if self.controller.was_terminated: break
                    log_frame.log(f"--- ERROR processing {input_path.name}: {file_error} ---")
            
            self.after(0, self.denoised_file_var.set, "")
            is_success = True
            message = f"Step 1 completed for all {total_files} files!" if all_files_succeeded else "Step 1 finished, but one or more files failed."
        except Exception as e:
            if not self.controller.was_terminated:
                log_frame.log(f"A critical error occurred: {e}")
                message = f"A critical error occurred:\n{e}"
        finally:
            self.after(0, self.on_pipeline_step_complete, 1, is_success, message)

    def execute_step2_test(self):
        is_success = False
        message = ""
        log_frame = self.controller.log_frame
        try:
            input_path = self.denoised_file_var.get()
            if not input_path or not os.path.exists(input_path):
                raise ValueError("Denoised input file not found. Please run Step 1 or browse for a file.")
            thinned_laz_path = get_laz_output_filename(input_path, "_thinned")
            decimation, reso, window = self.decimation_var.get(), ("1.0" if self.reso_var_step2.get() == "US Feet (1.0)" else "0.25"), self.window_var_step2.get()
            cmd_decimate = ["pdal", "translate", input_path, thinned_laz_path, "decimation", f"--filters.decimation.step={decimation}"]
            if not self.run_command_in_thread(cmd_decimate, f"Executing Decimation...\nOutput: {os.path.basename(thinned_laz_path)}", "Decimation successful."):
                raise RuntimeError("Decimation step failed.")
            
            all_slopes_successful = True
            for slope in ["0.05", "0.15", "0.25", "0.35"]:
                log_frame.log("\n" + "-"*20)
                output_tif = Path(thinned_laz_path).with_name(f"{Path(thinned_laz_path).stem}_dtm_pt{slope.replace('.', '')}.tif")
                pipeline = [thinned_laz_path, {"type": "filters.smrf", "scalar": 1.25, "slope": slope, "threshold": 0.2, "window": window}, {"type": "filters.range", "limits": "Classification[2:2]"}, {"type": "writers.gdal", "filename": str(output_tif), "resolution": reso, "output_type": "mean"}]
                try:
                    _execute_pdal_pipeline(pipeline, log_frame, f"Testing slope {slope}...", controller=self.controller, frame_instance=self)
                except Exception:
                    all_slopes_successful = False
                    if self.controller.was_terminated: break
            
            is_success = True
            message = "Step 2 completed successfully!" if all_slopes_successful else "Step 2 finished, but some slope tests failed."
        except Exception as e:
            if not self.controller.was_terminated:
                message = f"An error occurred in Step 2:\n{e}"
        finally:
            self.after(0, self.on_pipeline_step_complete, 2, is_success, message)

    def execute_step3_classify(self):
        is_success = False
        message = ""
        log_frame = self.controller.log_frame
        try:
            if self.batch_mode_step3.get():
                files_to_process = self.input_files_list_step3
                if not files_to_process:
                    raise ValueError("Batch mode is on, but no folder is selected or the folder is empty.")
            else:
                single_file = self.denoised_file_var.get()
                if not os.path.isfile(single_file):
                    raise ValueError("Please select a valid input denoised LAZ file.")
                files_to_process = [single_file]
            
            reso = "1.0" if self.reso_var_step3.get() == "US Feet (1.0)" else "0.25"
            slope = self.slope_var_step3.get()
            window = self.window_var_step3.get()
            threshold = self.threshold_var_step3.get()
            
            total_files = len(files_to_process)
            all_files_succeeded = True

            for i, input_path in enumerate(files_to_process):
                log_frame.log(f"\n--- ({i+1}/{total_files}) Classifying: {os.path.basename(input_path)} ---")

                slope_for_filename = slope.replace('.', '')
                
                if threshold != "0.20":
                    threshold_for_filename = threshold.replace('.', '')
                    suffix = f"_slope{slope_for_filename}_th{threshold_for_filename}_gnd"
                else:
                    suffix = f"_slope{slope_for_filename}_gnd"

                gnd_laz_path = get_laz_output_filename(input_path, suffix)
                dtm_tif_path = get_output_filename(gnd_laz_path, "_dtm").replace(os.path.splitext(gnd_laz_path)[1], ".tif")

                cmd_smrf = ["pdal", "translate", input_path, gnd_laz_path, "smrf", f"--filters.smrf.scalar=1.25", f"--filters.smrf.slope={slope}", f"--filters.smrf.threshold={threshold}", f"--filters.smrf.window={window}", "--filters.smrf.returns=first,last,intermediate,only"]
                
                try:
                    if not self.run_command_in_thread(cmd_smrf, f"Executing SMRF for ground classification...\nOutput: {os.path.basename(gnd_laz_path)}", "Ground classification successful."):
                        raise RuntimeError("SMRF classification step failed.")

                    cmd_dtm = ["pdal", "translate", gnd_laz_path, dtm_tif_path, "range", "-w", "writers.gdal", "--filters.range.limits=Classification[2:2]", f"--writers.gdal.resolution={reso}", "--writers.gdal.output_type=mean"]
                    if not self.run_command_in_thread(cmd_dtm, f"\nExecuting DTM Creation...\nOutput: {os.path.basename(dtm_tif_path)}", "DTM created successfully."):
                        raise RuntimeError("DTM creation step failed.")

                except Exception as file_error:
                    all_files_succeeded = False
                    if self.controller.was_terminated:
                        log_frame.log(f"--- Process for {os.path.basename(input_path)} was terminated by user. ---")
                        break
                    log_frame.log(f"--- ERROR processing {os.path.basename(input_path)}: {file_error} ---")

            is_success = True
            message = f"Step 3 completed successfully for all {total_files} files!" if all_files_succeeded else "Step 3 finished, but one or more files failed."
        except Exception as e:
            if not self.controller.was_terminated:
                message = f"An error occurred in Step 3:\n{e}"
        finally:
            self.after(0, self.on_pipeline_step_complete, 3, is_success, message)
            
    def run_command_in_thread(self, command, log_message, success_message):
        try:
            _execute_command(command, self.controller.log_frame, log_message, controller=self.controller, frame_instance=self)
            self.controller.log_frame.log(f"\n{success_message}")
            return True
        except Exception:
            return False

# --- Sub-Frame 3: FLAI Frame ---
class FlaiFrame(ttk.Frame):
    def __init__(self, parent, controller, classification_frame):
        super().__init__(parent)
        self.controller = controller
        self.classification_frame = classification_frame 
        self.bat_file_path = self.controller.classify_lidar_bat_path_var
        self.folder_path_var = tk.StringVar()
        self.single_file_path_var = tk.StringVar()
        self.batch_mode = tk.BooleanVar(value=False)
        self.unit_override_var = tk.StringVar(value="(Auto-detect)")
        self.UNIT_MAP = {"(Auto-detect)": None, "Meters": "meters", "US Survey Feet": "us-survey-foot", "International Feet": "foot"}
        self.files_list = []
        self.is_processing = False
        self.create_widgets()
        self.single_file_path_var.trace_add("write", self._check_run_button_state)
        self.folder_path_var.trace_add("write", self._check_run_button_state)
        self.bat_file_path.trace_add("write", self._check_run_button_state)

    def _toggle_input_mode(self):
        is_batch = self.batch_mode.get()
        self.single_file_frame.grid_remove() if is_batch else self.single_file_frame.grid()
        self.folder_frame.grid() if is_batch else self.folder_frame.grid_remove()
        self._check_run_button_state()

    def create_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        
        input_container = ttk.Labelframe(self, text="1. Select Input", padding=15, style="Info.TLabelframe")
        input_container.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        input_container.columnconfigure(1, weight=1)

        batch_toggle = ttk.Checkbutton(input_container, text="Batch Mode (Process entire folder)", variable=self.batch_mode, command=self._toggle_input_mode, bootstyle="round-toggle")
        batch_toggle.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        Tooltip(batch_toggle, "Check this to process all .laz files in a selected folder. Uncheck to process a single file.")

        self.single_file_frame = ttk.Frame(input_container)
        self.single_file_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        self.single_file_frame.columnconfigure(1, weight=1)
        ttk.Label(self.single_file_frame, text="Input point cloud file (.laz):").grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Entry(self.single_file_frame, textvariable=self.single_file_path_var, state="readonly").grid(row=0, column=1, sticky="ew", padx=(0, 5))
        self.browse_button_single = ttk.Button(self.single_file_frame, text="Browse...", command=self.browse_laz_file, bootstyle="secondary")
        self.browse_button_single.grid(row=0, column=2, sticky="e")
        
        self.folder_frame = ttk.Frame(input_container)
        self.folder_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        self.folder_frame.columnconfigure(1, weight=1)
        ttk.Label(self.folder_frame, text="Input folder with .laz files:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Entry(self.folder_frame, textvariable=self.folder_path_var, state="readonly").grid(row=0, column=1, sticky="ew", padx=(0, 5))
        self.browse_button_folder = ttk.Button(self.folder_frame, text="Browse...", command=self.browse_laz_folder, bootstyle="secondary")
        self.browse_button_folder.grid(row=0, column=2, sticky="e")
        
        self.folder_frame.grid_remove()

        params_frame = ttk.Labelframe(self, text="2. Set Parameters (Optional)", padding=10, style="Info.TLabelframe")
        params_frame.grid(row=1, column=0, sticky="ew", pady=10)
        params_frame.columnconfigure(1, weight=1)

        ttk.Label(params_frame, text="Unit Override:").grid(row=0, column=0, sticky="w", padx=(0,10))
        unit_combo = ttk.Combobox(params_frame, textvariable=self.unit_override_var, values=list(self.UNIT_MAP.keys()), state="readonly", width=20)
        unit_combo.grid(row=0, column=1, sticky="w")
        Tooltip(unit_combo, "Optional: Force a specific unit. This will skip unit detection from the file header.")

        run_frame = ttk.Labelframe(self, text="3. Run Process", padding=10, style="Info.TLabelframe")
        run_frame.grid(row=2, column=0, sticky="ew", pady=10)
        self.run_container = ttk.Frame(run_frame)
        self.run_container.pack(fill='x')
        self.process_button = ttk.Button(self.run_container, text="Run FLAI", command=self.start_processing_thread, bootstyle="primary", state="disabled")
        self.process_button.pack(side='left', ipady=5, padx=(0, 10))
        Tooltip(self.process_button, "Execute the FLAI classification by running the configured .bat script.")
        self.progress = ttk.Progressbar(self.run_container, orient="horizontal", length=300, mode="determinate", bootstyle="primary")
        self.progress.pack(side="left", padx=5)
        
        reset_frame = ttk.Frame(self)
        reset_frame.grid(row=3, column=0, sticky="e", pady=(10,0))
        
        self.stop_button = ttk.Button(reset_frame, text="Stop Process", command=lambda: self.controller.terminate_frame_process(self), bootstyle="secondary", state="disabled")
        self.stop_button.pack(side="left", padx=(0, 5))
        Tooltip(self.stop_button, "Forcefully stop the current running process.")

        reset_btn = ttk.Button(reset_frame, text="Reset All", command=self.reset_ui, bootstyle="secondary-outline")
        reset_btn.pack(side="left")
        Tooltip(reset_btn, "Clear the input file selection.")

    def reset_ui(self):
        self.single_file_path_var.set("")
        self.folder_path_var.set("")
        self.files_list.clear()
        self.batch_mode.set(False)
        self.unit_override_var.set("(Auto-detect)")
        self._toggle_input_mode()
        self.controller.log_frame.log("FLAI Classification tool has been reset.")

    def _check_run_button_state(self, *args):
        if self.is_processing: return
        bat_ok = os.path.isfile(self.bat_file_path.get())
        if self.batch_mode.get():
            files_ok = bool(self.files_list)
        else:
            files_ok = os.path.isfile(self.single_file_path.get())
        self.process_button.config(state="normal" if bat_ok and files_ok else "disabled")

    def browse_laz_file(self):
        path = filedialog.askopenfilename(title="Select a LAZ file", filetypes=[("LAZ files", "*.laz")])
        if path:
            self.single_file_path.set(path)
        self._check_run_button_state()
        
    def browse_laz_folder(self):
        directory = filedialog.askdirectory(title="Select a folder with LAZ files")
        if directory:
            laz_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith('.laz')]
            if laz_files:
                self.files_list = laz_files
                self.folder_path_var.set(f"{len(laz_files)} .laz files found in '{os.path.basename(directory)}'")
            else:
                self.files_list.clear()
                self.folder_path_var.set("No .laz files found in selected folder.")
                messagebox.showwarning("No Files Found", "The selected folder does not contain any .laz files.")
        else:
            self.files_list.clear()
            self.folder_path_var.set("")
        self._check_run_button_state()

    def set_ui_state(self, is_processing):
        self.is_processing = is_processing
        state = "disabled" if is_processing else "normal"
        if is_processing:
            self.process_button.config(text="Processing...")
            self.progress.config(mode="indeterminate")
            self.progress.start()
            self.stop_button.config(state="normal")
        else:
            self.process_button.config(text="Run FLAI")
            self.progress.stop()
            self.progress.config(mode="determinate", value=0)
            self.stop_button.config(state="disabled")
        
        for widget in (self.browse_button_single, self.browse_button_folder, self.process_button):
            widget.config(state=state)
        self._check_run_button_state()

    def start_processing_thread(self):
        if self.is_processing: return
        self.set_ui_state(True)
        self.controller.log_frame.log(f"\n{'='*20}\n--- [FLAI] Starting Classification ---\n{'='*20}")
        threading.Thread(target=self.run_flai_processing, args=(self.bat_file_path.get(),), daemon=True, name="FLAI_Process").start()
    
    def run_flai_processing(self, bat_path):
        log = self.controller.log_frame
        
        if self.batch_mode.get():
            files_to_process = self.files_list
            if not files_to_process:
                self.after(0, self.on_processing_complete, 0, False, "Batch mode is on, but no folder is selected or it is empty.")
                return
        else:
            single_file = self.single_file_path_var.get()
            if not os.path.isfile(single_file):
                self.after(0, self.on_processing_complete, 0, False, "Please select a valid input LAZ file.")
                return
            files_to_process = [single_file]
        
        total_files = len(files_to_process)
        all_success = True
        final_message = ""

        for i, input_laz in enumerate(files_to_process):
            log.log(f"\n--- ({i+1}/{total_files}) Processing: {os.path.basename(input_laz)} ---")
            temp_bat_filepath = None
            try:
                with open(bat_path, 'r') as f: original_script_content = f.read()
                safe_input_laz = os.path.normpath(input_laz)
                replacement_line = f'set INPUT="{safe_input_laz}"'
                lines, new_lines, found_and_replaced = original_script_content.splitlines(), [], False
                for line in lines:
                    if not found_and_replaced and line.strip().lower().startswith('set input='):
                        new_lines.append(replacement_line)
                        found_and_replaced = True
                        log.log(f"Found and replaced INPUT variable with: {safe_input_laz}")
                    else:
                        new_lines.append(line)
                if not found_and_replaced:
                    log.log("Could not find 'set INPUT=' line. Injecting variable at the top of the script.")
                    try: insert_pos = next(i for i, line in enumerate(new_lines) if line.strip().lower() == '@echo off') + 1
                    except StopIteration: insert_pos = 0
                    new_lines.insert(insert_pos, replacement_line)
                modified_script_content = "\r\n".join(new_lines)
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.bat', newline='') as temp_bat_file:
                    temp_bat_file.write(modified_script_content)
                    temp_bat_filepath = temp_bat_file.name

                unit_display_name = self.unit_override_var.get()
                unit_command_value = self.UNIT_MAP.get(unit_display_name)
                
                command_to_run = [temp_bat_filepath]
                if unit_command_value:
                    command_to_run.append(unit_command_value)
                    log.log(f"Unit override selected: Appending '{unit_command_value}' to the command.")

                _execute_command(
                    command=command_to_run, log_widget=self.controller.log_frame,
                    log_message=f"--- Executing temporary batch script based on {os.path.basename(bat_path)} ---",
                    controller=self.controller, frame_instance=self
                )
            except Exception as e:
                all_success = False
                if self.controller.was_terminated:
                    log.log(f"--- Process for {os.path.basename(input_laz)} was terminated by user. ---")
                    final_message = "Process was terminated by the user."
                    break
                log.log(f"--- ERROR processing {os.path.basename(input_laz)}: {e} ---")
            finally:
                if temp_bat_filepath and os.path.exists(temp_bat_filepath):
                    try:
                        os.remove(temp_bat_filepath)
                        log.log(f"Cleaned up temporary file: {temp_bat_filepath}")
                    except OSError as err:
                        log.log(f"Error cleaning up temporary file: {err}")
        
        if not final_message:
            final_message = f"FLAI processing is complete for all {total_files} file(s)." if all_success else "Process finished, but one or more files failed. Check the log for details."
        
        self.after(0, self.on_processing_complete, total_files, all_success, final_message)

    def on_processing_complete(self, total_files, all_success, message):
        self.controller.log_frame.log("\n--- Batch script execution finished ---")
        
        self.set_ui_state(False)
        self._check_run_button_state()

        if all_success:
            messagebox.showinfo("Process Complete", message)
        else:
            if not self.controller.was_terminated:
                messagebox.showwarning("Warning", message)
        self.controller.was_terminated = False