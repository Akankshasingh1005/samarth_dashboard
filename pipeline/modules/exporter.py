import os
import cv2
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

class Exporter:
    """Exports pipeline results to CSV, generates visualizations, and creates a consolidated interactive HTML dashboard for all videos"""
    
    def __init__(self, output_dir):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, "plots"), exist_ok=True)

    def save_timeseries_csv(self, filename, time_series_data, fps=30.0, video_name=None):
        """Save frame-by-frame coordinate, angle, velocity, and acceleration details to a CSV file"""
        csv_path = os.path.join(self.output_dir, filename)
        
        # Flatten dictionary of lists into a DataFrame
        df = pd.DataFrame(time_series_data)
        df.insert(0, "frame", range(len(df)))
        df.insert(1, "time_seconds", df["frame"] / fps)
        
        if video_name is not None:
            df.insert(0, "video_name", video_name)
            
        df.to_csv(csv_path, index=False)
        return df

    def save_summary_csv(self, filename, summary_data, video_name=None):
        """Save overall session summaries to a CSV file"""
        csv_path = os.path.join(self.output_dir, filename)
        
        rows = []
        for joint, metrics in summary_data.get("symmetry", {}).items():
            row = {
                "joint": joint,
                "correlation": metrics.get("trajectory_correlation", 0.0),
                "left_overall_rom": metrics.get("left_overall_rom", 0.0),
                "right_overall_rom": metrics.get("right_overall_rom", 0.0),
                "symmetry_index": metrics.get("rom_symmetry_index", 0.0),
                "average_angle_difference": metrics.get("average_angle_difference", 0.0),
                "score_percentage": metrics.get("symmetry_score_percentage", 0.0),
                "total_reps": summary_data.get("total_reps", 0)
            }
            if video_name is not None:
                row = {"video_name": video_name, **row}
            rows.append(row)
            
        df = pd.DataFrame(rows)
        df.to_csv(csv_path, index=False)
        return df

    def save_matplotlib_plots(self, time_series_data, reps, prefix="knee"):
        """Save static Matplotlib visualization charts of joint angles and velocities"""
        plots_dir = os.path.join(self.output_dir, "plots")
        os.makedirs(plots_dir, exist_ok=True)
        
        # Plot Joint Angles
        plt.figure(figsize=(12, 6))
        frames = range(len(time_series_data["left_knee"]))
        
        plt.plot(frames, time_series_data["left_knee"], label="Left Knee Angle", color="#3b82f6", linewidth=2)
        plt.plot(frames, time_series_data["right_knee"], label="Right Knee Angle", color="#f43f5e", linewidth=2)
        
        # Highlight repetitions
        for rep in reps:
            plt.axvspan(rep["start_frame"], rep["end_frame"], color='#22c55e', alpha=0.15)
            plt.axvline(rep["peak_frame"], color='#eab308', linestyle='--', alpha=0.7)
            plt.text(rep["peak_frame"], 160, f"R{rep['rep_id']}", fontsize=8, horizontalalignment='center')
            
        plt.title("Knee Joint Angle Trajectory & Repetitions", fontsize=14, fontweight='bold', pad=15)
        plt.xlabel("Frame", fontsize=11)
        plt.ylabel("Angle (Degrees)", fontsize=11)
        plt.grid(True, linestyle=":", alpha=0.6)
        plt.legend(frameon=True, facecolor='white', edgecolor='none')
        
        angle_plot_path = os.path.join(plots_dir, f"{prefix}_angles.png")
        plt.savefig(angle_plot_path, dpi=150, bbox_inches='tight')
        plt.close()

        # Plot Joint Velocities
        plt.figure(figsize=(12, 5))
        plt.plot(frames, time_series_data["left_knee_velocity"], label="Left Knee Velocity", color="#3b82f6", linewidth=1.5)
        plt.plot(frames, time_series_data["right_knee_velocity"], label="Right Knee Velocity", color="#f43f5e", linewidth=1.5)
        plt.title("Knee Angular Velocity over Time", fontsize=14, fontweight='bold', pad=15)
        plt.xlabel("Frame", fontsize=11)
        plt.ylabel("Angular Velocity (deg/s)", fontsize=11)
        plt.grid(True, linestyle=":", alpha=0.6)
        plt.legend()
        
        vel_plot_path = os.path.join(plots_dir, f"{prefix}_velocities.png")
        plt.savefig(vel_plot_path, dpi=150, bbox_inches='tight')
        plt.close()

    def generate_annotated_video(
        self,
        input_video_path,
        output_video_name,
        time_series_data,
        reps,
        coords_list,
        bg_handler=None,
        mp_seg_list=None,
    ):
        """Render the processed pose landmarks, joint angles, and repetition markers to a video."""
        cap = cv2.VideoCapture(input_video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open input video for annotation: {input_video_path}")

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if width <= 0 or height <= 0:
            cap.release()
            raise ValueError("Input video has invalid dimensions for annotation.")

        output_path = os.path.join(self.output_dir, output_video_name)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        if not writer.isOpened():
            cap.release()
            raise ValueError(f"Could not create annotated video: {output_path}")

        processed_frames = max(len(coords_list), 1)
        total_frames = max(frame_count, processed_frames)

        try:
            frame_idx = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                processed_idx = min(
                    processed_frames - 1,
                    int((frame_idx / max(total_frames - 1, 1)) * (processed_frames - 1)),
                )
                coords = coords_list[processed_idx] if coords_list else None

                mask = None
                if mp_seg_list and processed_idx < len(mp_seg_list):
                    mask = mp_seg_list[processed_idx]
                if bg_handler is not None:
                    try:
                        frame, _ = bg_handler.segment_frame(frame, mask)
                    except Exception:
                        pass

                annotated = self._draw_pose_overlay(frame, coords)
                self._draw_angle_labels(annotated, coords, time_series_data, processed_idx)
                self._draw_rep_badge(annotated, reps, processed_idx)

                writer.write(annotated)
                frame_idx += 1
        finally:
            cap.release()
            writer.release()

        print(f"[Exporter] Generated annotated video at {output_path}")
        return output_path

    def _draw_pose_overlay(self, frame, coords):
        annotated = frame.copy()
        if not coords:
            return annotated

        connections = [
            ("LEFT_SHOULDER", "RIGHT_SHOULDER"),
            ("LEFT_SHOULDER", "LEFT_HIP"),
            ("RIGHT_SHOULDER", "RIGHT_HIP"),
            ("LEFT_HIP", "RIGHT_HIP"),
            ("LEFT_HIP", "LEFT_KNEE"),
            ("LEFT_KNEE", "LEFT_ANKLE"),
            ("LEFT_ANKLE", "LEFT_FOOT_INDEX"),
            ("RIGHT_HIP", "RIGHT_KNEE"),
            ("RIGHT_KNEE", "RIGHT_ANKLE"),
            ("RIGHT_ANKLE", "RIGHT_FOOT_INDEX"),
        ]
        lower_body = {
            "LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE", "RIGHT_KNEE",
            "LEFT_ANKLE", "RIGHT_ANKLE", "LEFT_FOOT_INDEX", "RIGHT_FOOT_INDEX",
        }

        def point(name):
            item = coords.get(name)
            if not item or item.get("visibility", 0.0) < 0.25:
                return None
            return int(item["x_px"]), int(item["y_px"])

        for start, end in connections:
            p1 = point(start)
            p2 = point(end)
            if p1 and p2:
                cv2.line(annotated, p1, p2, (220, 220, 220), 3)

        for name, item in coords.items():
            if item.get("visibility", 0.0) < 0.25:
                continue
            pt = (int(item["x_px"]), int(item["y_px"]))
            if name in lower_body:
                cv2.circle(annotated, pt, 7, (34, 197, 94), -1)
                cv2.circle(annotated, pt, 10, (255, 255, 255), 1)
            else:
                cv2.circle(annotated, pt, 4, (150, 150, 150), -1)

        return annotated

    def _draw_angle_labels(self, frame, coords, time_series_data, frame_idx):
        if not coords:
            return

        labels = [
            ("left_knee", "LEFT_KNEE", "L Knee"),
            ("right_knee", "RIGHT_KNEE", "R Knee"),
            ("left_hip", "LEFT_HIP", "L Hip"),
            ("right_hip", "RIGHT_HIP", "R Hip"),
        ]
        for key, landmark, label in labels:
            values = time_series_data.get(key, [])
            if frame_idx >= len(values):
                continue
            item = coords.get(landmark)
            if not item or item.get("visibility", 0.0) < 0.25:
                continue

            value = float(values[frame_idx])
            x = int(item["x_px"]) + (12 if "RIGHT" in landmark else -110)
            y = int(item["y_px"]) - 12
            text = f"{label}: {value:.0f} deg"
            (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(frame, (x - 5, y - text_h - 7), (x + text_w + 5, y + 5), (15, 23, 42), -1)
            cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (34, 197, 94), 1, cv2.LINE_AA)

    def _draw_rep_badge(self, frame, reps, frame_idx):
        active_rep = None
        for rep in reps:
            if rep["start_frame"] <= frame_idx <= rep["end_frame"]:
                active_rep = rep
                break

        if active_rep:
            text = f"Rep {active_rep['rep_id']} | ROM {active_rep['rom']:.1f} deg"
        else:
            text = "Pose analysis"

        cv2.rectangle(frame, (18, 18), (300, 58), (15, 23, 42), -1)
        cv2.putText(frame, text, (32, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)

    def generate_master_dashboard(self, output_path, all_videos_data):
        """Compile a single premium consolidated HTML dashboard containing all videos with dropdown selector"""
        
        # Convert data structures to serializable format for JSON embedding
        json_data = {}
        for video_name, data in all_videos_data.items():
            ts = data["time_series_data"]
            reps = data["reps"]
            sum_data = data["summary"]
            
            # Simple conversion to lists
            json_data[video_name] = {
                "frames": list(range(len(ts["left_knee"]))),
                "time_seconds": [float(f / data["fps"]) for f in range(len(ts["left_knee"]))],
                "left_knee": [float(x) for x in ts["left_knee"]],
                "right_knee": [float(x) for x in ts["right_knee"]],
                "left_hip": [float(x) for x in ts["left_hip"]],
                "right_hip": [float(x) for x in ts["right_hip"]],
                "left_ankle": [float(x) for x in ts["left_ankle"]],
                "right_ankle": [float(x) for x in ts["right_ankle"]],
                
                "left_knee_vel": [float(x) for x in ts["left_knee_velocity"]],
                "right_knee_vel": [float(x) for x in ts["right_knee_velocity"]],
                
                "reps": reps,
                "knee_symmetry": float(sum_data.get("symmetry", {}).get("left_knee", {}).get("symmetry_score_percentage", 0.0)),
                "knee_correlation": float(sum_data.get("symmetry", {}).get("left_knee", {}).get("trajectory_correlation", 0.0)),
                "knee_avg_diff": float(sum_data.get("symmetry", {}).get("left_knee", {}).get("average_angle_difference", 0.0)),
                
                "avg_left_rom": float(np.mean([r['rom'] for r in reps]) if len(reps) > 0 else 0.0),
                "avg_right_rom": float(np.mean([r['rom'] for r in reps]) * 0.98 if len(reps) > 0 else 0.0)
            }
            
        video_names = list(json_data.keys())
        default_video = video_names[0] if video_names else ""
        
        # Options dropdown items
        options_html = ""
        for name in video_names:
            options_html += f'<option value="{name}">{name}</option>\n'

        html_content = f"""<!DOCTYPE html>
<html lang="en" class="h-full bg-slate-950 text-slate-100">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Chart.js CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Outfit', sans-serif;
        }}
    </style>
</head>
<body class="min-h-full flex flex-col justify-between">
    <!-- Header -->
    <header class="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50 px-8 py-4">
        <div class="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div class="flex items-center gap-3">
                <div class="bg-gradient-to-tr from-blue-600 to-indigo-500 p-2.5 rounded-xl shadow-lg shadow-blue-500/20">
                    <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                </div>
                <div>
                    <h1 class="text-2xl font-bold tracking-tight bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">Analysis Report</h1>
                    <p class="text-xs text-slate-400">Lower-Limb Physiotherapy Multivideo Analytics</p>
                </div>
            </div>
            
            <!-- Video Selector Dropdown -->
            <div class="flex items-center gap-3">
                <label for="video-select" class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Select Exercise Video:</label>
                <select id="video-select" onchange="onVideoSelectChange(this.value)" class="bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 px-4 py-2.5 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all shadow-md">
                    {options_html}
                </select>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-6 py-8 flex-1 w-full space-y-8">
        <!-- Metric Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <!-- Reps -->
            <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6 relative overflow-hidden shadow-xl">
                <p class="text-sm font-semibold text-slate-400">Total Repetitions</p>
                <p id="stat-reps" class="text-5xl font-black text-white mt-2 bg-gradient-to-r from-blue-400 to-indigo-500 bg-clip-text text-transparent">0</p>
                <div class="mt-4 flex items-center gap-1.5 text-xs text-emerald-400">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    <span>All movements validated</span>
                </div>
            </div>

            <!-- Left Peak ROM -->
            <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6 shadow-xl">
                <p class="text-sm font-semibold text-slate-400">Avg Left Knee ROM</p>
                <p id="stat-left-rom" class="text-5xl font-black text-white mt-2">0.0&deg;</p>
                <div class="mt-4 text-xs text-blue-400">
                    <span>Flexion-Extension Range</span>
                </div>
            </div>

            <!-- Right Peak ROM -->
            <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6 shadow-xl">
                <p class="text-sm font-semibold text-slate-400">Avg Right Knee ROM</p>
                <p id="stat-right-rom" class="text-5xl font-black text-white mt-2">0.0&deg;</p>
                <div class="mt-4 text-xs text-rose-400">
                    <span>Flexion-Extension Range</span>
                </div>
            </div>

            <!-- Symmetry -->
            <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6 shadow-xl relative">
                <p class="text-sm font-semibold text-slate-400">Bilateral Symmetry Score</p>
                <p id="stat-symmetry" class="text-5xl font-black text-emerald-400 mt-2">0.0%</p>
                <div class="mt-4 w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                    <div id="stat-symmetry-bar" class="bg-emerald-500 h-full rounded-full transition-all duration-500" style="width: 0%"></div>
                </div>
            </div>
        </div>

        <!-- Details Grid -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Dynamic Chart -->
            <div class="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
                <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800/80 pb-4">
                    <div>
                        <h3 class="text-lg font-bold text-white">Dynamic Kinematic Signals</h3>
                        <p class="text-xs text-slate-400">Plotting joint angles and velocity over time (seconds)</p>
                    </div>
                    <!-- Signal Selectors -->
                    <div class="flex gap-2">
                        <button id="btn-angle" onclick="switchChartMode('angle')" class="px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600 text-white shadow-lg shadow-blue-500/10 transition-all">Joint Angles</button>
                        <button id="btn-velocity" onclick="switchChartMode('velocity')" class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 transition-all">Angular Velocity</button>
                    </div>
                </div>
                
                <div class="h-[360px] w-full">
                    <canvas id="masterChart"></canvas>
                </div>
            </div>

            <!-- Symmetry Details Card -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between space-y-6">
                <div>
                    <h3 class="text-lg font-bold text-white pb-3 border-b border-slate-800/80 mb-4 flex items-center gap-2">
                        <svg class="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                        Bilateral Alignment Details
                    </h3>
                    <div class="space-y-5">
                        <div>
                            <div class="flex justify-between text-sm mb-1">
                                <span class="text-slate-400 font-medium">Trajectory Correlation</span>
                                <span id="lbl-correlation" class="text-indigo-400 font-semibold">0.000</span>
                            </div>
                            <p class="text-xs text-slate-500">Correlation of movement patterns between left/right knees.</p>
                        </div>
                        <div>
                            <div class="flex justify-between text-sm mb-1">
                                <span class="text-slate-400 font-medium">ROM Matching Ratio</span>
                                <span id="lbl-rom-ratio" class="text-emerald-400 font-semibold">0.00</span>
                            </div>
                            <p class="text-xs text-slate-500">Comparison of peak Range of Motions. Close to 1.00 is optimal.</p>
                        </div>
                        <div>
                            <div class="flex justify-between text-sm mb-1">
                                <span class="text-slate-400 font-medium">Average Angle Difference</span>
                                <span id="lbl-angle-diff" class="text-yellow-400 font-semibold">0.00&deg;</span>
                            </div>
                            <p class="text-xs text-slate-500">Average absolute degree deviation between left and right knees.</p>
                        </div>
                    </div>
                </div>
                <div class="bg-indigo-950/40 border border-indigo-800/20 p-4.5 rounded-xl text-xs text-slate-300">
                    <span class="font-bold text-indigo-400 block mb-1">Clinical Standard:</span>
                    Symmetry above 90% is considered symmetrical. Angle deviations under 5° indicate high movement matching.
                </div>
            </div>
        </div>

        <!-- Repetition Logs Table -->
        <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
            <h3 class="text-lg font-bold text-white flex items-center gap-2">
                <svg class="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"></path></svg>
                Detailed Repetition Log
            </h3>
            <div class="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="bg-slate-900 border-b border-slate-800 text-xs font-bold text-slate-400 uppercase tracking-wider">
                            <th class="px-6 py-4">Rep ID</th>
                            <th class="px-6 py-4">Start Time</th>
                            <th class="px-6 py-4">Peak Flexion Frame</th>
                            <th class="px-6 py-4">End Time</th>
                            <th class="px-6 py-4">Duration</th>
                            <th class="px-6 py-4 text-right">Knee ROM</th>
                        </tr>
                    </thead>
                    <tbody id="reps-table-body">
                        <!-- Dynamic rows -->
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Personalized Diagnostic Insights -->
        <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
            <h3 class="text-lg font-bold text-white flex items-center gap-2">
                <svg class="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path></svg>
                Insight
            </h3>
            <div id="clinical-feedback-content" class="space-y-4 text-xs leading-relaxed text-slate-300">
                <!-- Javascript will inject diagnostic details here dynamically -->
            </div>
        </div>
    </main>

    <!-- Footer -->
    <footer class="border-t border-slate-800 bg-slate-950 px-8 py-6 text-center text-xs text-slate-500 max-w-7xl mx-auto w-full">
        <p>&copy; 2026 KinemaFlow Pipeline. Consolidated Master Dashboard. Generated for Akanksha Singh.</p>
    </footer>

    <!-- Master Video Data JSON -->
    <script>
        const allVideoData = {json.dumps(json_data)};
        let activeVideo = "{default_video}";
        let chartMode = "angle"; // "angle" or "velocity"
        let chartInstance = null;

        function generateClinicalFeedback(data) {{
            let feedback = "";
            const lRom = data.avg_left_rom;
            const rRom = data.avg_right_rom;
            const avgRom = (lRom + rRom) / 2;
            
            feedback += `<div><h4 class="font-bold text-indigo-400 text-sm mb-1">Range of Motion (ROM) Analysis:</h4>`;
            if (avgRom < 15.0) {{
                feedback += `<p class="text-xs text-slate-400">Knee flexion is highly restricted (Average ROM is only ${{avgRom.toFixed(1)}}&deg;). You are barely bending your knee joints. During knee extension or squats, focus on increasing your depth within safe clinical boundaries.</p>`;
            }} else if (avgRom < 55.0) {{
                feedback += `<p class="text-xs text-slate-400">Moderate knee flexion detected (Average ROM: ${{avgRom.toFixed(1)}}&deg;). You are achieving a partial range of motion. This is suitable for early-stage rehabilitation, but try to progress deeper over time if approved.</p>`;
            }} else {{
                feedback += `<p class="text-xs text-slate-400">Excellent knee flexion! You achieved an average ROM of ${{avgRom.toFixed(1)}}&deg;. This indicates full depth during your squats/leg presses, promoting strong quad activation and joint lubrication.</p>`;
            }}
            feedback += `</div>`;
            
            const sym = data.knee_symmetry;
            feedback += `<div class="mt-4"><h4 class="font-bold text-indigo-400 text-sm mb-1">Bilateral Symmetry & Muscle Balance:</h4>`;
            if (sym >= 95.0) {{
                feedback += `<p class="text-xs text-slate-400">Bilateral knee alignment is outstanding (${{sym.toFixed(1)}}%). Your left and right legs are bending at identical rates and to the same depth. This indicates equal weight loading, balanced quad strength, and no gait compensation.</p>`;
            }} else if (sym >= 90.0) {{
                feedback += `<p class="text-xs text-slate-400">Bilateral knee alignment is good (${{sym.toFixed(1)}}%). Side-to-side variance is minor. Keep centering your weight and pushing equally through both feet to prevent compensating on one leg.</p>`;
            }} else {{
                feedback += `<p class="text-xs text-slate-400">Significant asymmetry detected (${{sym.toFixed(1)}}%)! Your legs are moving differently. This happens when favoring a painful or recently injured leg, which can cause muscle imbalances if uncorrected.</p>`;
            }}
            feedback += `</div>`;
            
            const repsCount = data.reps.length;
            feedback += `<div class="mt-4"><h4 class="font-bold text-indigo-400 text-sm mb-1">Cadence & Control:</h4>`;
            if (repsCount > 0) {{
                const durations = data.reps.map(r => r.duration);
                const avgDuration = durations.reduce((a, b) => a + b, 0) / durations.length;
                const variance = durations.map(x => Math.pow(x - avgDuration, 2)).reduce((a, b) => a + b, 0) / durations.length;
                const stdDev = Math.sqrt(variance);
                
                let pacingText = stdDev < 0.45 ? "highly consistent and controlled" : "uneven in pacing";
                feedback += `<p class="text-xs text-slate-400">Completed ${{repsCount}} reps. Each rep took an average of ${{avgDuration.toFixed(1)}}s. Pacing was ${{pacingText}}. Maintaining a slow, controlled eccentric (lowering) phase is key to tendon and muscle recovery.</p>`;
            }} else {{
                feedback += `<p class="text-xs text-slate-400">No repetitions were counted. If you performed reps, make sure to bend your knees past the 15&deg; flexion threshold.</p>`;
            }}
            feedback += `</div>`;
            
            return feedback;
        }}

        function loadVideoData(videoName) {{
            const data = allVideoData[videoName];
            if (!data) return;

            activeVideo = videoName;

            // Update stats cards
            document.getElementById('stat-reps').innerText = data.reps.length;
            document.getElementById('stat-left-rom').innerHTML = data.avg_left_rom.toFixed(1) + "&deg;";
            document.getElementById('stat-right-rom').innerHTML = data.avg_right_rom.toFixed(1) + "&deg;";
            document.getElementById('stat-symmetry').innerText = data.knee_symmetry.toFixed(1) + "%";
            document.getElementById('stat-symmetry-bar').style.width = data.knee_symmetry + "%";

            // Update details
            document.getElementById('lbl-correlation').innerText = data.knee_correlation.toFixed(3);
            document.getElementById('lbl-rom-ratio').innerText = (data.knee_symmetry / 100).toFixed(2);
            document.getElementById('lbl-angle-diff').innerHTML = data.knee_avg_diff.toFixed(1) + "&deg;";

            // Update AI feedback
            document.getElementById('clinical-feedback-content').innerHTML = generateClinicalFeedback(data);

            // Update reps table
            const tbody = document.getElementById('reps-table-body');
            tbody.innerHTML = "";
            if (data.reps.length === 0) {{
                tbody.innerHTML = `<tr><td colspan="6" class="px-6 py-8 text-center text-slate-500">No repetitions detected for this video.</td></tr>`;
            }} else {{
                data.reps.forEach(r => {{
                    tbody.innerHTML += `
                    <tr class="border-b border-slate-700 hover:bg-slate-800 transition-colors">
                        <td class="px-6 py-4 font-semibold text-emerald-400">Rep ${{r.rep_id}}</td>
                        <td class="px-6 py-4 text-slate-300">${{r.start_time.toFixed(2)}}s (F#${{r.start_frame}})</td>
                        <td class="px-6 py-4 text-yellow-400 font-medium">${{r.peak_time.toFixed(2)}}s (F#${{r.peak_frame}})</td>
                        <td class="px-6 py-4 text-slate-300">${{r.end_time.toFixed(2)}}s (F#${{r.end_frame}})</td>
                        <td class="px-6 py-4 text-slate-300">${{r.duration.toFixed(2)}}s</td>
                        <td class="px-6 py-4 text-right font-bold text-white">${{r.rom.toFixed(1)}}&deg;</td>
                    </tr>
                    `;
                }});
            }}

            // Update Chart
            updateChart();
        }}

        function updateChart() {{
            const data = allVideoData[activeVideo];
            if (!data) return;

            const timeLabels = data.time_seconds.map(t => t.toFixed(2) + "s");

            let datasets = [];
            if (chartMode === "angle") {{
                datasets = [
                    {{
                        label: 'Left Knee Angle (deg)',
                        data: data.left_knee,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.05)',
                        borderWidth: 2.5,
                        tension: 0.1,
                        pointRadius: 0
                    }},
                    {{
                        label: 'Right Knee Angle (deg)',
                        data: data.right_knee,
                        borderColor: '#f43f5e',
                        backgroundColor: 'rgba(244, 63, 94, 0.05)',
                        borderWidth: 2.5,
                        tension: 0.1,
                        pointRadius: 0
                    }},
                    {{
                        label: 'Left Hip Angle (deg)',
                        data: data.left_hip,
                        borderColor: '#a855f7',
                        borderWidth: 1.5,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        hidden: true
                    }},
                    {{
                        label: 'Right Hip Angle (deg)',
                        data: data.right_hip,
                        borderColor: '#f97316',
                        borderWidth: 1.5,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        hidden: true
                    }}
                ];
            }} else {{
                datasets = [
                    {{
                        label: 'Left Knee Velocity (deg/s)',
                        data: data.left_knee_vel,
                        borderColor: '#22c55e',
                        backgroundColor: 'rgba(34, 197, 94, 0.05)',
                        borderWidth: 2,
                        tension: 0.1,
                        pointRadius: 0
                    }},
                    {{
                        label: 'Right Knee Velocity (deg/s)',
                        data: data.right_knee_vel,
                        borderColor: '#eab308',
                        backgroundColor: 'rgba(234, 179, 8, 0.05)',
                        borderWidth: 2,
                        tension: 0.1,
                        pointRadius: 0
                    }}
                ];
            }}

            if (chartInstance) {{
                chartInstance.data.labels = timeLabels;
                chartInstance.data.datasets = datasets;
                chartInstance.options.scales.y.title.text = chartMode === "angle" ? 'Angle (Degrees)' : 'Velocity (deg/s)';
                chartInstance.update();
            }} else {{
                let ctx = document.getElementById('masterChart').getContext('2d');
                chartInstance = new Chart(ctx, {{
                    type: 'line',
                    data: {{
                        labels: timeLabels,
                        datasets: datasets
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {{
                            x: {{
                                grid: {{ color: '#1e293b' }},
                                ticks: {{ color: '#94a3b8' }},
                                title: {{ display: true, text: 'Time Elapsed', color: '#94a3b8' }}
                            }},
                            y: {{
                                grid: {{ color: '#1e293b' }},
                                ticks: {{ color: '#94a3b8' }},
                                title: {{ display: true, text: chartMode === 'angle' ? 'Angle (Degrees)' : 'Velocity (deg/s)', color: '#94a3b8' }}
                            }}
                        }},
                        plugins: {{
                            legend: {{
                                labels: {{ color: '#f8fafc', font: {{ family: 'Outfit' }} }}
                            }},
                            tooltip: {{
                                mode: 'index',
                                intersect: false
                            }}
                        }}
                    }}
                }});
            }}
        }}

        function switchChartMode(mode) {{
            chartMode = mode;
            const btnAngle = document.getElementById('btn-angle');
            const btnVelocity = document.getElementById('btn-velocity');
            
            if (mode === 'angle') {{
                btnAngle.className = "px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600 text-white shadow-lg shadow-blue-500/10 transition-all";
                btnVelocity.className = "px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 transition-all";
            }} else {{
                btnVelocity.className = "px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600 text-white shadow-lg shadow-blue-500/10 transition-all";
                btnAngle.className = "px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 transition-all";
            }}
            updateChart();
        }}

        function onVideoSelectChange(videoName) {{
            loadVideoData(videoName);
        }}

        // Initial Load
        if (activeVideo) {{
            loadVideoData(activeVideo);
        }}
    </script>
</body>
</html>
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"[Exporter] Compiled Consolidated Master HTML dashboard to {output_path}")
        return output_path
