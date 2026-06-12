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
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

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
    from beanie import PydanticObjectId

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
    prev_angles = None
    flexion_history = []
    last_rep_frame = -60  # Min frames between rep counts

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
        logger.info(f"[WS Session] Closed — session={session_id}, total_frames={frame_index}, reps={rep_count}")
