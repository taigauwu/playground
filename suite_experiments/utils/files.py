import os

def get_output_filename(input_file, suffix):
    """Generates a unique output filename with a given suffix."""
    file_name_without_ext, file_extension = os.path.splitext(input_file)
    base_output_file = f"{file_name_without_ext}{suffix}{file_extension}"
    counter = 0
    output_file = base_output_file
    while os.path.exists(output_file):
        counter += 1
        output_file = f"{file_name_without_ext}{suffix}_{counter}{file_extension}"
    return output_file

def get_laz_output_filename(input_file, suffix):
    """Generates a unique output filename with a given suffix, forcing .laz extension."""
    file_name_without_ext, _ = os.path.splitext(input_file)
    base_output_file = f"{file_name_without_ext}{suffix}.laz"
    counter = 0
    output_file = base_output_file
    while os.path.exists(output_file):
        counter += 1
        output_file = f"{file_name_without_ext}{suffix}_{counter}.laz"
    return output_file