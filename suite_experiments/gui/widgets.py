import tkinter as tk
import ttkbootstrap as ttk
import threading

FONT_FAMILY = "Segoe UI"

class Tooltip:
    """Creates a tooltip for a given widget with a delay."""
    def __init__(self, widget, text, delay=500, wraplength=250):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.wraplength = wraplength
        self.tooltip_window = None
        self.after_id = None
        self.widget.bind("<Enter>", self.schedule_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
        self.widget.bind("<ButtonPress>", self.hide_tooltip)

    def schedule_tooltip(self, event=None):
        self.cancel_schedule()
        self.after_id = self.widget.after(self.delay, self.show_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window: return
        
        # --- FIX: Handle widgets without 'insert' cursor ---
        try:
            x, y, _, _ = self.widget.bbox("insert")
            x += self.widget.winfo_rootx() + 25
            y += self.widget.winfo_rooty() + 20
        except (tk.TclError, ValueError, AttributeError):
            # Fallback for Buttons, Checkbuttons, etc.
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
            
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip_window, text=self.text, justify='left',
                       background="#ffffe0", relief='solid', borderwidth=1,
                       wraplength=self.wraplength, font=(FONT_FAMILY, 9, "normal"))
        label.pack(ipadx=1)

    def hide_tooltip(self, event=None):
        self.cancel_schedule()
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None
    
    def cancel_schedule(self):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

class OperationLogFrame(ttk.Labelframe):
    def __init__(self, parent, controller):
        super().__init__(parent, text="Operation Log", bootstyle="secondary")
        self.controller = controller
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.log_widget = tk.Text(self, wrap=tk.WORD, height=10, font=("Courier New", 9))
        v_scroll = ttk.Scrollbar(self, orient="vertical", command=self.log_widget.yview, bootstyle="round")
        self.log_widget.configure(yscrollcommand=v_scroll.set)

        button_frame = ttk.Frame(self)
        clear_button = ttk.Button(button_frame, text="Clear", width=8, command=self.clear, bootstyle="secondary")
        hide_button = ttk.Button(button_frame, text="Hide", width=8, command=lambda: self.controller.show_log(False), bootstyle="secondary")
        
        self.log_widget.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        button_frame.grid(row=0, column=2, sticky="ns", padx=(5, 5))
        
        clear_button.pack(pady=5, anchor="n")
        Tooltip(clear_button, "Clear all messages from this log.")
        hide_button.pack(pady=5, anchor="n")
        Tooltip(hide_button, "Hide the operation log panel.")

        self.log_widget.config(state="disabled")

    def log(self, message):
        """Prints messages to the Operation Log Frame text box with thread info."""
        thread_name = threading.current_thread().name
        log_prefix = "[GUI]" if thread_name == "MainThread" else f"[{thread_name}]"
        def _log_thread_safe():
            self.controller.show_log(True)
            self.log_widget.config(state="normal")
            if message.strip().startswith("="*20):
                self.log_widget.insert(tk.END, "\n")
            self.log_widget.insert(tk.END, f"{log_prefix}: {message}\n")
            self.log_widget.see(tk.END)
            self.log_widget.config(state="disabled")
        self.controller.after(0, _log_thread_safe)
        
    def clear(self):
        self.log_widget.config(state="normal")
        self.log_widget.delete("1.0", tk.END)
        self.log_widget.config(state="disabled")
        
    def clear_and_log(self, message):
        def _clear_log_thread_safe():
            self.clear()
            self.log(message)
        self.controller.after(0, _clear_log_thread_safe)