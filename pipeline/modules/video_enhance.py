"""
video_enhance.py - Adaptive Video Quality Enhancement for Kinematics Pipeline
==============================================================================
Detects and corrects common adverse video conditions per-frame before pose
estimation, improving MediaPipe landmark detection on real-world clinical footage.

Conditions handled:
    - Low contrast (CLAHE on LAB L-channel)
    - High contrast / overexposure (gamma compression)
    - Low brightness / underexposure (gamma boost + CLAHE)
    - High brightness / glare (gamma compression)
    - Gaussian / sensor noise (Fast Non-Local Means denoising)
    - Salt-and-pepper noise (median filter)
    - Motion blur / camera shake (unsharp masking)
    - Colour cast / white balance drift (grey-world correction)
    - Low-light (dark + noisy combined path)
"""

import cv2
import numpy as np
from config import (
    ENHANCE_VIDEO,
    ENHANCE_LEVEL,
    LOW_CONTRAST_THRESHOLD,
    LOW_BRIGHTNESS_THRESHOLD,
    HIGH_BRIGHTNESS_THRESHOLD,
    BLUR_SHARPNESS_THRESHOLD,
    NOISE_THRESHOLD,
    CLAHE_CLIP_LIMIT,
    CLAHE_TILE_SIZE,
    DENOISE_H,
    UNSHARP_STRENGTH,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _mean_luminance(gray: np.ndarray) -> float:
    """Return mean pixel value of a grayscale image (0â€“255)."""
    return float(np.mean(gray))


def _michelson_contrast(gray: np.ndarray) -> float:
    """
    Michelson contrast = (Lmax - Lmin) / (Lmax + Lmin).
    Returns a value in [0, 1]; low value = flat / low contrast.
    """
    lmax = float(np.max(gray))
    lmin = float(np.min(gray))
    denom = lmax + lmin
    return (lmax - lmin) / denom if denom > 0 else 0.0


def _laplacian_variance(gray: np.ndarray) -> float:
    """Variance of the Laplacian - measures sharpness; low = blurry."""
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    return float(lap.var())


def _estimate_noise(gray: np.ndarray) -> float:
    """
    Estimate noise standard deviation using the difference between the image
    and a lightly Gaussian-blurred version.  High value = noisy.
    """
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    diff = gray.astype(np.float32) - blurred.astype(np.float32)
    return float(np.std(diff))


def _colour_cast_deviation(bgr: np.ndarray) -> float:
    """
    Measure how far per-channel means deviate from overall mean.
    Returns RMS deviation; high = significant colour cast.
    """
    means = np.mean(bgr.reshape(-1, 3), axis=0)          # [B_mean, G_mean, R_mean]
    overall = np.mean(means)
    deviations = means - overall
    return float(np.sqrt(np.mean(deviations ** 2)))


def _highlight_clipping_fraction(gray: np.ndarray, threshold: int = 245) -> float:
    """Fraction of pixels at or above `threshold` (blown-out / clipped highlights)."""
    clipped = np.sum(gray >= threshold)
    return clipped / gray.size


def _salt_pepper_fraction(gray: np.ndarray) -> float:
    """
    Fraction of pixels that are isolated extremes (0 or 255) but whose
    neighbours are not - a simple salt-and-pepper indicator.
    """
    extreme = ((gray == 0) | (gray == 255)).astype(np.uint8)
    # Dilate to find isolated extremes (at least one non-extreme neighbour)
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(1 - extreme, kernel)
    isolated = extreme & dilated
    return float(np.sum(isolated)) / gray.size


# ---------------------------------------------------------------------------
# VideoEnhancer
# ---------------------------------------------------------------------------

class VideoEnhancer:
    """
    Adaptive per-frame video quality enhancer.

    Usage::

        enhancer = VideoEnhancer()
        enhanced_frame, quality_report = enhancer.enhance(frame)

    Parameters
    ----------
    enabled : bool
        Master switch.  If False, ``enhance()`` returns the original frame
        with an empty report.
    level : str
        ``"auto"``   - apply corrections only when a condition is detected.
        ``"light"``  - auto with more conservative thresholds.
        ``"aggressive"`` - always apply all corrections regardless of detection.
    """

    def __init__(self, enabled: bool = ENHANCE_VIDEO, level: str = ENHANCE_LEVEL):
        self.enabled = enabled
        self.level = level.lower()

        # Build CLAHE object (reusable, thread-local safe)
        self._clahe = cv2.createCLAHE(
            clipLimit=CLAHE_CLIP_LIMIT,
            tileGridSize=CLAHE_TILE_SIZE,
        )

        # Threshold multipliers per level
        _multiplier = {"light": 1.5, "auto": 1.0, "aggressive": 0.0}
        m = _multiplier.get(self.level, 1.0)

        self._low_contrast_thr = LOW_CONTRAST_THRESHOLD * (1.0 + 0.3 * m)
        self._low_brightness_thr = LOW_BRIGHTNESS_THRESHOLD * (1.0 + 0.2 * m)
        self._high_brightness_thr = HIGH_BRIGHTNESS_THRESHOLD * (1.0 - 0.1 * m)
        self._blur_thr = BLUR_SHARPNESS_THRESHOLD * (1.0 + 0.5 * m)
        self._noise_thr = NOISE_THRESHOLD * (1.0 - 0.3 * m)

        # Cumulative condition counters (for end-of-video reporting)
        self.condition_counts: dict = {
            "low_contrast": 0,
            "overexposed": 0,
            "underexposed": 0,
            "high_glare": 0,
            "gaussian_noise": 0,
            "salt_pepper_noise": 0,
            "motion_blur": 0,
            "colour_cast": 0,
            "low_light": 0,
            "total_enhanced": 0,
        }

        print(f"[VideoEnhancer] Initialized - enabled={enabled}, level='{level}'")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enhance(self, frame: np.ndarray) -> tuple:
        """
        Detect quality issues in *frame* and apply targeted corrections.

        Parameters
        ----------
        frame : np.ndarray
            BGR uint8 image (as returned by cv2.VideoCapture or VideoProcessor).

        Returns
        -------
        enhanced : np.ndarray
            Corrected BGR uint8 image (same shape as input).
        report : dict
            Conditions detected and corrections applied for this frame.
        """
        if not self.enabled:
            return frame, {}

        report: dict = {"conditions": [], "corrections": []}

        if self.level == "aggressive":
            # Apply full stack unconditionally
            enhanced = self._apply_all(frame, report)
        else:
            # Adaptive path - detect then correct
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            issues = self._detect(frame, gray, report)
            enhanced = self._correct(frame, gray, issues, report)

        if report["corrections"]:
            self.condition_counts["total_enhanced"] += 1

        return enhanced, report

    def get_summary(self) -> dict:
        """Return cumulative condition counts across all processed frames."""
        return dict(self.condition_counts)

    def reset_counts(self):
        """Reset per-video counters."""
        for k in self.condition_counts:
            self.condition_counts[k] = 0

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def _detect(self, bgr: np.ndarray, gray: np.ndarray, report: dict) -> set:
        """
        Run all quality checks and return a set of detected condition strings.
        Also updates the running condition_counts and the per-frame report.
        """
        issues = set()

        luminance = _mean_luminance(gray)
        contrast = _michelson_contrast(gray)
        sharpness = _laplacian_variance(gray)
        noise_std = _estimate_noise(gray)
        cast_dev = _colour_cast_deviation(bgr)
        clipping = _highlight_clipping_fraction(gray)
        sp_fraction = _salt_pepper_fraction(gray)

        # â”€â”€ Low contrast â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if contrast < self._low_contrast_thr:
            issues.add("low_contrast")
            self.condition_counts["low_contrast"] += 1

        # â”€â”€ Overexposed / clipped highlights â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if luminance > self._high_brightness_thr or clipping > 0.05:
            if luminance > 220:
                issues.add("high_glare")
                self.condition_counts["high_glare"] += 1
            else:
                issues.add("overexposed")
                self.condition_counts["overexposed"] += 1

        # â”€â”€ Underexposed / low brightness â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if luminance < self._low_brightness_thr:
            if noise_std > self._noise_thr:
                issues.add("low_light")           # dark + noisy â†’ combined path
                self.condition_counts["low_light"] += 1
            else:
                issues.add("underexposed")
                self.condition_counts["underexposed"] += 1

        # â”€â”€ Motion blur â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if sharpness < self._blur_thr:
            issues.add("motion_blur")
            self.condition_counts["motion_blur"] += 1

        # â”€â”€ Gaussian / sensor noise â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if noise_std > self._noise_thr and "low_light" not in issues:
            issues.add("gaussian_noise")
            self.condition_counts["gaussian_noise"] += 1

        # â”€â”€ Salt-and-pepper noise â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if sp_fraction > 0.003:
            issues.add("salt_pepper_noise")
            self.condition_counts["salt_pepper_noise"] += 1

        # â”€â”€ Colour cast â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if cast_dev > 12.0:
            issues.add("colour_cast")
            self.condition_counts["colour_cast"] += 1

        if issues:
            report["conditions"] = sorted(issues)

        return issues

    # ------------------------------------------------------------------
    # Correction
    # ------------------------------------------------------------------

    def _correct(self, bgr: np.ndarray, gray: np.ndarray, issues: set, report: dict) -> np.ndarray:
        """Apply targeted corrections in the safest pipeline order."""
        img = bgr.copy()

        # 1. Colour cast - fix white balance first so later steps see neutral colours
        if "colour_cast" in issues:
            img = self._fix_colour_cast(img)
            report["corrections"].append("grey_world_wb")

        # 2. Salt-and-pepper - median before anything else to remove spikes
        if "salt_pepper_noise" in issues:
            img = self._remove_salt_pepper(img)
            report["corrections"].append("median_filter")

        # 3. Low-light - strong denoise then CLAHE (order matters)
        if "low_light" in issues:
            img = self._denoise_nlm(img, h=DENOISE_H + 3)
            img = self._apply_clahe_lab(img)
            img = self._gamma_correction(img, gamma=0.7)
            report["corrections"].append("low_light_path")

        else:
            # 3a. Gaussian noise
            if "gaussian_noise" in issues:
                img = self._denoise_nlm(img, h=DENOISE_H)
                report["corrections"].append("nlm_denoise")

            # 3b. Brightness corrections
            if "underexposed" in issues:
                img = self._gamma_correction(img, gamma=0.65)
                report["corrections"].append("gamma_boost")

            if "overexposed" in issues:
                img = self._gamma_correction(img, gamma=1.5)
                report["corrections"].append("gamma_compress")

            if "high_glare" in issues:
                img = self._gamma_correction(img, gamma=1.8)
                # Gentle blur to smooth blown-out regions
                img = cv2.GaussianBlur(img, (3, 3), 0.5)
                report["corrections"].append("glare_correction")

            # 3c. Contrast (after brightness so CLAHE sees corrected histogram)
            if "low_contrast" in issues:
                img = self._apply_clahe_lab(img)
                report["corrections"].append("clahe_lab")

        # 4. Motion blur - sharpen last so we don't amplify noise
        if "motion_blur" in issues:
            img = self._unsharp_mask(img, strength=UNSHARP_STRENGTH)
            report["corrections"].append("unsharp_mask")

        return img

    def _apply_all(self, bgr: np.ndarray, report: dict) -> np.ndarray:
        """Aggressive mode: apply the full enhancement stack unconditionally."""
        img = bgr.copy()
        img = self._fix_colour_cast(img)
        img = self._remove_salt_pepper(img)
        img = self._denoise_nlm(img, h=DENOISE_H)
        img = self._apply_clahe_lab(img)
        img = self._unsharp_mask(img, strength=UNSHARP_STRENGTH)
        report["corrections"].append("aggressive_full_stack")
        return img

    # ------------------------------------------------------------------
    # Individual correction primitives
    # ------------------------------------------------------------------

    @staticmethod
    def _gamma_correction(bgr: np.ndarray, gamma: float) -> np.ndarray:
        """
        Apply power-law gamma correction.
        gamma < 1.0 â†’ brighten (boost dark frames)
        gamma > 1.0 â†’ darken (compress bright / overexposed frames)
        Uses a precomputed lookup table for speed.
        """
        inv_gamma = 1.0 / gamma
        lut = np.array(
            [((i / 255.0) ** inv_gamma) * 255 for i in range(256)],
            dtype=np.uint8,
        )
        return cv2.LUT(bgr, lut)

    def _apply_clahe_lab(self, bgr: np.ndarray) -> np.ndarray:
        """
        Convert to LAB colour space, apply CLAHE only to the L (luminance)
        channel, then convert back.  This avoids colour saturation artefacts.
        """
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        l_ch, a_ch, b_ch = cv2.split(lab)
        l_eq = self._clahe.apply(l_ch)
        lab_eq = cv2.merge((l_eq, a_ch, b_ch))
        return cv2.cvtColor(lab_eq, cv2.COLOR_LAB2BGR)

    @staticmethod
    def _denoise_nlm(bgr: np.ndarray, h: int = DENOISE_H) -> np.ndarray:
        """
        Fast Non-Local Means denoising.  Works well for Gaussian / sensor noise.
        h: filter strength - higher = stronger noise removal, slightly more blur.
        """
        return cv2.fastNlMeansDenoisingColored(bgr, None, h, h, 7, 21)

    @staticmethod
    def _remove_salt_pepper(bgr: np.ndarray, ksize: int = 3) -> np.ndarray:
        """Median filter to remove salt-and-pepper (impulse) noise."""
        return cv2.medianBlur(bgr, ksize)

    @staticmethod
    def _unsharp_mask(bgr: np.ndarray, strength: float = UNSHARP_STRENGTH,
                      sigma: float = 1.0) -> np.ndarray:
        """
        Unsharp masking for motion-blur / camera-shake correction.
        enhanced = original + strength * (original - blurred)
        Clips to valid [0, 255] uint8 range.
        """
        blurred = cv2.GaussianBlur(bgr, (0, 0), sigma)
        sharpened = cv2.addWeighted(bgr, 1.0 + strength, blurred, -strength, 0)
        return np.clip(sharpened, 0, 255).astype(np.uint8)

    @staticmethod
    def _fix_colour_cast(bgr: np.ndarray) -> np.ndarray:
        """
        Grey-world white balance:  scale each channel so its mean equals the
        overall mean luminance.  Corrects tinted / colour-casted footage.
        """
        result = bgr.astype(np.float32)
        b_mean = np.mean(result[:, :, 0])
        g_mean = np.mean(result[:, :, 1])
        r_mean = np.mean(result[:, :, 2])
        overall_mean = (b_mean + g_mean + r_mean) / 3.0

        if b_mean > 0:
            result[:, :, 0] *= (overall_mean / b_mean)
        if g_mean > 0:
            result[:, :, 1] *= (overall_mean / g_mean)
        if r_mean > 0:
            result[:, :, 2] *= (overall_mean / r_mean)

        return np.clip(result, 0, 255).astype(np.uint8)
