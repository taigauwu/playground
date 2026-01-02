import subprocess
import json
import sys
import os
import shutil

# Graceful import for GeoPandas
try:
    import geopandas as gpd
except ImportError:
    gpd = None

def _log(callback, message):
    """Helper to send messages to the GUI log or print to console."""
    if callback:
        callback(message)
    else:
        print(message)

def _generate_auto_path(input_path, suffix):
    base, ext = os.path.splitext(input_path)
    if not ext or ext.lower() not in ['.las', '.laz']:
        ext = ".laz"
    return f"{base}{suffix}{ext}"

def cleanup_shapefile(filepath, log_callback=None):
    base, _ = os.path.splitext(filepath)
    extensions = ['.shp', '.shx', '.dbf', '.prj', '.cpg', '.sbn', '.sbx']
    for ext in extensions:
        file_to_delete = base + ext
        if os.path.exists(file_to_delete):
            try:
                os.remove(file_to_delete)
            except OSError:
                pass

def process_point_cloud_with_wrench(pdal_exe, pdal_wrench_exe, input_file, polygon_file, output_file, buffer_distance, smrf_params, log_callback=None):
    temp_buffered_shapefile = "buffered_temp.shp"
    temp_initial_clip_file = "clipped_temp.laz"
    temp_classified_file = "classified_temp.laz"
    temp_pipeline_json = "classify_pipeline_temp.json"
    polygon_to_use = polygon_file

    try:
        # --- Step 1: Buffer ---
        if buffer_distance > 0:
            _log(log_callback, f"--- Step 1: Buffering shapefile by {buffer_distance} units ---")
            gdf = gpd.read_file(polygon_file)
            gdf.geometry = gdf.geometry.buffer(buffer_distance)
            gdf.to_file(temp_buffered_shapefile)
            polygon_to_use = temp_buffered_shapefile

        # --- Step 2: Initial Clip ---
        _log(log_callback, "\n--- Step 2: Performing initial clip ---")
        clip_cmd = [pdal_wrench_exe, "clip", "-i", input_file, "-p", polygon_to_use, "-o", temp_initial_clip_file]
        _log(log_callback, f"Executing: {' '.join(clip_cmd)}")
        subprocess.run(clip_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)

        # --- Step 3: Classify ---
        _log(log_callback, "\n--- Step 3: Classifying ground points ---")
        pipeline_def = {
            "pipeline": [
                {"type": "readers.las", "filename": temp_initial_clip_file},
                {"type": "filters.smrf", **smrf_params},
                {"type": "writers.las", "filename": temp_classified_file, "compression": "laszip"}
            ]
        }
        with open(temp_pipeline_json, 'w') as f:
            json.dump(pipeline_def, f, indent=4)
        
        pipeline_cmd = [pdal_exe, "pipeline", temp_pipeline_json]
        _log(log_callback, f"Executing Pipeline: {' '.join(pipeline_cmd)}")
        subprocess.run(pipeline_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)

        # --- Step 4: Final Clip ---
        _log(log_callback, "\n--- Step 4: Performing final clip to original boundary ---")
        final_clip_cmd = [pdal_wrench_exe, "clip", "-i", temp_classified_file, "-p", polygon_file, "-o", output_file]
        _log(log_callback, f"Executing: {' '.join(final_clip_cmd)}")
        subprocess.run(final_clip_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)

        _log(log_callback, f"Inside processing complete. Output: {output_file}")

    except subprocess.CalledProcessError as e:
        _log(log_callback, f"[!] Error in subprocess: {e.stdout}")
        raise e
    finally:
        # Cleanup
        for f in [temp_initial_clip_file, temp_classified_file, temp_pipeline_json]:
            if os.path.exists(f):
                os.remove(f)
        if buffer_distance > 0 and os.path.exists(temp_buffered_shapefile):
            cleanup_shapefile(temp_buffered_shapefile)

def extract_outside_points(pdal_wrench_exe, input_cloud, polygon_file, output_file, log_callback=None):
    _log(log_callback, "\n--- Starting Outside Point Extraction ---")
    temp_boundary_shp = "boundary_temp.shp"
    temp_outside_shp = "outside_area_temp.shp"
    
    try:
        # 1. Boundary
        _log(log_callback, "[1/3] Creating boundary shapefile...")
        subprocess.run([pdal_wrench_exe, "boundary", "-i", input_cloud, "-o", temp_boundary_shp], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)

        # 2. Difference
        _log(log_callback, "[2/3] Calculating 'outside' area using GeoPandas...")
        boundary_gdf = gpd.read_file(temp_boundary_shp)
        polygon_gdf = gpd.read_file(polygon_file)
        
        if boundary_gdf.crs != polygon_gdf.crs:
            _log(log_callback, "Reprojecting polygon to match boundary CRS...")
            polygon_gdf = polygon_gdf.to_crs(boundary_gdf.crs)

        outside_gdf = gpd.overlay(boundary_gdf, polygon_gdf, how='difference')
        outside_gdf.to_file(temp_outside_shp)

        # 3. Clip
        _log(log_callback, "[3/3] Clipping point cloud to 'outside' area...")
        subprocess.run([pdal_wrench_exe, "clip", "-i", input_cloud, "-p", temp_outside_shp, "-o", output_file], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
        _log(log_callback, f"Outside extraction complete. Output: {output_file}")

    except subprocess.CalledProcessError as e:
        _log(log_callback, f"[!] Error in subprocess: {e.stdout}")
        raise e
    finally:
        cleanup_shapefile(temp_boundary_shp)
        cleanup_shapefile(temp_outside_shp)

def merge_point_clouds(pdal_exe, input_file_in, input_file_out, output_file, log_callback=None):
    _log(log_callback, f"\n--- Merging '{os.path.basename(input_file_in)}' and '{os.path.basename(input_file_out)}' ---")
    try:
        cmd = [pdal_exe, "merge", input_file_in, input_file_out, output_file]
        _log(log_callback, f"Executing: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
        _log(log_callback, f"Merge complete. Final Output: {output_file}")
    finally:
        for f in [input_file_in, input_file_out]:
            if os.path.exists(f):
                os.remove(f)

def run_smrf_workflow(input_cloud, input_polygon, slope, threshold, cell, window, pdal_exe, pdal_wrench_exe, log_callback=None):
    """Main entry point for the workflow."""
    if gpd is None:
        raise ImportError("GeoPandas is not installed. Please run 'pip install geopandas' to use this tool.")

    input_cloud = os.path.normpath(input_cloud)
    input_polygon = os.path.normpath(input_polygon)
    
    # Define Outputs
    intermediate_inside = _generate_auto_path(input_cloud, "_in")
    intermediate_outside = _generate_auto_path(input_cloud, "_out")
    final_output = _generate_auto_path(input_cloud, "_SMRF")
    
    buffer_distance = window - 1
    
    smrf_params = {
        "slope": slope,
        "window": window,
        "threshold": threshold,
        "cell": cell
    }

    # 1. Process Inside
    process_point_cloud_with_wrench(
        pdal_exe, pdal_wrench_exe, input_cloud, input_polygon, 
        intermediate_inside, buffer_distance, smrf_params, log_callback
    )
    
    # 2. Process Outside
    extract_outside_points(
        pdal_wrench_exe, input_cloud, input_polygon, 
        intermediate_outside, log_callback
    )
    
    # 3. Merge
    merge_point_clouds(
        pdal_exe, intermediate_inside, intermediate_outside, 
        final_output, log_callback
    )
    
    return final_output