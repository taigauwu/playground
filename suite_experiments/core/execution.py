import subprocess
import sys
import os
import json
import tempfile

# Update the function signature to accept 'failure_patterns'
def _execute_command(command, log_widget, log_message, controller=None, frame_instance=None, on_complete=None, failure_patterns=None):
    """
    A generic helper to execute a command-line tool in a thread.
    
    Args:
        failure_patterns (list): Optional. A list of specific strings that, if found in output,
                                 should trigger a failure even if the Exit Code is 0.
                                 Example: ["FATAL ERROR:", "License invalid"]
    """

    log_widget.log(log_message)
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, 
            text=True,
            creationflags=creation_flags,
            encoding='utf-8',
            errors='ignore'
        )
        if controller and frame_instance:
            controller.running_processes[frame_instance] = process
        
        found_failure_pattern = None

        for line in iter(process.stdout.readline, ''):
            log_widget.log(line.strip())
            
            # --- THE HYBRID FIX ---
            # Only check for keywords if the caller specifically provided them.
            if failure_patterns:
                for pattern in failure_patterns:
                    # Case-insensitive check for specific failure phrases
                    if pattern.lower() in line.lower():
                        found_failure_pattern = pattern

        process.stdout.close()
        return_code = process.wait()

        # Fail if Exit Code is bad OR if we found a specific "naughty" phrase
        if return_code != 0:
            log_widget.log(f"\nProcess failed with exit code: {return_code}")
            raise subprocess.CalledProcessError(return_code, command)
        
        if found_failure_pattern:
            log_widget.log(f"\nProcess marked as failed due to keyword: '{found_failure_pattern}'")
            # We raise a custom error to trigger the 'except' block below
            raise RuntimeError(f"Tool reported error: {found_failure_pattern}")
        
        log_widget.log(f"\nCommand completed successfully.")
        if on_complete:
            on_complete()

    except FileNotFoundError as e:
        log_widget.log(f"\n--- ERROR ---")
        log_widget.log(f"File not found: {e.filename}. Please ensure the tool is in your system's PATH or the path is correctly configured.")
        raise
    except (subprocess.CalledProcessError, RuntimeError) as e:
        # This catches both the Exit Code errors AND our custom Keyword errors
        if not (controller and controller.was_terminated):
            log_widget.log(f"\n--- ERROR ---")
            log_widget.log(str(e))
        raise
    except Exception as e:
        log_widget.log(f"\nAn unexpected error occurred: {e}")
        raise
    finally:
        if controller and frame_instance and frame_instance in controller.running_processes:
            del controller.running_processes[frame_instance]

# ... The rest of the file (_execute_las_command, _execute_pdal_pipeline) remains the same ...
# Note: You can also update _execute_las_command similarly if you want to catch LAStools specific errors.