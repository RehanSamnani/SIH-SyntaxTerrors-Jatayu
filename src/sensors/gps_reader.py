#!/usr/bin/env python3
"""
GPS reader for Raspberry Pi using NEO-6M (UART on /dev/serial0).

Features:
- Opens /dev/serial0 at 9600 baud
- Parses NMEA with pynmea2 (GGA/RMC)
- Writes latest fix JSON to /home/pi/drone/telemetry/gps_latest.json
- Publishes to MQTT topic: drone/<DEVICE_ID>/gps (QoS 1)
- Retries serial and MQTT connections with backoff
- Graceful shutdown on SIGINT/SIGTERM

Wiring (NEO-6M → Raspberry Pi):
- VCC → 5V, GND → GND
- TX → GPIO15 (RXD)
- RX → GPIO14 (TXD)

Ensure serial login shell is disabled and serial hardware is enabled in raspi-config.
"""

import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import pynmea2  # type: ignore
import serial  # type: ignore
import paho.mqtt.client as mqtt  # type: ignore


DEVICE_ID = os.getenv("DEVICE_ID", "pi-drone-01")
SERIAL_PORT = os.getenv("GPS_SERIAL_PORT", "/dev/serial0")
SERIAL_BAUD = int(os.getenv("GPS_SERIAL_BAUD", "9600"))

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TLS_ENABLED = os.getenv("MQTT_TLS_ENABLED", "false").lower() == "true"
MQTT_CA_CERT = os.getenv("MQTT_CA_CERT", "/etc/ssl/certs/ca-certificates.crt")
MQTT_TOPIC = f"drone/{DEVICE_ID}/gps"

OUTPUT_JSON_PATH = Path(os.getenv("GPS_OUTPUT_PATH", "/home/pi/drone/telemetry/gps_latest.json"))
OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)


def setup_logger() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


class GracefulKiller:
    def __init__(self) -> None:
        self._kill = False
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)

    def _on_signal(self, signum: int, frame: Any) -> None:  # noqa: ARG002
        logging.info("Received signal %s, shutting down...", signum)
        self._kill = True

    @property
    def should_stop(self) -> bool:
        return self._kill


def connect_serial_with_retries(port: str, baud: int, retries: int = 10, backoff: float = 1.5) -> serial.Serial:
    attempt = 0
    while True:
        try:
            ser = serial.Serial(port, baudrate=baud, timeout=1)
            logging.info("Opened serial port %s at %d baud", port, baud)
            return ser
        except Exception as exc:  # noqa: BLE001
            attempt += 1
            if attempt > retries:
                logging.exception("Failed to open serial port after %d attempts", retries)
                raise
            delay = min(10.0, backoff ** attempt)
            logging.warning("Serial open failed (%s). Retry %d/%d in %.1fs", exc, attempt, retries, delay)
            time.sleep(delay)


def connect_mqtt_with_retries(client: mqtt.Client, retries: int = 10, backoff: float = 1.5) -> None:
    attempt = 0
    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
            logging.info("Connected to MQTT %s:%d", MQTT_HOST, MQTT_PORT)
            return
        except Exception as exc:  # noqa: BLE001
            attempt += 1
            if attempt > retries:
                logging.exception("Failed to connect MQTT after %d attempts", retries)
                raise
            delay = min(10.0, backoff ** attempt)
            logging.warning("MQTT connect failed (%s). Retry %d/%d in %.1fs", exc, attempt, retries, delay)
            time.sleep(delay)


def build_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(client_id=f"gps-{DEVICE_ID}")
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    if MQTT_TLS_ENABLED:
        try:
            client.tls_set(ca_certs=MQTT_CA_CERT)
        except Exception:  # noqa: BLE001
            logging.exception("Failed to set TLS; continuing without TLS")
    return client


def parse_nmea_to_fix(nmea: str) -> Optional[Dict[str, Any]]:
    try:
        msg = pynmea2.parse(nmea)
    except Exception:
        return None

    fix: Dict[str, Any] = {
        "device_id": DEVICE_ID,
        "raw": None,
    }

    if isinstance(msg, pynmea2.types.talker.GGA):
        # GPS fix data
        fix.update(
            {
                "type": "GGA",
                "timestamp": getattr(msg, "timestamp", None).isoformat() if getattr(msg, "timestamp", None) else None,
                "lat": msg.latitude if hasattr(msg, "latitude") else None,
                "lon": msg.longitude if hasattr(msg, "longitude") else None,
                "alt": float(msg.altitude) if getattr(msg, "altitude", None) else None,
                "num_sats": int(msg.num_sats) if getattr(msg, "num_sats", None) else None,
                "hdop": float(msg.horizontal_dil) if getattr(msg, "horizontal_dil", None) else None,
                "quality": int(msg.gps_qual) if getattr(msg, "gps_qual", None) else None,
            }
        )
        return fix
    if isinstance(msg, pynmea2.types.talker.RMC):
        fix.update(
            {
                "type": "RMC",
                "timestamp": getattr(msg, "datestamp", None).isoformat() + "T" + getattr(msg, "timestamp", None).isoformat()
                if getattr(msg, "datestamp", None) and getattr(msg, "timestamp", None)
                else None,
                "lat": msg.latitude if hasattr(msg, "latitude") else None,
                "lon": msg.longitude if hasattr(msg, "longitude") else None,
                "spd_over_grnd": float(msg.spd_over_grnd) if getattr(msg, "spd_over_grnd", None) else None,
                "true_course": float(msg.true_course) if getattr(msg, "true_course", None) else None,
                "status": getattr(msg, "status", None),
            }
        )
        return fix
    return None


def write_latest_fix_json(fix: Dict[str, Any]) -> None:
    try:
        with OUTPUT_JSON_PATH.open("w", encoding="utf-8") as f:
            json.dump(fix, f, ensure_ascii=False, indent=2)
    except Exception:  # noqa: BLE001
        logging.exception("Failed to write %s", OUTPUT_JSON_PATH)


def publish_mqtt_fix(client: mqtt.Client, fix: Dict[str, Any]) -> None:
    try:
        payload = json.dumps(fix).encode("utf-8")
        result = client.publish(MQTT_TOPIC, payload=payload, qos=1)
        result.wait_for_publish(2.0)
    except Exception:  # noqa: BLE001
        logging.exception("Failed to publish MQTT message")


def main() -> None:
    setup_logger()
    logging.info("Starting gps_reader (device_id=%s, port=%s)", DEVICE_ID, SERIAL_PORT)
    killer = GracefulKiller()

    mqtt_client = build_mqtt_client()
    connect_mqtt_with_retries(mqtt_client)

    ser = connect_serial_with_retries(SERIAL_PORT, SERIAL_BAUD)

    # Read loop
    buffer = b""
    last_publish_ts = 0.0
    while not killer.should_stop:
        try:
            chunk = ser.read(128)
            if not chunk:
                continue
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                nmea_str = line.decode(errors="ignore").strip()
                if not nmea_str:
                    continue
                fix = parse_nmea_to_fix(nmea_str)
                if not fix:
                    continue
                now = time.time()
                # Limit writes/publishes to ~1 Hz
                if now - last_publish_ts >= 1.0:
                    write_latest_fix_json(fix)
                    publish_mqtt_fix(mqtt_client, fix)
                    last_publish_ts = now
        except Exception:
            logging.exception("Error in read loop; continuing")
            time.sleep(0.5)

    try:
        ser.close()
    except Exception:  # noqa: BLE001
        pass
    try:
        mqtt_client.disconnect()
    except Exception:  # noqa: BLE001
        pass
    logging.info("gps_reader stopped")


if __name__ == "__main__":
    main()


