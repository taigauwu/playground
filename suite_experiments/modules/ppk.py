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

class GNSSFrame(BaseToolFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "GNSS Utilities (RTKLib)")
        
        self.raw_file_var = tk.StringVar()
        self.raw_format_var = tk.StringVar(value="u-blox")
        self.crx_files_list = []
        self.crx_batch_mode = tk.BooleanVar(value=True)
        self.crx_input_summary = tk.StringVar()
        self.viz_file_var = tk.StringVar()
        
        self.is_processing = False
        
        self.create_widgets()
        self._check_run_states()

    def create_widgets(self):
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        
        tab_conv = ttk.Frame(notebook, padding=15)
        tab_crx = ttk.Frame(notebook, padding=15)
        tab_viz = ttk.Frame(notebook, padding=15)
        
        notebook.add(tab_conv, text='Raw to RINEX')
        notebook.add(tab_crx, text='Hatanaka Decompression')
        notebook.add(tab_viz, text='Visualization')
        
        self.setup_convbin_tab(tab_conv)
        self.setup_crx2rnx_tab(tab_crx)
        self.setup_viz_tab(tab_viz)

        # Footer
        action_frame = ttk.Frame(self.content_frame)
        action_frame.grid(row=1, column=0, sticky="e", pady=(10,0))
        self.stop_button = ttk.Button(action_frame, text="Stop Process", command=lambda: self.controller.terminate_frame_process(self), bootstyle="secondary", state="disabled")
        self.stop_button.pack(side="left", padx=(0, 5))
        ttk.Button(action_frame, text="Reset All", command=self.reset_ui, bootstyle="secondary-outline").pack(side="left")

    def _check_run_states(self, *args):
        if self.is_processing: return
        rtk_ok = os.path.isdir(self.controller.rtklib_path_var.get())
        
        # Convbin
        self.conv_btn.config(state="normal" if rtk_ok and os.path.isfile(self.raw_file_var.get()) else "disabled")
        # CRX
        self.crx_btn.config(state="normal" if rtk_ok and self.crx_files_list else "disabled")
        # Viz
        self.viz_btn.config(state="normal" if rtk_ok and os.path.isfile(self.viz_file_var.get()) else "disabled")
        self.viz_launch_btn.config(state="normal" if rtk_ok else "disabled")

    def reset_ui(self):
        self.raw_file_var.set("")
        self.crx_files_list = []
        self.crx_input_summary.set("")
        self.viz_file_var.set("")
        self._check_run_states()
        self.controller.log_frame.log("GNSS Utilities reset.")

    # --- TAB 1: CONVBIN ---
    def setup_convbin_tab(self, parent):
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text="Convert raw GNSS binary logs (ubx, bin) to RINEX using convbin.exe").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 15))
        
        ttk.Label(parent, text="Input Raw File:").grid(row=1, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.raw_file_var, state="readonly").grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Button(parent, text="Browse...", command=self.browse_raw, bootstyle="secondary").grid(row=1, column=2)
        
        ttk.Label(parent, text="Format:").grid(row=2, column=0, sticky="w", pady=10)
        fmt_combo = ttk.Combobox(parent, textvariable=self.raw_format_var, values=["u-blox", "auto", "rtcm3"], state="readonly", width=15)
        fmt_combo.grid(row=2, column=1, sticky="w", padx=5)
        
        self.conv_btn = ttk.Button(parent, text="Convert to RINEX", command=self.run_convbin, bootstyle="primary")
        self.conv_btn.grid(row=3, column=0, columnspan=3, pady=20, sticky="w")
        
        self.conv_progress = ttk.Progressbar(parent, orient="horizontal", length=300, mode="determinate")
        self.conv_progress.grid(row=3, column=1, sticky="w", padx=(120, 0))

    def browse_raw(self):
        path = filedialog.askopenfilename(filetypes=[("GNSS Raw", "*.ubx *.bin *.rtcm"), ("All files", "*.*")])
        if path:
            self.raw_file_var.set(path)
            self._check_run_states()

    def run_convbin(self):
        self.set_processing(True, self.conv_btn, self.conv_progress)
        threading.Thread(target=self._convbin_worker, daemon=True).start()

    def _convbin_worker(self):
        try:
            rtk_path = self.controller.rtklib_path_var.get()
            exe = os.path.join(rtk_path, "convbin.exe")
            if not os.path.exists(exe): raise FileNotFoundError("convbin.exe not found.")
            
            input_path = self.raw_file_var.get()
            base_dir = os.path.dirname(input_path)
            
            # Default behavior: outputs to same dir with standard extensions
            # -r = format (ubx, etc)
            fmt_map = {"u-blox": "ubx", "rtcm3": "rtcm3", "auto": "auto"}
            fmt = fmt_map.get(self.raw_format_var.get(), "auto")
            
            cmd = [exe, "-r", fmt, "-d", base_dir, input_path]
            
            # Since convbin outputs multiple files (obs, nav), we verify success by exit code
            _execute_command(cmd, self.controller.log_frame, f"Converting {os.path.basename(input_path)}...", self.controller, self)
            
            msg = "Conversion complete! Check folder for .obs and .nav files."
            self.after(0, lambda: messagebox.showinfo("Success", msg))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.after(0, lambda: self.set_processing(False, self.conv_btn, self.conv_progress))

    # --- TAB 2: CRX2RNX ---
    def setup_crx2rnx_tab(self, parent):
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text="Decompress Hatanaka (.crx, .XXd) files to standard RINEX (.rnx, .XXo)").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 15))
        
        ttk.Label(parent, text="Input Files:").grid(row=1, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.crx_input_summary, state="readonly").grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Button(parent, text="Select Files...", command=self.browse_crx, bootstyle="secondary").grid(row=1, column=2)
        
        self.crx_btn = ttk.Button(parent, text="Decompress Files", command=self.run_crx, bootstyle="primary")
        self.crx_btn.grid(row=2, column=0, columnspan=3, pady=20, sticky="w")
        
        self.crx_progress = ttk.Progressbar(parent, orient="horizontal", length=300, mode="determinate")
        self.crx_progress.grid(row=2, column=1, sticky="w", padx=(120, 0))

    def browse_crx(self):
        files = filedialog.askopenfilenames(filetypes=[("Hatanaka RINEX", "*.crx *.??d"), ("All files", "*.*")])
        if files:
            self.crx_files_list = list(files)
            self.crx_input_summary.set(f"{len(files)} files selected")
            self._check_run_states()

    def run_crx(self):
        self.set_processing(True, self.crx_btn, self.crx_progress)
        threading.Thread(target=self._crx_worker, daemon=True).start()

    def _crx_worker(self):
        try:
            rtk_path = self.controller.rtklib_path_var.get()
            exe = os.path.join(rtk_path, "crx2rnx.exe")
            if not os.path.exists(exe): raise FileNotFoundError("crx2rnx.exe not found.")
            
            for f in self.crx_files_list:
                # crx2rnx modifies/creates file in place. 
                # "crx2rnx.exe file.d" -> creates "file.o"
                cmd = [exe, f]
                _execute_command(cmd, self.controller.log_frame, f"Decompressing {os.path.basename(f)}...", self.controller, self)
            
            self.after(0, lambda: messagebox.showinfo("Success", "All files decompressed."))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.after(0, lambda: self.set_processing(False, self.crx_btn, self.crx_progress))

    # --- TAB 3: RTKPLOT ---
    def setup_viz_tab(self, parent):
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text="Launch RTKPLOT for visualization (POS, OBS, etc)").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 15))
        
        ttk.Label(parent, text="File to Open (Optional):").grid(row=1, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.viz_file_var, state="readonly").grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Button(parent, text="Browse...", command=self.browse_viz, bootstyle="secondary").grid(row=1, column=2)
        
        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=20, sticky="w")
        
        self.viz_btn = ttk.Button(btn_frame, text="Open File in RTKPLOT", command=lambda: self.launch_rtkplot(self.viz_file_var.get()), bootstyle="info")
        self.viz_btn.pack(side="left", padx=(0, 10))
        
        self.viz_launch_btn = ttk.Button(btn_frame, text="Launch Empty RTKPLOT", command=lambda: self.launch_rtkplot(None), bootstyle="secondary")
        self.viz_launch_btn.pack(side="left")

    def browse_viz(self):
        path = filedialog.askopenfilename(filetypes=[("Solution/RINEX", "*.pos *.sol *.obs *.rnx *.??o"), ("All files", "*.*")])
        if path:
            self.viz_file_var.set(path)
            self._check_run_states()

    def launch_rtkplot(self, filepath):
        rtk_path = self.controller.rtklib_path_var.get()
        exe = os.path.join(rtk_path, "rtkplot.exe")
        if not os.path.exists(exe):
            messagebox.showerror("Error", "rtkplot.exe not found.")
            return

        cmd = [exe]
        if filepath:
            cmd.append(filepath)
            
        self.controller.log_frame.log(f"Launching external tool: {' '.join(cmd)}")
        # Use Popen so it doesn't block the Python GUI
        subprocess.Popen(cmd, cwd=rtk_path)

    # --- Helpers ---
    def set_processing(self, active, btn, progress):
        self.is_processing = active
        if active:
            btn.config(state="disabled")
            progress.config(mode="indeterminate")
            progress.start()
            self.stop_button.config(state="normal")
        else:
            progress.stop()
            progress.config(mode="determinate", value=0)
            self.stop_button.config(state="disabled")
            self._check_run_states()