import numpy as np
from scipy.signal import savgol_filter
from config import SAVGOL_WINDOW_LENGTH, SAVGOL_POLYORDER

def smooth_signal(signal, window_length=SAVGOL_WINDOW_LENGTH, polyorder=SAVGOL_POLYORDER):
    """
    Applies Savitzky-Golay filter to smooth a 1D time-series signal.
    Handles small signal lengths dynamically to prevent crashes.
    """
    arr = np.array(signal)
    n = len(arr)
    
    # If the signal is too short to smooth
    if n <= 3:
        return list(arr)
        
    # Dynamically adjust window length if signal size is smaller than window_length
    curr_window = window_length
    if n <= curr_window:
        # Window length must be odd and less than signal size n
        curr_window = n - 1 if n % 2 == 0 else n - 2
        # Ensure it is at least 3
        curr_window = max(3, curr_window)

    # Ensure polyorder is less than window length
    curr_polyorder = polyorder
    if curr_polyorder >= curr_window:
        curr_polyorder = curr_window - 1

    try:
        smoothed = savgol_filter(arr, window_length=curr_window, polyorder=curr_polyorder)
        return list(smoothed)
    except Exception as e:
        print(f"[filter_utils] Warning: Savitzky-Golay failed: {e}. Returning original signal.")
        return list(arr)

def smooth_joint_trajectories(time_series_data, joints_list, window_length=SAVGOL_WINDOW_LENGTH, polyorder=SAVGOL_POLYORDER):
    """
    Smooths multiple signals in a dictionary.
    time_series_data: dict of lists, e.g. {"left_knee": [...], "right_knee": [...]}
    joints_list: list of keys to smooth.
    """
    smoothed_data = {}
    for key, signal in time_series_data.items():
        if key in joints_list and len(signal) > 0:
            smoothed_data[key] = smooth_signal(signal, window_length, polyorder)
        else:
            smoothed_data[key] = signal
    return smoothed_data
