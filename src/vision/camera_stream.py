#!/usr/bin/env python3
"""
Pi Camera capture utility using OpenCV VideoCapture (libcamera backend on Bullseye/Bookworm).

Features:
- Grabs frames at configured resolution and FPS target
- Displays FPS in logs and can save a snapshot to disk
- Provides a simple CLI to run capture and save a frame
- Graceful shutdown on SIGINT/SIGTERM
"""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

import cv2  # type: ignore


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


def setup_logger() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def open_camera(width: int, height: int, fps: int) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    if not cap.isOpened():
        raise RuntimeError("Failed to open camera")
    return cap


def run_capture(width: int, height: int, fps: int, snapshot: Path | None) -> None:
    setup_logger()
    logging.info("Starting camera_stream %dx%d @ %d FPS", width, height, fps)
    killer = GracefulKiller()

    cap = open_camera(width, height, fps)
    last_time = time.time()
    frames = 0
    saved = False

    try:
        while not killer.stop:
            ok, frame = cap.read()
            if not ok:
                logging.warning("Frame grab failed")
                time.sleep(0.01)
                continue
            frames += 1
            now = time.time()
            if now - last_time >= 1.0:
                logging.info("FPS: %d", frames)
                frames = 0
                last_time = now
            if snapshot and not saved:
                cv2.imwrite(str(snapshot), frame)
                logging.info("Saved snapshot to %s", snapshot)
                saved = True
                # Continue capture to validate FPS if desired
    finally:
        cap.release()
        logging.info("camera_stream stopped")



def main() -> None:
    parser = argparse.ArgumentParser(description="Pi Camera capture utility")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--snapshot", type=Path, default=None, help="Path to save a single frame")
    args = parser.parse_args()

    try:
        run_capture(args.width, args.height, args.fps, args.snapshot)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()

