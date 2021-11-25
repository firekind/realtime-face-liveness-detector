import sys
import os
sys.path.insert(1, os.getcwd())
from utility.video_utils import VideoUtils
from face_det.TDDFA import TDDFA
from face_det.FaceBoxes import FaceBoxes
from face_detector import FaceDetector
import cv2
import yaml
import numpy as np
import tensorflow as tf

import onnxruntime

# Allow GPU memory growth
gpus = tf.config.experimental.list_physical_devices('GPU')
if gpus:
    try:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
    except RuntimeError as e:
        print(e)

# Model path
FAS_MODEL_PATH = "model/antispoofing.h5"
ONNX_MODEL_PATH = "model/permuted_antispoofing.onnx"
USE_ONNX = True
FACE_THRESHOLD = 0.7
BLUR_THRESHOLD = 350

def get_normal_face(img):
    return img/255.

def get_max_face(face_locations):
    return max(face_locations, key=lambda x: (x[2]-x[0]) * (x[3]-x[1]))

def predict_onnx(session, tensor):
    """
    ONNX model inputs: ['permute_input']
    ONNX model outputs: ['sequential']
    """
    tensor = np.float32(tensor)
    x = tensor if isinstance(tensor, list) else [tensor]
    feed = dict([(input.name, x[n]) for n, input in enumerate(session.get_inputs())])
    pred_onnx = session.run(None, feed)[0]

    return pred_onnx

def predict_tf(model, tensor):
    return model.predict(tensor)

if not USE_ONNX:
    print("[INFO] Loading Model Weights")
    model = VideoUtils.load_keras_model(FAS_MODEL_PATH)
else:
    print("[INFO] Loading ONNX Model")
    model = onnxruntime.InferenceSession(ONNX_MODEL_PATH)

print("[INFO] Loading Face Detector")
face_detector = FaceDetector()

print("[INFO] Starting video stream...")
root_path = "face_det"
cfg = yaml.load(open('%s/configs/mb1_120x120.yml' % root_path), Loader=yaml.SafeLoader)
cfg['bfm_fp'] = os.path.join(root_path, cfg['bfm_fp'])
cfg['checkpoint_fp'] = os.path.join(root_path, cfg['checkpoint_fp'])

# Initialise the face detector
use_gpu_flag = 1
face_boxes = FaceBoxes(gpu_mode=False if use_gpu_flag == 0 else True)
tddfa = TDDFA(gpu_mode=False if use_gpu_flag == 0 else True, **cfg)

# Read the video stream
video = cv2.VideoCapture(0)

while True:
    if not video.isOpened():
        print("[ERROR] Cannot find webcam")
        pass

    # Read the feed from webcam
    ret, frame = video.read()

    # Call face detector to obtain face image
    frame_bgr = frame[..., ::-1]
    boxes = face_detector(np.array(frame_bgr))
    facebox = face_detector(np.array(frame))

    # Check if face is present
    n = len(boxes[0])

    if n == 0:
        cv2.putText(frame, "Faces: %s" % (n), (500, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 200), 2)
    else:
        cv2.putText(frame, "Faces: %s" % (n), (480, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 200), 2)
        face_image = VideoUtils.get_liveness_score(frame, boxes[0])
        # blur_value = VideoUtils.estimate_blur(frame)
        # raw_face_loc = VideoUtils.cut_face_locations(frame, facebox[0])
        # blurness = np.round(VideoUtils.estimate_blur(raw_face_loc), 2)
        
        model_input = face_image[0]
        if USE_ONNX:
            model_input = np.transpose(model_input, (0, 3, 1, 2))
        pred = predict_onnx(model, model_input) if USE_ONNX else predict_tf(model, model_input)
        liveness_score = (np.round(pred[:, 1].tolist()[0], 3))

        # Frame annotations
        # cv2.putText(frame, "Blur: %s" % blurness, (480, 50), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0,0,255) if blurness < BLUR_THRESHOLD else (0, 200, 0), 2)
        cv2.putText(frame, "Liveness: %s" % liveness_score, (20, 30), cv2.FONT_HERSHEY_DUPLEX,0.7, (0, 0, 200) if liveness_score < FACE_THRESHOLD else (0, 200, 0), 1)
        cv2.rectangle(frame, (boxes[0][0][3], boxes[0][0][2]), (boxes[0][0][1], boxes[0][0][0]), (255, 0, 0), 2)

    cv2.imshow("Face Detector", frame)

    # Reduce the frames for a more slower detection
    key = cv2.waitKey(15)
    if key == ord('q'):
        break
video.release()
cv2.destroyAllWindows()
