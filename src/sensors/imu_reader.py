#!/usr/bin/env python3
"""
IMU reader for Raspberry Pi using MPU-6050 over I2C (address 0x68).

Features:
- Reads accelerometer and gyroscope data via smbus2
- Applies simple complementary filter to estimate pitch/roll
- Logs JSON lines and prints periodic summary
- Graceful shutdown on SIGINT/SIGTERM

Wiring (MPU-6050 → Raspberry Pi):
- VCC → 3.3V, GND → GND
- SDA → GPIO2 (SDA1), SCL → GPIO3 (SCL1)

Check with: i2cdetect -y 1
"""

import json
import logging
import math
import signal
import sys
import time
from pathlib import Path
from typing import Tuple

from smbus2 import SMBus  # type: ignore


I2C_BUS = 1
MPU_ADDRESS = 0x68

PWR_MGMT_1 = 0x6B
ACCEL_XOUT_H = 0x3B
GYRO_XOUT_H = 0x43

LOG_PATH = Path("/home/pi/drone/telemetry/imu_log.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def setup_logger() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


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


def read_word_2c(bus: SMBus, addr: int, reg: int) -> int:
    high = bus.read_byte_data(addr, reg)
    low = bus.read_byte_data(addr, reg + 1)
    val = (high << 8) + low
    if val >= 0x8000:
        return -((65535 - val) + 1)
    return val


def read_accel_gyro(bus: SMBus) -> Tuple[float, float, float, float, float, float]:
    # Raw values
    accel_x = read_word_2c(bus, MPU_ADDRESS, ACCEL_XOUT_H)
    accel_y = read_word_2c(bus, MPU_ADDRESS, ACCEL_XOUT_H + 2)
    accel_z = read_word_2c(bus, MPU_ADDRESS, ACCEL_XOUT_H + 4)
    gyro_x = read_word_2c(bus, MPU_ADDRESS, GYRO_XOUT_H)
    gyro_y = read_word_2c(bus, MPU_ADDRESS, GYRO_XOUT_H + 2)
    gyro_z = read_word_2c(bus, MPU_ADDRESS, GYRO_XOUT_H + 4)

    # Scale factors
    accel_scale = 16384.0  # LSB/g for +/-2g
    gyro_scale = 131.0  # LSB/(deg/s) for +/-250 deg/s

    ax = accel_x / accel_scale
    ay = accel_y / accel_scale
    az = accel_z / accel_scale
    gx = gyro_x / gyro_scale
    gy = gyro_y / gyro_scale
    gz = gyro_z / gyro_scale
    return ax, ay, az, gx, gy, gz


def complementary_filter(ax: float, ay: float, az: float, gx: float, gy: float, dt: float, alpha: float, state: Tuple[float, float]) -> Tuple[float, float]:
    # Accelerometer angles (in degrees)
    acc_pitch = math.degrees(math.atan2(ay, math.sqrt(ax * ax + az * az)))
    acc_roll = math.degrees(math.atan2(-ax, az))

    prev_pitch, prev_roll = state
    pitch = alpha * (prev_pitch + gx * dt) + (1 - alpha) * acc_pitch
    roll = alpha * (prev_roll + gy * dt) + (1 - alpha) * acc_roll
    return pitch, roll


def main() -> None:
    setup_logger()
    logging.info("Starting imu_reader (MPU-6050 at 0x%02X)", MPU_ADDRESS)
    killer = GracefulKiller()

    with SMBus(I2C_BUS) as bus:
        # Wake up device
        bus.write_byte_data(MPU_ADDRESS, PWR_MGMT_1, 0)
        time.sleep(0.05)

        last_ts = time.time()
        pitch, roll = 0.0, 0.0
        alpha = 0.98
        rate_hz = 50.0
        interval = 1.0 / rate_hz
        next_log = 0.0

        with LOG_PATH.open("a", encoding="utf-8") as logf:
            while not killer.stop:
                now = time.time()
                dt = max(1e-3, now - last_ts)
                if dt < interval:
                    time.sleep(interval - dt)
                    now = time.time()
                    dt = now - last_ts
                last_ts = now

                try:
                    ax, ay, az, gx, gy, gz = read_accel_gyro(bus)
                    pitch, roll = complementary_filter(ax, ay, az, gx, gy, dt, alpha, (pitch, roll))

                    sample = {
                        "ts": now,
                        "accel": {"x_g": ax, "y_g": ay, "z_g": az},
                        "gyro": {"x_dps": gx, "y_dps": gy, "z_dps": gz},
                        "est": {"pitch_deg": pitch, "roll_deg": roll},
                    }
                    logf.write(json.dumps(sample) + "\n")
                    if now >= next_log:
                        logging.info("pitch=%.2f roll=%.2f ax=%.2f ay=%.2f az=%.2f", pitch, roll, ax, ay, az)
                        next_log = now + 1.0
                except Exception:
                    logging.exception("IMU read error; continuing")
                    time.sleep(0.05)

    logging.info("imu_reader stopped")


if __name__ == "__main__":
    main()


