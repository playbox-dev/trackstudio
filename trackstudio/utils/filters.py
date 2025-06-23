"""
Tracking utilities including Kalman filter for smooth track prediction
"""

import numpy as np


class SimpleKalmanFilter:
    """
    Simple 2D Kalman filter for position and velocity tracking.

    This filter uses a constant velocity model to predict object positions
    and updates predictions based on new measurements.

    Attributes:
        state: State vector [x, y, vx, vy]
        F: State transition matrix
        H: Measurement matrix
        Q: Process noise covariance
        R: Measurement noise covariance
        P: State covariance matrix
        S: Innovation covariance
        K: Kalman gain
    """

    def __init__(
        self, initial_pos: tuple[float, float], process_noise: float = 1.0, measurement_noise: float = 10.0
    ) -> None:
        """
        Initialize Kalman filter.

        Args:
            initial_pos: Initial (x, y) position
            process_noise: Process noise (higher = less trust in model)
            measurement_noise: Measurement noise (higher = less trust in measurements)
        """
        # State: [x, y, vx, vy]
        self.state = np.array([initial_pos[0], initial_pos[1], 0.0, 0.0])

        # State transition matrix (constant velocity model)
        self.F = np.array(
            [
                [1, 0, 1, 0],  # x = x + vx
                [0, 1, 0, 1],  # y = y + vy
                [0, 0, 1, 0],  # vx = vx
                [0, 0, 0, 1],  # vy = vy
            ]
        )

        # Measurement matrix (we only measure position)
        self.H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]])

        # Process noise covariance
        self.Q = np.eye(4) * process_noise
        self.Q[2, 2] = process_noise * 0.1  # Less noise for velocity
        self.Q[3, 3] = process_noise * 0.1

        # Measurement noise covariance
        self.R = np.eye(2) * measurement_noise

        # State covariance
        self.P = np.eye(4) * 100  # Initial uncertainty

        # Innovation covariance
        self.S = np.zeros((2, 2))

        # Kalman gain
        self.K = np.zeros((4, 2))

    def predict(self, dt: float = 1.0) -> tuple[float, float]:
        """
        Predict next state.

        Args:
            dt: Time step

        Returns:
            Predicted (x, y) position
        """
        # Update state transition matrix with time step
        self.F[0, 2] = dt
        self.F[1, 3] = dt

        # Predict state
        self.state = self.F @ self.state

        # Predict covariance
        self.P = self.F @ self.P @ self.F.T + self.Q

        return float(self.state[0]), float(self.state[1])

    def update(self, measurement: tuple[float, float]) -> tuple[float, float]:
        """
        Update state with new measurement.

        Args:
            measurement: Measured (x, y) position

        Returns:
            Updated (x, y) position
        """
        z = np.array(measurement)

        # Innovation (measurement residual)
        y = z - self.H @ self.state

        # Innovation covariance
        self.S = self.H @ self.P @ self.H.T + self.R

        # Kalman gain
        self.K = self.P @ self.H.T @ np.linalg.inv(self.S)

        # Update state
        self.state = self.state + self.K @ y

        # Update covariance
        identity = np.eye(4)
        self.P = (identity - self.K @ self.H) @ self.P

        return float(self.state[0]), float(self.state[1])

    def get_position(self) -> tuple[float, float]:
        """
        Get current position estimate.

        Returns:
            Current (x, y) position estimate
        """
        return float(self.state[0]), float(self.state[1])

    def get_velocity(self) -> tuple[float, float]:
        """
        Get current velocity estimate.

        Returns:
            Current (vx, vy) velocity estimate
        """
        return float(self.state[2]), float(self.state[3])

    def get_state(self) -> np.ndarray:
        """
        Get full state vector.

        Returns:
            Copy of the full state vector [x, y, vx, vy]
        """
        return self.state.copy()


class TrackSmoother:
    """
    Simple exponential moving average smoother for tracks.

    This smoother uses exponential moving average to reduce noise
    in track positions over time.

    Attributes:
        alpha: Smoothing factor (0-1, higher = more weight on recent values)
        smooth_pos: Current smoothed position (None if not initialized)
    """

    def __init__(self, alpha: float = 0.7) -> None:
        """
        Initialize smoother.

        Args:
            alpha: Smoothing factor (0-1, higher = more weight on recent)
        """
        self.alpha = alpha
        self.smooth_pos: np.ndarray | None = None

    def update(self, position: tuple[float, float]) -> tuple[float, float]:
        """
        Update smoothed position.

        Args:
            position: New position measurement

        Returns:
            Smoothed position
        """
        if self.smooth_pos is None:
            self.smooth_pos = np.array(position, dtype=np.float64)
        else:
            self.smooth_pos = self.alpha * np.array(position, dtype=np.float64) + (1 - self.alpha) * self.smooth_pos

        return float(self.smooth_pos[0]), float(self.smooth_pos[1])

    def reset(self) -> None:
        """
        Reset the smoother.

        Clears the current smoothed position, causing the next update
        to initialize with the new position.
        """
        self.smooth_pos = None
