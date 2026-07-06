import numpy as np
from scipy.signal import find_peaks

class FeatureExtractor:
    """Extracts high-level features such as repetitions, ROM, and performs bilateral symmetry analysis"""
    
    def __init__(self, fps=30.0):
        self.fps = fps

    def detect_repetitions(self, signal, min_rom=15.0, distance_seconds=1.5):
        """
        Detect repetitions from a joint angle trajectory (e.g., knee or hip angle).
        Assumes flexion decreases the joint angle (e.g. straight leg is ~180 deg, bent leg is ~90 deg).
        We detect peaks in the 'flexion' angle (180 - angle).
        """
        arr = np.array(signal)
        n = len(arr)
        if n < self.fps * 2:
            return []  # Too short to detect repetitions
            
        # Convert to flexion angle (so straight is 0, maximum bend is high)
        # Note: If the angle is already normalized or behaves differently, we handle it
        # For knee/hip, 180 is straight, so 180 - angle represents flexion.
        flexion = 180.0 - arr
        
        # Parameters for peak detection
        min_peak_distance = int(distance_seconds * self.fps)
        
        # Find peaks of flexion (maximum extension of the exercise)
        # We set height to min_rom to filter out noise
        peaks, properties = find_peaks(flexion, distance=min_peak_distance, height=min_rom)
        
        reps = []
        for i, peak in enumerate(peaks):
            # Search backward from peak to find the start of the rep (local minimum in flexion)
            start_frame = 0
            for f in range(peak, 0, -1):
                if f < peak - 1 and flexion[f] <= flexion[f+1] and flexion[f] <= flexion[f-1]:
                    start_frame = f
                    break
                # Fallback if no local min found
                if flexion[f] < 5.0:
                    start_frame = f
                    break
            if start_frame == 0:
                # Find global min in window before peak
                search_start = max(0, peak - int(2.5 * self.fps))
                start_frame = search_start + np.argmin(flexion[search_start:peak])

            # Search forward from peak to find the end of the rep
            end_frame = n - 1
            for f in range(peak, n - 1):
                if f > peak + 1 and flexion[f] <= flexion[f+1] and flexion[f] <= flexion[f-1]:
                    end_frame = f
                    break
                # Fallback if no local min found
                if flexion[f] < 5.0:
                    end_frame = f
                    break
            if end_frame == n - 1:
                # Find global min in window after peak
                search_end = min(n, peak + int(2.5 * self.fps))
                end_frame = peak + np.argmin(flexion[peak:search_end])

            # Verify it's a valid repetition by checking amplitude
            rep_rom = float(np.max(flexion[start_frame:end_frame]) - np.min(flexion[start_frame:end_frame]))
            if rep_rom >= min_rom:
                reps.append({
                    "rep_id": i + 1,
                    "start_frame": int(start_frame),
                    "peak_frame": int(peak),
                    "end_frame": int(end_frame),
                    "start_time": float(start_frame / self.fps),
                    "peak_time": float(peak / self.fps),
                    "end_time": float(end_frame / self.fps),
                    "duration": float((end_frame - start_frame) / self.fps),
                    "rom": rep_rom
                })
                
        return reps

    def calculate_rom_metrics(self, signal, reps):
        """Calculate min, max, and Range of Motion (ROM) for each detected repetition"""
        arr = np.array(signal)
        rom_metrics = []
        for rep in reps:
            start = rep["start_frame"]
            end = rep["end_frame"]
            rep_slice = arr[start:end+1]
            
            min_angle = float(np.min(rep_slice))
            max_angle = float(np.max(rep_slice))
            rom = float(max_angle - min_angle)
            
            rom_metrics.append({
                "rep_id": rep["rep_id"],
                "min_angle": min_angle,
                "max_angle": max_angle,
                "rom": rom
            })
        return rom_metrics

    def analyze_symmetry(self, left_signals, right_signals, joints_of_interest):
        """
        Perform bilateral symmetry analysis by comparing left vs right joint metrics.
        Returns a dict of similarity scores and offset analyses.
        """
        symmetry_results = {}
        
        for joint in joints_of_interest:
            left_arr = np.array(left_signals[joint])
            right_arr = np.array(right_signals[joint])
            
            n = min(len(left_arr), len(right_arr))
            if n < 10:
                continue
                
            left_slice = left_arr[:n]
            right_slice = right_arr[:n]
            
            # 1. Pearson Correlation Coefficient (trajectory shape similarity)
            correlation = 0.0
            if np.std(left_slice) > 0 and np.std(right_slice) > 0:
                correlation = float(np.corrcoef(left_slice, right_slice)[0, 1])
            
            # 2. ROM Comparison
            left_rom_overall = float(np.max(left_slice) - np.min(left_slice))
            right_rom_overall = float(np.max(right_slice) - np.min(right_slice))
            
            rom_ratio = 1.0
            if max(left_rom_overall, right_rom_overall) > 0:
                rom_ratio = 1.0 - (abs(left_rom_overall - right_rom_overall) / max(left_rom_overall, right_rom_overall))
            
            # 3. Dynamic Range Offset (average difference in angles)
            avg_diff = float(np.mean(np.abs(left_slice - right_slice)))
            
            # Overall Symmetry Index (weighted combination of correlation and ROM ratio)
            # Correlation can be negative, so we clip it to 0
            clipped_corr = max(0.0, correlation)
            symmetry_score = float((clipped_corr * 0.4 + rom_ratio * 0.6) * 100.0)
            
            symmetry_results[joint] = {
                "trajectory_correlation": correlation,
                "left_overall_rom": left_rom_overall,
                "right_overall_rom": right_rom_overall,
                "rom_symmetry_index": rom_ratio,
                "average_angle_difference": avg_diff,
                "symmetry_score_percentage": symmetry_score
            }
            
        return symmetry_results
