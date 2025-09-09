#!/usr/bin/env python3
"""
Mission runner for AI-enabled drone companion system.

This service:
- Loads mission definitions from JSON files
- Simulates waypoint navigation with configurable speed
- Implements reactive state machine for mission execution
- Handles obstacle detection with pause/resume logic
- Simulates payload delivery with servo commands
- Publishes mission status and simulated telemetry
- Logs mission states and events

Features:
- Waypoint interpolation with configurable speed
- State machine: IDLE → TAKEOFF → ENROUTE → HOLD → DELIVERY → RETURN → LANDED → ERROR
- Obstacle handling with temporary waypoint insertion
- MQTT integration for commands and status
- Comprehensive logging and error handling

Usage:
    python mission_runner.py [--mission mission.json] [--speed 5.0] [--dry-run]
"""

import argparse
import json
import logging
import logging.handlers
import os
import signal
import sys
import time
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import paho.mqtt.client as mqtt  # type: ignore


# Configuration from environment variables
DEVICE_ID = os.getenv("DEVICE_ID", "pi-drone-01")
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TLS_ENABLED = os.getenv("MQTT_TLS_ENABLED", "false").lower() == "true"
MQTT_CA_CERT = os.getenv("MQTT_CA_CERT", "/etc/ssl/certs/ca-certificates.crt")

# Mission configuration
DEFAULT_MISSION_PATH = Path("data/sample_missions/sample_mission.json")
DEFAULT_SPEED = float(os.getenv("MISSION_SPEED", "5.0"))  # m/s
DEFAULT_ALTITUDE = float(os.getenv("MISSION_ALTITUDE", "50.0"))  # meters

# MQTT Topics
TELEMETRY_TOPIC = f"drone/{DEVICE_ID}/telemetry"
MISSION_STATUS_TOPIC = f"drone/{DEVICE_ID}/mission/status"
MISSION_COMMAND_TOPIC = f"drone/{DEVICE_ID}/mission/command"
OBSTACLE_TOPIC = f"drone/{DEVICE_ID}/obstacles"
SERVO_COMMAND_TOPIC = f"drone/{DEVICE_ID}/servo/command"

# Logging configuration
MISSION_LOG_PATH = Path("/home/pi/drone/logs/mission_runner.log")
MISSION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


class MissionState(Enum):
    """Mission execution states."""
    IDLE = "IDLE"
    TAKEOFF = "TAKEOFF"
    ENROUTE = "ENROUTE"
    HOLD = "HOLD"
    DELIVERY = "DELIVERY"
    RETURN = "RETURN"
    LANDED = "LANDED"
    ERROR = "ERROR"
    PAUSED = "PAUSED"


@dataclass
class Waypoint:
    """Mission waypoint definition."""
    lat: float
    lon: float
    alt: float
    hold_seconds: float = 0.0
    action: str = "none"
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Mission:
    """Mission definition."""
    mission_id: str
    name: str
    waypoints: List[Waypoint]
    payload_metadata: Dict[str, Any] = None
    max_speed: float = 5.0
    default_altitude: float = 50.0
    
    def __post_init__(self):
        if self.payload_metadata is None:
            self.payload_metadata = {}


@dataclass
class MissionStatus:
    """Current mission status."""
    mission_id: str
    state: MissionState
    current_waypoint: int
    total_waypoints: int
    progress_percent: float
    estimated_time_remaining: float
    current_position: Tuple[float, float, float]  # lat, lon, alt
    target_position: Tuple[float, float, float]
    speed: float
    timestamp: float
    error_message: Optional[str] = None


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


class MissionRunner:
    """Mission execution engine with state machine."""
    
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.killer = GracefulKiller()
        
        # Mission state
        self.current_mission: Optional[Mission] = None
        self.mission_status: Optional[MissionStatus] = None
        self.current_waypoint_index = 0
        self.mission_start_time = 0.0
        self.waypoint_start_time = 0.0
        self.hold_start_time = 0.0
        
        # Position simulation
        self.current_position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.target_position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.speed = DEFAULT_SPEED
        
        # Obstacle handling
        self.obstacle_detected = False
        self.obstacle_position: Optional[Tuple[float, float, float]] = None
        self.original_waypoint_index = 0
        
        # MQTT client
        self.mqtt_client: Optional[mqtt.Client] = None
        
        # State machine
        self.state = MissionState.IDLE
        
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
        file_handler = logging.handlers.RotatingFileHandler(
            MISSION_LOG_PATH, maxBytes=5*1024*1024, backupCount=3
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
        client = mqtt.Client(client_id=f"mission-runner-{DEVICE_ID}")
        
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
            # Subscribe to command and obstacle topics
            client.subscribe(MISSION_COMMAND_TOPIC, qos=1)
            client.subscribe(OBSTACLE_TOPIC, qos=1)
            logging.info("Subscribed to topics: %s, %s", MISSION_COMMAND_TOPIC, OBSTACLE_TOPIC)
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
            
            if msg.topic == MISSION_COMMAND_TOPIC:
                self._handle_mission_command(data)
            elif msg.topic == OBSTACLE_TOPIC:
                self._handle_obstacle_detection(data)
                
        except Exception as exc:
            logging.error("Failed to parse MQTT message from %s: %s", msg.topic, exc)
    
    def _handle_mission_command(self, command: Dict[str, Any]) -> None:
        """Handle mission commands."""
        cmd_type = command.get("type", "")
        
        if cmd_type == "start" and self.state == MissionState.IDLE:
            mission_id = command.get("mission_id")
            if mission_id:
                self._load_and_start_mission(mission_id)
        elif cmd_type == "pause" and self.state in [MissionState.ENROUTE, MissionState.HOLD]:
            self._pause_mission()
        elif cmd_type == "resume" and self.state == MissionState.PAUSED:
            self._resume_mission()
        elif cmd_type == "abort":
            self._abort_mission()
        else:
            logging.warning("Invalid command %s for state %s", cmd_type, self.state)
    
    def _handle_obstacle_detection(self, obstacle: Dict[str, Any]) -> None:
        """Handle obstacle detection events."""
        if self.state not in [MissionState.ENROUTE, MissionState.HOLD]:
            return
        
        obstacle_type = obstacle.get("type", "unknown")
        confidence = obstacle.get("confidence", 0.0)
        
        # Only react to high-confidence obstacles
        if confidence > 0.7:
            logging.warning("Obstacle detected: %s (confidence: %.2f)", obstacle_type, confidence)
            self.obstacle_detected = True
            self.obstacle_position = (
                obstacle.get("lat", self.current_position[0]),
                obstacle.get("lon", self.current_position[1]),
                obstacle.get("alt", self.current_position[2])
            )
            self._pause_mission()
    
    def load_mission(self, mission_path: Path) -> Mission:
        """Load mission from JSON file."""
        try:
            with mission_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            
            waypoints = []
            for wp_data in data.get("waypoints", []):
                waypoint = Waypoint(
                    lat=wp_data["lat"],
                    lon=wp_data["lon"],
                    alt=wp_data.get("alt", data.get("default_altitude", DEFAULT_ALTITUDE)),
                    hold_seconds=wp_data.get("hold_seconds", 0.0),
                    action=wp_data.get("action", "none"),
                    metadata=wp_data.get("metadata", {})
                )
                waypoints.append(waypoint)
            
            mission = Mission(
                mission_id=data["mission_id"],
                name=data.get("name", "Unnamed Mission"),
                waypoints=waypoints,
                payload_metadata=data.get("payload_metadata", {}),
                max_speed=data.get("max_speed", DEFAULT_SPEED),
                default_altitude=data.get("default_altitude", DEFAULT_ALTITUDE)
            )
            
            logging.info("Loaded mission: %s (%d waypoints)", mission.name, len(waypoints))
            return mission
            
        except Exception as exc:
            logging.error("Failed to load mission from %s: %s", mission_path, exc)
            raise
    
    def _load_and_start_mission(self, mission_id: str) -> None:
        """Load and start a mission by ID."""
        try:
            # Look for mission file
            mission_path = Path(f"data/sample_missions/{mission_id}.json")
            if not mission_path.exists():
                mission_path = Path(f"data/sample_missions/sample_mission.json")
            
            self.current_mission = self.load_mission(mission_path)
            self._start_mission()
            
        except Exception as exc:
            logging.error("Failed to start mission %s: %s", mission_id, exc)
            self.state = MissionState.ERROR
            self.mission_status.error_message = str(exc)
    
    def _start_mission(self) -> None:
        """Start mission execution."""
        if not self.current_mission:
            return
        
        self.state = MissionState.TAKEOFF
        self.current_waypoint_index = 0
        self.mission_start_time = time.time()
        self.speed = self.current_mission.max_speed
        
        # Set initial position (first waypoint)
        if self.current_mission.waypoints:
            first_wp = self.current_mission.waypoints[0]
            self.current_position = (first_wp.lat, first_wp.lon, 0.0)  # Start on ground
            self.target_position = (first_wp.lat, first_wp.lon, first_wp.alt)
        
        logging.info("Starting mission: %s", self.current_mission.name)
        self._publish_mission_status()
    
    def _pause_mission(self) -> None:
        """Pause mission execution."""
        if self.state in [MissionState.ENROUTE, MissionState.HOLD]:
            self.state = MissionState.PAUSED
            logging.info("Mission paused")
            self._publish_mission_status()
    
    def _resume_mission(self) -> None:
        """Resume mission execution."""
        if self.state == MissionState.PAUSED:
            # Clear obstacle flag
            self.obstacle_detected = False
            self.obstacle_position = None
            
            # Resume appropriate state
            if self.current_waypoint_index < len(self.current_mission.waypoints):
                current_wp = self.current_mission.waypoints[self.current_waypoint_index]
                if current_wp.hold_seconds > 0:
                    self.state = MissionState.HOLD
                else:
                    self.state = MissionState.ENROUTE
            else:
                self.state = MissionState.RETURN
            
            logging.info("Mission resumed")
            self._publish_mission_status()
    
    def _abort_mission(self) -> None:
        """Abort mission execution."""
        self.state = MissionState.ERROR
        self.mission_status.error_message = "Mission aborted by command"
        logging.warning("Mission aborted")
        self._publish_mission_status()
    
    def _calculate_distance(self, pos1: Tuple[float, float, float], pos2: Tuple[float, float, float]) -> float:
        """Calculate distance between two positions in meters (simplified)."""
        # Simplified distance calculation (not accounting for Earth's curvature)
        lat1, lon1, alt1 = pos1
        lat2, lon2, alt2 = pos2
        
        # Convert to meters (rough approximation)
        lat_diff = (lat2 - lat1) * 111320  # meters per degree latitude
        lon_diff = (lon2 - lon1) * 111320 * abs(lat1)  # meters per degree longitude (varies with latitude)
        alt_diff = alt2 - alt1
        
        return (lat_diff**2 + lon_diff**2 + alt_diff**2)**0.5
    
    def _interpolate_position(self, start: Tuple[float, float, float], end: Tuple[float, float, float], 
                            progress: float) -> Tuple[float, float, float]:
        """Interpolate position between start and end based on progress (0.0 to 1.0)."""
        lat = start[0] + (end[0] - start[0]) * progress
        lon = start[1] + (end[1] - start[1]) * progress
        alt = start[2] + (end[2] - start[2]) * progress
        return (lat, lon, alt)
    
    def _update_position(self) -> None:
        """Update current position based on mission state and timing."""
        if not self.current_mission or self.current_waypoint_index >= len(self.current_mission.waypoints):
            return
        
        current_wp = self.current_mission.waypoints[self.current_waypoint_index]
        target_pos = (current_wp.lat, current_wp.lon, current_wp.alt)
        
        if self.state == MissionState.TAKEOFF:
            # Move to first waypoint altitude
            self.target_position = target_pos
            distance = self._calculate_distance(self.current_position, target_pos)
            if distance < 1.0:  # Within 1 meter
                self.state = MissionState.ENROUTE
                self.waypoint_start_time = time.time()
            else:
                # Interpolate position
                elapsed = time.time() - self.mission_start_time
                total_time = distance / self.speed
                progress = min(1.0, elapsed / total_time)
                self.current_position = self._interpolate_position(
                    (self.current_position[0], self.current_position[1], 0.0),
                    target_pos, progress
                )
        
        elif self.state == MissionState.ENROUTE:
            # Move to current waypoint
            distance = self._calculate_distance(self.current_position, target_pos)
            if distance < 1.0:  # Within 1 meter
                # Reached waypoint
                self.current_position = target_pos
                if current_wp.hold_seconds > 0:
                    self.state = MissionState.HOLD
                    self.hold_start_time = time.time()
                else:
                    self._advance_to_next_waypoint()
            else:
                # Interpolate position
                elapsed = time.time() - self.waypoint_start_time
                total_time = distance / self.speed
                progress = min(1.0, elapsed / total_time)
                self.current_position = self._interpolate_position(
                    self.current_position, target_pos, progress
                )
        
        elif self.state == MissionState.HOLD:
            # Hold at current waypoint
            elapsed = time.time() - self.hold_start_time
            if elapsed >= current_wp.hold_seconds:
                self._advance_to_next_waypoint()
        
        elif self.state == MissionState.DELIVERY:
            # Execute delivery action
            self._execute_delivery_action(current_wp)
            self._advance_to_next_waypoint()
        
        elif self.state == MissionState.RETURN:
            # Return to start position
            start_pos = (self.current_mission.waypoints[0].lat, 
                        self.current_mission.waypoints[0].lon, 0.0)
            distance = self._calculate_distance(self.current_position, start_pos)
            if distance < 1.0:
                self.state = MissionState.LANDED
            else:
                elapsed = time.time() - self.waypoint_start_time
                total_time = distance / self.speed
                progress = min(1.0, elapsed / total_time)
                self.current_position = self._interpolate_position(
                    self.current_position, start_pos, progress
                )
    
    def _advance_to_next_waypoint(self) -> None:
        """Advance to the next waypoint in the mission."""
        self.current_waypoint_index += 1
        
        if self.current_waypoint_index >= len(self.current_mission.waypoints):
            # Mission complete, return to start
            self.state = MissionState.RETURN
            self.waypoint_start_time = time.time()
        else:
            # Move to next waypoint
            self.state = MissionState.ENROUTE
            self.waypoint_start_time = time.time()
    
    def _execute_delivery_action(self, waypoint: Waypoint) -> None:
        """Execute delivery action at waypoint."""
        action = waypoint.action.lower()
        
        if action == "deliver":
            # Simulate servo command for payload release
            servo_command = {
                "device_id": DEVICE_ID,
                "timestamp": time.time(),
                "command": "release",
                "waypoint": self.current_waypoint_index,
                "payload_metadata": self.current_mission.payload_metadata
            }
            
            self._publish_servo_command(servo_command)
            logging.info("Payload delivery executed at waypoint %d", self.current_waypoint_index)
        
        elif action == "photo":
            # Simulate photo capture
            photo_data = {
                "device_id": DEVICE_ID,
                "timestamp": time.time(),
                "waypoint": self.current_waypoint_index,
                "location": {
                    "lat": self.current_position[0],
                    "lon": self.current_position[1],
                    "alt": self.current_position[2]
                },
                "mission_id": self.current_mission.mission_id
            }
            
            logging.info("Photo captured at waypoint %d", self.current_waypoint_index)
            # In real implementation, would save photo and metadata
    
    def _publish_servo_command(self, command: Dict[str, Any]) -> None:
        """Publish servo command to MQTT."""
        if not self.mqtt_client:
            return
        
        try:
            payload = json.dumps(command).encode("utf-8")
            result = self.mqtt_client.publish(SERVO_COMMAND_TOPIC, payload=payload, qos=1)
            result.wait_for_publish(2.0)
            logging.debug("Published servo command")
        except Exception as exc:
            logging.error("Failed to publish servo command: %s", exc)
    
    def _publish_mission_status(self) -> None:
        """Publish current mission status to MQTT."""
        if not self.mqtt_client or not self.current_mission:
            return
        
        # Calculate progress
        total_waypoints = len(self.current_mission.waypoints)
        progress = (self.current_waypoint_index / total_waypoints) * 100 if total_waypoints > 0 else 0
        
        # Estimate time remaining
        elapsed = time.time() - self.mission_start_time
        if progress > 0:
            estimated_total = elapsed / (progress / 100)
            time_remaining = max(0, estimated_total - elapsed)
        else:
            time_remaining = 0
        
        self.mission_status = MissionStatus(
            mission_id=self.current_mission.mission_id,
            state=self.state,
            current_waypoint=self.current_waypoint_index,
            total_waypoints=total_waypoints,
            progress_percent=progress,
            estimated_time_remaining=time_remaining,
            current_position=self.current_position,
            target_position=self.target_position,
            speed=self.speed,
            timestamp=time.time(),
            error_message=getattr(self.mission_status, 'error_message', None) if self.mission_status else None
        )
        
        try:
            payload = json.dumps(asdict(self.mission_status), default=str).encode("utf-8")
            result = self.mqtt_client.publish(MISSION_STATUS_TOPIC, payload=payload, qos=1)
            result.wait_for_publish(2.0)
            logging.debug("Published mission status: %s (%.1f%%)", self.state.value, progress)
        except Exception as exc:
            logging.error("Failed to publish mission status: %s", exc)
    
    def _publish_simulated_telemetry(self) -> None:
        """Publish simulated telemetry data."""
        if not self.mqtt_client:
            return
        
        telemetry = {
            "device_id": DEVICE_ID,
            "timestamp": time.time(),
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()),
            "battery": {
                "voltage": 12.4,
                "percentage": 85.0
            },
            "camera": {
                "available": True,
                "resolution": "1920x1080",
                "fps": 30,
                "recording": False
            },
            "gps": {
                "lat": self.current_position[0],
                "lon": self.current_position[1],
                "alt": self.current_position[2],
                "num_sats": 8,
                "hdop": 1.2,
                "quality": 1
            },
            "imu": {
                "pitch_deg": 0.0,
                "roll_deg": 0.0,
                "accel": {"x_g": 0.0, "y_g": 0.0, "z_g": 1.0},
                "gyro": {"x_dps": 0.0, "y_dps": 0.0, "z_dps": 0.0}
            },
            "mission": {
                "mission_id": self.current_mission.mission_id if self.current_mission else None,
                "state": self.state.value,
                "waypoint": self.current_waypoint_index,
                "progress_percent": getattr(self.mission_status, 'progress_percent', 0) if self.mission_status else 0
            }
        }
        
        try:
            payload = json.dumps(telemetry).encode("utf-8")
            result = self.mqtt_client.publish(TELEMETRY_TOPIC, payload=payload, qos=1)
            result.wait_for_publish(2.0)
        except Exception as exc:
            logging.error("Failed to publish simulated telemetry: %s", exc)
    
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
    
    def run(self, mission_path: Optional[Path] = None, speed: float = DEFAULT_SPEED) -> None:
        """Main mission runner loop."""
        logging.info("Starting mission runner (device_id=%s, dry_run=%s)", DEVICE_ID, self.dry_run)
        
        # Connect to MQTT
        self.mqtt_client = self.build_mqtt_client()
        self.connect_mqtt_with_retries()
        
        # Load initial mission if provided
        if mission_path and mission_path.exists():
            try:
                self.current_mission = self.load_mission(mission_path)
                self.speed = speed
                logging.info("Loaded mission: %s", self.current_mission.name)
            except Exception as exc:
                logging.error("Failed to load initial mission: %s", exc)
        
        # Main loop
        last_status_publish = 0.0
        last_telemetry_publish = 0.0
        
        while not self.killer.should_stop:
            try:
                now = time.time()
                
                # Update position and state
                if self.current_mission and self.state != MissionState.IDLE:
                    self._update_position()
                
                # Publish status every 2 seconds
                if now - last_status_publish >= 2.0:
                    if self.current_mission:
                        self._publish_mission_status()
                    last_status_publish = now
                
                # Publish telemetry every 1 second
                if now - last_telemetry_publish >= 1.0:
                    self._publish_simulated_telemetry()
                    last_telemetry_publish = now
                
                # Log state changes
                if hasattr(self, '_last_state') and self._last_state != self.state:
                    logging.info("State changed: %s → %s", self._last_state.value, self.state.value)
                self._last_state = self.state
                
                time.sleep(0.1)  # Small sleep to prevent busy waiting
                
            except Exception as exc:
                logging.exception("Error in mission loop: %s", exc)
                time.sleep(1.0)
        
        # Cleanup
        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception as exc:
                logging.error("Error disconnecting MQTT: %s", exc)
        
        logging.info("Mission runner stopped")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Mission runner for drone companion system")
    parser.add_argument("--mission", type=Path, default=DEFAULT_MISSION_PATH,
                       help="Path to mission JSON file")
    parser.add_argument("--speed", type=float, default=DEFAULT_SPEED,
                       help="Mission speed in m/s")
    parser.add_argument("--dry-run", action="store_true",
                       help="Run in dry-run mode (simulate without MQTT)")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Set logging level")
    
    args = parser.parse_args()
    
    # Create mission runner
    runner = MissionRunner(dry_run=args.dry_run)
    runner.setup_logging(args.log_level)
    
    try:
        runner.run(mission_path=args.mission, speed=args.speed)
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
    except Exception as exc:
        logging.exception("Fatal error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
