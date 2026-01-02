import re
import subprocess
import sys
import os
import requests
from tkinter import messagebox

METER_TO_US_FT = 3.280833438333123
METER_TO_INTL_FT = 3.28084

def get_published_from_local(local_string, units):
    """Handles the local string workflow."""

    proj_units = "m" if units == "meters" else units
    local_string = re.sub(r'\+units=\w+', '', local_string).strip() + f" +units={proj_units}"

    with open("local.txt", "w") as f: f.write(local_string)

    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        result = subprocess.run(['gdalsrsinfo', '-o', 'wkt1', 'local.txt'], capture_output=True, text=True, check=True, creationflags=creation_flags)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(f"gdalsrsinfo failed. Ensure GDAL is in your PATH. Error: {e}")
    finally:
        if os.path.exists("local.txt"): os.remove("local.txt")
    return result.stdout.strip()

def get_published_from_epsg(epsg_code, current_unit, desired_unit):
    """Handles the published workflow using an EPSG code."""

    # Note: Short-circuit check removed to ensure WKT is always fetched and validated/modified.
    # This prevents issues where an EPSG code (defined in Meters) is assigned to a file 
    # intended to be Feet just because the user selected "Feet" for both dropdowns.

    try:
        response = requests.get(f"https://epsg.io/{epsg_code}.wkt")
        response.raise_for_status()
        wkt_initial = response.text
        if "not found" in wkt_initial.lower(): raise ValueError(f"WKT for EPSG:{epsg_code} not found.")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Could not retrieve WKT from epsg.io: {e}")
    
    return modify_wkt_for_units(wkt_initial, current_unit, desired_unit)

def _get_scale_factor(current, desired):
    """Calculates the scaling factor for converting from a current unit to a desired unit."""
    if current == desired: return 1.0
    
    factors_from_meter = {"us-ft": METER_TO_US_FT, "ft": METER_TO_INTL_FT}
    
    # Convert current unit to meters
    to_meters = 1.0 / factors_from_meter[current] if current != "meters" else 1.0
        
    # Convert meters to desired unit
    from_meters = factors_from_meter[desired] if desired != "meters" else 1.0
        
    return to_meters * from_meters

def modify_wkt_for_units(wkt_string, current_unit, desired_unit):
    """Scales parameters and updates units in a WKT string between any specified units."""

    # Note: Short-circuit check removed here as well to force WKT processing.
    
    scale_factor = _get_scale_factor(current_unit, desired_unit)
    
    # WKT UNIT block definitions (conversion factor is always TO METERS)
    UNIT_DEFS = {
        "us-ft": f'UNIT["US survey foot", {1 / METER_TO_US_FT:.12f}, AUTHORITY["EPSG", "9003"]]',
        "ft": f'UNIT["foot", {1 / METER_TO_INTL_FT:.12f}, AUTHORITY["EPSG", "9002"]]',
        "meters": 'UNIT["metre", 1.0, AUTHORITY["EPSG", "9001"]]'
    }
    
    # Regex patterns to find existing UNIT blocks
    UNIT_PATTERNS = {
        "meters": r'UNIT\["(metre|meter)",\s*1[^\]]*\]',
        "us-ft": r'UNIT\["(US survey foot|foot_us)",\s*0\.3048006[^\]]*\]',
        "ft": r'UNIT\["(foot|international foot)",\s*0\.3048[^\]]*\]'
    }

    if not re.search(UNIT_PATTERNS[current_unit], wkt_string, re.IGNORECASE):
        messagebox.showwarning("Unit Mismatch", f"The source WKT from epsg.io does not appear to be in the selected 'Current Unit' ({current_unit}). Conversion may be incorrect.")

    wkt_modified = wkt_string

    def scale_parameter(wkt, param_name, factor):
        pattern = re.compile(f'(PARAMETER\\["{param_name}",\\s*(-?[\\d\\.]+)\\])', re.IGNORECASE)
        match = pattern.search(wkt)
        if match:
            original_block, original_value = match.group(1), match.group(2)
            scaled_value = float(original_value) * factor
            new_block = original_block.replace(original_value, f"{scaled_value:.12f}")
            return wkt.replace(original_block, new_block)
        return wkt
    
    for param in ["False_Easting", "False_Northing"]: wkt_modified = scale_parameter(wkt_modified, param, scale_factor)
    
    return re.sub(UNIT_PATTERNS[current_unit], UNIT_DEFS[desired_unit], wkt_modified, flags=re.IGNORECASE)

def validate_and_format_wkt(wkt_text):
    """
    Takes a raw WKT string (WKT1 or WKT2), saves it temporarily,
    and uses gdalsrsinfo to convert it to a standard WKT1 format
    suitable for LAS 1.2 headers.
    """
    temp_filename = "temp_wkt_def.txt"
    
    # Save user input to file
    with open(temp_filename, "w") as f:
        f.write(wkt_text)

    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        
        # -o wkt1 forces the output to be the older, compatible format
        result = subprocess.run(
            ['gdalsrsinfo', '-o', 'wkt1', temp_filename],
            capture_output=True, 
            text=True, 
            check=True, 
            creationflags=creation_flags
        )
        return result.stdout.strip()
        
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(f"Failed to validate WKT. Ensure it is a valid coordinate system string.\nError: {e}")
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)