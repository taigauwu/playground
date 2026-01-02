import tkinter as tk
import ttkbootstrap as ttk
from tkinter import filedialog, messagebox
import threading
import os
from gui.base import BaseToolFrame
from gui.widgets import Tooltip
from core.execution import _execute_las_command
from utils.files import get_laz_output_filename
from utils.projections import METER_TO_US_FT, METER_TO_INTL_FT

class ScaleToolFrame(BaseToolFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Scale Point Cloud")
        self.CONVERSION_FACTORS = {("Meters", "US Survey Feet"): METER_TO_US_FT, ("Meters", "International Feet"): 1 / 0.3048}
        self.units = ["Meters", "US Survey Feet", "International Feet"]
        
        self.single_file_path = tk.StringVar()
        self.folder_path_display = tk.StringVar()
        self.files_list = []
        self.batch_mode = tk.BooleanVar(value=False)
        self.current_unit_var = tk.StringVar()
        self.desired_unit_var = tk.StringVar()
        self.rescale_var = tk.StringVar(value="No Rescale")
        self.x_scale_var = tk.BooleanVar(value=False)
        self.y_scale_var = tk.BooleanVar(value=False)
        self.z_scale_var = tk.BooleanVar(value=False)
        self.is_processing = False
        
        self.create_widgets()
        
        self.single_file_path.trace_add("write", self._check_run_button_state)
        self.folder_path_display.trace_add("write", self._check_run_button_state)
        self.current_unit_var.trace_add("write", self._check_run_button_state)
        self.desired_unit_var.trace_add("write", self._check_run_button_state)

    def _check_run_button_state(self, *args):
        if self.is_processing: return
        
        if self.batch_mode.get():
            files_ok = bool(self.files_list)
        else:
            files_ok = os.path.isfile(self.single_file_path.get())
            
        units_ok = bool(self.current_unit_var.get() and self.desired_unit_var.get())
        lastools_ok = os.path.isdir(self.controller.lastools_path_var.get())
        if files_ok and units_ok and lastools_ok:
            self.run_button.config(state="normal")
        else:
            self.run_button.config(state="disabled")

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

        params_frame = ttk.Labelframe(self.content_frame, text="2. Set Scaling Parameters", padding=10, style="Info.TLabelframe")
        params_frame.grid(row=1, column=0, sticky="ew", pady=10)
        params_frame.grid_columnconfigure(0, weight=1)
        
        unit_frame = ttk.Frame(params_frame)
        unit_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        unit_frame.grid_columnconfigure((1, 3), weight=1)
        ttk.Label(unit_frame, text="Current Unit:").grid(row=0, column=0, sticky="w")
        current_unit_combo = ttk.Combobox(unit_frame, textvariable=self.current_unit_var, values=self.units, state="readonly")
        current_unit_combo.grid(row=0, column=1, sticky="ew", padx=5)
        Tooltip(current_unit_combo, "The current unit of measurement of the point cloud.")
        ttk.Label(unit_frame, text="Desired Unit:").grid(row=0, column=2, sticky="w", padx=(10, 0))
        desired_unit_combo = ttk.Combobox(unit_frame, textvariable=self.desired_unit_var, values=self.units, state="readonly")
        desired_unit_combo.grid(row=0, column=3, sticky="ew", padx=5)
        Tooltip(desired_unit_combo, "The target unit of measurement you want to convert the point cloud to.")
        
        axis_frame = ttk.Frame(params_frame)
        axis_frame.grid(row=1, column=0, sticky="w", pady=(0, 10))
        ttk.Label(axis_frame, text="Axes to Scale:").pack(side="left", padx=(0, 10))
        cb_x = ttk.Checkbutton(axis_frame, text="X", variable=self.x_scale_var, bootstyle="round-toggle"); cb_x.pack(side="left", padx=15); Tooltip(cb_x, "Apply scaling to the X-axis coordinates.")
        cb_y = ttk.Checkbutton(axis_frame, text="Y", variable=self.y_scale_var, bootstyle="round-toggle"); cb_y.pack(side="left", padx=15); Tooltip(cb_y, "Apply scaling to the Y-axis coordinates.")
        cb_z = ttk.Checkbutton(axis_frame, text="Z", variable=self.z_scale_var, bootstyle="round-toggle"); cb_z.pack(side="left", padx=15); Tooltip(cb_z, "Apply scaling to the Z-axis coordinates.")

        rescale_frame = ttk.Frame(params_frame)
        rescale_frame.grid(row=2, column=0, sticky="w")
        ttk.Label(rescale_frame, text="Rescale Factor (for overflows):").grid(row=0, column=0, sticky="w")
        rescale_combo = ttk.Combobox(rescale_frame, textvariable=self.rescale_var, values=["No Rescale", "0.001", "0.01"], state="readonly", width=15)
        rescale_combo.grid(row=0, column=1, sticky="w", padx=5)
        Tooltip(rescale_combo, "Apply a rescale factor to prevent coordinate overflows. Use if LAStools warns about overflows.")
        
        action_frame = ttk.Labelframe(self.content_frame, text="3. Run Process", padding=10, style="Info.TLabelframe")
        action_frame.grid(row=2, column=0, sticky="ew")
        run_container = ttk.Frame(action_frame)
        run_container.grid(row=0, column=0, sticky="w")
        self.run_button = ttk.Button(run_container, text="Run Scaling", command=self.start_scaling_thread, bootstyle="primary", state="disabled")
        self.run_button.pack(side="left", padx=(0, 10))
        Tooltip(self.run_button, "Execute the scaling process using LAStools.")
        self.progress = ttk.Progressbar(run_container, orient="horizontal", length=300, mode="determinate", bootstyle="primary")
        self.progress.pack(side="left")

        reset_frame = ttk.Frame(self.content_frame)
        reset_frame.grid(row=3, column=0, sticky="e", pady=(10,0))
        
        self.stop_button = ttk.Button(reset_frame, text="Stop Process", command=lambda: self.controller.terminate_frame_process(self), bootstyle="secondary", state="disabled")
        self.stop_button.pack(side="left", padx=(0, 5))
        Tooltip(self.stop_button, "Forcefully stop the current running process.")

        reset_btn = ttk.Button(reset_frame, text="Reset All", command=self.reset_ui, bootstyle="secondary-outline")
        reset_btn.pack(side="left")
        Tooltip(reset_btn, "Clear all inputs and selections in this tool.")

    def reset_ui(self):
        self.single_file_path.set("")
        self.folder_path_display.set("")
        self.files_list.clear()
        self.batch_mode.set(False)
        self._toggle_input_mode()
        self.current_unit_var.set("")
        self.desired_unit_var.set("")
        self.x_scale_var.set(False)
        self.y_scale_var.set(False)
        self.z_scale_var.set(False)
        self.rescale_var.set("No Rescale")
        self.controller.log_frame.log("Scaling tool has been reset.")

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

    def get_scale_factor(self, current, desired):
        if current == desired: return 1.0
        if (current, desired) in self.CONVERSION_FACTORS: return self.CONVERSION_FACTORS[(current, desired)]
        if (desired, current) in self.CONVERSION_FACTORS: return 1.0 / self.CONVERSION_FACTORS[(desired, current)]
        return self.get_scale_factor(current, "Meters") * self.get_scale_factor("Meters", desired)

    def set_processing_state(self, is_processing):
        self.is_processing = is_processing
        if is_processing:
            self.run_button.config(text="Processing...", state="disabled")
            self.progress.config(mode="indeterminate")
            self.progress.start()
            self.stop_button.config(state="normal")
        else:
            self.run_button.config(text="Run Scaling")
            self.progress.stop()
            self.progress.config(mode="determinate", value=0)
            self._check_run_button_state()
            self.stop_button.config(state="disabled")

    def start_scaling_thread(self):
        if self.is_processing: return
        self.controller.log_frame.log(f"\n{'='*20}\n--- [SCALE] Starting Scaling Operation ---\n{'='*20}")
        self.set_processing_state(True)
        threading.Thread(target=self._run_scaling_operation, daemon=True, name="LAStools_Scaling").start()

    def on_scaling_complete(self, total_files, all_success):
        """Handles UI updates after the scaling process is complete."""
        self.set_processing_state(False)
        if all_success:
            messagebox.showinfo("Success", f"Scaling complete for all {total_files} file(s)!")
        else:
            if not self.controller.was_terminated:
                messagebox.showwarning("Warning", "Process finished, but one or more files failed. Check the log for details.")
        self.controller.was_terminated = False

    def _run_scaling_operation(self):
        all_success = True
        total_files = 0
        try:
            if self.batch_mode.get():
                files_to_process = self.files_list
                if not files_to_process:
                    raise ValueError("Batch mode is on, but no folder is selected or it is empty.")
            else:
                single_file = self.single_file_path.get()
                if not os.path.isfile(single_file):
                    raise ValueError("Please select a valid input LAZ file.")
                files_to_process = [single_file]

            current, desired = self.current_unit_var.get(), self.desired_unit_var.get()
            if not current or not desired:
                raise ValueError("Please select both current and desired units.")
            
            factor = self.get_scale_factor(current, desired)
            use_x, use_y, use_z = self.x_scale_var.get(), self.y_scale_var.get(), self.z_scale_var.get()
            if not any([use_x, use_y, use_z]):
                raise ValueError("Please select at least one axis to scale.")
            
            axes_suffix_parts = []
            if use_x: axes_suffix_parts.append('x')
            if use_y: axes_suffix_parts.append('y')
            if use_z: axes_suffix_parts.append('z')
            axes_suffix = "".join(axes_suffix_parts)

            x_factor = factor if use_x else 1.0
            y_factor = factor if use_y else 1.0
            z_factor = factor if use_z else 1.0

            total_files = len(files_to_process)
            lastools_path = self.controller.lastools_path_var.get()

            for i, file_path in enumerate(files_to_process):
                self.controller.log_frame.log(f"\n({i+1}/{total_files}) Scaling: {os.path.basename(file_path)}")
                try:
                    las2las_exe = os.path.join(lastools_path, "las2las.exe")
                    suffix = f"_sc_{axes_suffix}" if axes_suffix else "_sc"
                    output_path = get_laz_output_filename(file_path, suffix)

                    command = [las2las_exe]
                    rescale_option = self.rescale_var.get()
                    if rescale_option != "No Rescale":
                        command.extend(["-rescale", rescale_option, rescale_option, rescale_option])
                    
                    command.extend([
                        "-i", file_path, "-scale_x", str(x_factor), "-scale_y", str(y_factor),
                        "-scale_z", str(z_factor), "-o", output_path, "-olaz"
                    ])
                    
                    output_log = _execute_las_command(command, self.controller.log_frame, controller=self.controller, frame_instance=self)
                    
                    if "overflows caused by" in output_log:
                        overflow_message = "Overflows warning detected, deleting the output file. Please scale again with a rescale factor."
                        self.controller.log_frame.log(overflow_message)
                        if os.path.exists(output_path):
                            os.remove(output_path)
                        all_success = False
                    else:
                         self.controller.log_frame.log(f"\nCommand completed successfully.")

                except Exception as file_error:
                    all_success = False
                    if self.controller.was_terminated:
                        self.controller.log_frame.log(f"    --- Process for {os.path.basename(file_path)} was terminated by user. ---")
                        break
                    self.controller.log_frame.log(f"    --- ERROR processing {os.path.basename(file_path)}: {file_error} ---")
            
        except Exception as e:
            if not self.controller.was_terminated:
                messagebox.showerror("Error", f"An unexpected error occurred: {e}")
            all_success = False
        finally:
            self.after(0, self.on_scaling_complete, total_files, all_success)