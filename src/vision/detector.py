#!/usr/bin/env python3
"""
Lightweight obstacle detector for Raspberry Pi Camera using TFLite MobileNet SSD.

Features
- Captures frames via OpenCV (libcamera backend on Bullseye/Bookworm)
- Runs TFLite inference (CPU by default) with frame resize and frame skipping
- Prints detections and publishes obstacle events to MQTT `drone/<id>/obstacles`
- Heuristic distance estimate based on bounding box pixel height (calibration friendly)
- Robust logging and graceful shutdown

Performance tips
- Use smaller input sizes (e.g., 300x300, 320x320). Control with --model_width/--model_height
- Use --skip_frames to reduce inference frequency (e.g., process every 2nd/3rd frame)
- Use grayscale preview or avoid any extra drawing/display on the Pi
- Ensure the Pi is in performance governor mode and use a heatsink/fan
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2  # type: ignore
import numpy as np
from paho.mqtt import client as mqtt  # type: ignore

try:
    # Prefer standalone tflite-runtime on Raspberry Pi
    from tflite_runtime.interpreter import Interpreter  # type: ignore
except Exception:  # noqa: BLE001
    # Fallback to full TF if installed (less ideal on Pi)
    from tensorflow.lite.python.interpreter import Interpreter  # type: ignore


# =============================
# Utilities
# =============================


class GracefulKiller:
    def __init__(self) -> None:
        self._stop = False
        signal.signal(signal.SIGINT, self._on)
        signal.signal(signal.SIGTERM, self._on)

    def _on(self, signum, frame):  # noqa: ANN001, ANN201, D401
        self._stop = True

    @property
    def stop(self) -> bool:
        return self._stop


def setup_logger(verbosity: int) -> None:
    level = logging.WARNING if verbosity <= 0 else logging.INFO if verbosity == 1 else logging.DEBUG
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")


def now_ms() -> int:
    return int(time.time() * 1000)


# =============================
# Models and post-processing
# =============================


@dataclass
class Detection:
    label: str
    confidence: float
    bbox_xywh: Tuple[int, int, int, int]  # x, y, w, h in pixels of original frame
    distance_m: float | None
    severity: str


def load_labels(labels_path: Path | None) -> List[str]:
    default_labels = [
        "background",
        "person",
        "bicycle",
        "car",
        "motorcycle",
        "airplane",
        "bus",
        "train",
        "truck",
        "boat",
        "traffic light",
        "fire hydrant",
        "street sign",
        "stop sign",
        "parking meter",
        "bench",
        "bird",
        "cat",
        "dog",
        "horse",
        "sheep",
        "cow",
        "elephant",
        "bear",
        "zebra",
        "giraffe",
        "hat",
        "backpack",
        "umbrella",
        "shoe",
        "eye glasses",
        "handbag",
        "tie",
        "suitcase",
        "frisbee",
        "skis",
        "snowboard",
        "sports ball",
        "kite",
        "baseball bat",
        "baseball glove",
        "skateboard",
        "surfboard",
        "tennis racket",
        "bottle",
        "plate",
        "wine glass",
        "cup",
        "fork",
        "knife",
        "spoon",
        "bowl",
        "banana",
        "apple",
        "sandwich",
        "orange",
        "broccoli",
        "carrot",
        "hot dog",
        "pizza",
        "donut",
        "cake",
        "chair",
        "couch",
        "potted plant",
        "bed",
        "mirror",
        "dining table",
        "window",
        "desk",
        "toilet",
        "door",
        "tv",
        "laptop",
        "mouse",
        "remote",
        "keyboard",
        "cell phone",
        "microwave",
        "oven",
        "toaster",
        "sink",
        "refrigerator",
        "blender",
        "book",
        "clock",
        "vase",
        "scissors",
        "teddy bear",
        "hair drier",
        "toothbrush",
    ]
    if labels_path is None:
        return default_labels
    try:
        with labels_path.open("r", encoding="utf-8") as f:
            labels = [line.strip() for line in f if line.strip()]
        return labels or default_labels
    except Exception as exc:  # noqa: BLE001
        logging.warning("Failed to read labels %s: %s", labels_path, exc)
        return default_labels


def estimate_distance_m(bbox_h_px: int, frame_h_px: int, k: float) -> float:
    """
    Heuristic distance estimate: distance ≈ k / (bbox_h_px / frame_h_px).
    
    This is a simplified distance estimation based on object size in the image.
    The formula assumes objects appear smaller as they get farther away.
    
    Args:
        bbox_h_px: Height of bounding box in pixels
        frame_h_px: Height of camera frame in pixels  
        k: Calibration constant (default: 40.0)
        
    Returns:
        Estimated distance in meters
        
    Note:
        This is a rough approximation. For accurate distance measurement,
        use stereo cameras, LiDAR, or other depth sensors. Calibration
        is required by placing known objects at known distances.
    """
    ratio = max(bbox_h_px / max(frame_h_px, 1), 1e-6)
    return float(k / ratio)


def compute_severity(conf: float, distance_m: float | None) -> str:
    if distance_m is not None:
        if distance_m < 5:
            return "critical"
        if distance_m < 15:
            return "warning"
    # Fallback to confidence if no distance
    if conf >= 0.6:
        return "warning"
    return "info"


def select_tensors(interpreter: Interpreter) -> Tuple[int, int, int, int]:
    """
    MobileNet SSD TFLite commonly exposes 4 outputs:
    - boxes: [1, num, 4] (ymin, xmin, ymax, xmax) normalized
    - classes: [1, num]
    - scores: [1, num]
    - num_detections: [1]
    Returns tuple of output tensor indices in (boxes_i, classes_i, scores_i, count_i)
    """
    output_details = interpreter.get_output_details()
    # Try to map by shape semantics
    boxes_i = classes_i = scores_i = count_i = -1
    for d in output_details:
        shape = d["shape"]
        if len(shape) == 3 and shape[-1] == 4:
            boxes_i = d["index"]
        elif len(shape) == 2:
            # Could be classes or scores depending on dtype
            if d["dtype"] in (np.float32, np.float16):
                scores_i = d["index"]
            else:
                classes_i = d["index"]
        elif len(shape) == 1 or (len(shape) == 2 and shape[0] == 1 and shape[1] == 1):
            count_i = d["index"]
    if min(boxes_i, classes_i, scores_i, count_i) < 0:
        # Some models expose different ordering; fallback to positional
        if len(output_details) >= 4:
            boxes_i, classes_i, scores_i, count_i = (
                output_details[0]["index"],
                output_details[1]["index"],
                output_details[2]["index"],
                output_details[3]["index"],
            )
        else:
            raise RuntimeError("Unexpected TFLite output tensors; cannot map outputs")
    return boxes_i, classes_i, scores_i, count_i


def preprocess(frame_bgr: np.ndarray, input_size: Tuple[int, int]) -> Tuple[np.ndarray, float, float]:
    ih, iw = input_size
    resized = cv2.resize(frame_bgr, (iw, ih))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    input_data = np.expand_dims(rgb, axis=0).astype(np.uint8)
    return input_data, frame_bgr.shape[1], frame_bgr.shape[0]


def run_inference(
    interpreter: Interpreter,
    boxes_i: int,
    classes_i: int,
    scores_i: int,
    count_i: int,
    input_data: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    input_detail = interpreter.get_input_details()[0]
    # Support quantized and float models
    if input_detail["dtype"] == np.float32:
        input_scale, input_zero_point = input_detail.get("quantization", (1.0, 0))
        if input_scale == 0:
            input_scale = 1.0
        x = input_data.astype(np.float32)
        x = (x - input_zero_point) * input_scale  # normally scale to 0..1
    else:
        x = input_data

    interpreter.set_tensor(input_detail["index"], x)
    interpreter.invoke()

    boxes = interpreter.get_tensor(boxes_i)[0]
    classes = interpreter.get_tensor(classes_i)[0]
    scores = interpreter.get_tensor(scores_i)[0]
    if count_i is not None:
        try:
            num = int(np.squeeze(interpreter.get_tensor(count_i)))
        except Exception:  # noqa: BLE001
            num = len(scores)
    else:
        num = len(scores)
    return boxes, classes, scores, num


def postprocess_detections(
    boxes: np.ndarray,
    classes: np.ndarray,
    scores: np.ndarray,
    num: int,
    frame_w: int,
    frame_h: int,
    labels: List[str],
    conf_threshold: float,
    distance_k: float | None,
) -> List[Detection]:
    detections: List[Detection] = []
    for i in range(num):
        conf = float(scores[i])
        if conf < conf_threshold:
            continue
        ymin, xmin, ymax, xmax = boxes[i]
        # TFLite mobilenet-ssd gives normalized coords
        x1 = int(max(0, xmin) * frame_w)
        y1 = int(max(0, ymin) * frame_h)
        x2 = int(min(1, xmax) * frame_w)
        y2 = int(min(1, ymax) * frame_h)
        w = max(0, x2 - x1)
        h = max(0, y2 - y1)
        class_id = int(classes[i])
        label = labels[class_id] if 0 <= class_id < len(labels) else f"class_{class_id}"

        distance_m = None
        if distance_k is not None and h > 0:
            distance_m = round(estimate_distance_m(h, frame_h, distance_k), 2)
        severity = compute_severity(conf, distance_m)
        detections.append(
            Detection(label=label, confidence=conf, bbox_xywh=(x1, y1, w, h), distance_m=distance_m, severity=severity)
        )
    return detections


# =============================
# MQTT
# =============================


def make_mqtt_client(client_id: str, host: str, port: int, username: str | None, password: str | None) -> mqtt.Client:
    client = mqtt.Client(client_id=client_id, clean_session=True, protocol=mqtt.MQTTv311)
    if username and password:
        client.username_pw_set(username=username, password=password)
    client.connect(host, port, keepalive=30)
    return client


def publish_obstacle(client: mqtt.Client, drone_id: str, det: Detection) -> None:
    """
    Publish obstacle detection event to MQTT.
    
    Publishes to topic: drone/<drone_id>/obstacles
    Message format matches mission runner expectations for automatic
    pause/resume behavior.
    
    Args:
        client: MQTT client instance
        drone_id: Unique drone identifier
        det: Detection object with bbox, confidence, and metadata
    """
    x, y, w, h = det.bbox_xywh
    payload: Dict[str, Any] = {
        "timestamp_ms": now_ms(),
        "drone_id": drone_id,
        "event": "obstacle",
        "label": det.label,
        "confidence": round(det.confidence, 3),
        "bbox": {"x": x, "y": y, "w": w, "h": h},
        "severity": det.severity,
    }
    if det.distance_m is not None:
        payload["distance_m"] = det.distance_m
    topic = f"drone/{drone_id}/obstacles"
    client.publish(topic, json.dumps(payload), qos=1, retain=False)


# =============================
# Camera
# =============================


def open_camera(width: int, height: int, fps: int) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    if not cap.isOpened():
        raise RuntimeError("Failed to open camera")
    return cap


# =============================
# Main loop
# =============================


def main() -> None:
    parser = argparse.ArgumentParser(description="TFLite MobileNet SSD obstacle detector")
    parser.add_argument("--drone_id", default=os.getenv("DRONE_ID", "pi01"))
    parser.add_argument("--mqtt_host", default=os.getenv("MQTT_HOST", "localhost"))
    parser.add_argument("--mqtt_port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--mqtt_username", default=os.getenv("MQTT_USERNAME"))
    parser.add_argument("--mqtt_password", default=os.getenv("MQTT_PASSWORD"))

    parser.add_argument(
        "--model_path",
        type=Path,
        default=Path(os.getenv("MODEL_PATH", "models/mobilenet_ssd_v1.tflite")),
        help="Path to TFLite model",
    )
    parser.add_argument(
        "--labels_path",
        type=Path,
        default=Path(os.getenv("LABELS_PATH", "models/coco_labels.txt")),
        help="Path to labels file (one per line)",
    )
    parser.add_argument("--conf_threshold", type=float, default=float(os.getenv("CONF_THRESHOLD", "0.5")))
    parser.add_argument("--top_k", type=int, default=int(os.getenv("TOP_K", "20")))
    parser.add_argument("--skip_frames", type=int, default=int(os.getenv("SKIP_FRAMES", "2")), help="Process every Nth frame")
    parser.add_argument("--distance_k", type=float, default=float(os.getenv("DIST_K", "40.0")), help="Heuristic distance constant")

    parser.add_argument("--cam_width", type=int, default=int(os.getenv("CAM_W", "640")))
    parser.add_argument("--cam_height", type=int, default=int(os.getenv("CAM_H", "480")))
    parser.add_argument("--cam_fps", type=int, default=int(os.getenv("CAM_FPS", "15")))
    parser.add_argument("--model_width", type=int, default=int(os.getenv("MODEL_W", "300")))
    parser.add_argument("--model_height", type=int, default=int(os.getenv("MODEL_H", "300")))
    parser.add_argument("-v", "--verbose", action="count", default=1)

    args = parser.parse_args()

    setup_logger(args.verbose)
    logging.info(
        "Starting detector for drone_id=%s, MQTT %s:%d, model=%s",
        args.drone_id,
        args.mqtt_host,
        args.mqtt_port,
        args.model_path,
    )

    labels = load_labels(args.labels_path if args.labels_path.exists() else None)

    # Load model
    if not args.model_path.exists():
        logging.error("Model not found at %s", args.model_path)
        sys.exit(2)
    interpreter = Interpreter(model_path=str(args.model_path))
    interpreter.allocate_tensors()
    boxes_i, classes_i, scores_i, count_i = select_tensors(interpreter)

    # Camera
    cap = open_camera(args.cam_width, args.cam_height, args.cam_fps)

    # MQTT
    try:
        mqtt_client = make_mqtt_client(
            client_id=f"detector-{args.drone_id}",
            host=args.mqtt_host,
            port=args.mqtt_port,
            username=args.mqtt_username,
            password=args.mqtt_password,
        )
    except Exception as exc:  # noqa: BLE001
        logging.error("MQTT connection failed: %s", exc)
        sys.exit(3)

    killer = GracefulKiller()

    frame_idx = 0
    last_fps_t = time.time()
    frames_in_window = 0

    try:
        while not killer.stop:
            ok, frame = cap.read()
            if not ok:
                logging.warning("Frame grab failed")
                time.sleep(0.005)
                continue

            frame_idx += 1
            frames_in_window += 1

            if args.skip_frames > 1 and (frame_idx % args.skip_frames) != 0:
                # Skip inference to save CPU
                # Still keep FPS accounting
                pass
            else:
                input_data, frame_w, frame_h = preprocess(frame, (args.model_height, args.model_width))
                boxes, classes, scores, num = run_inference(
                    interpreter, boxes_i, classes_i, scores_i, count_i, input_data
                )
                # Keep only top_k by confidence
                idxs = np.argsort(scores)[::-1][: args.top_k]
                boxes = boxes[idxs]
                classes = classes[idxs]
                scores = scores[idxs]
                detections = postprocess_detections(
                    boxes,
                    classes,
                    scores,
                    int(min(num, len(scores))),
                    int(frame_w),
                    int(frame_h),
                    labels,
                    args.conf_threshold,
                    distance_k=args.distance_k,
                )

                for det in detections:
                    # Print concise human-readable line
                    x, y, w, h = det.bbox_xywh
                    dist = f", {det.distance_m}m" if det.distance_m is not None else ""
                    print(f"[{det.severity}] {det.label} {det.confidence:.2f} bbox=({x},{y},{w},{h}){dist}")
                    publish_obstacle(mqtt_client, args.drone_id, det)

            # FPS log once per second
            now = time.time()
            if now - last_fps_t >= 1.0:
                logging.info("FPS: %d", frames_in_window)
                frames_in_window = 0
                last_fps_t = now

    except Exception as exc:  # noqa: BLE001
        logging.exception("Detector crashed: %s", exc)
    finally:
        try:
            cap.release()
        except Exception:  # noqa: BLE001
            pass
        try:
            mqtt_client.disconnect()
        except Exception:  # noqa: BLE001
            pass
        logging.info("detector stopped")


if __name__ == "__main__":
    main()


