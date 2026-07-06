import os
import pandas as pd

def verify_pipeline():
    print("==================================================")
    print("RUNNING PIPELINE INTEGRITY AND VALIDATION CHECK")
    print("==================================================")
    
    workspace = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(workspace, "output")
    
    expected_files = [
        "all_videos_timeseries.csv",
        "all_videos_summary.csv",
        "master_dashboard.html"
    ]
    
    all_passed = True
    print("\n[Step 1] File Existence Check:")
    for file in expected_files:
        file_path = os.path.join(output_dir, file)
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"  [PASS] {file} exists (size: {size} bytes)")
        else:
            print(f"  [FAIL] {file} is missing!")
            all_passed = False
            
    if not all_passed:
        print("\n[Verification Summary] FAILED - One or more files are missing.")
        return False
        
    print("\n[Step 2] Time-series CSV Schema Verification:")
    ts_csv = os.path.join(output_dir, "all_videos_timeseries.csv")
    try:
        df = pd.read_csv(ts_csv)
        required_cols = [
            "video_name", "frame", "time_seconds",
            "left_knee", "right_knee", "left_hip", "right_hip", "left_ankle", "right_ankle",
            "left_knee_velocity", "right_knee_velocity", "left_knee_acceleration", "right_knee_acceleration"
        ]
        
        missing_cols = [c for c in required_cols if c not in df.columns]
        if len(missing_cols) == 0:
            print(f"  [PASS] Master CSV has shape {df.shape} and all required columns.")
            print(f"  [INFO] Unique videos in CSV: {df['video_name'].unique()}")
            print(f"  [INFO] Average Left Knee Angle overall: {df['left_knee'].mean():.2f} degrees")
        else:
            print(f"  [FAIL] CSV is missing columns: {missing_cols}")
            all_passed = False
    except Exception as e:
        print(f"  [FAIL] Error reading CSV: {e}")
        all_passed = False

    print("\n[Step 3] Exercise Summary Verification:")
    summary_csv = os.path.join(output_dir, "all_videos_summary.csv")
    try:
        df_sum = pd.read_csv(summary_csv)
        print(f"  [PASS] Master Summary CSV verified. Shape: {df_sum.shape}")
        for idx, row in df_sum.iterrows():
            print(f"    - Video: {row['video_name']} | Joint: {row['joint']} | Symmetry Score: {row['score_percentage']:.2f}%")
    except Exception as e:
        print(f"  [FAIL] Error reading summary CSV: {e}")
        all_passed = False

    if all_passed:
        print("\n==================================================")
        print("VERIFICATION COMPLETED: ALL PIPELINE CHECKS PASSED!")
        print("==================================================")
        return True
    else:
        print("\n==================================================")
        print("VERIFICATION FAILED: SEE DETAILED LOGS ABOVE")
        print("==================================================")
        return False

if __name__ == "__main__":
    verify_pipeline()
