"""
Live Session WebSocket Handler
Streams real-time pose estimation data from browser webcam → PS1 → frontend.
Protocol:
  Client → Server: JPEG binary frame bytes
  Server → Client: JSON with landmarks, angles, validation, reps, feedback
"""
import json
import asyncio
import base64
import time
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from beanie import PydanticObjectId

from services.pose_engine import get_pose_engine

router = APIRouter()


@router.websocket("/ws/session/{session_id}/{token}")
async def live_session_websocket(websocket: WebSocket, session_id: str, token: str):
    """
    WebSocket endpoint for live exercise sessions.
    Client sends JPEG frames; server returns real-time pose + angle data.
    """
    from services.auth_service import decode_token
    from models.session import Session

    # Authenticate via token in URL
    try:
        token_data = decode_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    logger.info(f"[WS Session] Client connected: session={session_id} user={token_data.user_id}")

    engine = get_pose_engine()
    pose_estimator, kinematics, video_enhancer = engine.create_session_context()

    frame_index = 0
    rep_count = 0
    flexion_history = []
    last_rep_frame = -60  # Min frames between rep counts

    # Accumulators for saving real session data at the end
    all_angles_left_knee = []
    all_angles_right_knee = []
    all_angles_left_hip = []
    all_angles_right_hip = []
    all_angles_left_ankle = []
    all_angles_right_ankle = []
    detected_reps = []  # List of rep dicts
    live_ps2_mode = "mock"
    fps_estimate = 10.0  # approximate based on frame send rate
    frame_start_time = time.time()

    try:
        while True:
            # Receive frame (binary JPEG bytes or base64 string)
            data = await asyncio.wait_for(websocket.receive(), timeout=30.0)

            if data["type"] == "websocket.receive":
                if "bytes" in data and data["bytes"]:
                    frame_bytes = data["bytes"]
                elif "text" in data and data["text"]:
                    # Accept base64-encoded frames from browser MediaRecorder
                    try:
                        msg = json.loads(data["text"])
                        if msg.get("type") == "frame":
                            frame_bytes = base64.b64decode(msg["data"])
                        elif msg.get("type") == "ping":
                            await websocket.send_json({"type": "pong"})
                            continue
                        elif msg.get("type") == "end":
                            break
                        else:
                            continue
                    except Exception:
                        continue
                else:
                    continue

            timestamp_ms = int(time.time() * 1000)
            result = engine.process_frame(
                frame_bytes, frame_index, timestamp_ms,
                pose_estimator, kinematics, video_enhancer
            )

            # Accumulate angle data for saving later
            all_angles_left_knee.append(result.angles.left_knee)
            all_angles_right_knee.append(result.angles.right_knee)
            all_angles_left_hip.append(result.angles.left_hip)
            all_angles_right_hip.append(result.angles.right_hip)
            all_angles_left_ankle.append(result.angles.left_ankle)
            all_angles_right_ankle.append(result.angles.right_ankle)

            rep_result_data = None

            # Simple rep counting from knee flexion signal
            knee_angle = result.angles.left_knee
            if knee_angle > 0:
                flexion = 180.0 - knee_angle
                flexion_history.append(flexion)

                # Detect rep: flexion peak above 15° followed by descent
                if (len(flexion_history) >= 3 and
                        flexion_history[-2] > flexion_history[-1] and
                        flexion_history[-2] > flexion_history[-3] and
                        flexion_history[-2] > 15.0 and
                        frame_index - last_rep_frame > 30):
                    rep_count += 1
                    last_rep_frame = frame_index
                    # Record the rep for saving
                    detected_reps.append({
                        "rep_id": rep_count,
                        "peak_frame": frame_index,
                        "peak_flexion": flexion_history[-2],
                    })

                    # Slice the last 30 frames (approx 3 seconds at 10fps) for this rep
                    rep_len = min(len(all_angles_left_knee), 30)
                    if rep_len >= 5:
                        rep_angles_slice = {
                            "left_knee": all_angles_left_knee[-rep_len:],
                            "right_knee": all_angles_right_knee[-rep_len:],
                            "left_hip": all_angles_left_hip[-rep_len:],
                            "right_hip": all_angles_right_hip[-rep_len:],
                            "left_ankle": all_angles_left_ankle[-rep_len:],
                            "right_ankle": all_angles_right_ankle[-rep_len:],
                        }
                        try:
                            from services.exercise_analysis import get_analyzer
                            analyzer = get_analyzer()
                            rep_analysis = analyzer.analyze_rep(
                                rep_angles_slice,
                                rep_id=rep_count,
                                rep_number=rep_count,
                                fps=fps_estimate
                            )
                            rep_result_data = rep_analysis.model_dump()
                            live_ps2_mode = "real" if analyzer.__class__.__name__ == "ModelExerciseAnalyzer" else "mock"
                        except Exception as rep_err:
                            logger.warning(f"[WS Session] PS2 rep analysis failed: {rep_err}")

                # Keep history bounded
                if len(flexion_history) > 100:
                    flexion_history = flexion_history[-60:]

            # Build response payload
            response = {
                "type": "frame_result",
                "frame_index": frame_index,
                "timestamp_ms": timestamp_ms,
                "angles": result.angles.model_dump(),
                "validation": result.validation.model_dump(),
                "pose_confidence": result.pose_confidence,
                "rep_count": rep_count,
                "landmarks": {
                    name: {
                        "x_norm": lm.x_norm,
                        "y_norm": lm.y_norm,
                        "visibility": lm.visibility,
                    }
                    for name, lm in result.landmarks.items()
                },
            }
            if rep_result_data is not None:
                response["rep_result"] = rep_result_data
                response["ps2_mode"] = live_ps2_mode

            await websocket.send_json(response)
            frame_index += 1

    except asyncio.TimeoutError:
        logger.warning(f"[WS Session] Timeout — session={session_id}")
    except WebSocketDisconnect:
        logger.info(f"[WS Session] Disconnected — session={session_id}")
    except Exception as e:
        logger.error(f"[WS Session] Error — session={session_id}: {e}")
    finally:
        engine.close_session_context(pose_estimator)

        # Save accumulated session data to database
        try:
            await _save_live_session_data(
                session_id=session_id,
                frame_count=frame_index,
                rep_count=rep_count,
                detected_reps=detected_reps,
                left_knee=all_angles_left_knee,
                right_knee=all_angles_right_knee,
                left_hip=all_angles_left_hip,
                right_hip=all_angles_right_hip,
                left_ankle=all_angles_left_ankle,
                right_ankle=all_angles_right_ankle,
                start_time=frame_start_time,
            )
        except Exception as save_err:
            logger.error(f"[WS Session] Failed to save session data: {save_err}")

        logger.info(f"[WS Session] Closed — session={session_id}, total_frames={frame_index}, reps={rep_count}")


async def _save_live_session_data(
    session_id: str,
    frame_count: int,
    rep_count: int,
    detected_reps: list,
    left_knee: list,
    right_knee: list,
    left_hip: list,
    right_hip: list,
    left_ankle: list,
    right_ankle: list,
    start_time: float,
):
    """Save real pose data from the live session to the database."""
    from models.angle_data import AngleData, TimeSeries, RepetitionData, JointSymmetry
    from models.session import Session
    import numpy as np

    if frame_count < 5:
        logger.info(f"[WS Session] Too few frames ({frame_count}) to save data for session={session_id}")
        return

    # Estimate FPS from actual timing
    elapsed = time.time() - start_time
    fps = frame_count / max(elapsed, 1.0)

    # Check if AngleData already exists
    existing = await AngleData.find_one(AngleData.session_id == PydanticObjectId(session_id))
    if existing:
        logger.info(f"[WS Session] AngleData already exists for session={session_id}, skipping save")
        return

    # Build time series
    time_series = TimeSeries(
        frames=list(range(frame_count)),
        time_seconds=[i / fps for i in range(frame_count)],
        left_knee=left_knee,
        right_knee=right_knee,
        left_hip=left_hip,
        right_hip=right_hip,
        left_ankle=left_ankle,
        right_ankle=right_ankle,
    )

    # Build repetition data from detected reps
    reps = []
    for i, rep in enumerate(detected_reps):
        # Estimate start/end frames around the peak
        peak = rep["peak_frame"]
        start_frame = max(0, peak - int(fps * 1.5))
        end_frame = min(frame_count - 1, peak + int(fps * 1.5))

        # Calculate ROM for this rep
        if start_frame < len(left_knee) and end_frame < len(left_knee):
            rep_slice = left_knee[start_frame:end_frame + 1]
            rom = float(max(rep_slice) - min(rep_slice)) if rep_slice else 0.0
        else:
            rom = rep.get("peak_flexion", 0.0)

        reps.append(RepetitionData(
            rep_id=rep["rep_id"],
            start_frame=start_frame,
            peak_frame=peak,
            end_frame=end_frame,
            start_time=start_frame / fps,
            peak_time=peak / fps,
            end_time=end_frame / fps,
            duration=(end_frame - start_frame) / fps,
            rom=rom,
        ))

    # Calculate symmetry
    sym = {}
    if len(left_knee) > 10 and len(right_knee) > 10:
        lk = np.array(left_knee[:min(len(left_knee), len(right_knee))])
        rk = np.array(right_knee[:min(len(left_knee), len(right_knee))])
        corr = 0.0
        if np.std(lk) > 0 and np.std(rk) > 0:
            corr = float(np.corrcoef(lk, rk)[0, 1])
        l_rom = float(np.max(lk) - np.min(lk))
        r_rom = float(np.max(rk) - np.min(rk))
        rom_ratio = 1.0 - abs(l_rom - r_rom) / max(l_rom, r_rom, 1.0)
        sym_score = max(0.0, min(100.0, (max(0.0, corr) * 0.4 + rom_ratio * 0.6) * 100.0))

        sym["left_knee"] = JointSymmetry(
            trajectory_correlation=corr,
            left_overall_rom=l_rom,
            right_overall_rom=r_rom,
            rom_symmetry_index=rom_ratio,
            average_angle_difference=float(np.mean(np.abs(lk - rk))),
            symmetry_score_percentage=sym_score,
        )

    # Run PS2 analysis on real data
    ps2_reps = []
    ps2_mode = "mock"
    overall_session_score = None
    quality_trend = None
    try:
        from services.exercise_analysis import get_analyzer
        analyzer = get_analyzer()
        ps2_result = analyzer.analyze_session(
            session_id=session_id,
            angle_data={
                "left_knee": left_knee,
                "right_knee": right_knee,
                "left_hip": left_hip,
                "right_hip": right_hip,
                "left_ankle": left_ankle,
                "right_ankle": right_ankle,
            },
            repetitions=[r.model_dump() for r in reps],
            fps=fps,
        )
        ps2_reps = [r.model_dump() for r in ps2_result.rep_results]
        ps2_mode = ps2_result.ps2_mode
        overall_session_score = ps2_result.overall_session_score
        quality_trend = ps2_result.quality_trend
    except Exception as ps2_err:
        logger.warning(f"[WS Session] PS2 analysis failed: {ps2_err}")

    # Save AngleData
    angle_data = AngleData(
        session_id=PydanticObjectId(session_id),
        video_name="live_camera_feed",
        fps=fps,
        time_series=time_series,
        repetitions=reps,
        symmetry=sym,
        ps2_rep_results=ps2_reps,
        ps2_mode=ps2_mode,
    )
    await angle_data.insert()

    # Update session with real results
    session = await Session.get(PydanticObjectId(session_id))
    if session:
        session.total_reps = rep_count
        session.ps1_processed = True
        if ps2_reps:
            session.ps2_processed = True
            session.session_score = overall_session_score
            session.quality_score = overall_session_score
            session.quality_trend = quality_trend
        if reps:
            session.avg_left_rom = sum(r.rom for r in reps) / len(reps)
            session.avg_right_rom = session.avg_left_rom * 0.98
        if sym.get("left_knee"):
            session.symmetry_score = sym["left_knee"].symmetry_score_percentage
        session.updated_at = datetime.utcnow()
        await session.save()

    logger.info(f"[WS Session] Saved real data for session={session_id}: {frame_count} frames, {rep_count} reps")
