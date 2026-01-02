import tkinter as tk
import ttkbootstrap as ttk
from tkinter import filedialog, messagebox, scrolledtext
import pandas as pd
import numpy as np
import os
import threading
import sys
import json
from gui.base import BaseToolFrame
from gui.widgets import Tooltip
from utils.geometry import calculate_3d_affine, calculate_2d_conformal, calculate_translation_only
from utils.files import get_laz_output_filename
from core.execution import _execute_pdal_pipeline

# Optional imports for plotting
try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    import matplotlib.patheffects as patheffects
except ImportError:
    pass

class GeoreferenceFrame(BaseToolFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Georeference Point Cloud")
        self.master_df = None
        self.point_vars = {}
        self.matrix_3d_affine, self.matrix_2d_conformal, self.matrix_translation_only = "", "", ""
        self.input_laz_path, self.results_data = tk.StringVar(), {}
        self.sash_configured = False
        self.is_processing = False
        self.create_widgets()
        self.input_laz_path.trace_add("write", lambda *args: self.check_enable_run_button())

    def _limit_sash_drag(self, event=None):
        try:
            if self.middle_frame.sashpos(0) < 260:
                self.middle_frame.sashpos(0, 260)
        except tk.TclError:
            pass

    def _configure_sash_once(self, event=None):
        if not self.sash_configured and self.middle_frame.winfo_width() > 1:
            self.middle_frame.sashpos(0, 300)
            self.middle_frame.bind("<B1-Motion>", self._limit_sash_drag)
            self.sash_configured = True

    def _on_mousewheel(self, event):
        delta = -1 if event.num == 4 or event.delta > 0 else 1
        self.point_canvas.yview_scroll(delta, "units")

    def create_widgets(self):
        self.content_frame.grid_rowconfigure(2, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)
        top_frame = ttk.Labelframe(self.content_frame, text="1. Load Control Points CSV File", padding=10, style="Info.TLabelframe")
        top_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(top_frame, text="Input GCP file (.csv):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.csv_file_path_var = tk.StringVar()
        entry_button_frame = ttk.Frame(top_frame)
        entry_button_frame.grid(row=0, column=1, sticky="ew")
        entry_button_frame.grid_columnconfigure(0, weight=1)
        csv_entry = ttk.Entry(entry_button_frame, textvariable=self.csv_file_path_var)
        csv_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        Tooltip(csv_entry, "Select the CSV file containing Ground Control Points. Required columns: Name, Easting, Northing, Height, X, Y, Z.")
        ttk.Button(entry_button_frame, text="Browse...", command=self.browse_csv, bootstyle="secondary").grid(row=0, column=1)

        note_label = ttk.Label(top_frame, text="Note: The CSV file should have the following format (header included): Name, Easting, Northing, Height, X, Y, Z", bootstyle="secondary")
        note_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=(5,0))

        self.middle_frame = ttk.Panedwindow(self.content_frame, orient=tk.HORIZONTAL)
        self.middle_frame.grid(row=1, column=0, sticky="nsew")
        self.middle_frame.bind("<Configure>", self._configure_sash_once)

        self.control_frame = ttk.Labelframe(self.middle_frame, text="2. Select Points & Recalculate", padding=10, style="Info.TLabelframe")
        self.control_frame.grid_rowconfigure(0, weight=1)
        self.control_frame.grid_columnconfigure(0, weight=1)
        self.middle_frame.add(self.control_frame, weight=1)
        
        checkbox_container = ttk.Frame(self.control_frame)
        checkbox_container.grid(row=0, column=0, sticky="nsew")
        self.point_canvas = tk.Canvas(checkbox_container, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(checkbox_container, orient="vertical", command=self.point_canvas.yview, bootstyle="round")
        self.point_frame = ttk.Frame(self.point_canvas)
        self.point_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.point_canvas.pack(side="left", fill="both", expand=True)
        
        # --- FIX 1: Removed the conflicting <Configure> bindings that caused the crash ---
        self.canvas_window = self.point_canvas.create_window((0, 0), window=self.point_frame, anchor="nw")
        for widget in [self.point_canvas, self.point_frame]:
            for event_type in ["<MouseWheel>", "<Button-4>", "<Button-5>"]: widget.bind(event_type, self._on_mousewheel)
        
        recalc_button = ttk.Button(self.control_frame, text="Recalculate Transformations", command=self.recalculate_transformations, bootstyle="secondary")
        recalc_button.grid(row=1, column=0, pady=(10, 0))
        Tooltip(recalc_button, "Recalculate all transformation matrices based on the currently selected control points.")
        
        notebook_container = ttk.Labelframe(self.middle_frame, text="3. Select transformation method and review results", padding=10, style="Info.TLabelframe")
        notebook_container.grid_rowconfigure(0, weight=1)
        notebook_container.grid_columnconfigure(0, weight=1)
        self.middle_frame.add(notebook_container, weight=1)
        
        self.notebook = ttk.Notebook(notebook_container)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        
        button_frame = ttk.Frame(notebook_container)
        button_frame.grid(row=1, column=0, sticky="w", pady=(10, 0))
        
        self.export_button = ttk.Button(button_frame, text="Export Results to CSV", command=self.export_results_to_csv, state="disabled", bootstyle="secondary")
        self.export_button.pack(side="left")
        Tooltip(self.export_button, "Export the detailed results of the currently selected transformation method to a CSV file.")

        self.plot_button = ttk.Button(button_frame, text="Plot Residuals", command=self.plot_residuals, state="disabled", bootstyle="secondary")
        self.plot_button.pack(side="left", padx=(10, 0))
        Tooltip(self.plot_button, "Generate a 2D plot of the XY residuals for the selected transformation.")
        
        self.tab_3d, self.tab_2d, self.tab_trans = ttk.Frame(self.notebook, padding=5), ttk.Frame(self.notebook, padding=5), ttk.Frame(self.notebook, padding=5)
        self.notebook.add(self.tab_trans, text="Translation")
        self.notebook.add(self.tab_2d, text="2D Conformal")
        self.notebook.add(self.tab_3d, text="3D Affine")
        Tooltip(self.tab_trans, "Calculate a simple translation based on the average difference between control points.")
        Tooltip(self.tab_2d, "Calculate a 2D conformal transformation (scaling, rotation, translation). Requires at least 2 points.")
        Tooltip(self.tab_3d, "Calculate a full 3D affine transformation. Requires at least 3 points.")
        
        self.results_3d, self.results_2d, self.results_trans = self.create_results_widgets(self.tab_3d), self.create_results_widgets(self.tab_2d), self.create_results_widgets(self.tab_trans)
        
        load_frame = ttk.Labelframe(self.content_frame, text="4. Load Point Cloud File", padding=10, style="Info.TLabelframe")
        load_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        load_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(load_frame, text="Input point cloud file (.laz/.las):").grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")
        laz_entry = ttk.Entry(load_frame, textvariable=self.input_laz_path)
        laz_entry.grid(row=0, column=1, sticky="ew")
        Tooltip(laz_entry, "Select the point cloud file (.laz or .las) that you want to transform.")
        ttk.Button(load_frame, text="Browse...", command=self.browse_laz, bootstyle="secondary").grid(row=0, column=2, padx=(10, 0))
        
        run_frame = ttk.Labelframe(self.content_frame, text="5. Run Process", padding=10, style="Info.TLabelframe")
        run_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        action_frame = ttk.Frame(run_frame)
        action_frame.grid(row=0, column=0, sticky="w")
        self.run_transform_button = ttk.Button(action_frame, text="Run Transformation", command=self.start_transform_thread, state="disabled", bootstyle="primary")
        self.run_transform_button.pack(side="left", padx=(0, 10))
        Tooltip(self.run_transform_button, "Apply the selected transformation matrix to the input point cloud file.")
        self.transform_progress = ttk.Progressbar(action_frame, orient="horizontal", length=300, mode="determinate", bootstyle="primary")
        self.transform_progress.pack(side="left")

        reset_frame = ttk.Frame(self.content_frame)
        reset_frame.grid(row=4, column=0, sticky="e", pady=(10,0))
        
        self.stop_button = ttk.Button(reset_frame, text="Stop Process", command=lambda: self.controller.terminate_frame_process(self), bootstyle="secondary", state="disabled")
        self.stop_button.pack(side="left", padx=(0, 5))
        Tooltip(self.stop_button, "Forcefully stop the current running process.")

        reset_btn = ttk.Button(reset_frame, text="Reset All", command=self.reset_ui, bootstyle="secondary-outline")
        reset_btn.pack(side="left")
        Tooltip(reset_btn, "Clear all inputs, selections, and results in this tool.")

    def reset_ui(self):
        self.csv_file_path_var.set("")
        self.input_laz_path.set("")
        self.master_df = None
        for widget in self.point_frame.winfo_children():
            widget.destroy()
        self.point_vars.clear()
        self.clear_all_results()
        self.controller.log_frame.log("Georeferencing tool has been reset.")

    def populate_point_selection(self):
        # 1. Clear existing items
        for widget in self.point_frame.winfo_children():
            widget.destroy()
        
        self.point_vars.clear()
        
        # 2. Loop through every GCP in the CSV
        for point_name in self.master_df['Name']:
            var = tk.BooleanVar(value=True)
            self.point_vars[point_name] = var
            
            # --- ROBUST NAME HANDLING START ---
            # Step A: Create the variable unconditionally (Handles normal names)
            display_name = str(point_name)
            
            # Step B: Shorten it only if it is too long (Handles long names)
            if len(display_name) > 20:
                display_name = display_name[:20] + "..."
            # --- ROBUST NAME HANDLING END ---

            # Step C: Create the checkbox using the safe 'display_name'
            cb = ttk.Checkbutton(self.point_frame, text=display_name, variable=var)
            
            # Add scroll support
            for event_type in ["<MouseWheel>", "<Button-4>", "<Button-5>"]: 
                cb.bind(event_type, self._on_mousewheel)
            
            cb.pack(anchor="w", padx=5, pady=2)

        # 3. Update the scrollbar area
        self.point_frame.update_idletasks()
        self.point_canvas.configure(scrollregion=self.point_canvas.bbox("all"))
        
    def create_results_widgets(self, parent_tab):
        parent_tab.grid_rowconfigure(0, weight=1)
        parent_tab.grid_columnconfigure(0, weight=1)
        text_widget = scrolledtext.ScrolledText(parent_tab, wrap=tk.WORD, height=10, font=("Courier New", 9))
        text_widget.grid(row=0, column=0, sticky="nsew")
        text_widget.config(state="disabled")
        return text_widget

    def browse_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            self.csv_file_path_var.set(path)
            self.load_and_process_csv(path)

    def browse_laz(self):
        path = filedialog.askopenfilename(filetypes=[("Lidar Files", "*.laz *.las"), ("All files", "*.*")])
        if path: self.input_laz_path.set(path)

    def load_and_process_csv(self, path):
        try:
            self.master_df = pd.read_csv(path, header=0, names=['Name', 'E', 'N', 'H', 'X', 'Y', 'Z'])
            if self.master_df.isnull().values.any(): raise ValueError("CSV contains missing values.")
            if not all(col in self.master_df.columns for col in ['E', 'N', 'H', 'X', 'Y', 'Z']): raise ValueError("CSV must contain columns: Name, E, N, H, X, Y, Z")
            self.populate_point_selection()
            self.recalculate_transformations()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load or process CSV:\n{e}")
            self.master_df = None
            self.clear_all_results()

    def recalculate_transformations(self):
        if self.master_df is None: return
        excluded_points = [name for name, var in self.point_vars.items() if not var.get()]
        df_for_calc = self.master_df[~self.master_df['Name'].isin(excluded_points)].copy()
        if df_for_calc.empty:
            messagebox.showwarning("Warning", "At least one point must be selected.")
            return
        self.update_3d_affine_results(df_for_calc)
        self.update_2d_conformal_results(df_for_calc)
        self.update_translation_results(df_for_calc)

    def format_results(self, matrix_str, before, after, TEs, vrmse, trmse, df):
        output = f"PDAL Transformation Matrix:\n\"{matrix_str}\"\n\n--- DELTAS BEFORE TRANSFORMATION ---\n"
        
        header_fmt = "{:<15} {:>12} {:>12} {:>12}\n"
        row_fmt    = "{:<15} {:>12.4f} {:>12.4f} {:>12.4f}\n"

        output += header_fmt.format("Point", "dX", "dY", "dZ")
        output += "-" * 51 + "\n"
        
        for i, row in enumerate(before): 
            clean_row = [float(x) for x in row]
            
            # --- FIX 4: Truncate name in report ---
            clean_name = str(df['Name'].iloc[i])
            if len(clean_name) > 15:
                clean_name = clean_name[:12] + "..."
                
            output += row_fmt.format(clean_name, *clean_row)
            
        output += "\n--- DELTAS AFTER TRANSFORMATION ---\n"
        
        header_fmt_after = "{:<15} {:>12} {:>12} {:>12} {:>12}\n"
        row_fmt_after    = "{:<15} {:>12.4f} {:>12.4f} {:>12.4f} {:>12.4f}\n"

        output += header_fmt_after.format("Point", "dX", "dY", "dZ", "TE")
        output += "-" * 63 + "\n"
        
        for i, row in enumerate(after): 
            clean_row = [float(x) for x in row]
            
            clean_name = str(df['Name'].iloc[i])
            if len(clean_name) > 15:
                clean_name = clean_name[:12] + "..."
                
            output += row_fmt_after.format(clean_name, *clean_row, float(TEs[i]))
            
        output += f"\n--- STATISTICS ---\nVertical RMSE (VRMSE): {float(vrmse):.4f}\nTotal RMSE (TRMSE):     {float(trmse):.4f}\n"
        output += "\n**These values are just estimates. Please still check the point cloud coordinates after transformation.**"
        return output

    def display_results(self, widget, content):
        widget.config(state="normal")
        widget.delete(1.0, tk.END)
        widget.insert(tk.END, content)
        widget.config(state="disabled")

    def clear_all_results(self):
        self.matrix_3d_affine, self.matrix_2d_conformal, self.matrix_translation_only = "", "", ""
        self.results_data = {}
        self.display_results(self.results_3d, "Load a CSV file to begin.")
        self.display_results(self.results_2d, "Load a CSV file to begin.")
        self.display_results(self.results_trans, "Load a CSV file to begin.")
        self.export_button.config(state="disabled")
        self.plot_button.config(state="disabled")
        self.check_enable_run_button()

    def update_3d_affine_results(self, df):
        try:
            if len(df) < 3: raise ValueError("3D Affine requires at least 3 selected points.")
            matrix, before, after, TEs, vrmse, trmse = calculate_3d_affine(df)
            self.matrix_3d_affine = matrix
            self.display_results(self.results_3d, self.format_results(matrix, before, after, TEs, vrmse, trmse, df))
            df_before = pd.DataFrame(before, columns=['dX', 'dY', 'dZ'], index=df['Name'])
            df_after = pd.DataFrame(np.column_stack((after, TEs)), columns=['dX', 'dY', 'dZ', 'TE'], index=df['Name'])
            self.results_data['3d_affine'] = {'matrix': matrix, 'before': df_before, 'after': df_after, 'vrmse': vrmse, 'trmse': trmse}
            self.export_button.config(state="normal")
            self.plot_button.config(state="normal")
        except Exception as e:
            self.matrix_3d_affine = ""
            self.display_results(self.results_3d, f"Could not perform 3D Affine calculation.\n\nError: {e}")
        self.check_enable_run_button()

    def update_2d_conformal_results(self, df):
        try:
            if len(df) < 2: raise ValueError("2D Conformal requires at least 2 selected points.")
            matrix, before, after, TEs, vrmse, trmse = calculate_2d_conformal(df)
            self.matrix_2d_conformal = matrix
            self.display_results(self.results_2d, self.format_results(matrix, before, after, TEs, vrmse, trmse, df))
            df_before = pd.DataFrame(before, columns=['dX', 'dY', 'dZ'], index=df['Name'])
            df_after = pd.DataFrame(np.column_stack((after, TEs)), columns=['dX', 'dY', 'dZ', 'TE'], index=df['Name'])
            self.results_data['2d_conformal'] = {'matrix': matrix, 'before': df_before, 'after': df_after, 'vrmse': vrmse, 'trmse': trmse}
            self.export_button.config(state="normal")
            self.plot_button.config(state="normal")
        except Exception as e:
            self.matrix_2d_conformal = ""
            self.display_results(self.results_2d, f"Could not perform 2D Conformal calculation.\n\nError: {e}")
        self.check_enable_run_button()

    def update_translation_results(self, df):
        try:
            if df.empty: raise ValueError("Translation requires at least 1 control point.")
            matrix, before, after, TEs, vrmse, trmse = calculate_translation_only(df)
            self.matrix_translation_only = matrix
            self.display_results(self.results_trans, self.format_results(matrix, before, after, TEs, vrmse, trmse, df))
            df_before = pd.DataFrame(before, columns=['dX', 'dY', 'dZ'], index=df['Name'])
            df_after = pd.DataFrame(np.column_stack((after, TEs)), columns=['dX', 'dY', 'dZ', 'TE'], index=df['Name'])
            self.results_data['translation_only'] = {'matrix': matrix, 'before': df_before, 'after': df_after, 'vrmse': vrmse, 'trmse': trmse}
            self.export_button.config(state="normal")
            self.plot_button.config(state="normal")
        except Exception as e:
            self.matrix_translation_only = ""
            self.display_results(self.results_trans, f"Could not perform Translation calculation.\n\nError: {e}")
        self.check_enable_run_button()

    def export_results_to_csv(self):
        try:
            transform_keys = ['translation_only', '2d_conformal', '3d_affine']
            selected_key = transform_keys[self.notebook.index(self.notebook.select())]
            results = self.results_data.get(selected_key)
            if not results:
                messagebox.showwarning("No Data", "No results to export for the selected transformation.")
                return
            filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], title="Save Georeferencing Report")
            if not filepath: return
            with open(filepath, 'w', newline='') as f:
                f.write(f"Georeferencing Report - {selected_key.replace('_', ' ').title()}\n\nPDAL Transformation Matrix\n")
                pd.DataFrame(np.array(results['matrix'].split(), dtype=float).reshape(4, 4)).to_csv(f, header=False, index=False)
                f.write("\n\nDeltas Before Transformation\n")
                results['before'].to_csv(f)
                f.write("\n\nDeltas After Transformation\n")
                results['after'].to_csv(f)
                f.write("\n\nStatistics\n")
                pd.DataFrame({'Metric': ['Vertical RMSE (VRMSE)', 'Total RMSE (TRMSE)'], 'Value': [results['vrmse'], results['trmse']]}).to_csv(f, index=False)
            messagebox.showinfo("Success", f"Results exported to:\n{os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"An error occurred during export:\n{e}")

    def plot_residuals(self):
        try:
            # Ensure matplotlib is installed
            if 'matplotlib.figure' not in sys.modules:
                messagebox.showerror("Error", "Matplotlib is required for plotting. Please install it.")
                return

            transform_keys = ['translation_only', '2d_conformal', '3d_affine']
            selected_key = transform_keys[self.notebook.index(self.notebook.select())]
            results = self.results_data.get(selected_key)
            
            if not results or 'after' not in results:
                messagebox.showwarning("No Data", "No results to plot for the selected transformation.")
                return

            excluded_points = [name for name, var in self.point_vars.items() if not var.get()]
            df_for_plot = self.master_df[~self.master_df['Name'].isin(excluded_points)].copy()
            df_plot_data = df_for_plot.merge(results['after'], left_on='Name', right_index=True)

            E, N = df_plot_data['E'].values, df_plot_data['N'].values
            dX, dY, dZ = df_plot_data['dX'].values, df_plot_data['dY'].values, df_plot_data['dZ'].values
            names = df_plot_data['Name'].values
            
            plot_window = tk.Toplevel(self)
            plot_window.title(f"Residuals Plot - {selected_key.replace('_', ' ').title()}")
            plot_window.geometry("900x800")

            dark_mode = self.controller.theme_is_dark.get()
            bg_color = '#222b33' if dark_mode else '#f0f0f0'
            text_color = '#ffffff' if dark_mode else '#000000'
            grid_color = '#444444' if dark_mode else '#cccccc'
            
            plot_window.config(bg=bg_color)

            fig = Figure(figsize=(8, 8), dpi=100, facecolor=bg_color)
            ax = fig.add_subplot(111, facecolor=bg_color)

            plot_range_x = E.max() - E.min() if E.size > 1 else 1
            plot_range_y = N.max() - N.min() if N.size > 1 else 1
            plot_range = max(plot_range_x, plot_range_y)
            if plot_range == 0: plot_range = 1
            max_xy_residual = np.max(np.sqrt(dX**2 + dY**2)) if dX.size > 0 else 0
            arrow_scale_factor = plot_range / (max_xy_residual * 20) if max_xy_residual > 0 else 1

            scatter = ax.scatter(E, N, c=dZ, cmap='viridis', zorder=3, edgecolors='grey', linewidths=0.5)
            
            ax.quiver(E, N, dX * arrow_scale_factor, dY * arrow_scale_factor, dZ, angles='xy', scale_units='xy', scale=1, cmap='viridis', width=0.004, zorder=2)

            for i, name in enumerate(names):
                ax.text(E[i], N[i], f' {name}', fontsize=9, va='bottom', ha='left', color=text_color, zorder=4,
                        path_effects=[patheffects.withStroke(linewidth=3, foreground=bg_color)])

            initial_xlim = ax.get_xlim()
            initial_ylim = ax.get_ylim()

            cbar = fig.colorbar(scatter, ax=ax)
            cbar.set_label('dZ (Vertical Residual)', color=text_color)
            cbar.ax.yaxis.set_tick_params(color=text_color)
            cbar.ax.tick_params(axis='y', labelcolor=text_color)
            cbar.outline.set_edgecolor(text_color)

            ax.set_title(f"Post-Transformation Residuals (Arrows scaled x{arrow_scale_factor:.1f})", color=text_color)
            ax.set_xlabel("X Coordinate", color=text_color)
            ax.set_ylabel("Y Coordinate", color=text_color)

            ax.grid(True, linestyle='--', alpha=0.6, color=grid_color)
            ax.set_aspect('equal', adjustable='box')
            ax.tick_params(axis='x', colors=text_color)
            ax.tick_params(axis='y', colors=text_color)
            for spine in ax.spines.values():
                spine.set_edgecolor(text_color)

            fig.tight_layout()
            
            canvas = FigureCanvasTkAgg(fig, master=plot_window)
            canvas.draw()
            
            def on_scroll(event):
                if event.xdata is None or event.ydata is None: return
                ax = event.inaxes
                if ax is None: return

                scale = 1.1 if event.button == 'up' else 1/1.1
                
                cur_xlim = ax.get_xlim()
                cur_ylim = ax.get_ylim()

                new_xlim = (
                    (cur_xlim[0] - event.xdata) * scale + event.xdata,
                    (cur_xlim[1] - event.xdata) * scale + event.xdata
                )
                new_ylim = (
                    (cur_ylim[0] - event.ydata) * scale + event.ydata,
                    (cur_ylim[1] - event.ydata) * scale + event.ydata
                )
                
                ax.set_xlim(new_xlim)
                ax.set_ylim(new_ylim)
                canvas.draw_idle()

            canvas.mpl_connect('scroll_event', on_scroll)

            toolbar = NavigationToolbar2Tk(canvas, plot_window)
            toolbar.config(background=bg_color)

            def reset_zoom():
                """Resets the view to the initial full extent."""
                ax.set_xlim(initial_xlim)
                ax.set_ylim(initial_ylim)
                canvas.draw_idle()

            def zoom_center(scale):
                """Zooms in or out, centered on the current view."""
                xlim = ax.get_xlim()
                ylim = ax.get_ylim()
                x_center, y_center = (xlim[0] + xlim[1]) / 2, (ylim[0] + ylim[1]) / 2
                x_range, y_range = (xlim[1] - xlim[0]) * scale, (ylim[1] - ylim[0]) * scale
                ax.set_xlim([x_center - x_range / 2, x_center + x_range / 2])
                ax.set_ylim([y_center - y_range / 2, y_center + y_range / 2])
                canvas.draw_idle()

            reset_zoom_btn = ttk.Button(toolbar, text="⤧", command=reset_zoom, width=2, bootstyle="secondary-outline")
            reset_zoom_btn.pack(side=tk.RIGHT, padx=2)
            Tooltip(reset_zoom_btn, "Reset View / Zoom to Fit")

            zoom_out_btn = ttk.Button(toolbar, text="-", command=lambda: zoom_center(1.1), width=2, bootstyle="secondary-outline")
            zoom_out_btn.pack(side=tk.RIGHT, padx=2)
            Tooltip(zoom_out_btn, "Zoom Out (or use mouse wheel)")

            zoom_in_btn = ttk.Button(toolbar, text="+", command=lambda: zoom_center(0.9), width=2, bootstyle="secondary-outline")
            zoom_in_btn.pack(side=tk.RIGHT, padx=2)
            Tooltip(zoom_in_btn, "Zoom In (or use mouse wheel)")

            for child in toolbar.winfo_children():
                if isinstance(child, tk.Button) and not isinstance(child, ttk.Button):
                    button_bg = '#444444' if dark_mode else '#dddddd'
                    active_bg = '#555555' if dark_mode else '#cccccc'
                    child.config(background=button_bg, relief='flat', borderwidth=0, activebackground=active_bg)
                elif isinstance(child, (tk.Label, ttk.Label)):
                    child.config(background=bg_color, foreground=text_color)
                elif isinstance(child, tk.Frame):
                    child.config(background=bg_color)
            toolbar.update()
            
            canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        except Exception as e:
            messagebox.showerror("Plotting Error", f"An error occurred while generating the plot:\n{e}")

    def check_enable_run_button(self):
        if self.is_processing: return
        matrices_available = bool(self.matrix_3d_affine or self.matrix_2d_conformal or self.matrix_translation_only)
        state = "normal" if bool(self.input_laz_path.get()) and matrices_available else "disabled"
        self.run_transform_button.config(state=state)

    def set_processing_state(self, is_processing):
        self.is_processing = is_processing
        if is_processing:
            self.run_transform_button.config(text="Processing...", state="disabled")
            self.transform_progress.config(mode="indeterminate")
            self.transform_progress.start()
            self.stop_button.config(state="normal")
        else:
            self.run_transform_button.config(text="Run Transformation")
            self.transform_progress.stop()
            self.transform_progress.config(mode="determinate")
            self.transform_progress['value'] = 0
            self.check_enable_run_button()
            self.stop_button.config(state="disabled")

    def start_transform_thread(self):
        if self.is_processing: return
        self.controller.log_frame.log(f"\n{'='*20}\n--- [GEOREFERENCE] Starting Transformation ---\n{'='*20}")
        self.set_processing_state(True)
        threading.Thread(target=self.run_point_cloud_transformation, daemon=True, name="Georeferencing").start()

    def on_transform_complete(self, is_success, message):
        """Handles UI updates after the transformation process is complete."""
        self.set_processing_state(False)
        if is_success:
            messagebox.showinfo("Success", message)
        elif message and not self.controller.was_terminated:
            messagebox.showerror("Error", message)
        self.controller.was_terminated = False # Reset flag

    def run_point_cloud_transformation(self):
        is_success = False
        message = ""
        try:
            input_laz = self.input_laz_path.get()
            if not os.path.isfile(input_laz):
                raise FileNotFoundError("Please select a valid input point cloud file.")
            
            matrices = {
                "3d_affine": self.matrix_3d_affine,
                "2d_conformal": self.matrix_2d_conformal,
                "translation_only": self.matrix_translation_only
            }
            abbreviations = {
                "3d_affine": "3d",
                "2d_conformal": "2d",
                "translation_only": "tr"
            }
            
            selected_type_key = ['translation_only', '2d_conformal', '3d_affine'][self.notebook.index(self.notebook.select())]
            chosen_matrix = matrices[selected_type_key]
            
            if not chosen_matrix:
                raise ValueError(f"No valid matrix for '{selected_type_key}'. Please ensure calculation succeeded.")
            
            suffix = f"_{abbreviations[selected_type_key]}"
            output_path = get_laz_output_filename(input_laz, suffix)

            pipeline = [
                {"type": "readers.las", "filename": input_laz},
                {"type": "filters.transformation", "matrix": chosen_matrix},
                {
                    "type": "writers.las",
                    "filename": output_path,
                    "minor_version": 2,
                    "dataformat_id": 3,
                    "forward": "all",
                    "scale_x": 0.001, "scale_y": 0.001, "scale_z": 0.001,
                    "offset_x": "auto", "offset_y": "auto", "offset_z": "auto"
                }
            ]
            
            log_message = f"> Executing PDAL transform pipeline...\n  Input: {os.path.basename(input_laz)}\n  Output: {os.path.basename(output_path)}\n"
            _execute_pdal_pipeline(pipeline, self.controller.log_frame, log_message, controller=self.controller, frame_instance=self)
            
            is_success = True
            message = f"Point Cloud Transformation complete!\nOutput: {os.path.basename(output_path)}"
            
        except Exception as e:
            if not self.controller.was_terminated:
                message = f"Transformation Failed:\n{e}"
            is_success = False
            
        finally:
            self.after(0, self.on_transform_complete, is_success, message)