/**
 * Pose Overlay Drawing Utility
 * ============================
 * Draws skeleton keypoints, connections, and angle labels on a canvas overlay.
 * Connection topology matches the PS1 PoseEstimator.draw_landmarks() method
 * in pipeline/modules/pose_estimator.py.
 */

// Landmark type from WebSocket
interface Landmark {
  x_norm: number;
  y_norm: number;
  visibility: number;
}

interface FrameAngles {
  left_hip: number;
  right_hip: number;
  left_knee: number;
  right_knee: number;
  left_ankle: number;
  right_ankle: number;
}

// Skeletal connections — same topology as PS1's draw_landmarks()
// Maps landmark names to connected landmark names
const SKELETON_CONNECTIONS: [string, string][] = [
  // Torso
  ['LEFT_SHOULDER', 'RIGHT_SHOULDER'],
  ['LEFT_SHOULDER', 'LEFT_HIP'],
  ['RIGHT_SHOULDER', 'RIGHT_HIP'],
  ['LEFT_HIP', 'RIGHT_HIP'],
  // Left leg
  ['LEFT_HIP', 'LEFT_KNEE'],
  ['LEFT_KNEE', 'LEFT_ANKLE'],
  // Right leg
  ['RIGHT_HIP', 'RIGHT_KNEE'],
  ['RIGHT_KNEE', 'RIGHT_ANKLE'],
];

// Lower-body joints get bright green markers (matches PS1's green circles)
const LOWER_BODY_JOINTS = new Set([
  'LEFT_HIP', 'RIGHT_HIP',
  'LEFT_KNEE', 'RIGHT_KNEE',
  'LEFT_ANKLE', 'RIGHT_ANKLE',
]);

// Angle label positions — show angle near the joint
const ANGLE_JOINTS: { key: keyof FrameAngles; landmark: string; label: string }[] = [
  { key: 'left_knee', landmark: 'LEFT_KNEE', label: 'L Knee' },
  { key: 'right_knee', landmark: 'RIGHT_KNEE', label: 'R Knee' },
  { key: 'left_hip', landmark: 'LEFT_HIP', label: 'L Hip' },
  { key: 'right_hip', landmark: 'RIGHT_HIP', label: 'R Hip' },
];

/**
 * Draw pose skeleton overlay on a canvas.
 * 
 * @param ctx Canvas 2D rendering context
 * @param width Canvas width in pixels
 * @param height Canvas height in pixels
 * @param landmarks Dict of landmark name → {x_norm, y_norm, visibility}
 * @param angles Optional joint angles to display as labels
 * @param options Drawing options
 */
export function drawPoseOverlay(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  landmarks: Record<string, Landmark>,
  angles?: FrameAngles | null,
  options?: {
    showAngles?: boolean;
    lineColor?: string;
    jointColor?: string;
    lineWidth?: number;
  }
) {
  const {
    showAngles = true,
    lineColor = 'rgba(200, 200, 200, 0.8)',
    jointColor = '#22C55E',
    lineWidth = 2,
  } = options ?? {};

  // Clear the overlay canvas
  ctx.clearRect(0, 0, width, height);

  if (!landmarks || Object.keys(landmarks).length === 0) return;

  // Helper: get pixel coords from normalized landmark
  const getPoint = (name: string): [number, number] | null => {
    const lm = landmarks[name];
    if (!lm || lm.visibility < 0.25) return null;
    return [lm.x_norm * width, lm.y_norm * height];
  };

  // Draw skeleton connections (bone lines)
  ctx.strokeStyle = lineColor;
  ctx.lineWidth = lineWidth;
  ctx.lineCap = 'round';

  for (const [from, to] of SKELETON_CONNECTIONS) {
    const p1 = getPoint(from);
    const p2 = getPoint(to);
    if (p1 && p2) {
      ctx.beginPath();
      ctx.moveTo(p1[0], p1[1]);
      ctx.lineTo(p2[0], p2[1]);
      ctx.stroke();
    }
  }

  // Draw joint keypoints
  for (const [name, lm] of Object.entries(landmarks)) {
    if (lm.visibility < 0.25) continue;
    const x = lm.x_norm * width;
    const y = lm.y_norm * height;

    const isLowerBody = LOWER_BODY_JOINTS.has(name);
    const radius = isLowerBody ? 6 : 3;
    const color = isLowerBody ? jointColor : 'rgba(150, 150, 150, 0.7)';

    ctx.beginPath();
    ctx.arc(x, y, radius, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();

    // Draw outer ring on lower body joints for visibility
    if (isLowerBody) {
      ctx.beginPath();
      ctx.arc(x, y, radius + 2, 0, 2 * Math.PI);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }

  // Draw angle labels near joints
  if (showAngles && angles) {
    ctx.font = 'bold 11px Inter, sans-serif';
    ctx.textAlign = 'left';

    for (const { key, landmark, label } of ANGLE_JOINTS) {
      const pt = getPoint(landmark);
      const val = angles[key];
      if (!pt || val <= 0) continue;

      const offsetX = landmark.startsWith('LEFT') ? -60 : 12;
      const textX = pt[0] + offsetX;
      const textY = pt[1] - 10;

      // Background pill
      const text = `${label}: ${val.toFixed(0)}°`;
      const metrics = ctx.measureText(text);
      const bgW = metrics.width + 8;
      const bgH = 16;

      ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
      ctx.beginPath();
      ctx.roundRect(textX - 4, textY - 12, bgW, bgH, 4);
      ctx.fill();

      // Text
      ctx.fillStyle = '#22C55E';
      ctx.fillText(text, textX, textY);
    }
  }
}
