# services/models_loader.py
"""
MediaPipe model loader.
Requires mediapipe==0.10.10 (has mp.solutions + Tasks API).
"""

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe import solutions
from mediapipe.framework.formats import landmark_pb2
import numpy as np


class ModelLoader:
    def __init__(self):
        # Face Landmarker (Tasks API)
        base_options = python.BaseOptions(
            model_asset_path="models/face_landmarker.task"
        )
        face_options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            num_faces=1,
        )
        self.face_mesh = vision.FaceLandmarker.create_from_options(face_options)

        # Pose Landmarker (Tasks API)
        base_options = python.BaseOptions(
            model_asset_path="models/pose_landmarker_lite.task"
        )
        pose_options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            output_segmentation_masks=True,
        )
        self.pose = vision.PoseLandmarker.create_from_options(pose_options)

    def draw_face_landmarks(self, rgb_image, detection_result):
        face_landmarks_list = detection_result.face_landmarks
        annotated_image = np.copy(rgb_image)

        for face_landmarks in face_landmarks_list:
            proto = landmark_pb2.NormalizedLandmarkList()
            proto.landmark.extend([
                landmark_pb2.NormalizedLandmark(x=l.x, y=l.y, z=l.z)
                for l in face_landmarks
            ])
            solutions.drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=proto,
                connections=mp.solutions.face_mesh.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp.solutions.drawing_styles.
                get_default_face_mesh_tesselation_style()
            )
            solutions.drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=proto,
                connections=mp.solutions.face_mesh.FACEMESH_CONTOURS,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp.solutions.drawing_styles.
                get_default_face_mesh_contours_style()
            )
            solutions.drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=proto,
                connections=mp.solutions.face_mesh.FACEMESH_IRISES,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp.solutions.drawing_styles.
                get_default_face_mesh_iris_connections_style()
            )
        return annotated_image

    def draw_pose_landmarks(self, annotated_image, detection_result):
        pose_landmarks_list = detection_result.pose_landmarks
        if pose_landmarks_list:
            for pose_landmarks in pose_landmarks_list:
                proto = landmark_pb2.NormalizedLandmarkList()
                proto.landmark.extend([
                    landmark_pb2.NormalizedLandmark(x=lm.x, y=lm.y, z=lm.z)
                    for lm in pose_landmarks
                ])
                solutions.drawing_utils.draw_landmarks(
                    annotated_image,
                    proto,
                    solutions.pose.POSE_CONNECTIONS,
                    solutions.drawing_styles.get_default_pose_landmarks_style()
                )
        return annotated_image
