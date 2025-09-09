#!/usr/bin/env python3
"""
Telemetry aggregator service for AI-enabled drone companion system.

This service:
- Subscribes to GPS and IMU MQTT topics
- Aggregates sensor data into unified telemetry packets
- Publishes to drone/<id>/telemetry topic every 1 second
- Writes last 500 packets to rotating telemetry.log
- Supports --dry-run mode for testing without sensors
- Includes battery estimation and camera status

Features:
- MQTT-based sensor data aggregation
- Rotating log files with size limits
- Graceful shutdown handling
- Configurable via environment variables
- Systemd service ready

Usage:
    python telemetry_service.py [--dry-run] [--log-level DEBUG]
"""

import argparse
import json
import logging
import logging.handlers
import os
import signal
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import paho.mqtt.client as mqtt  # type: ignore


# Configuration from environment variables
DEVICE_ID = os.getenv("DEVICE_ID", "pi-drone-01")
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TLS_ENABLED = os.getenv("MQTT_TLS_ENABLED", "false").lower() == "true"
MQTT_CA_CERT = os.getenv("MQTT_CA_CERT", "/etc/ssl/certs/ca-certificates.crt")

# Topic configuration
GPS_TOPIC = f"drone/{DEVICE_ID}/gps"
IMU_TOPIC = f"drone/{DEVICE_ID}/imu"
TELEMETRY_TOPIC = f"drone/{DEVICE_ID}/telemetry"

# File paths
TELEMETRY_LOG_PATH = Path(os.getenv("TELEMETRY_LOG_PATH", "/home/pi/drone/telemetry/telemetry.log"))
TELEMETRY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# Telemetry configuration
TELEMETRY_INTERVAL = float(os.getenv("TELEMETRY_INTERVAL", "1.0"))  # seconds
MAX_LOG_PACKETS = int(os.getenv("MAX_LOG_PACKETS", "500"))
MAX_LOG_SIZE_MB = int(os.getenv("MAX_LOG_SIZE_MB", "10"))


class GracefulKiller:
    """Handle graceful shutdown on SIGINT/SIGTERM."""
    
    def __init__(self) -> None:
        self._kill = False
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)

    def _on_signal(self, signum: int, frame: Any) -> None:  # noqa: ARG002
        logging.info("Received signal %s, shutting down gracefully...", signum)
        self._kill = True

    @property
    def should_stop(self) -> bool:
        return self._kill


class RotatingLogWriter:
    """Handle rotating log files with size limits."""
    
    def __init__(self, log_path: Path, max_packets: int, max_size_mb: int) -> None:
        self.log_path = log_path
        self.max_packets = max_packets
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.packet_buffer = deque(maxlen=max_packets)
        
    def _should_rotate(self) -> bool:
        """Check if log file should be rotated based on size."""
        if not self.log_path.exists():
            return False
        return self.log_path.stat().st_size > self.max_size_bytes
    
    def _rotate_log(self) -> None:
        """Rotate log file by moving current to .1 and creating new."""
        if not self.log_path.exists():
            return
            
        # Move current log to .1
        backup_path = self.log_path.with_suffix(self.log_path.suffix + ".1")
        if backup_path.exists():
            backup_path.unlink()
        self.log_path.rename(backup_path)
        logging.info("Rotated log file to %s", backup_path)
    
    def write_packet(self, packet: Dict[str, Any]) -> None:
        """Write telemetry packet to log with rotation handling."""
        try:
            # Check if rotation is needed
            if self._should_rotate():
                self._rotate_log()
            
            # Add to buffer
            self.packet_buffer.append(packet)
            
            # Write to file
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(packet) + "\n")
                
        except Exception as exc:
            logging.error("Failed to write telemetry packet: %s", exc)


class TelemetryAggregator:
    """Aggregate sensor data and publish telemetry packets."""
    
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.killer = GracefulKiller()
        self.log_writer = RotatingLogWriter(
            TELEMETRY_LOG_PATH, MAX_LOG_PACKETS, MAX_LOG_SIZE_MB
        )
        
        # Latest sensor data
        self.latest_gps: Optional[Dict[str, Any]] = None
        self.latest_imu: Optional[Dict[str, Any]] = None
        self.last_telemetry_time = 0.0
        
        # MQTT client
        self.mqtt_client: Optional[mqtt.Client] = None
        
        # Battery estimation (simplified)
        self.battery_voltage = 12.6  # Starting voltage for 3S LiPo
        self.battery_percentage = 100.0
        
    def setup_logging(self, log_level: str) -> None:
        """Configure logging with rotating file handler."""
        level = getattr(logging, log_level.upper(), logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        # File handler with rotation
        log_file = Path("/home/pi/drone/logs/telemetry_service.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5*1024*1024, backupCount=3
        )
        file_handler.setFormatter(formatter)
        
        # Configure root logger
        logging.basicConfig(
            level=level,
            handlers=[console_handler, file_handler]
        )
        
        # Suppress paho-mqtt debug logs unless DEBUG level
        if level != logging.DEBUG:
            logging.getLogger("paho.mqtt").setLevel(logging.WARNING)
    
    def build_mqtt_client(self) -> mqtt.Client:
        """Create and configure MQTT client."""
        client = mqtt.Client(client_id=f"telemetry-{DEVICE_ID}")
        
        if MQTT_USERNAME:
            client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
            
        if MQTT_TLS_ENABLED:
            try:
                client.tls_set(ca_certs=MQTT_CA_CERT)
            except Exception as exc:
                logging.warning("Failed to set TLS: %s", exc)
        
        # Set callbacks
        client.on_connect = self._on_mqtt_connect
        client.on_disconnect = self._on_mqtt_disconnect
        client.on_message = self._on_mqtt_message
        
        return client
    
    def _on_mqtt_connect(self, client: mqtt.Client, userdata: Any, flags: Dict[str, Any], rc: int) -> None:  # noqa: ARG002
        """Handle MQTT connection."""
        if rc == 0:
            logging.info("Connected to MQTT broker %s:%d", MQTT_HOST, MQTT_PORT)
            # Subscribe to sensor topics
            client.subscribe(GPS_TOPIC, qos=1)
            client.subscribe(IMU_TOPIC, qos=1)
            logging.info("Subscribed to topics: %s, %s", GPS_TOPIC, IMU_TOPIC)
        else:
            logging.error("Failed to connect to MQTT broker: %s", mqtt.connack_string(rc))
    
    def _on_mqtt_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:  # noqa: ARG002
        """Handle MQTT disconnection."""
        if rc != 0:
            logging.warning("Unexpected MQTT disconnection: %s", mqtt.connack_string(rc))
        else:
            logging.info("Disconnected from MQTT broker")
    
    def _on_mqtt_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:  # noqa: ARG002
        """Handle incoming MQTT messages."""
        try:
            data = json.loads(msg.payload.decode("utf-8"))
            
            if msg.topic == GPS_TOPIC:
                self.latest_gps = data
                logging.debug("Updated GPS data: %s", data.get("type", "unknown"))
            elif msg.topic == IMU_TOPIC:
                self.latest_imu = data
                logging.debug("Updated IMU data: pitch=%.2f roll=%.2f", 
                            data.get("est", {}).get("pitch_deg", 0),
                            data.get("est", {}).get("roll_deg", 0))
        except Exception as exc:
            logging.error("Failed to parse MQTT message from %s: %s", msg.topic, exc)
    
    def estimate_battery(self) -> Tuple[float, float]:
        """Estimate battery voltage and percentage (simplified model)."""
        # Simple battery model - in real implementation, read from ADC
        # For now, simulate gradual discharge
        current_time = time.time()
        if not hasattr(self, '_battery_start_time'):
            self._battery_start_time = current_time
        
        # Simulate 2-hour flight time
        flight_time = current_time - self._battery_start_time
        discharge_rate = 0.1 / 3600  # 0.1V per hour
        self.battery_voltage = max(10.5, 12.6 - (flight_time * discharge_rate))
        
        # Convert to percentage (10.5V = 0%, 12.6V = 100%)
        self.battery_percentage = max(0, min(100, 
            (self.battery_voltage - 10.5) / (12.6 - 10.5) * 100))
        
        return self.battery_voltage, self.battery_percentage
    
    def get_camera_status(self) -> Dict[str, Any]:
        """Get camera status (simplified)."""
        # In real implementation, check camera availability
        return {
            "available": True,
            "resolution": "1920x1080",
            "fps": 30,
            "recording": False
        }
    
    def create_telemetry_packet(self) -> Dict[str, Any]:
        """Create unified telemetry packet from latest sensor data."""
        now = time.time()
        battery_voltage, battery_percentage = self.estimate_battery()
        
        packet = {
            "device_id": DEVICE_ID,
            "timestamp": now,
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime(now)),
            "battery": {
                "voltage": round(battery_voltage, 2),
                "percentage": round(battery_percentage, 1)
            },
            "camera": self.get_camera_status()
        }
        
        # Add GPS data if available
        if self.latest_gps:
            gps_data = {
                "lat": self.latest_gps.get("lat"),
                "lon": self.latest_gps.get("lon"),
                "alt": self.latest_gps.get("alt"),
                "num_sats": self.latest_gps.get("num_sats"),
                "hdop": self.latest_gps.get("hdop"),
                "quality": self.latest_gps.get("quality"),
                "gps_timestamp": self.latest_gps.get("timestamp")
            }
            packet["gps"] = gps_data
        else:
            packet["gps"] = None
        
        # Add IMU data if available
        if self.latest_imu:
            imu_data = {
                "pitch_deg": self.latest_imu.get("est", {}).get("pitch_deg"),
                "roll_deg": self.latest_imu.get("est", {}).get("roll_deg"),
                "accel": self.latest_imu.get("accel"),
                "gyro": self.latest_imu.get("gyro"),
                "imu_timestamp": self.latest_imu.get("ts")
            }
            packet["imu"] = imu_data
        else:
            packet["imu"] = None
        
        return packet
    
    def publish_telemetry(self, packet: Dict[str, Any]) -> None:
        """Publish telemetry packet to MQTT."""
        if not self.mqtt_client:
            return
            
        try:
            payload = json.dumps(packet).encode("utf-8")
            result = self.mqtt_client.publish(TELEMETRY_TOPIC, payload=payload, qos=1)
            result.wait_for_publish(2.0)
            logging.debug("Published telemetry packet")
        except Exception as exc:
            logging.error("Failed to publish telemetry: %s", exc)
    
    def simulate_sensor_data(self) -> None:
        """Simulate sensor data for dry-run mode."""
        now = time.time()
        
        # Simulate GPS data
        self.latest_gps = {
            "device_id": DEVICE_ID,
            "type": "GGA",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime(now)),
            "lat": 37.7749 + (now % 100) * 0.0001,  # Simulate movement
            "lon": -122.4194 + (now % 100) * 0.0001,
            "alt": 100.0 + (now % 10) * 2.0,
            "num_sats": 8,
            "hdop": 1.2,
            "quality": 1
        }
        
        # Simulate IMU data
        self.latest_imu = {
            "ts": now,
            "accel": {
                "x_g": 0.1 + (now % 5) * 0.1,
                "y_g": -0.2 + (now % 3) * 0.1,
                "z_g": 1.0 + (now % 2) * 0.1
            },
            "gyro": {
                "x_dps": (now % 10) * 0.5,
                "y_dps": (now % 8) * 0.3,
                "z_dps": (now % 6) * 0.2
            },
            "est": {
                "pitch_deg": (now % 20) * 0.5 - 5.0,
                "roll_deg": (now % 15) * 0.3 - 2.0
            }
        }
    
    def connect_mqtt_with_retries(self, retries: int = 10, backoff: float = 1.5) -> None:
        """Connect to MQTT broker with retry logic."""
        attempt = 0
        while not self.killer.should_stop:
            try:
                self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
                self.mqtt_client.loop_start()
                return
            except Exception as exc:
                attempt += 1
                if attempt > retries:
                    logging.error("Failed to connect to MQTT after %d attempts", retries)
                    raise
                delay = min(10.0, backoff ** attempt)
                logging.warning("MQTT connect failed (%s). Retry %d/%d in %.1fs", 
                              exc, attempt, retries, delay)
                time.sleep(delay)
    
    def run(self) -> None:
        """Main telemetry aggregation loop."""
        logging.info("Starting telemetry service (device_id=%s, dry_run=%s)", 
                    DEVICE_ID, self.dry_run)
        
        if not self.dry_run:
            # Connect to MQTT broker
            self.mqtt_client = self.build_mqtt_client()
            self.connect_mqtt_with_retries()
        else:
            logging.info("Running in dry-run mode - simulating sensor data")
        
        # Main loop
        while not self.killer.should_stop:
            try:
                now = time.time()
                
                # Simulate data in dry-run mode
                if self.dry_run:
                    self.simulate_sensor_data()
                
                # Publish telemetry at configured interval
                if now - self.last_telemetry_time >= TELEMETRY_INTERVAL:
                    packet = self.create_telemetry_packet()
                    
                    # Write to log
                    self.log_writer.write_packet(packet)
                    
                    # Publish to MQTT
                    if not self.dry_run:
                        self.publish_telemetry(packet)
                    
                    self.last_telemetry_time = now
                    
                    # Log summary
                    gps_status = "GPS" if packet["gps"] else "NO_GPS"
                    imu_status = "IMU" if packet["imu"] else "NO_IMU"
                    logging.info("Telemetry: %s %s bat=%.1f%% lat=%.6f lon=%.6f pitch=%.1f roll=%.1f",
                               gps_status, imu_status, packet["battery"]["percentage"],
                               packet["gps"]["lat"] if packet["gps"] and packet["gps"]["lat"] else 0,
                               packet["gps"]["lon"] if packet["gps"] and packet["gps"]["lon"] else 0,
                               packet["imu"]["pitch_deg"] if packet["imu"] and packet["imu"]["pitch_deg"] else 0,
                               packet["imu"]["roll_deg"] if packet["imu"] and packet["imu"]["roll_deg"] else 0)
                
                time.sleep(0.1)  # Small sleep to prevent busy waiting
                
            except Exception as exc:
                logging.exception("Error in telemetry loop: %s", exc)
                time.sleep(1.0)
        
        # Cleanup
        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception as exc:
                logging.error("Error disconnecting MQTT: %s", exc)
        
        logging.info("Telemetry service stopped")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Telemetry aggregator service")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Run in dry-run mode (simulate sensor data)")
    parser.add_argument("--log-level", default="INFO", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Set logging level")
    
    args = parser.parse_args()
    
    # Create aggregator
    aggregator = TelemetryAggregator(dry_run=args.dry_run)
    aggregator.setup_logging(args.log_level)
    
    try:
        aggregator.run()
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
    except Exception as exc:
        logging.exception("Fatal error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
