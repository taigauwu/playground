import subprocess
import sys
import os
import json
import tempfile

def _execute_command(command, log_widget, log_message, controller=None, frame_instance=None, on_complete=None):
    """A generic helper to execute a command-line tool in a thread."""

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
        
        error_keyword_found = False
        error_keywords = ["error", "failed", "exception", "could not find"]

        for line in iter(process.stdout.readline, ''):
            log_widget.log(line.strip())
            # Check each line for any of our keywords
            if any(keyword in line.lower() for keyword in error_keywords):
                error_keyword_found = True

        process.stdout.close()
        return_code = process.wait()

        if return_code != 0 or error_keyword_found:
            log_widget.log("\nProcess failed due to non-zero exit code or error keyword in log.")
            raise subprocess.CalledProcessError(return_code, command)
        log_widget.log(f"\nCommand completed successfully.")
        if on_complete:
            on_complete()

    except FileNotFoundError as e:
        log_widget.log(f"\n--- ERROR ---")
        log_widget.log(f"File not found: {e.filename}. Please ensure the tool is in your system's PATH or the path is correctly configured.")
        raise
    except subprocess.CalledProcessError as e:
        if not (controller and controller.was_terminated):
            log_widget.log(f"\n--- ERROR ---")
            log_widget.log(f"Command failed with exit code {e.returncode}.")
        raise
    except Exception as e:
        log_widget.log(f"\nAn unexpected error occurred: {e}")
        raise
    finally:
        if controller and frame_instance and frame_instance in controller.running_processes:
            del controller.running_processes[frame_instance]

def _execute_las_command(command, log_widget, controller=None, frame_instance=None):
    """Executes a LAStools command, logs its output, and captures it for review."""
    log_widget.log(f"Executing: {' '.join(command)}")
    output_lines = []
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, creationflags=creation_flags, encoding='utf-8', errors='ignore'
        )
        if controller and frame_instance:
            controller.running_processes[frame_instance] = process

        for line in iter(process.stdout.readline, ''):
            stripped_line = line.strip()
            log_widget.log(stripped_line)
            output_lines.append(stripped_line)
        process.stdout.close()
        return_code = process.wait()
        output = "\n".join(output_lines)
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command, output=output)
        return output
    except FileNotFoundError:
        error_msg = f"Error: The command '{command[0]}' was not found. Please ensure the path to LAStools is correct."
        log_widget.log(error_msg)
        raise
    except subprocess.CalledProcessError as e:
        if not (controller and controller.was_terminated):
            log_widget.log(f"\n--- ERROR ---\nCommand failed with exit code {e.returncode}.")
        raise
    except Exception as e:
        log_widget.log(f"\nAn unexpected error occurred: {e}")
        raise
    finally:
        if controller and frame_instance and frame_instance in controller.running_processes:
            del controller.running_processes[frame_instance]

def _execute_pdal_pipeline(pipeline, log_widget, log_message, controller=None, frame_instance=None):
    """ A generic helper function to execute a PDAL pipeline from a JSON object. """

    temp_dir = tempfile.gettempdir()
    pipeline_file = os.path.join(temp_dir, "pipeline_temp.json")
    with open(pipeline_file, "w") as f:
        json.dump(pipeline, f, indent=4)

    try:
        log_widget.log(log_message)
        # PDAL path is usually in system PATH, but we could theoretically pass the config path here too
        # For now, we assume 'pdal' is available globally or set in env
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        process = subprocess.Popen(
            ["pdal", "pipeline", pipeline_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creation_flags,
            encoding='utf-8'
        )
        if controller and frame_instance:
            controller.running_processes[frame_instance] = process

        stdout, stderr = process.communicate()
        
        if stdout: log_widget.log(f"\n--- PDAL Output ---\n{stdout}")
        if process.returncode != 0:
            if not (controller and controller.was_terminated):
                log_widget.log(f"\n--- PDAL Errors ---\n{stderr}\n")
            raise RuntimeError("PDAL pipeline failed. Check the log for details.")
        else:
            log_widget.log("PDAL pipeline completed successfully.\n")
    finally:
        if controller and frame_instance and frame_instance in controller.running_processes:
            del controller.running_processes[frame_instance]
        if os.path.exists(pipeline_file):
            os.remove(pipeline_file)