"""
Camera Validation WebSocket Handler
Dedicated channel for the camera positioning/validation screen.
Returns validation checklist state per-frame without recording session data.
"""
import json
import asyncio
import base64
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from services.pose_engine import get_pose_engine

router = APIRouter()


@router.websocket("/ws/camera/{token}")
async def camera_validation_websocket(websocket: WebSocket, token: str):
    """
    WebSocket for the camera validation screen.
    No session data is stored - purely for live positioning feedback.
    """
    from services.auth_service import decode_token
    try:
        token_data = decode_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    logger.info(f"[WS Camera] Connected: user={token_data.user_id}")

    engine = get_pose_engine()
    pose_estimator, kinematics, video_enhancer = engine.create_session_context()
    frame_index = 0
    prev_landmarks = None  # Per-session landmark state for camera stability check

    try:
        while True:
            data = await asyncio.wait_for(websocket.receive(), timeout=15.0)
            frame_bytes = None

            if data["type"] == "websocket.receive":
                if "bytes" in data and data["bytes"]:
                    frame_bytes = data["bytes"]
                elif "text" in data and data["text"]:
                    try:
                        msg = json.loads(data["text"])
                        if msg.get("type") == "frame":
                            frame_bytes = base64.b64decode(msg["data"])
                        elif msg.get("type") == "ping":
                            await websocket.send_json({"type": "pong"})
                            continue
                        elif msg.get("type") == "stop":
                            break
                    except Exception:
                        continue

            if not frame_bytes:
                continue

            timestamp_ms = int(time.time() * 1000)
            result = engine.process_frame(
                frame_bytes, frame_index, timestamp_ms,
                pose_estimator, kinematics, video_enhancer,
                prev_landmarks=prev_landmarks,
            )
            # Update per-session prev_landmarks for next frame's stability check
            if result.landmarks:
                prev_landmarks = {name: {"x_norm": lm.x_norm, "y_norm": lm.y_norm} for name, lm in result.landmarks.items()}

            response = {
                "type": "validation",
                "frame_index": frame_index,
                "validation": result.validation.model_dump(),
                "angles": result.angles.model_dump(),
                "pose_confidence": result.pose_confidence,
                "landmarks": {
                    name: {"x_norm": lm.x_norm, "y_norm": lm.y_norm, "visibility": lm.visibility}
                    for name, lm in result.landmarks.items()
                },
            }
            await websocket.send_json(response)
            frame_index += 1

    except asyncio.TimeoutError:
        logger.info(f"[WS Camera] Timeout")
    except WebSocketDisconnect:
        logger.info(f"[WS Camera] Disconnected")
    except Exception as e:
        logger.error(f"[WS Camera] Error: {e}")
    finally:
        engine.close_session_context(pose_estimator)
