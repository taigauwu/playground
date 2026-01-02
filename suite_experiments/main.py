# -*- coding: utf-8 -*-
"""
==========================================
Lidar Utility Suite - Entry Point
==========================================
This is the main execution script for the application.
It handles the initial imports, crash logging, and starts the GUI loop.
"""

import sys
import traceback

try:
    from gui.main_window import App
except ImportError as e:
    print("CRITICAL ERROR: Could not import the main application.")
    print(f"Details: {e}")
    print("\nEnsure your directory structure looks like this:")
    print("LidarApp/")
    print("   ├── main.py")
    print("   └── gui/")
    print("       ├── __init__.py")
    print("       └── main_window.py")
    sys.exit(1)

if __name__ == "__main__":
    try:
        # Initialize the main application window
        app = App()
        
        # Start the GUI event loop
        app.mainloop()

    except Exception as e:
        # This preserves the global crash logging from your original script
        import traceback
        error_msg = "A fatal error occurred:\n" + str(e) + "\n\n" + traceback.format_exc()
        
        print("Application crashed. Writing to crash_log.txt...")
        print(error_msg)
        
        with open("crash_log.txt", "w") as f:
            f.write(error_msg)
        
        # If possible, try to show a native OS alert if the GUI crashed hard
        try:
            import tkinter.messagebox
            root = tkinter.Tk()
            root.withdraw()  # Hide the main window
            tkinter.messagebox.showerror("Fatal Error", f"The application crashed.\nSee crash_log.txt for details.\n\nError: {e}")
            root.destroy()
        except:
            pass
        
        sys.exit(1)