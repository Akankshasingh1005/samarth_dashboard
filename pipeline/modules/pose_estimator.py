import os
import urllib.request
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from config import LANDMARKS, WEIGHTS_DIR

class PoseEstimator:
    """Uses the MediaPipe Tasks Vision API to estimate human skeletal landmarks and extract joint coordinates"""
    
    def __init__(self, min_detection_confidence=0.5, min_tracking_confidence=0.5, enable_segmentation=True):
        # Configure model path
        self.model_filename = "pose_landmarker_full.task"
        self.model_path = os.path.join(WEIGHTS_DIR, self.model_filename)
        self.enable_segmentation = enable_segmentation
        
        # Ensure model weights are downloaded
        self._ensure_model_exists()
        
        # Initialize MediaPipe PoseLandmarker
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            output_segmentation_masks=enable_segmentation,
            min_pose_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        
        seg_label = "enabled" if enable_segmentation else "disabled"
        print(f"[PoseEstimator] Initializing PoseLandmarker (segmentation={seg_label})...")
        self.landmarker = vision.PoseLandmarker.create_from_options(options)
        self.frame_timestamp_ms = 0

    def _ensure_model_exists(self):
        """Downloads the MediaPipe Pose Landmarker model task file if it's missing"""
        if not os.path.exists(self.model_path):
            url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task"
            print(f"[PoseEstimator] Downloading Pose Landmarker model from {url}...")
            try:
                os.makedirs(WEIGHTS_DIR, exist_ok=True)
                # Download using urllib
                urllib.request.urlretrieve(url, self.model_path)
                print(f"[PoseEstimator] Model downloaded successfully and saved to {self.model_path}")
            except Exception as e:
                raise IOError(f"Failed to download MediaPipe Pose Landmarker model: {e}. Check internet connection or place file manually.")

    def process_frame(self, frame):
        """Process a BGR frame, return raw results and segmentation mask"""
        # Convert BGR OpenCV image to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Create MediaPipe Image object
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        
        # In VIDEO running mode, we must supply a monotonically increasing timestamp in milliseconds
        # Frame rate of 30fps means dt ~ 33ms
        self.frame_timestamp_ms += 33
        
        # Inference
        result = self.landmarker.detect_for_video(mp_image, self.frame_timestamp_ms)
        
        # Extract segmentation mask if requested and returned
        segmentation_mask = None
        if result.segmentation_masks and len(result.segmentation_masks) > 0:
            # The mask is returned as an mp.Image containing floating point values [0.0, 1.0]
            mask_img = result.segmentation_masks[0]
            segmentation_mask = mask_img.numpy_view()
            
        return result, segmentation_mask

    def extract_joint_coordinates(self, result, frame_shape):
        """Extract x, y, z coordinates of lower-limb joints from PoseLandmarker results"""
        h, w = frame_shape[:2]
        coords = {}

        if not result.pose_landmarks or len(result.pose_landmarks) == 0:
            return None

        # Take first detected pose landmarks
        landmarks = result.pose_landmarks[0]

        # Extract coordinates of interest
        for name, idx in LANDMARKS.items():
            if idx < len(landmarks):
                landmark = landmarks[idx]
                px_x = int(landmark.x * w)
                px_y = int(landmark.y * h)
                
                coords[name] = {
                    "x_norm": landmark.x,
                    "y_norm": landmark.y,
                    "z_norm": landmark.z,
                    "visibility": getattr(landmark, "visibility", 1.0),
                    "x_px": px_x,
                    "y_px": px_y
                }
            
        return coords

    def draw_landmarks(self, frame, result):
        """Custom skeletal drawing logic because solutions.drawing_utils is legacy"""
        annotated_frame = frame.copy()
        
        if not result.pose_landmarks or len(result.pose_landmarks) == 0:
            return annotated_frame
            
        landmarks = result.pose_landmarks[0]
        h, w = frame.shape[:2]
        
        # Skeletal joint connections to draw
        connections = [
            # Torso
            (11, 12), (11, 23), (12, 24), (23, 24),
            # Left leg
            (23, 25), (25, 27), (27, 29), (29, 31), (27, 31),
            # Right leg
            (24, 26), (26, 28), (28, 30), (30, 32), (28, 32)
        ]
        
        # Draw connections
        for idx1, idx2 in connections:
            if idx1 < len(landmarks) and idx2 < len(landmarks):
                lm1, lm2 = landmarks[idx1], landmarks[idx2]
                pt1 = (int(lm1.x * w), int(lm1.y * h))
                pt2 = (int(lm2.x * w), int(lm2.y * h))
                cv2.line(annotated_frame, pt1, pt2, (200, 200, 200), 2)
                
        # Draw joint nodes
        for idx in range(len(landmarks)):
            # Draw lower body joints with green circles, others with grey
            lm = landmarks[idx]
            pt = (int(lm.x * w), int(lm.y * h))
            if idx in LANDMARKS.values():
                cv2.circle(annotated_frame, pt, 5, (34, 197, 94), -1)  # Green circle
            else:
                cv2.circle(annotated_frame, pt, 3, (150, 150, 150), -1)  # Small grey circle
                
        return annotated_frame

    def close(self):
        """Release MediaPipe resources"""
        if hasattr(self, 'landmarker') and self.landmarker is not None:
            try:
                self.landmarker.close()
            except Exception:
                pass

    def __del__(self):
        self.close()
