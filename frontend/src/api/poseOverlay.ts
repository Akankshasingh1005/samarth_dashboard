/**
 * Pose Overlay Drawing Utility
 * ============================
 * Draws skeleton keypoints, connections, angle arcs, and correctness feedback
 * on a canvas overlay. Shows MediaPipe-style joint visualization with color-coded
 * angle feedback (green=good, amber=warning, red=bad).
 *
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

// Ideal angle ranges for correctness feedback
// These define what "good form" looks like for typical rehab exercises
interface AngleRange {
  good: [number, number];    // Green zone - correct form
  warning: [number, number]; // Amber zone - slightly off
  // Anything outside warning = red (bad form)
}

const DEFAULT_ANGLE_RANGES: Record<string, AngleRange> = {
  left_knee:  { good: [80, 170], warning: [60, 175] },
  right_knee: { good: [80, 170], warning: [60, 175] },
  left_hip:   { good: [90, 175], warning: [70, 180] },
  right_hip:  { good: [90, 175], warning: [70, 180] },
  left_ankle: { good: [75, 110], warning: [60, 120] },
  right_ankle:{ good: [75, 110], warning: [60, 120] },
};

// Skeletal connections - same topology as PS1's draw_landmarks()
// Maps landmark names to connected landmark names
const SKELETON_CONNECTIONS: [string, string][] = [
  // Torso
  ['LEFT_SHOULDER', 'RIGHT_SHOULDER'],
  ['LEFT_SHOULDER', 'LEFT_HIP'],
  ['RIGHT_SHOULDER', 'RIGHT_HIP'],
  ['LEFT_HIP', 'RIGHT_HIP'],
  // Left arm (if available)
  ['LEFT_SHOULDER', 'LEFT_ELBOW'],
  ['LEFT_ELBOW', 'LEFT_WRIST'],
  // Right arm (if available)
  ['RIGHT_SHOULDER', 'RIGHT_ELBOW'],
  ['RIGHT_ELBOW', 'RIGHT_WRIST'],
  // Left leg
  ['LEFT_HIP', 'LEFT_KNEE'],
  ['LEFT_KNEE', 'LEFT_ANKLE'],
  // Right leg
  ['RIGHT_HIP', 'RIGHT_KNEE'],
  ['RIGHT_KNEE', 'RIGHT_ANKLE'],
];

// Lower-body joints get special treatment (larger markers, angle display)
const LOWER_BODY_JOINTS = new Set([
  'LEFT_HIP', 'RIGHT_HIP',
  'LEFT_KNEE', 'RIGHT_KNEE',
  'LEFT_ANKLE', 'RIGHT_ANKLE',
]);

// Angle joint definitions with their connected bones for arc drawing
const ANGLE_JOINTS: {
  key: keyof FrameAngles;
  landmark: string;
  parent: string;   // bone going "up" from this joint
  child: string;    // bone going "down" from this joint
  label: string;
}[] = [
  { key: 'left_knee',  landmark: 'LEFT_KNEE',  parent: 'LEFT_HIP',      child: 'LEFT_ANKLE',  label: 'L Knee' },
  { key: 'right_knee', landmark: 'RIGHT_KNEE', parent: 'RIGHT_HIP',     child: 'RIGHT_ANKLE', label: 'R Knee' },
  { key: 'left_hip',   landmark: 'LEFT_HIP',   parent: 'LEFT_SHOULDER', child: 'LEFT_KNEE',   label: 'L Hip' },
  { key: 'right_hip',  landmark: 'RIGHT_HIP',  parent: 'RIGHT_SHOULDER',child: 'RIGHT_KNEE',  label: 'R Hip' },
];

/**
 * Get correctness color for a given angle value
 */
function getAngleStatus(angleKey: string, value: number): 'good' | 'warning' | 'bad' {
  const range = DEFAULT_ANGLE_RANGES[angleKey];
  if (!range) return 'good';
  if (value >= range.good[0] && value <= range.good[1]) return 'good';
  if (value >= range.warning[0] && value <= range.warning[1]) return 'warning';
  return 'bad';
}

const STATUS_COLORS = {
  good:    { fill: '#22C55E', glow: 'rgba(34, 197, 94, 0.4)', text: '#22C55E', bg: 'rgba(34, 197, 94, 0.15)', border: 'rgba(34, 197, 94, 0.6)' },
  warning: { fill: '#F59E0B', glow: 'rgba(245, 158, 11, 0.4)', text: '#F59E0B', bg: 'rgba(245, 158, 11, 0.15)', border: 'rgba(245, 158, 11, 0.6)' },
  bad:     { fill: '#EF4444', glow: 'rgba(239, 68, 68, 0.5)',  text: '#EF4444', bg: 'rgba(239, 68, 68, 0.2)',  border: 'rgba(239, 68, 68, 0.7)' },
};

/**
 * Draw an angle arc between two bone segments at a joint.
 */
function drawAngleArc(
  ctx: CanvasRenderingContext2D,
  joint: [number, number],
  parent: [number, number],
  child: [number, number],
  status: 'good' | 'warning' | 'bad',
  angleValue: number
) {
  const colors = STATUS_COLORS[status];
  const arcRadius = Math.min(30, Math.max(18, angleValue / 6));

  // Calculate angles of the two bones relative to the joint
  const angle1 = Math.atan2(parent[1] - joint[1], parent[0] - joint[0]);
  const angle2 = Math.atan2(child[1] - joint[1], child[0] - joint[0]);

  // Draw the arc fill
  ctx.beginPath();
  ctx.moveTo(joint[0], joint[1]);
  ctx.arc(joint[0], joint[1], arcRadius, angle1, angle2, false);
  ctx.closePath();
  ctx.fillStyle = colors.bg;
  ctx.fill();

  // Draw the arc border
  ctx.beginPath();
  ctx.arc(joint[0], joint[1], arcRadius, angle1, angle2, false);
  ctx.strokeStyle = colors.border;
  ctx.lineWidth = 2;
  ctx.stroke();
}

/**
 * Draw pose skeleton overlay on a canvas.
 * 
 * @param ctx Canvas 2D rendering context
 * @param width Canvas width in pixels
 * @param height Canvas height in pixels
 * @param landmarks Dict of landmark name -> {x_norm, y_norm, visibility}
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
    showArcs?: boolean;
    showCorrectness?: boolean;
    lineColor?: string;
    jointColor?: string;
    lineWidth?: number;
    angleRanges?: Record<string, AngleRange>;
  }
) {
  const {
    showAngles = true,
    showArcs = true,
    showCorrectness = true,
    lineColor = 'rgba(200, 200, 200, 0.8)',
    jointColor: _jointColor = '#22C55E',
    lineWidth = 2.5,
    angleRanges: _angleRanges = DEFAULT_ANGLE_RANGES,
  } = options ?? {};
  void _jointColor;
  void _angleRanges;

  // Clear the overlay canvas
  ctx.clearRect(0, 0, width, height);

  if (!landmarks || Object.keys(landmarks).length === 0) return;

  // Helper: get pixel coords from normalized landmark
  const getPoint = (name: string): [number, number] | null => {
    const lm = landmarks[name];
    if (!lm || lm.visibility < 0.25) return null;
    return [lm.x_norm * width, lm.y_norm * height];
  };

  // Determine per-joint status if angles are available
  const jointStatus: Record<string, 'good' | 'warning' | 'bad'> = {};
  if (angles && showCorrectness) {
    for (const { key, landmark } of ANGLE_JOINTS) {
      const val = angles[key];
      if (val > 0) {
        jointStatus[landmark] = getAngleStatus(key, val);
      }
    }
  }

  // ─── Draw skeleton connections (bone lines) ────────────────────────
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  for (const [from, to] of SKELETON_CONNECTIONS) {
    const p1 = getPoint(from);
    const p2 = getPoint(to);
    if (p1 && p2) {
      // Color the bone based on adjacent joint status
      const fromStatus = jointStatus[from];
      const toStatus = jointStatus[to];
      let boneColor = lineColor;

      if (showCorrectness && (fromStatus || toStatus)) {
        // If either end has a status, use the worse one
        const worse = (fromStatus === 'bad' || toStatus === 'bad') ? 'bad'
          : (fromStatus === 'warning' || toStatus === 'warning') ? 'warning'
          : (fromStatus === 'good' || toStatus === 'good') ? 'good'
          : null;
        if (worse) {
          boneColor = STATUS_COLORS[worse].fill;
        }
      }

      // Draw bone glow (thicker, translucent)
      if (showCorrectness && (fromStatus || toStatus)) {
        ctx.beginPath();
        ctx.moveTo(p1[0], p1[1]);
        ctx.lineTo(p2[0], p2[1]);
        ctx.strokeStyle = boneColor.replace(')', ', 0.25)').replace('rgb(', 'rgba(');
        ctx.lineWidth = lineWidth + 4;
        ctx.stroke();
      }

      // Draw bone line
      ctx.beginPath();
      ctx.moveTo(p1[0], p1[1]);
      ctx.lineTo(p2[0], p2[1]);
      ctx.strokeStyle = boneColor;
      ctx.lineWidth = lineWidth;
      ctx.stroke();
    }
  }

  // ─── Draw angle arcs at joints ─────────────────────────────────────
  if (showArcs && angles) {
    for (const { key, landmark, parent, child } of ANGLE_JOINTS) {
      const jointPt = getPoint(landmark);
      const parentPt = getPoint(parent);
      const childPt = getPoint(child);
      const val = angles[key];

      if (jointPt && parentPt && childPt && val > 0) {
        const status = jointStatus[landmark] || 'good';
        drawAngleArc(ctx, jointPt, parentPt, childPt, status, val);
      }
    }
  }

  // ─── Draw joint keypoints ──────────────────────────────────────────
  for (const [name, lm] of Object.entries(landmarks)) {
    if (lm.visibility < 0.25) continue;
    const x = lm.x_norm * width;
    const y = lm.y_norm * height;

    const isLowerBody = LOWER_BODY_JOINTS.has(name);
    const status = jointStatus[name];

    if (isLowerBody) {
      const colors = status ? STATUS_COLORS[status] : STATUS_COLORS.good;
      const radius = 7;

      // Outer glow
      ctx.beginPath();
      ctx.arc(x, y, radius + 6, 0, 2 * Math.PI);
      ctx.fillStyle = colors.glow;
      ctx.fill();

      // White ring
      ctx.beginPath();
      ctx.arc(x, y, radius + 2, 0, 2 * Math.PI);
      ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
      ctx.fill();

      // Inner filled circle
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = colors.fill;
      ctx.fill();

      // Center dot
      ctx.beginPath();
      ctx.arc(x, y, 2, 0, 2 * Math.PI);
      ctx.fillStyle = 'white';
      ctx.fill();
    } else {
      // Non-lower-body joints: subtle small dots
      const radius = 3;
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = 'rgba(200, 200, 200, 0.8)';
      ctx.fill();
    }
  }

  // ─── Draw angle labels with correctness status ─────────────────────
  if (showAngles && angles) {
    ctx.textAlign = 'left';

    for (const { key, landmark, label } of ANGLE_JOINTS) {
      const pt = getPoint(landmark);
      const val = angles[key];
      if (!pt || val <= 0) continue;

      const status = jointStatus[landmark] || 'good';
      const colors = STATUS_COLORS[status];
      const statusIcon = status === 'good' ? '✓' : status === 'warning' ? '!' : '✗';

      const offsetX = landmark.startsWith('LEFT') ? -80 : 16;
      const textX = pt[0] + offsetX;
      const textY = pt[1] - 14;

      // Build display text
      const angleText = `${val.toFixed(0)}°`;
      const fullText = `${statusIcon} ${label}: ${angleText}`;

      // Measure text
      ctx.font = 'bold 11px Inter, system-ui, sans-serif';
      const metrics = ctx.measureText(fullText);
      const bgW = metrics.width + 14;
      const bgH = 20;

      // Background pill with status color
      ctx.fillStyle = colors.bg;
      ctx.beginPath();
      ctx.roundRect(textX - 6, textY - 14, bgW, bgH, 6);
      ctx.fill();

      // Border
      ctx.strokeStyle = colors.border;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.roundRect(textX - 6, textY - 14, bgW, bgH, 6);
      ctx.stroke();

      // Status icon
      ctx.fillStyle = colors.text;
      ctx.font = 'bold 11px Inter, system-ui, sans-serif';
      ctx.fillText(statusIcon, textX + 1, textY);

      // Label text
      ctx.fillStyle = 'rgba(255, 255, 255, 0.95)';
      ctx.fillText(` ${label}: `, textX + ctx.measureText(statusIcon).width + 2, textY);

      // Angle value (bright)
      const labelWidth = ctx.measureText(` ${label}: `).width;
      ctx.fillStyle = colors.text;
      ctx.font = 'bold 12px Inter, system-ui, sans-serif';
      ctx.fillText(angleText, textX + ctx.measureText(statusIcon).width + 2 + labelWidth, textY);
    }
  }
}
