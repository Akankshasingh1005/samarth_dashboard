import os
import cv2
import numpy as np
import torch
import importlib.util
from config import ISNET_WEIGHTS_PATH, ISNET_INPUT_SIZE, MODELS_DIR

class BackgroundSegmenter:
    """Handles background removal/segmentation using IS-Net architecture, falling back to MediaPipe pose segmentation if weights are missing"""
    def __init__(self, use_isnet=True, device="cpu"):
        self.device = torch.device("cuda" if torch.cuda.is_available() and device == "cuda" else "cpu")
        self.use_isnet = use_isnet
        self.isnet_loaded = False
        self.net = None

        if self.use_isnet:
            # Check if weights file exists
            if os.path.exists(ISNET_WEIGHTS_PATH):
                try:
                    print(f"[BackgroundSegmenter] Loading IS-Net weights from {ISNET_WEIGHTS_PATH}...")
                    isnet_module_path = os.path.join(MODELS_DIR, "isnet.py")
                    spec = importlib.util.spec_from_file_location("pipeline_isnet", isnet_module_path)
                    if spec is None or spec.loader is None:
                        raise ImportError(f"Unable to load IS-Net module from {isnet_module_path}")
                    isnet_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(isnet_module)
                    ISNetDIS = isnet_module.ISNetDIS
                    self.net = ISNetDIS(in_ch=3, out_ch=1)
                    # Load model state dict
                    state_dict = torch.load(ISNET_WEIGHTS_PATH, map_location=self.device)
                    # Clean state dict keys if they have 'module.' prefix (from DataParallel training)
                    if next(iter(state_dict.keys())).startswith('module.'):
                        state_dict = {k[7:]: v for k, v in state_dict.items()}
                    self.net.load_state_dict(state_dict)
                    self.net.to(self.device)
                    self.net.eval()
                    self.isnet_loaded = True
                    print("[BackgroundSegmenter] IS-Net loaded successfully.")
                except Exception as e:
                    print(f"[BackgroundSegmenter] WARNING: Failed to load IS-Net: {e}. Falling back to MediaPipe segmentation.")
            else:
                print(f"[BackgroundSegmenter] INFO: IS-Net weights not found at {ISNET_WEIGHTS_PATH}.")
                print("[BackgroundSegmenter] The pipeline will fall back to MediaPipe's built-in segmentation or standard foreground isolation.")

    def segment_frame_isnet(self, frame):
        """Perform background subtraction on a single frame using IS-Net"""
        if not self.isnet_loaded or self.net is None:
            return None

        h, w, c = frame.shape
        # Preprocessing: resize to 1024x1024, transpose to CxHxW, normalize
        im_resize = cv2.resize(frame, ISNET_INPUT_SIZE)
        im_tensor = torch.tensor(im_resize, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0) / 255.0
        
        # Mean/std normalization (standard ImageNet normalization)
        mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
        im_tensor = (im_tensor - mean) / std
        im_tensor = im_tensor.to(self.device)

        with torch.no_grad():
            # IS-Net returns 6 side maps (d1, d2, d3, d4, d5, d6). d1 is the final resolution prediction
            d1, *_ = self.net(im_tensor)
            
            # Extract and resize mask back to original frame size
            mask = d1.squeeze().cpu().numpy()
            mask = cv2.resize(mask, (w, h))
            
            # Threshold to get binary mask
            binary_mask = (mask > 0.5).astype(np.uint8) * 255
            
        return binary_mask

    def apply_mask(self, frame, mask):
        """Apply a binary segmentation mask to isolate foreground from background"""
        if mask is None:
            return frame
        # Apply mask
        foreground = cv2.bitwise_and(frame, frame, mask=mask)
        # Create solid background (e.g. green screen or white)
        background = np.ones_like(frame) * 240  # Soft grey background
        background = cv2.bitwise_and(background, background, mask=cv2.bitwise_not(mask))
        return cv2.add(foreground, background)

    def segment_frame(self, frame, mp_segmentation_mask=None):
        """Main segmentation endpoint, trying IS-Net first, then MediaPipe mask, and finally returning original"""
        mask = None
        if self.isnet_loaded:
            try:
                mask = self.segment_frame_isnet(frame)
            except Exception as e:
                print(f"[BackgroundSegmenter] IS-Net inference failed: {e}. Trying fallback.")

        # Fallback to MediaPipe mask if provided and IS-Net failed/was skipped
        if mask is None and mp_segmentation_mask is not None:
            # mp_segmentation_mask is a float array [0.0, 1.0] from MediaPipe Pose
            mask = (mp_segmentation_mask > 0.4).astype(np.uint8) * 255

        # If we have a mask, return the background-removed frame and the mask
        if mask is not None:
            bg_removed = self.apply_mask(frame, mask)
            return bg_removed, mask
        
        # Standard fallback (simply return original)
        return frame, None
