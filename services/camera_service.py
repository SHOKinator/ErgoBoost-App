# services/camera_service.py
import cv2
from utils.logger import setup_logger

logger = setup_logger(__name__)


class CameraService:
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.cap = None
        self.is_running = False

    def start(self):
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                logger.error(f"Failed to open camera {self.camera_index}")
                return False
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.is_running = True
            logger.info(f"Camera {self.camera_index} started")
            return True
        except Exception as e:
            logger.error(f"Failed to start camera: {e}")
            return False

    def read_frame(self):
        if not self.is_running or self.cap is None:
            return None
        ret, frame = self.cap.read()
        if not ret:
            return None
        return frame

    def stop(self):
        if self.cap:
            self.cap.release()
            self.is_running = False
            logger.info("Camera stopped")
