import os

# Base Directories
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(WORKSPACE_DIR, "output")
MODELS_DIR = os.path.join(WORKSPACE_DIR, "models")
WEIGHTS_DIR = os.path.join(MODELS_DIR, "weights")

# Ensure directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(WEIGHTS_DIR, exist_ok=True)

# IS-Net Configuration
ISNET_WEIGHTS_FILE = "isnet-general-use.pth"
ISNET_WEIGHTS_PATH = os.path.join(WEIGHTS_DIR, ISNET_WEIGHTS_FILE)
# Optional URL to download general weights if needed
ISNET_DOWNLOAD_URL = "https://huggingface.co/briaai/RMBG-1.4/resolve/main/model.onnx" # Note: we use this or MP fallback
ISNET_INPUT_SIZE = (1024, 1024)

# Video Processing Parameters
VIDEO_RESIZE_WIDTH = 640
VIDEO_RESIZE_HEIGHT = 480
FRAME_STANDARDIZATION = True  # Normalize pixel values to 0-1 range if needed

# ── Video Enhancement Parameters ───────────────────────────────────────────
# Master switch: set False to skip all enhancement and pass raw frames through.
ENHANCE_VIDEO = True

# Enhancement aggressiveness:
#   "auto"       – detect each condition per frame and apply only needed fixes
#   "light"      – auto but with more conservative (higher) detection thresholds
#   "aggressive" – unconditionally apply the full correction stack every frame
ENHANCE_LEVEL = "auto"

# Contrast: Michelson contrast below this value → apply CLAHE
LOW_CONTRAST_THRESHOLD = 0.20

# Brightness: mean pixel luminance thresholds (0–255)
LOW_BRIGHTNESS_THRESHOLD = 30    # Below → underexposed / low-light (relaxed)
HIGH_BRIGHTNESS_THRESHOLD = 220  # Above → overexposed / glare (relaxed)

# Sharpness: Laplacian variance below this → motion blur detected
BLUR_SHARPNESS_THRESHOLD = 40.0

# Noise: estimated noise std-dev above this → noisy frame detected
NOISE_THRESHOLD = 25.0

# CLAHE (Contrast Limited Adaptive Histogram Equalisation)
CLAHE_CLIP_LIMIT = 2.0          # Higher → more aggressive contrast stretching
CLAHE_TILE_SIZE = (8, 8)        # Local tile grid size

# NLM Denoising filter strength (h parameter in cv2.fastNlMeansDenoisingColored)
DENOISE_H = 10

# Unsharp masking: weight applied when sharpening blurry frames
UNSHARP_STRENGTH = 1.5

# Kinematics Parameters
SAVGOL_WINDOW_LENGTH = 11  # Must be odd
SAVGOL_POLYORDER = 2       # Polynomial order for fitting

# Joints of Interest (MediaPipe landmarks IDs)
LANDMARKS = {
    "LEFT_SHOULDER": 11,
    "RIGHT_SHOULDER": 12,
    "LEFT_HIP": 23,
    "RIGHT_HIP": 24,
    "LEFT_KNEE": 25,
    "RIGHT_KNEE": 26,
    "LEFT_ANKLE": 27,
    "RIGHT_ANKLE": 28,
    "LEFT_HEEL": 29,
    "RIGHT_HEEL": 30,
    "LEFT_FOOT_INDEX": 31,
    "RIGHT_FOOT_INDEX": 32
}

# Exercise analysis parameters
ROM_THRESHOLD_MIN = 10.0   # Minimum angle difference to consider a repetition valid
SMOOTHING_SENSITIVITY = 1.0

# Export parameters
SAVE_ANNOTATED_VIDEO = False  # Set to True to output visual skeletal video overlays
