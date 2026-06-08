import numpy as np

class KinematicsExtractor:
    """Calculates lower-limb joint angles, velocities, and accelerations from spatial coordinate trajectories"""
    
    @staticmethod
    def calculate_angle_2d(p1, p2, p3):
        """
        Calculate the 2D angle (in degrees) at vertex p2 formed by vectors p2->p1 and p2->p3.
        Points p1, p2, p3 are represented as dicts or arrays with keys/indices for (x, y).
        """
        # Convert inputs to numpy arrays
        v1 = np.array([p1[0] - p2[0], p1[1] - p2[1]])
        v2 = np.array([p3[0] - p2[0], p3[1] - p2[1]])
        
        # Calculate dot product and magnitudes
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        
        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0
            
        # Cosine of the angle
        cos_angle = dot_product / (norm_v1 * norm_v2)
        # Handle numerical issues (clamping)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        
        # Angle in degrees
        angle = np.arccos(cos_angle)
        return float(np.degrees(angle))

    def extract_angles(self, frame_joints):
        """
        Extract lower-limb joint angles (hip, knee, ankle) for both left and right sides.
        frame_joints: dictionary containing joint coordinates extracted by PoseEstimator.
        """
        if frame_joints is None:
            return None

        # Prepare point coordinates as (x, y) tuples
        def get_pt(name):
            return (frame_joints[name]["x_px"], frame_joints[name]["y_px"])

        try:
            # Left side joints
            l_shoulder = get_pt("LEFT_SHOULDER")
            l_hip = get_pt("LEFT_HIP")
            l_knee = get_pt("LEFT_KNEE")
            l_ankle = get_pt("LEFT_ANKLE")
            l_foot = get_pt("LEFT_FOOT_INDEX")

            # Right side joints
            r_shoulder = get_pt("RIGHT_SHOULDER")
            r_hip = get_pt("RIGHT_HIP")
            r_knee = get_pt("RIGHT_KNEE")
            r_ankle = get_pt("RIGHT_ANKLE")
            r_foot = get_pt("RIGHT_FOOT_INDEX")

            # Calculate Angles
            angles = {
                # Hip: Shoulder - Hip - Knee
                "left_hip": self.calculate_angle_2d(l_shoulder, l_hip, l_knee),
                "right_hip": self.calculate_angle_2d(r_shoulder, r_hip, r_knee),
                
                # Knee: Hip - Knee - Ankle
                "left_knee": self.calculate_angle_2d(l_hip, l_knee, l_ankle),
                "right_knee": self.calculate_angle_2d(r_hip, r_knee, r_ankle),
                
                # Ankle: Knee - Ankle - Foot Index (or Heel, let's use Foot Index to capture flexion)
                "left_ankle": self.calculate_angle_2d(l_knee, l_ankle, l_foot),
                "right_ankle": self.calculate_angle_2d(r_knee, r_ankle, r_foot)
            }
            return angles
            
        except KeyError as e:
            print(f"[KinematicsExtractor] Warning: Missing key {e} for angle calculation")
            return None

    def calculate_derivatives(self, time_series_angles, fps):
        """
        Calculate angular velocity (first derivative) and acceleration (second derivative)
        for a list/array of angles over time.
        time_series_angles: List or array of angles
        fps: frame rate of the video (defines dt = 1/fps)
        """
        angles = np.array(time_series_angles)
        n = len(angles)
        if n < 2:
            return np.zeros(n), np.zeros(n)
            
        dt = 1.0 / fps

        # Velocity: first derivative (degrees/second)
        # Using central differences for interior points, forward/backward for boundary
        velocity = np.zeros(n)
        velocity[1:-1] = (angles[2:] - angles[:-2]) / (2 * dt)
        velocity[0] = (angles[1] - angles[0]) / dt
        velocity[-1] = (angles[-1] - angles[-2]) / dt

        # Acceleration: second derivative (degrees/second^2)
        acceleration = np.zeros(n)
        acceleration[1:-1] = (velocity[2:] - velocity[:-2]) / (2 * dt)
        acceleration[0] = (velocity[1] - velocity[0]) / dt
        acceleration[-1] = (velocity[-1] - velocity[-2]) / dt

        return list(velocity), list(acceleration)
