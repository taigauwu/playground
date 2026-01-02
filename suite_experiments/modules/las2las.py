import tkinter as tk
import ttkbootstrap as ttk
from tkinter import filedialog, messagebox
import threading
import os
import subprocess
from pathlib import Path
from gui.base import BaseToolFrame
from gui.widgets import Tooltip
from core.execution import _execute_command

class Las2lasFrame(BaseToolFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "LAS2LAS Point Cloud Utility")
        
        # --- Variables ---
        self.convert_input_file, self.output_base_name = tk.StringVar(), tk.StringVar()
        self.merge_files_summary, self.merge_output_name = tk.StringVar(), tk.StringVar()
        
        # Convert
        self.convert_folder_path_display = tk.StringVar()
        self.convert_files_list = []
        self.convert_batch_mode = tk.BooleanVar(value=False)

        # Decimate
        self.decimate_single_file_path = tk.StringVar()
        self.decimate_folder_path_display = tk.StringVar()
        self.decimate_files_list = []
        self.decimate_batch_mode = tk.BooleanVar(value=False)

        # Drop 0
        self.drop0_single_file_path = tk.StringVar()
        self.drop0_folder_path_display = tk.StringVar()
        self.drop0_files_list = []
        self.drop0_batch_mode = tk.BooleanVar(value=False)
        
        # Rescale
        self.rescale_single_file_path = tk.StringVar()
        self.rescale_folder_path_display = tk.StringVar()
        self.rescale_files_list = []
        self.rescale_batch_mode = tk.BooleanVar(value=False)
        self.rescale_factor_var = tk.StringVar(value="0.01")

        # Info & View
        self.info_file_path = tk.StringVar()
        self.view_file_path = tk.StringVar()

        self.merge_files_list = []
        self.is_processing = False
        self.create_widgets()
        self._check_all_run_buttons_state()

    def create_widgets(self):
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        
        # Create Tabs (Renamed variables for clarity)
        tab_decimate = ttk.Frame(notebook, padding=15)
        tab_drop0 = ttk.Frame(notebook, padding=15)
        tab_info = ttk.Frame(notebook, padding=15)
        tab_convert = ttk.Frame(notebook, padding=15) # LAS to LAZ
        tab_merge = ttk.Frame(notebook, padding=15)
        tab_rescale = ttk.Frame(notebook, padding=15)
        tab_view = ttk.Frame(notebook, padding=15)
        
        # Add Tabs in Alphabetical Order
        notebook.add(tab_decimate, text='Decimate')
        notebook.add(tab_drop0, text='Drop Class 0')
        notebook.add(tab_info, text='Info')
        notebook.add(tab_convert, text='LAS to LAZ')
        notebook.add(tab_merge, text='Merge')
        notebook.add(tab_rescale, text='Rescale')
        notebook.add(tab_view, text='View')
        
        # Setup Tabs content
        self.setup_decimate_tab(tab_decimate)
        self.setup_drop_class_0_tab(tab_drop0)
        self.setup_info_tab(tab_info)
        self.setup_las_to_laz_tab(tab_convert)
        self.setup_merge_tab(tab_merge)
        self.setup_rescale_tab(tab_rescale)
        self.setup_view_tab(tab_view)
        
        # Tooltips
        Tooltip(tab_decimate, "Reduce the point density of a .laz file by keeping every 4th point.")
        Tooltip(tab_drop0, "Remove all points assigned to Class 0 (Never Classified).")
        Tooltip(tab_info, "Run lasinfo to view file header, bounding box, and VLRs.")
        Tooltip(tab_convert, "Convert a single .las file to the compressed .laz format.")
        Tooltip(tab_merge, "Combine multiple .las or .laz files into a single merged .laz file.")
        Tooltip(tab_rescale, "Rescale coordinate resolution (e.g. to 0.01) to fix precision issues.")
        Tooltip(tab_view, "Launch lasview to visualize the point cloud in 3D.")

        # Footer Actions
        action_frame = ttk.Frame(self.content_frame)
        action_frame.grid(row=1, column=0, sticky="e", pady=(10,0))

        self.stop_button = ttk.Button(action_frame, text="Stop Process", command=lambda: self.controller.terminate_frame_process(self), bootstyle="secondary", state="disabled")
        self.stop_button.pack(side="left", padx=(0, 5))
        Tooltip(self.stop_button, "Forcefully stop the current running process.")
        
        reset_btn = ttk.Button(action_frame, text="Reset All", command=self.reset_ui, bootstyle="secondary-outline")
        reset_btn.pack(side="left")
        Tooltip(reset_btn, "Reset all fields in all tabs.")

    def reset_ui(self):
        # Convert
        self.convert_input_file.set("")
        self.output_base_name.set("")
        self.convert_folder_path_display.set("")
        self.convert_files_list.clear()
        self.convert_batch_mode.set(False)
        self._toggle_input_mode_convert()

        # Decimate
        self.decimate_single_file_path.set("")
        self.decimate_folder_path_display.set("")
        self.decimate_files_list.clear()
        self.decimate_batch_mode.set(False)
        self._toggle_input_mode_decimate()
        
        # Drop 0
        self.drop0_single_file_path.set("")
        self.drop0_folder_path_display.set("")
        self.drop0_files_list.clear()
        self.drop0_batch_mode.set(False)
        self._toggle_input_mode_drop0()
        
        # Rescale
        self.rescale_single_file_path.set("")
        self.rescale_folder_path_display.set("")
        self.rescale_files_list.clear()
        self.rescale_batch_mode.set(False)
        self.rescale_factor_var.set("0.01")
        self._toggle_input_mode_rescale()

        # Info & View
        self.info_file_path.set("")
        self.view_file_path.set("")

        # Merge
        self.merge_files_summary.set("")
        self.merge_output_name.set("")
        self.merge_files_list.clear()
        
        self.controller.log_frame.log("LAS2LAS Utility has been reset.")
        self._check_all_run_buttons_state()

    def set_processing_state(self, is_processing, widgets):
        self.is_processing = is_processing
        all_buttons = [
            self.convert_btn, self.browse_las_btn, 
            self.run_decimate_btn, self.run_drop0_btn, 
            self.run_rescale_btn, self.run_info_btn, 
            self.run_view_btn, self.run_merge_btn, 
            self.select_merge_btn
        ]
        
        if is_processing:
            state = "disabled"
            if widgets and 'run_button' in widgets:
                widgets['run_button'].config(text="Processing...")
            if widgets and 'progress_bar' in widgets:
                widgets['progress_bar'].config(mode="indeterminate")
                widgets['progress_bar'].start()
            for btn in all_buttons: 
                if btn: btn.config(state=state)
            self.stop_button.config(state="normal")
        else:
            state = "normal"
            if widgets and 'run_button' in widgets:
                widgets['run_button'].config(text=widgets['original_text'])
            if widgets and 'progress_bar' in widgets:
                widgets['progress_bar'].stop()
                widgets['progress_bar'].config(mode="determinate", value=0)
            for btn in all_buttons: 
                if btn: btn.config(state=state)
            self._check_all_run_buttons_state()
            self.stop_button.config(state="disabled")

    def _check_all_run_buttons_state(self, *args):
        if self.is_processing: return

        # Convert
        if self.convert_batch_mode.get():
            self.convert_btn.config(state="normal" if self.convert_files_list else "disabled")
        else:
            self.convert_btn.config(state="normal" if os.path.isfile(self.convert_input_file.get()) else "disabled")
        
        # Decimate
        if self.decimate_batch_mode.get():
            self.run_decimate_btn.config(state="normal" if self.decimate_files_list else "disabled")
        else:
            self.run_decimate_btn.config(state="normal" if os.path.isfile(self.decimate_single_file_path.get()) else "disabled")

        # Drop 0
        if self.drop0_batch_mode.get():
            self.run_drop0_btn.config(state="normal" if self.drop0_files_list else "disabled")
        else:
            self.run_drop0_btn.config(state="normal" if os.path.isfile(self.drop0_single_file_path.get()) else "disabled")

        # Rescale
        if self.rescale_batch_mode.get():
            self.run_rescale_btn.config(state="normal" if self.rescale_files_list else "disabled")
        else:
            self.run_rescale_btn.config(state="normal" if os.path.isfile(self.rescale_single_file_path.get()) else "disabled")

        # Info & View
        self.run_info_btn.config(state="normal" if os.path.isfile(self.info_file_path.get()) else "disabled")
        self.run_view_btn.config(state="normal" if os.path.isfile(self.view_file_path.get()) else "disabled")

        # Merge
        self.run_merge_btn.config(state="normal" if len(self.merge_files_list) > 1 else "disabled")

    # ==================== TAB 1: DECIMATE ====================
    def setup_decimate_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text="Decimates high density point cloud into medium density.").pack(anchor='w', pady=(0, 10), fill='x')
        
        input_frame = ttk.Labelframe(parent, text="1. Select Input", padding=10, style="Info.TLabelframe"); input_frame.pack(fill='x', pady=(0, 10))
        input_frame.columnconfigure(0, weight=1)

        ttk.Checkbutton(input_frame, text="Batch Mode (Process entire folder)", variable=self.decimate_batch_mode, command=self._toggle_input_mode_decimate, bootstyle="round-toggle").pack(anchor='w', pady=(0, 10))

        self.decimate_single_file_frame = ttk.Frame(input_frame); self.decimate_single_file_frame.pack(fill='x'); self.decimate_single_file_frame.columnconfigure(1, weight=1)
        ttk.Label(self.decimate_single_file_frame, text="Input File (.laz/.las):").grid(row=0, column=0, sticky='w', padx=(0,10))
        ttk.Entry(self.decimate_single_file_frame, textvariable=self.decimate_single_file_path, state="readonly").grid(row=0, column=1, sticky='ew')
        ttk.Button(self.decimate_single_file_frame, text="Select File...", bootstyle="secondary", command=self.select_decimate_file).grid(row=0, column=2, padx=(5,0))
        self.decimate_single_file_path.trace_add("write", self._check_all_run_buttons_state)

        self.decimate_folder_frame = ttk.Frame(input_frame); self.decimate_folder_frame.pack(fill='x'); self.decimate_folder_frame.columnconfigure(1, weight=1)
        ttk.Label(self.decimate_folder_frame, text="Input Folder:").grid(row=0, column=0, sticky='w', padx=(0,10))
        deci_folder_entry = ttk.Entry(self.decimate_folder_frame, textvariable=self.decimate_folder_path_display, state="readonly")
        deci_folder_entry.grid(row=0, column=1, sticky='ew')
        ttk.Button(self.decimate_folder_frame, text="Select Folder...", bootstyle="secondary", command=self.select_decimate_folder).grid(row=0, column=2, padx=(5,0))
        self.decimate_folder_frame.pack_forget()

        run_frame = ttk.Labelframe(parent, text="2. Run Process", padding=10, style="Info.TLabelframe"); run_frame.pack(fill='x'); run_container = ttk.Frame(run_frame); run_container.pack(anchor='w')
        self.run_decimate_btn = ttk.Button(run_container, text="Run Decimation", command=self.run_decimation, bootstyle="primary"); self.run_decimate_btn.pack(side='left', padx=(0,10))
        self.decimate_progress = ttk.Progressbar(run_container, orient="horizontal", length=300, mode="determinate", bootstyle="primary"); self.decimate_progress.pack(side='left')

    def _toggle_input_mode_decimate(self):
        is_batch = self.decimate_batch_mode.get()
        self.decimate_single_file_frame.pack_forget() if is_batch else self.decimate_single_file_frame.pack(fill='x', expand=True)
        self.decimate_folder_frame.pack(fill='x', expand=True) if is_batch else self.decimate_folder_frame.pack_forget()
        self._check_all_run_buttons_state()

    def select_decimate_file(self):
        path = filedialog.askopenfilename(filetypes=[("Lidar Files", "*.laz *.las")])
        if path: self.decimate_single_file_path.set(path)
        self._check_all_run_buttons_state()
        
    def select_decimate_folder(self):
        directory = filedialog.askdirectory()
        if directory:
            files = [os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith(('.laz', '.las'))]
            if files:
                self.decimate_files_list = files
                self.decimate_folder_path_display.set(f"{len(files)} file(s) found")
            else:
                self.decimate_files_list = []
                self.decimate_folder_path_display.set("No files found")
        self._check_all_run_buttons_state()

    def run_decimation(self):
        files = self.decimate_files_list if self.decimate_batch_mode.get() else [self.decimate_single_file_path.get()]
        if not any(files): return
        widgets = {'run_button': self.run_decimate_btn, 'progress_bar': self.decimate_progress, 'original_text': 'Run Decimation'}
        self._run_batch_process(files, {'output_name': "{stem}_deci.laz", 'args': ["-keep_every_nth", "4"]}, "Decimation", widgets)

    # ==================== TAB 2: DROP CLASS 0 ====================
    def setup_drop_class_0_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text="Removes points with classification 0 (Never Classified)").pack(anchor='w', pady=(0, 10), fill='x')
        input_frame = ttk.Labelframe(parent, text="1. Select Input", padding=10, style="Info.TLabelframe"); input_frame.pack(fill='x', pady=(0, 10)); input_frame.columnconfigure(0, weight=1)
        ttk.Checkbutton(input_frame, text="Batch Mode (Process entire folder)", variable=self.drop0_batch_mode, command=self._toggle_input_mode_drop0, bootstyle="round-toggle").pack(anchor='w', pady=(0, 10))
        
        self.drop0_single_file_frame = ttk.Frame(input_frame); self.drop0_single_file_frame.pack(fill='x'); self.drop0_single_file_frame.columnconfigure(1, weight=1)
        ttk.Label(self.drop0_single_file_frame, text="Input File (.laz/.las):").grid(row=0, column=0, sticky='w', padx=(0,10))
        ttk.Entry(self.drop0_single_file_frame, textvariable=self.drop0_single_file_path, state="readonly").grid(row=0, column=1, sticky='ew')
        ttk.Button(self.drop0_single_file_frame, text="Select File...", bootstyle="secondary", command=self.select_drop0_file).grid(row=0, column=2, padx=(5,0))
        self.drop0_single_file_path.trace_add("write", self._check_all_run_buttons_state)
        
        self.drop0_folder_frame = ttk.Frame(input_frame); self.drop0_folder_frame.pack(fill='x'); self.drop0_folder_frame.columnconfigure(1, weight=1)
        ttk.Label(self.drop0_folder_frame, text="Input Folder:").grid(row=0, column=0, sticky='w', padx=(0,10))
        ttk.Entry(self.drop0_folder_frame, textvariable=self.drop0_folder_path_display, state="readonly").grid(row=0, column=1, sticky='ew')
        ttk.Button(self.drop0_folder_frame, text="Select Folder...", bootstyle="secondary", command=self.select_drop0_folder).grid(row=0, column=2, padx=(5,0))
        self.drop0_folder_frame.pack_forget()

        run_frame = ttk.Labelframe(parent, text="2. Run Process", padding=10, style="Info.TLabelframe"); run_frame.pack(fill='x'); run_container = ttk.Frame(run_frame); run_container.pack(anchor='w')
        self.run_drop0_btn = ttk.Button(run_container, text="Run Process", command=self.run_drop_class_0, bootstyle="primary"); self.run_drop0_btn.pack(side='left', padx=(0,10))
        self.drop0_progress = ttk.Progressbar(run_container, orient="horizontal", length=300, mode="determinate", bootstyle="primary"); self.drop0_progress.pack(side='left')

    def _toggle_input_mode_drop0(self):
        is_batch = self.drop0_batch_mode.get()
        self.drop0_single_file_frame.pack_forget() if is_batch else self.drop0_single_file_frame.pack(fill='x', expand=True)
        self.drop0_folder_frame.pack(fill='x', expand=True) if is_batch else self.drop0_folder_frame.pack_forget()
        self._check_all_run_buttons_state()

    def select_drop0_file(self):
        path = filedialog.askopenfilename(filetypes=[("Lidar Files", "*.laz *.las")])
        if path: self.drop0_single_file_path.set(path)
        self._check_all_run_buttons_state()
        
    def select_drop0_folder(self):
        directory = filedialog.askdirectory()
        if directory:
            files = [os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith(('.laz', '.las'))]
            if files:
                self.drop0_files_list = files
                self.drop0_folder_path_display.set(f"{len(files)} file(s) found")
            else:
                self.drop0_files_list = []
                self.drop0_folder_path_display.set("No files found")
        self._check_all_run_buttons_state()

    def run_drop_class_0(self):
        files = self.drop0_files_list if self.drop0_batch_mode.get() else [self.drop0_single_file_path.get()]
        if not any(files): return
        widgets = {'run_button': self.run_drop0_btn, 'progress_bar': self.drop0_progress, 'original_text': 'Run Process'}
        self._run_batch_process(files, {'output_name': "{stem}_drop0.laz", 'args': ["-drop_class", "0"]}, "Drop Class 0", widgets)

    # ==================== TAB 3: INFO ====================
    def setup_info_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text="Displays header info, bounding box, and VLRs (lasinfo).").pack(anchor='w', pady=(0, 15))
        
        input_frame = ttk.Labelframe(parent, text="1. Select File", padding=10, style="Info.TLabelframe")
        input_frame.pack(fill='x', pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)
        
        ttk.Label(input_frame, text="Input File:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Entry(input_frame, textvariable=self.info_file_path, state="readonly").grid(row=0, column=1, sticky="ew")
        ttk.Button(input_frame, text="Browse...", bootstyle="secondary", command=lambda: self._browse_single(self.info_file_path)).grid(row=0, column=2, padx=(5, 0))
        
        self.run_info_btn = ttk.Button(parent, text="Run Info", command=self.run_lasinfo, bootstyle="info", state="disabled")
        self.run_info_btn.pack(anchor="w", pady=10)

    def _browse_single(self, var):
        path = filedialog.askopenfilename(filetypes=[("Lidar Files", "*.laz *.las"), ("All files", "*.*")])
        if path:
            var.set(path)
        self._check_all_run_buttons_state()

    def run_lasinfo(self):
        file_path = self.info_file_path.get()
        if not file_path: return
        widgets = {'run_button': self.run_info_btn, 'original_text': 'Run Info'}
        self.set_processing_state(True, widgets)
        self.controller.log_frame.log(f"\n{'='*20}\n--- Running lasinfo ---\n{'='*20}")
        threading.Thread(target=self._lasinfo_thread, args=(file_path, widgets), daemon=True).start()

    def _lasinfo_thread(self, file_path, widgets):
        try:
            lastools_path = self.controller.lastools_path_var.get()
            exe = os.path.join(lastools_path, "lasinfo.exe")
            if not os.path.exists(exe): raise FileNotFoundError("lasinfo.exe not found.")
            command = [exe, "-i", file_path, "-no_check_integrity"]
            _execute_command(command, self.controller.log_frame, f"Analyzing {os.path.basename(file_path)}...", controller=self.controller, frame_instance=self)
        except Exception as e:
            if not self.controller.was_terminated:
                self.controller.log_frame.log(f"Error: {e}")
        finally:
            self.after(0, lambda: self.set_processing_state(False, widgets))

    # ==================== TAB 4: LAS TO LAZ ====================
    def setup_las_to_laz_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        input_frame = ttk.Labelframe(parent, text="1. Select Input", padding=10, style="Info.TLabelframe"); input_frame.pack(fill='x', pady=(0, 10)); input_frame.columnconfigure(0, weight=1)
        ttk.Checkbutton(input_frame, text="Batch Mode (Process entire folder)", variable=self.convert_batch_mode, command=self._toggle_input_mode_convert, bootstyle="round-toggle").pack(anchor='w', pady=(0, 10))
        
        self.convert_single_file_frame = ttk.Frame(input_frame); self.convert_single_file_frame.pack(fill='x'); self.convert_single_file_frame.columnconfigure(1, weight=1)
        ttk.Label(self.convert_single_file_frame, text="Input file (.las):").grid(row=0, column=0, sticky='w', padx=(0,10))
        ttk.Entry(self.convert_single_file_frame, textvariable=self.convert_input_file, state="readonly").grid(row=0, column=1, sticky='ew')
        ttk.Button(self.convert_single_file_frame, text="Browse...", bootstyle="secondary", command=self.select_convert_file).grid(row=0, column=2, padx=(5,0))
        self.convert_input_file.trace_add("write", self._check_all_run_buttons_state)
        
        self.convert_folder_frame = ttk.Frame(input_frame); self.convert_folder_frame.pack(fill='x'); self.convert_folder_frame.columnconfigure(1, weight=1)
        ttk.Label(self.convert_folder_frame, text="Input Folder:").grid(row=0, column=0, sticky='w', padx=(0,10))
        ttk.Entry(self.convert_folder_frame, textvariable=self.convert_folder_path_display, state="readonly").grid(row=0, column=1, sticky='ew')
        ttk.Button(self.convert_folder_frame, text="Select Folder...", bootstyle="secondary", command=self.select_convert_folder).grid(row=0, column=2, padx=(5,0))
        self.convert_folder_frame.pack_forget()

        output_frame = ttk.Labelframe(parent, text="2. Configure Output", padding=10, style="Info.TLabelframe"); output_frame.pack(fill='x', pady=(0, 10)); output_frame.columnconfigure(1, weight=1)
        ttk.Label(output_frame, text="Output File Name (Single Mode Only):").grid(row=0, column=0, sticky='w', padx=(0,10))
        ttk.Entry(output_frame, textvariable=self.output_base_name).grid(row=0, column=1, sticky='ew')
        
        run_frame = ttk.Labelframe(parent, text="3. Run Process", padding=10, style="Info.TLabelframe"); run_frame.pack(fill='x'); run_container = ttk.Frame(run_frame); run_container.pack(anchor='w')
        self.convert_btn = ttk.Button(run_container, text="Convert to LAZ", command=self.run_conversion, bootstyle="primary"); self.convert_btn.pack(side='left', padx=(0,10))
        self.convert_progress = ttk.Progressbar(run_container, orient="horizontal", length=300, mode="determinate", bootstyle="primary"); self.convert_progress.pack(side='left')

    def _toggle_input_mode_convert(self):
        is_batch = self.convert_batch_mode.get()
        self.convert_single_file_frame.pack_forget() if is_batch else self.convert_single_file_frame.pack(fill='x', expand=True)
        self.convert_folder_frame.pack(fill='x', expand=True) if is_batch else self.convert_folder_frame.pack_forget()
        self._check_all_run_buttons_state()

    def select_convert_file(self):
        path = filedialog.askopenfilename(title="Select a .las file", filetypes=[("LAS files", "*.las")])
        if path: self.convert_input_file.set(path)
        self._check_all_run_buttons_state()
        
    def select_convert_folder(self):
        directory = filedialog.askdirectory(title="Select a folder with LAS files")
        if directory:
            las_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith('.las')]
            if las_files:
                self.convert_files_list = las_files
                self.convert_folder_path_display.set(f"{len(las_files)} .las files found")
            else:
                self.convert_files_list.clear()
                self.convert_folder_path_display.set("No .las files found.")
                messagebox.showwarning("No Files Found", "The selected folder does not contain any .las files.")
        else:
            self.convert_files_list.clear()
            self.convert_folder_path_display.set("")
        self._check_all_run_buttons_state()

    def run_conversion(self):
        if self.convert_batch_mode.get():
            files_to_process = self.convert_files_list
        else:
            files_to_process = [self.convert_input_file.get()] if os.path.isfile(self.convert_input_file.get()) else []
        if not files_to_process:
            messagebox.showerror("Error", "No valid input files to process.")
            return
        widgets = {'run_button': self.convert_btn, 'progress_bar': self.convert_progress, 'original_text': 'Convert to LAZ'}
        self.set_processing_state(True, widgets)
        self.controller.log_frame.log(f"\n{'='*20}\n--- [LAS2LAS] Starting LAS to LAZ Conversion ---\n{'='*20}")
        threading.Thread(target=self._process_conversion_thread, args=(files_to_process, widgets), daemon=True, name="LAS_to_LAZ").start()

    def _process_conversion_thread(self, files_to_process, widgets):
        all_success = True
        try:
            lastools_path = self.controller.lastools_path_var.get()
            las2las_exe = os.path.join(lastools_path, "las2las.exe")
            if not os.path.exists(las2las_exe): raise FileNotFoundError("las2las.exe not found.")
            is_batch = self.convert_batch_mode.get()
            for i, file_path_str in enumerate(files_to_process):
                input_path = Path(file_path_str)
                self.controller.log_frame.log(f"\n({i+1}/{len(files_to_process)}) Converting: {input_path.name}")
                if is_batch:
                    output_file = input_path.with_suffix(".laz")
                else: 
                    output_base = self.output_base_name.get().strip()
                    output_file = input_path.with_name(f"{output_base}.laz") if output_base else input_path.with_suffix(".laz")
                command = [las2las_exe, "-i", str(input_path), "-o", str(output_file), "-olaz"]
                try:
                    _execute_command(command, self.controller.log_frame, f"    Output: {output_file.name}", controller=self.controller, frame_instance=self)
                except Exception as file_error:
                    all_success = False
                    if self.controller.was_terminated: break
                    self.controller.log_frame.log(f"    --- ERROR: {file_error} ---")
        except Exception as e:
            if not self.controller.was_terminated:
                messagebox.showerror("Error", f"An error occurred during conversion:\n{e}")
            all_success = False
        finally:
            self.after(0, self.on_conversion_complete, len(files_to_process), all_success, widgets)

    def on_conversion_complete(self, total_files, all_success, widgets):
        self.set_processing_state(False, widgets)
        if all_success:
            messagebox.showinfo("Success", f"Conversion complete for all {total_files} file(s)!")
        else:
            if not self.controller.was_terminated:
                messagebox.showwarning("Warning", "Process finished, but one or more files failed.")
        self.controller.was_terminated = False

    # ==================== TAB 5: MERGE ====================
    def setup_merge_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text="Merges multiple .las/.laz files into a single .laz file").pack(anchor='w', pady=(0, 10), fill='x')
        input_frame = ttk.Labelframe(parent, text="1. Select Input Files (2 or more)", padding=10, style="Info.TLabelframe"); input_frame.pack(fill='x', pady=(0, 10)); input_frame.columnconfigure(1, weight=1)
        ttk.Label(input_frame, text="Input point cloud files (.las/.laz):").grid(row=0, column=0, sticky='w', padx=(0,10))
        ttk.Entry(input_frame, textvariable=self.merge_files_summary, state="readonly").grid(row=0, column=1, sticky='ew')
        self.select_merge_btn = ttk.Button(input_frame, text="Select Files...", bootstyle="secondary", command=self.select_merge_files); self.select_merge_btn.grid(row=0, column=2, padx=(5,0))
        
        output_frame = ttk.Labelframe(parent, text="2. Configure Output", padding=10, style="Info.TLabelframe"); output_frame.pack(fill='x', pady=(0, 10)); output_frame.columnconfigure(1, weight=1)
        ttk.Label(output_frame, text="Output File Name (Optional):").grid(row=0, column=0, sticky='w', padx=(0,10))
        ttk.Entry(output_frame, textvariable=self.merge_output_name).grid(row=0, column=1, sticky='ew')
        ttk.Label(output_frame, text=".laz", bootstyle='secondary').grid(row=0, column=2, padx=5)
        
        run_frame = ttk.Labelframe(parent, text="3. Run Process", padding=10, style="Info.TLabelframe"); run_frame.pack(fill='x'); run_container = ttk.Frame(run_frame); run_container.pack(anchor='w')
        self.run_merge_btn = ttk.Button(run_container, text="Run Merge", command=self.run_merge, bootstyle="primary"); self.run_merge_btn.pack(side='left', padx=(0,10))
        self.merge_progress = ttk.Progressbar(run_container, orient="horizontal", length=300, mode="determinate", bootstyle="primary"); self.merge_progress.pack(side='left')

    def select_merge_files(self):
        files = filedialog.askopenfilenames(title="Select 2 or more files to merge", filetypes=[("LAZ/LAS Files", "*.laz *.las"), ("All files", "*.*")])
        if len(files) > 1:
            self.merge_files_list = list(files)
            self.merge_files_summary.set(f"{len(files)} file(s) selected")
        else:
            self.merge_files_list = []
            self.merge_files_summary.set("")
        self._check_all_run_buttons_state()

    def run_merge(self):
        widgets = {'run_button': self.run_merge_btn, 'progress_bar': self.merge_progress, 'original_text': 'Run Merge'}
        self.set_processing_state(True, widgets)
        self.controller.log_frame.log(f"\n{'='*20}\n--- [LAS2LAS] Starting Merge ---\n{'='*20}")
        threading.Thread(target=self._process_merge_thread, args=(widgets,), daemon=True, name="LAStools_Merge").start()

    def _process_merge_thread(self, widgets):
        is_success = False
        output_file_name = "N/A"
        try:
            lastools_path = self.controller.lastools_path_var.get()
            lasmerge_exe = os.path.join(lastools_path, "lasmerge.exe")
            if not os.path.exists(lasmerge_exe): raise FileNotFoundError("lasmerge.exe not found.")
            first_input_path = Path(self.merge_files_list[0])
            output_directory = first_input_path.parent
            custom_name = self.merge_output_name.get().strip()
            output_file_name = (custom_name if custom_name else "merged") + ".laz"
            output_file_path = output_directory / output_file_name
            command = [lasmerge_exe, "-i", *self.merge_files_list, "-o", str(output_file_path), "-olaz"]
            _execute_command(command, self.controller.log_frame, "Merging files...", controller=self.controller, frame_instance=self)
            is_success = True
        except Exception as e:
            is_success = False
            if not self.controller.was_terminated:
                output_file_name = str(e)
        finally:
            self.after(0, self.on_merge_complete, is_success, output_file_name, widgets)

    def on_merge_complete(self, is_success, output_file_name, widgets):
        self.set_processing_state(False, widgets)
        if is_success:
            messagebox.showinfo("Success", f"Merge complete!\nOutput: {output_file_name}")
        else:
            if not self.controller.was_terminated:
                messagebox.showerror("Error", f"An error occurred during merge:\n{output_file_name}")
        self.controller.was_terminated = False

    # ==================== TAB 6: RESCALE ====================
    def setup_rescale_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text="Rescale coordinate resolution to fix precision issues.").pack(anchor='w', pady=(0, 10), fill='x')
        input_frame = ttk.Labelframe(parent, text="1. Select Input", padding=10, style="Info.TLabelframe"); input_frame.pack(fill='x', pady=(0, 10)); input_frame.columnconfigure(0, weight=1)
        ttk.Checkbutton(input_frame, text="Batch Mode (Process entire folder)", variable=self.rescale_batch_mode, command=self._toggle_input_mode_rescale, bootstyle="round-toggle").pack(anchor='w', pady=(0, 10))
        
        self.rescale_single_file_frame = ttk.Frame(input_frame); self.rescale_single_file_frame.pack(fill='x'); self.rescale_single_file_frame.columnconfigure(1, weight=1)
        ttk.Label(self.rescale_single_file_frame, text="Input File (.laz/.las):").grid(row=0, column=0, sticky='w', padx=(0,10))
        ttk.Entry(self.rescale_single_file_frame, textvariable=self.rescale_single_file_path, state="readonly").grid(row=0, column=1, sticky='ew')
        ttk.Button(self.rescale_single_file_frame, text="Select File...", bootstyle="secondary", command=self.select_rescale_file).grid(row=0, column=2, padx=(5,0))
        self.rescale_single_file_path.trace_add("write", self._check_all_run_buttons_state)
        
        self.rescale_folder_frame = ttk.Frame(input_frame); self.rescale_folder_frame.pack(fill='x'); self.rescale_folder_frame.columnconfigure(1, weight=1)
        ttk.Label(self.rescale_folder_frame, text="Input Folder:").grid(row=0, column=0, sticky='w', padx=(0,10))
        ttk.Entry(self.rescale_folder_frame, textvariable=self.rescale_folder_path_display, state="readonly").grid(row=0, column=1, sticky='ew')
        ttk.Button(self.rescale_folder_frame, text="Select Folder...", bootstyle="secondary", command=self.select_rescale_folder).grid(row=0, column=2, padx=(5,0))
        self.rescale_folder_frame.pack_forget()

        params_frame = ttk.Labelframe(parent, text="2. Parameters", padding=10, style="Info.TLabelframe")
        params_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(params_frame, text="Rescale Factor:").pack(side="left", padx=(0, 10))
        ttk.Combobox(params_frame, textvariable=self.rescale_factor_var, values=["0.01", "0.001"], state="readonly", width=10).pack(side="left")

        run_frame = ttk.Labelframe(parent, text="3. Run Process", padding=10, style="Info.TLabelframe"); run_frame.pack(fill='x'); run_container = ttk.Frame(run_frame); run_container.pack(anchor='w')
        self.run_rescale_btn = ttk.Button(run_container, text="Run Rescale", command=self.run_rescale, bootstyle="primary"); self.run_rescale_btn.pack(side='left', padx=(0,10))
        self.rescale_progress = ttk.Progressbar(run_container, orient="horizontal", length=300, mode="determinate", bootstyle="primary"); self.rescale_progress.pack(side='left')

    def _toggle_input_mode_rescale(self):
        is_batch = self.rescale_batch_mode.get()
        self.rescale_single_file_frame.pack_forget() if is_batch else self.rescale_single_file_frame.pack(fill='x', expand=True)
        self.rescale_folder_frame.pack(fill='x', expand=True) if is_batch else self.rescale_folder_frame.pack_forget()
        self._check_all_run_buttons_state()

    def select_rescale_file(self):
        path = filedialog.askopenfilename(filetypes=[("Lidar Files", "*.laz *.las")])
        if path: self.rescale_single_file_path.set(path)
        self._check_all_run_buttons_state()
        
    def select_rescale_folder(self):
        directory = filedialog.askdirectory()
        if directory:
            files = [os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith(('.laz', '.las'))]
            if files:
                self.rescale_files_list = files
                self.rescale_folder_path_display.set(f"{len(files)} file(s) found")
            else:
                self.rescale_files_list = []
                self.rescale_folder_path_display.set("No files found")
        self._check_all_run_buttons_state()

    def run_rescale(self):
        files = self.rescale_files_list if self.rescale_batch_mode.get() else [self.rescale_single_file_path.get()]
        if not any(files): return
        factor = self.rescale_factor_var.get()
        widgets = {'run_button': self.run_rescale_btn, 'progress_bar': self.rescale_progress, 'original_text': 'Run Rescale'}
        self._run_batch_process(files, {'output_name': "{stem}_rescaled.laz", 'args': ["-rescale", factor, factor, factor]}, "Rescale", widgets)

    # ==================== TAB 7: VIEW ====================
    def setup_view_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text="Launches the 3D viewer (lasview).").pack(anchor='w', pady=(0, 15))
        
        input_frame = ttk.Labelframe(parent, text="1. Select File", padding=10, style="Info.TLabelframe")
        input_frame.pack(fill='x', pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)
        
        ttk.Label(input_frame, text="Input File:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Entry(input_frame, textvariable=self.view_file_path, state="readonly").grid(row=0, column=1, sticky="ew")
        ttk.Button(input_frame, text="Browse...", bootstyle="secondary", command=lambda: self._browse_single(self.view_file_path)).grid(row=0, column=2, padx=(5, 0))
        
        self.run_view_btn = ttk.Button(parent, text="Launch Viewer", command=self.run_lasview, bootstyle="success", state="disabled")
        self.run_view_btn.pack(anchor="w", pady=10)

    def run_lasview(self):
        file_path = self.view_file_path.get()
        if not file_path: return
        try:
            lastools_path = self.controller.lastools_path_var.get()
            exe = os.path.join(lastools_path, "lasview.exe")
            if not os.path.exists(exe): 
                messagebox.showerror("Error", "lasview.exe not found.")
                return
            self.controller.log_frame.log(f"Launching lasview for: {os.path.basename(file_path)}")
            subprocess.Popen([exe, "-i", file_path])
        except Exception as e:
            messagebox.showerror("Error", f"Could not launch lasview: {e}")

    # ==================== GENERIC BATCH PROCESS ====================
    def _run_batch_process(self, file_list, command_template, task_name, widgets):
        self.set_processing_state(True, widgets)
        self.controller.log_frame.log(f"\n{'='*20}\n--- [LAS2LAS] Starting {task_name} ---\n{'='*20}")
        threading.Thread(target=self._batch_thread_worker, args=(file_list, command_template, task_name, widgets), daemon=True, name=f"Batch_{task_name}").start()

    def on_batch_process_complete(self, task_name, all_success, widgets):
        self.set_processing_state(False, widgets)
        if all_success:
            messagebox.showinfo("Success", f"{task_name} completed successfully for all files.")
        else:
            if not self.controller.was_terminated:
                messagebox.showwarning("Warning", f"{task_name} completed, but one or more files failed.")
        self.controller.was_terminated = False

    def _batch_thread_worker(self, file_list, command_template, task_name, widgets):
        all_success = True
        try:
            lastools_path = self.controller.lastools_path_var.get()
            las2las_exe = os.path.join(lastools_path, "las2las.exe")
            if not os.path.exists(las2las_exe): raise FileNotFoundError("las2las.exe not found.")
            for i, file_path_str in enumerate(file_list):
                input_path = Path(file_path_str)
                output_file = input_path.with_name(command_template['output_name'].format(stem=input_path.stem))
                command = [las2las_exe, "-i", str(input_path), "-o", str(output_file), *command_template['args'], "-olaz"]
                try: 
                    _execute_command(command, self.controller.log_frame, f"({i+1}/{len(file_list)}) Processing {input_path.name}...", controller=self.controller, frame_instance=self)
                except Exception:
                    all_success = False
                    if self.controller.was_terminated: break
        except Exception as e:
            if not self.controller.was_terminated:
                messagebox.showerror("Error", f"Error in {task_name}:\n{e}")
            all_success = False
        finally:
            self.after(0, self.on_batch_process_complete, task_name, all_success, widgets)