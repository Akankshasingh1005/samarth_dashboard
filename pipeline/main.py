import os
import sys
import argparse
import numpy as np
import cv2
import pandas as pd
from config import WORKSPACE_DIR, OUTPUT_DIR, LANDMARKS, SAVE_ANNOTATED_VIDEO, ENHANCE_VIDEO, ENHANCE_LEVEL
from modules.video_utils import VideoProcessor
from modules.video_enhance import VideoEnhancer
from modules.background_seg import BackgroundSegmenter
from modules.pose_estimator import PoseEstimator
from modules.kinematics import KinematicsExtractor
from modules.filter_utils import smooth_joint_trajectories
from modules.feature_extractor import FeatureExtractor
from modules.exporter import Exporter

def generate_demo_video(output_path, width=640, height=480, fps=30.0, duration=8.0):
    """
    Generates a synthetic demo video of a person performing squat-like movements.
    We draw a realistic outline that MediaPipe can detect.
    """
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    num_frames = int(fps * duration)
    for frame_idx in range(num_frames):
        # Create a background (light grey room-like appearance)
        img = np.ones((height, width, 3), dtype=np.uint8) * 230
        
        # Draw floor and back wall guidelines
        cv2.line(img, (0, height - 80), (width, height - 80), (180, 180, 180), 2)
        cv2.line(img, (80, 0), (80, height), (200, 200, 200), 1)
        
        # Simulate a squatting figure (hip moves up and down, knees flex)
        t = frame_idx / fps
        cycle = (2 * np.pi * t) / 3.0
        squat_factor = 0.5 - 0.5 * np.cos(cycle)
        
        # Joint coordinates model
        torso_y_offset = int(squat_factor * 60)
        head_center = (320, 100 + torso_y_offset)
        shoulder = (320, 160 + torso_y_offset)
        hip = (320, 260 + torso_y_offset)
        
        knee_x = 320 - int(squat_factor * 40)
        knee_y = 350 + int(squat_factor * 15)
        ankle = (320, 420)
        
        # Draw shape
        cv2.circle(img, head_center, 25, (80, 80, 80), -1)
        cv2.line(img, head_center, hip, (80, 80, 80), 12)
        cv2.line(img, hip, (knee_x, knee_y), (80, 80, 80), 10)
        cv2.line(img, hip, (320 + (320 - knee_x), knee_y), (80, 80, 80), 10)
        cv2.line(img, (knee_x, knee_y), ankle, (80, 80, 80), 8)
        cv2.line(img, (320 + (320 - knee_x), knee_y), (320, 420), (80, 80, 80), 8)
        cv2.line(img, shoulder, (260, 200 + torso_y_offset), (80, 80, 80), 6)
        cv2.line(img, shoulder, (380, 200 + torso_y_offset), (80, 80, 80), 6)
        
        cv2.circle(img, (head_center[0] - 8, head_center[1] - 5), 3, (255, 255, 255), -1)
        cv2.circle(img, (head_center[0] + 8, head_center[1] - 5), 3, (255, 255, 255), -1)
        
        out.write(img)
        
    out.release()
    print(f"[Demo] Created synthetic demo video: {output_path}")

def run_pipeline_on_video(video_path, output_subfolder_dir, bg_handler, pose_estimator=None, stride=2, save_annotated_video=False, enhancer=None, skip_plots=False, enable_segmentation=True):
    """Executes the movement extraction pipeline on a single video file, returning processed data DataFrames"""
    video_name = os.path.basename(video_path)
    print(f"[Pipeline] Processing video: {video_name}...")

    # Initialize video reader
    reader = VideoProcessor(video_path)
    metadata = reader.get_metadata()
    
    # Calculate downsampled FPS
    fps = metadata["fps"] / stride

    # Initialize pose estimator if not shared
    if pose_estimator is None:
        pose_estimator = PoseEstimator(enable_segmentation=enable_segmentation)
        should_close_pose = True
    else:
        should_close_pose = False

    exporter = Exporter(output_subfolder_dir)
    kinematics = KinematicsExtractor()
    feature_extractor = FeatureExtractor(fps=fps)

    # Reset per-video quality counters on the shared enhancer
    if enhancer is not None:
        enhancer.reset_counts()

    # Raw signal arrays
    raw_trajectories = {
        "left_hip": [], "right_hip": [],
        "left_knee": [], "right_knee": [],
        "left_ankle": [], "right_ankle": []
    }
    
    coords_history = []
    mp_segmentation_masks = []

    frame_generator = reader.frame_generator(enhancer=enhancer)
    landmarks_detected_count = 0

    for frame_idx, (orig_frame, enhanced_frame, _quality_report) in enumerate(frame_generator):
        # Skip frames according to downsampling stride
        if frame_idx % stride != 0:
            continue

        # MediaPipe Pose Inference - use the quality-enhanced frame
        results, seg_mask = pose_estimator.process_frame(enhanced_frame)
        if enable_segmentation:
            mp_segmentation_masks.append(seg_mask)
        
        # Extract coordinates
        joints = pose_estimator.extract_joint_coordinates(results, orig_frame.shape)
        coords_history.append(joints)
        
        if joints is not None:
            landmarks_detected_count += 1
            angles = kinematics.extract_angles(joints)
            if angles is not None:
                for k in raw_trajectories.keys():
                    raw_trajectories[k].append(angles[k])
            else:
                for k in raw_trajectories.keys():
                    prev = raw_trajectories[k][-1] if len(raw_trajectories[k]) > 0 else 180.0
                    raw_trajectories[k].append(prev)
        else:
            for k in raw_trajectories.keys():
                prev = raw_trajectories[k][-1] if len(raw_trajectories[k]) > 0 else 180.0
                raw_trajectories[k].append(prev)

    reader.release()
    if should_close_pose:
        pose_estimator.close()
    
    # 1. Temporal Smoothing
    smoothed_trajectories = smooth_joint_trajectories(
        raw_trajectories, 
        joints_list=["left_knee", "right_knee", "left_hip", "right_hip", "left_ankle", "right_ankle"]
    )
    
    # 2. Extract Velocity and Acceleration
    for joint in ["left_knee", "right_knee", "left_hip", "right_hip", "left_ankle", "right_ankle"]:
        vel, acc = kinematics.calculate_derivatives(smoothed_trajectories[joint], fps=fps)
        smoothed_trajectories[f"{joint}_velocity"] = vel
        smoothed_trajectories[f"{joint}_acceleration"] = acc

    # 3. Detect Repetitions
    reps = feature_extractor.detect_repetitions(smoothed_trajectories["left_knee"], min_rom=15.0)

    # 4. Bilateral Symmetry Analysis
    symmetry_data = feature_extractor.analyze_symmetry(
        left_signals=smoothed_trajectories,
        right_signals=smoothed_trajectories,
        joints_of_interest=["left_knee", "left_hip", "left_ankle"]
    )
    
    aligned_symmetry = {
        "left_knee": symmetry_data.get("left_knee", {}),
        "left_hip": symmetry_data.get("left_hip", {}),
        "left_ankle": symmetry_data.get("left_ankle", {})
    }
    summary_metrics = {"symmetry": aligned_symmetry, "total_reps": len(reps)}

    # 5. Export Individual Outputs (with added timestamp and video name)
    ts_df = exporter.save_timeseries_csv("joint_data_timeseries.csv", smoothed_trajectories, fps=fps, video_name=video_name)
    sum_df = exporter.save_summary_csv("exercise_summary.csv", summary_metrics, video_name=video_name)
    if not skip_plots:
        exporter.save_matplotlib_plots(smoothed_trajectories, reps, prefix="knee")
    
    # Check option to save annotated video overlays
    if save_annotated_video:
        exporter.generate_annotated_video(
            input_video_path=video_path,
            output_video_name="annotated_video.mp4",
            time_series_data=smoothed_trajectories,
            reps=reps,
            coords_list=coords_history,
            bg_handler=bg_handler,
            mp_seg_list=mp_segmentation_masks
        )

    # Return results for consolidated reports
    quality_summary = enhancer.get_summary() if enhancer is not None else {}
    video_summary = {
        "time_series_data": smoothed_trajectories,
        "reps": reps,
        "summary": summary_metrics,
        "fps": fps,
        "landmarks_detected_count": landmarks_detected_count,
        "avg_left_rom": float(np.mean([r['rom'] for r in reps]) if len(reps) > 0 else 0.0),
        "avg_right_rom": float(np.mean([r['rom'] for r in reps]) * 0.98 if len(reps) > 0 else 0.0),
        "quality_summary": quality_summary,
    }

    return ts_df, sum_df, video_summary

def print_beautiful_summary(all_videos_data, master_csv_path, master_html_path):
    """Outputs a clean, human-readable summary table to the console"""
    print("\n" + "=" * 100)
    print(" " * 32 + "KINEMAFLOW PIPELINE RUN SUMMARY")
    print("=" * 100)
    print(f" {'Video Name':<30} | {'Reps':<6} | {'Avg Knee ROM (L/R)':<22} | {'Symmetry Score':<16} | {'Enhanced':<9} | {'Status':<6}")
    print("-" * 100)
    for video_name, data in all_videos_data.items():
        reps_count = len(data["reps"])
        avg_l = data["avg_left_rom"]
        avg_r = data["avg_right_rom"]
        symmetry = data["summary"].get("symmetry", {}).get("left_knee", {}).get("symmetry_score_percentage", 0.0)
        status = "PASS" if symmetry >= 90.0 else "WARN"
        rom_str = f"{avg_l:.1f}\u00b0 / {avg_r:.1f}\u00b0"
        q = data.get("quality_summary", {})
        enhanced_count = q.get("total_enhanced", 0)
        print(f" {video_name:<30} | {reps_count:<6} | {rom_str:<22} | {symmetry:.1f}%{'':11} | {enhanced_count:<9} | {status:<6}")
    print("-" * 100)

    # Print aggregated quality condition breakdown across all videos
    total_counts: dict = {}
    for data in all_videos_data.values():
        for cond, cnt in data.get("quality_summary", {}).items():
            if cond == "total_enhanced":
                continue
            total_counts[cond] = total_counts.get(cond, 0) + cnt
    if any(v > 0 for v in total_counts.values()):
        print("\n Video Quality Conditions Detected Across All Videos:")
        cond_labels = {
            "low_contrast":     "Low Contrast",
            "overexposed":      "Overexposed",
            "underexposed":     "Underexposed",
            "high_glare":       "High Glare",
            "gaussian_noise":   "Gaussian Noise",
            "salt_pepper_noise":"Salt-and-Pepper Noise",
            "motion_blur":      "Motion Blur",
            "colour_cast":      "Colour Cast",
            "low_light":        "Low-Light",
        }
        for key, label in cond_labels.items():
            count = total_counts.get(key, 0)
            if count > 0:
                print(f"   {label:<25}: {count} frame(s) corrected")

    print("-" * 100)
    print(f" Consolidated Time-Series CSV:   {master_csv_path}")
    print(f" Consolidated Master Dashboard:  {master_html_path}")
    print("=" * 100 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Physiotherapy Lower-Limb Kinematics Extraction Pipeline")
    parser.add_argument("--dataset", type=str, default="dataset", help="Directory containing input videos")
    parser.add_argument("--device", type=str, default="cpu", help="Device to run IS-Net on (cpu or cuda)")
    parser.add_argument("--stride", type=int, default=2, help="Frame downsampling stride (e.g. 2 to process every 2nd frame)")
    parser.add_argument("--save-video", action="store_true", default=SAVE_ANNOTATED_VIDEO, help="Render and save annotated video overlays (disabled by default)")
    parser.add_argument("--enhance", action=argparse.BooleanOptionalAction, default=ENHANCE_VIDEO,
                        help="Enable adaptive video quality enhancement (default: on). Use --no-enhance to disable.")
    parser.add_argument("--enhance-level", type=str, default=ENHANCE_LEVEL,
                        choices=["auto", "light", "aggressive"],
                        help="Enhancement aggressiveness: auto | light | aggressive (default: auto)")
    args = parser.parse_args()

    input_dir = os.path.join(WORKSPACE_DIR, args.dataset)
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Extract zip folders if present
    import zipfile
    zip_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.lower().endswith(".zip")]
    for zip_path in zip_files:
        zip_name = os.path.splitext(os.path.basename(zip_path))[0]
        extract_to = os.path.join(input_dir, zip_name)
        print(f"[Pipeline] Extracting zip archive {os.path.basename(zip_path)} to {extract_to}...")
        os.makedirs(extract_to, exist_ok=True)
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            print("[Pipeline] Archive unzipped successfully.")
        except Exception as e:
            print(f"[Pipeline] Zip extraction failed: {e}")

    bg_handler = BackgroundSegmenter(use_isnet=True, device=args.device)

    # Initialise adaptive video quality enhancer
    enhancer = VideoEnhancer(enabled=args.enhance, level=args.enhance_level)

    # Search for all videos recursively in the dataset folder
    video_extensions = (".mp4", ".avi", ".mov", ".mkv")
    videos = []
    for root, _, files in os.walk(input_dir):
        for f in files:
            if f.lower().endswith(video_extensions):
                videos.append(os.path.join(root, f))

    if len(videos) == 0:
        print(f"[Pipeline] No videos found in input folder '{input_dir}' or its subfolders.")
        print("[Pipeline] Creating a synthetic demo video for squat exercises to demonstrate pipeline execution...")
        demo_video_path = os.path.join(input_dir, "demo_squat.mp4")
        generate_demo_video(demo_video_path)
        videos.append(demo_video_path)

    # Collectors for consolidated files
    all_timeseries_dfs = []
    all_summaries_dfs = []
    all_videos_data = {}

    # Process videos
    pose_estimator = PoseEstimator()
    for video in videos:
        video_base = os.path.splitext(os.path.basename(video))[0]
        video_name = os.path.basename(video)
        video_output_dir = os.path.join(OUTPUT_DIR, video_base)

        # Execute pipeline on video sharing the PoseEstimator and VideoEnhancer instances
        ts_df, sum_df, video_summary = run_pipeline_on_video(
            video, video_output_dir, bg_handler, pose_estimator,
            stride=args.stride, save_annotated_video=args.save_video,
            enhancer=enhancer,
        )
        
        all_timeseries_dfs.append(ts_df)
        all_summaries_dfs.append(sum_df)
        all_videos_data[video_name] = video_summary
    pose_estimator.close()

    # Compile Consolidated Master CSV files
    master_ts_path = os.path.join(OUTPUT_DIR, "all_videos_timeseries.csv")
    master_sum_path = os.path.join(OUTPUT_DIR, "all_videos_summary.csv")

    if all_timeseries_dfs:
        master_ts_df = pd.concat(all_timeseries_dfs, ignore_index=True)
        master_ts_df.to_csv(master_ts_path, index=False)
        
    if all_summaries_dfs:
        master_sum_df = pd.concat(all_summaries_dfs, ignore_index=True)
        master_sum_df.to_csv(master_sum_path, index=False)

    # Compile Single Consolidated Master HTML Dashboard
    exporter_master = Exporter(OUTPUT_DIR)
    master_html_path = os.path.join(OUTPUT_DIR, "master_dashboard.html")
    exporter_master.generate_master_dashboard(master_html_path, all_videos_data)

    # Print beautiful summary in the console
    print_beautiful_summary(all_videos_data, master_ts_path, master_html_path)

if __name__ == "__main__":
    main()
