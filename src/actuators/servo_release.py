#!/usr/bin/env python3
"""
Servo control for payload release using gpiozero.Servo.

Features:
- CLI to arm, release, and reset positions
- Uses external 5V power for servo; shares ground with Pi
- Calibrated pulse widths configurable via env/flags
- Logs actions and exits gracefully
"""

import argparse
import logging
import os
import sys
import time

from gpiozero import Servo  # type: ignore


def setup_logger() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main() -> None:
    setup_logger()
    gpio = int(os.getenv("SERVO_GPIO", os.getenv("SERVO_PIN", "18")))
    min_pw = float(os.getenv("SERVO_MIN_PW", "0.0005"))
    max_pw = float(os.getenv("SERVO_MAX_PW", "0.0025"))

    parser = argparse.ArgumentParser(description="Servo payload release controller")
    parser.add_argument("action", choices=["arm", "release", "reset"], help="Servo action")
    parser.add_argument("--gpio", type=int, default=gpio)
    parser.add_argument("--min-pw", type=float, default=min_pw)
    parser.add_argument("--max-pw", type=float, default=max_pw)
    args = parser.parse_args()

    logging.info("Initializing servo on GPIO %d (min_pw=%.4f, max_pw=%.4f)", args.gpio, args["min_pw"] if isinstance(args, dict) and "min_pw" in args else args.min_pw, args["max_pw"] if isinstance(args, dict) and "max_pw" in args else args.max_pw)

    try:
        servo = Servo(args.gpio, min_pulse_width=args.min_pw, max_pulse_width=args.max_pw)
        time.sleep(0.2)

        if args.action == "arm":
            servo.min()  # arm position (adjust if needed)
            logging.info("Servo armed (min position)")
        elif args.action == "release":
            servo.max()  # release position
            logging.info("Servo release (max position)")
        elif args.action == "reset":
            servo.mid()  # neutral position
            logging.info("Servo reset (mid position)")

        time.sleep(0.8)
        servo.value = None  # detach signal to avoid jitter
    except Exception as exc:  # noqa: BLE001
        logging.error("Servo error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()


