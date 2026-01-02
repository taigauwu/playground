import tkinter as tk
import ttkbootstrap as ttk
from tkinter import messagebox
import threading
import subprocess
import os
import sys
import re
from time import sleep
from gui.base import BaseToolFrame
from gui.widgets import Tooltip

class DownloaderFrame(BaseToolFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Dataset Downloader")
        self.is_processing = False
        self.proc = None
        self.is_restarting = False
        self.input_var = tk.StringVar()
        self.password_var = tk.StringVar()

        # Pre-populate password from environment variable if it exists
        env_password = os.environ.get('PROCESSING_TOOLS_PASSWORD')
        if env_password:
            self.password_var.set(env_password)
            
        self.folder_name_var = tk.StringVar()
        self.create_widgets()
        self.input_var.trace_add("write", self._check_run_button_state)
        self.password_var.trace_add("write", self._check_run_button_state)
        self.controller.downloader_dest_path_var.trace_add("write", self._check_run_button_state)

    def create_widgets(self):
        self.content_frame.grid_columnconfigure(0, weight=1)
        input_frame = ttk.Labelframe(self.content_frame, text="1. Enter Details", padding=10, style="Info.TLabelframe")
        input_frame.grid(row=0, column=0, sticky="ew")
        input_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(input_frame, text="PQ Slug ID:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        slug_entry = ttk.Entry(input_frame, textvariable=self.input_var); slug_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=5, pady=5); Tooltip(slug_entry, "Enter the Project Quote Slug ID for the dataset to download.")
        
        ttk.Label(input_frame, text="Dataset or site name (Optional):").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        name_entry = ttk.Entry(input_frame, textvariable=self.folder_name_var); name_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=5); Tooltip(name_entry, "Optional: Provide a name to append to the downloaded folder for better organization.")

        ttk.Label(input_frame, text="Password:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        pass_entry = ttk.Entry(input_frame, textvariable=self.password_var, show="*"); pass_entry.grid(row=2, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        Tooltip(pass_entry, "Enter the password. Automatically read from PROCESSING_TOOLS_PASSWORD environment variable if set.")
        
        info_label = ttk.Label(self.content_frame, text="Note: The outputs are in the Datasets folder.", bootstyle="secondary")
        info_label.grid(row=1, column=0, sticky='w', pady=(5,10))

        run_frame = ttk.Labelframe(self.content_frame, text="2. Run Process", padding=10, style="Info.TLabelframe")
        run_frame.grid(row=2, column=0, sticky="ew", pady=10)
        action_frame = ttk.Frame(run_frame)
        action_frame.grid(row=0, column=0)
        self.run_button = ttk.Button(action_frame, text="Download Dataset", command=self.start_command_thread, state="disabled", bootstyle="primary")
        self.run_button.pack(side="left", padx=(0, 10))
        Tooltip(self.run_button, "Begin the dataset download process.")
        
        self.restart_button = ttk.Button(action_frame, text="Restart", command=self.restart_process, state="disabled", bootstyle="warning")
        self.restart_button.pack(side="left", padx=(0, 10))
        Tooltip(self.restart_button, "Terminate the current download and start a new one with the same inputs.")

        self.progress = ttk.Progressbar(action_frame, orient="horizontal", length=300, mode="determinate", bootstyle="primary")
        self.progress.pack(side="left")

        reset_frame = ttk.Frame(self.content_frame)
        reset_frame.grid(row=3, column=0, sticky="e", pady=(10,0))
        
        self.stop_button = ttk.Button(reset_frame, text="Stop Process", command=lambda: self.controller.terminate_frame_process(self), bootstyle="secondary", state="disabled")
        self.stop_button.pack(side="left", padx=(0, 5))
        Tooltip(self.stop_button, "Forcefully stop the current running process.")

        reset_btn = ttk.Button(reset_frame, text="Reset All", command=self.reset_ui, bootstyle="secondary-outline")
        reset_btn.pack(side="left")
        Tooltip(reset_btn, "Clear all input fields.")

    def reset_ui(self):
        self.input_var.set("")
        self.password_var.set("")
        self.folder_name_var.set("")
        self.controller.log_frame.log("Downloader tool has been reset.")


    def _check_run_button_state(self, *args):
        if self.is_processing: return
        is_valid = bool(self.input_var.get() and self.password_var.get() and self.controller.downloader_dest_path_var.get())
        self.run_button.config(state="normal" if is_valid else "disabled")

    def set_processing_state(self, is_processing):
        self.is_processing = is_processing
        if is_processing:
            self.run_button.config(text="Processing...", state="disabled")
            self.restart_button.config(state="normal")
            self.progress.config(mode="indeterminate")
            self.progress.start()
            self.stop_button.config(state="normal")
        else:
            self.run_button.config(text="Download Dataset")
            self.restart_button.config(state="disabled")
            self.progress.stop()
            self.progress.config(mode="determinate")
            self._check_run_button_state()
            self.stop_button.config(state="disabled")

    def start_command_thread(self):
        if self.is_processing and not self.is_restarting: return
        self.is_restarting = False
        self.set_processing_state(True)
        self.controller.log_frame.log(f"\n{'='*20}\n--- [DOWNLOADER] Starting Download Process ---\n{'='*20}")
        threading.Thread(target=self.run_command, daemon=True, name="Downloader").start()

    def restart_process(self):
        """Terminates the current download process and starts it again."""
        if not self.is_processing or not self.controller.running_processes.get(self):
            return

        log = self.controller.log_frame.log
        log("\n" + "="*20 + "\n--- RESTARTING DOWNLOAD ---\n" + "="*20)
        
        self.is_restarting = True
        self.controller.terminate_frame_process(self)
        
        self.after(500, self.start_command_thread)

    def on_download_complete(self, is_successful):
        """Handles UI updates after the download process is complete."""
        self.set_processing_state(False)
        
        if self.is_restarting:
            return
            
        if is_successful:
            messagebox.showinfo("Success", "Dataset download completed!")
        else:
            if not self.controller.was_terminated:
                messagebox.showerror("Error", "The download process failed. Check the log for details.")
        self.controller.was_terminated = False

    def run_command(self):
        log = self.controller.log_frame.log
        raw_input = self.input_var.get()
        password = self.password_var.get()

        match = re.search(r'pq[a-zA-Z0-9]{8}', raw_input)
        if match:
            user_input = match.group(0)
            log(f"Found and extracted PQ Slug ID: {user_input}")
        else:
            user_input = raw_input.strip()
            log(f"Warning: Could not find a 'pq...' pattern. Using stripped input: '{user_input}'")

        is_successful = False
        
        command_str = f'npx dataset-download "{user_input}"'
        log(f"Running command: {command_str}")

        self.proc = None
        try:
            base_destination = self.controller.downloader_dest_path_var.get()
            if not base_destination or not os.path.isdir(base_destination):
                raise FileNotFoundError("The destination folder in Configuration is not set or does not exist.")

            cwd = base_destination
            log(f"Executing download in folder: {cwd}\n")

            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            self.proc = subprocess.Popen(
                command_str,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=True,
                creationflags=creation_flags,
                encoding='utf-8',
                errors='replace'
            )
            self.controller.running_processes[self] = self.proc

            try:
                self.proc.stdin.write(password + '\n')
                self.proc.stdin.flush()
                self.proc.stdin.close()
            except (IOError, BrokenPipeError):
                log("Warning: Could not write password. The process may have exited prematurely.")

            keywords_to_show = [
                'lidar pq detected', 'fetching source', 'downloading',
                r'\(\d+ / \d+\)', 'flight file summary', 'valid flights',
                'invalid flights', 'orphan', 'gcp summary', 'downloaded gcp file',
                'found', 'capture', 'quality', 'duration', 'renamed', 'skipping',
                'already downloaded', 'error', 'missing', 'longest good quality'
            ]
            
            def _log_clean(line_to_log):
                self.controller.show_log(True)
                self.controller.log_frame.log_widget.config(state="normal")
                self.controller.log_frame.log_widget.insert(tk.END, f"> {line_to_log.strip()}\n")
                self.controller.log_frame.log_widget.see(tk.END)
                self.controller.log_frame.log_widget.config(state="disabled")

            for line in iter(self.proc.stdout.readline, ''):
                if self.is_restarting:
                    break
                line_lower = line.strip().lower()
                if not line_lower or not any(re.search(keyword, line_lower) for keyword in keywords_to_show):
                    continue
                self.after(0, _log_clean, line)

            self.proc.stdout.close()
            return_code = self.proc.wait()

            if self.is_restarting:
                log("Process loop exited due to restart flag.")
                return

            if return_code != 0:
                raise subprocess.CalledProcessError(return_code, command_str)

            is_successful = True
            log("\n--- Download process completed successfully. ---")

            custom_name_raw = self.folder_name_var.get().strip()
            if custom_name_raw:
                # 1. Replace spaces with underscores
                sanitized_name = custom_name_raw.replace(" ", "_")
                # 2. Remove special characters (keep alphanumeric and underscores)
                sanitized_name = re.sub(r'[^\w_]', '', sanitized_name)
                # Remove leading/trailing underscores that might result
                sanitized_name = sanitized_name.strip('_')
                
                original_folder_path = os.path.join(base_destination, user_input)
                new_folder_name = f"{user_input}_{sanitized_name}"
                new_folder_path = os.path.join(base_destination, new_folder_name)
                log(f"Attempting to rename output folder to: {new_folder_name}")

                max_attempts = 5
                for attempt in range(max_attempts):
                    try:
                        if os.path.isdir(original_folder_path):
                            os.rename(original_folder_path, new_folder_path)
                            log(f"    SUCCESS: Folder renamed to '{new_folder_name}'")
                            break
                        else:
                            log(f"    WARNING: Could not find downloaded folder '{user_input}' to rename.")
                            break
                    except (OSError, PermissionError) as e:
                        if attempt < max_attempts - 1:
                            log(f"    Rename failed (Attempt {attempt + 1}/{max_attempts}): {e}. Retrying in 2 seconds...")
                            sleep(2)
                        else:
                            log(f"    --- ERROR: Could not rename folder after {max_attempts} attempts. ---")
                            messagebox.showwarning(
                                "Rename Failed",
                                f"Download was successful, but the folder could not be automatically renamed due to a persistent file lock.\n\nPlease manually rename:\n'{original_folder_path}'\nto\n'{new_folder_path}'"
                            )

        except FileNotFoundError as e:
            log(f"\n--- ERROR ---\nCommand not found: {e.filename}. Is 'npx' in your system's PATH?")
            messagebox.showerror("Execution Error", f"Command not found: {e.filename}.\nPlease ensure Node.js and npx are installed.")
        except subprocess.CalledProcessError:
             if not self.controller.was_terminated:
                log("\n--- Command failed. See log for details. ---")
        except Exception as e:
            if not self.controller.was_terminated:
                log(f"\n--- ERROR ---\nAn unexpected error occurred: {e}")
                messagebox.showerror("Error", f"An unexpected error occurred:\n{e}")
        finally:
            if self in self.controller.running_processes:
                del self.controller.running_processes[self]
            if self.is_restarting:
                log("Old process thread exiting due to restart.")
                return

            if self.proc and self.proc.poll() is None:
                log("Terminating lingering process.")
                self.proc.terminate()
            
            self.after(0, self.on_download_complete, is_successful)