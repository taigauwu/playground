import sys
import numpy as np

# 1. Safe Import with Flag
HAS_TRANSFORMS3D = False
try:
    from transforms3d._gohlketransforms import affine_matrix_from_points
    HAS_TRANSFORMS3D = True
except ImportError:
    pass

def calculate_3d_affine(df):
    """Computes a 3D affine transformation matrix from control points."""
    
    # 2. Check dependency
    if not HAS_TRANSFORMS3D:
        raise ImportError("The 'transforms3d' library is missing.\nPlease install it: pip install transforms3d")

    # 3. CRITICAL FIX: Force data to Float. 
    try:
        gcp = df[['E', 'N', 'H']].to_numpy(dtype=float).transpose()
        pc = df[['X', 'Y', 'Z']].to_numpy(dtype=float).transpose()
    except ValueError:
        raise ValueError("Input CSV contains non-numeric data. Please check for headers or text in coordinate columns.")

    if pc.shape[1] < 3:
        raise ValueError("3D Affine transformation requires at least 3 control points.")
    
    # 4. Calculation
    M = affine_matrix_from_points(pc, gcp, shear=False, scale=True, usesvd=True)

    pc_extended = np.vstack([pc, np.ones(pc.shape[1])])
    new_coords = np.dot(M, pc_extended)

    dxdydz_before = (gcp - pc).transpose()
    dxdydz_after = (gcp - new_coords[0:3]).transpose()

    matrix_str = ' '.join(map(str, M.flatten()))

    TEs = np.sqrt(np.sum(dxdydz_after**2, axis=1))
    vrmse = np.sqrt(np.mean(dxdydz_after[:, 2]**2))
    trmse = np.sqrt(np.mean(TEs**2))

    return matrix_str, dxdydz_before, dxdydz_after, TEs, vrmse, trmse

def calculate_2d_conformal(df):
    """Computes a 2D conformal transformation."""
    num_pts = df.shape[0]

    if num_pts < 2:
        raise ValueError("2D Conformal transformation requires at least 2 control points.")
    
    # Force float types
    try:
        X = df['X'].values.astype(float)
        Y = df['Y'].values.astype(float)
        E = df['E'].values.astype(float)
        N = df['N'].values.astype(float)
    except ValueError:
        raise ValueError("Input CSV contains non-numeric data.")
    
    B_matrix = np.zeros((2 * num_pts, 4))
    B_matrix[:num_pts, 0], B_matrix[:num_pts, 1], B_matrix[:num_pts, 2] = X, -Y, 1
    B_matrix[num_pts:, 0], B_matrix[num_pts:, 1], B_matrix[num_pts:, 3] = Y, X, 1
    
    f_matrix = np.concatenate([E, N])
    
    try:
        a, b, TE_param, TN_param = np.linalg.lstsq(B_matrix, f_matrix, rcond=None)[0]
    except np.linalg.LinAlgError as e:
        raise RuntimeError(f"Could not solve 2D conformal transformation: {e}")
    
    # Calculate simple Z translation safely
    try:
        Tz_param = (df['H'].astype(float) - df['Z'].astype(float)).mean()
    except ValueError:
        Tz_param = 0.0
    
    M = np.array([[a, -b, 0, TE_param], [b, a, 0, TN_param], [0, 0, 1, Tz_param], [0, 0, 0, 1]])
    matrix_str = ' '.join(map(str, M.flatten()))

    gcp = df[['E', 'N', 'H']].to_numpy(dtype=float)
    pc = df[['X', 'Y', 'Z']].to_numpy(dtype=float)

    dxdydz_before = gcp - pc
    new_X = a * pc[:, 0] - b * pc[:, 1] + TE_param
    new_Y = b * pc[:, 0] + a * pc[:, 1] + TN_param
    new_Z = pc[:, 2] + Tz_param 
    dxdydz_after = np.column_stack((gcp[:, 0] - new_X, gcp[:, 1] - new_Y, gcp[:, 2] - new_Z))

    TEs = np.sqrt(np.sum(dxdydz_after**2, axis=1))
    vrmse = np.sqrt(np.mean(dxdydz_after[:, 2]**2))
    trmse = np.sqrt(np.mean(TEs**2))

    return matrix_str, dxdydz_before, dxdydz_after, TEs, vrmse, trmse

def calculate_translation_only(df):
    """Computes a simple translation by averaging XYZ differences."""
    if df.empty: raise ValueError("Translation requires at least 1 control point.")

    try:
        gcp = df[['E', 'N', 'H']].to_numpy(dtype=float)
        pc = df[['X', 'Y', 'Z']].to_numpy(dtype=float)
    except ValueError:
        raise ValueError("Input CSV contains non-numeric data.")

    deltas = gcp - pc
    dx_avg, dy_avg, dz_avg = deltas.mean(axis=0)
    
    M = np.array([[1, 0, 0, dx_avg], [0, 1, 0, dy_avg], [0, 0, 1, dz_avg], [0, 0, 0, 1]])
    matrix_str = ' '.join(map(str, M.flatten()))
    
    new_coords = pc + np.array([dx_avg, dy_avg, dz_avg])
    dxdydz_before = deltas
    dxdydz_after = gcp - new_coords
    
    TEs = np.sqrt(np.sum(dxdydz_after**2, axis=1))
    vrmse = np.sqrt(np.mean(dxdydz_after[:, 2]**2))
    trmse = np.sqrt(np.mean(TEs**2))

    return matrix_str, dxdydz_before, dxdydz_after, TEs, vrmse, trmse