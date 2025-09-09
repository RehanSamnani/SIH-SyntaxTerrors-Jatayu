#!/usr/bin/env python3
"""
Real-time telemetry monitoring script.

This script:
- Subscribes to telemetry topics
- Displays real-time telemetry data
- Provides data visualization
- Logs telemetry to files
- Monitors system health

Usage:
    python scripts/monitor_telemetry.py [--broker localhost] [--port 1883] [--device-id pi-drone-01]
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

import paho.mqtt.client as mqtt  # type: ignore


class TelemetryMonitor:
    """Monitor and display telemetry data in real-time."""
    
    def __init__(self, broker: str, port: int, device_id: str, 
                 username: Optional[str] = None, password: Optional[str] = None) -> None:
        self.broker = broker
        self.port = port
        self.device_id = device_id
        self.username = username
        self.password = password
        
        self.telemetry_topic = f"drone/{device_id}/telemetry"
        self.mqtt_client: Optional[mqtt.Client] = None
        
        # Data storage
        self.telemetry_history = deque(maxlen=100)  # Last 100 messages
        self.stats = {
            "messages_received": 0,
            "start_time": time.time(),
            "last_message_time": 0,
            "gps_fixes": 0,
            "imu_readings": 0
        }
        
        self.running = True
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum: int, frame: Any) -> None:  # noqa: ARG002
        """Handle shutdown signals."""
        logging.info("Received signal %s, stopping monitor...", signum)
        self.running = False
    
    def setup_logging(self) -> None:
        """Configure logging."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)]
        )
    
    def build_mqtt_client(self) -> mqtt.Client:
        """Create MQTT client."""
        client = mqtt.Client(client_id=f"telemetry-monitor-{int(time.time())}")
        
        if self.username:
            client.username_pw_set(self.username, self.password)
        
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        
        return client
    
    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Dict[str, Any], rc: int) -> None:  # noqa: ARG002
        """Handle MQTT connection."""
        if rc == 0:
            logging.info("✅ Connected to MQTT broker %s:%d", self.broker, self.port)
            client.subscribe(self.telemetry_topic, qos=1)
            logging.info("Subscribed to telemetry topic: %s", self.telemetry_topic)
        else:
            logging.error("❌ Failed to connect to MQTT broker: %s", mqtt.connack_string(rc))
    
    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:  # noqa: ARG002
        """Handle MQTT disconnection."""
        if rc != 0:
            logging.warning("Unexpected MQTT disconnection: %s", mqtt.connack_string(rc))
    
    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:  # noqa: ARG002
        """Handle incoming telemetry messages."""
        try:
            data = json.loads(msg.payload.decode("utf-8"))
            self.telemetry_history.append(data)
            self.stats["messages_received"] += 1
            self.stats["last_message_time"] = time.time()
            
            # Update stats
            if data.get("gps"):
                self.stats["gps_fixes"] += 1
            if data.get("imu"):
                self.stats["imu_readings"] += 1
            
            # Display telemetry
            self._display_telemetry(data)
            
        except Exception as exc:
            logging.error("Failed to parse telemetry message: %s", exc)
    
    def _display_telemetry(self, data: Dict[str, Any]) -> None:
        """Display telemetry data in a formatted way."""
        # Clear screen (works on most terminals)
        print("\033[2J\033[H", end="")
        
        # Header
        print("=" * 80)
        print(f"DRONE TELEMETRY MONITOR - Device: {self.device_id}")
        print("=" * 80)
        
        # Timestamp
        timestamp = data.get("timestamp_iso", "Unknown")
        print(f"Timestamp: {timestamp}")
        
        # Battery status
        battery = data.get("battery", {})
        voltage = battery.get("voltage", 0)
        percentage = battery.get("percentage", 0)
        battery_bar = self._create_progress_bar(percentage, 20)
        print(f"Battery:   {voltage:.2f}V ({percentage:.1f}%) {battery_bar}")
        
        # GPS status
        gps = data.get("gps")
        if gps and gps.get("lat") is not None:
            lat = gps.get("lat", 0)
            lon = gps.get("lon", 0)
            alt = gps.get("alt", 0)
            sats = gps.get("num_sats", 0)
            hdop = gps.get("hdop", 0)
            print(f"GPS:       Lat: {lat:.6f}° Lon: {lon:.6f}° Alt: {alt:.1f}m")
            print(f"           Sats: {sats} HDOP: {hdop:.1f}")
        else:
            print("GPS:       No fix")
        
        # IMU status
        imu = data.get("imu")
        if imu:
            pitch = imu.get("pitch_deg", 0)
            roll = imu.get("roll_deg", 0)
            accel = imu.get("accel", {})
            gyro = imu.get("gyro", {})
            print(f"IMU:       Pitch: {pitch:+.2f}° Roll: {roll:+.2f}°")
            print(f"           Accel: X:{accel.get('x_g', 0):+.2f} Y:{accel.get('y_g', 0):+.2f} Z:{accel.get('z_g', 0):+.2f} g")
            print(f"           Gyro:  X:{gyro.get('x_dps', 0):+.2f} Y:{gyro.get('y_dps', 0):+.2f} Z:{gyro.get('z_dps', 0):+.2f} °/s")
        else:
            print("IMU:       No data")
        
        # Camera status
        camera = data.get("camera", {})
        available = camera.get("available", False)
        resolution = camera.get("resolution", "Unknown")
        fps = camera.get("fps", 0)
        recording = camera.get("recording", False)
        print(f"Camera:    {'Available' if available else 'Unavailable'} {resolution}@{fps}fps {'🔴' if recording else '⚪'}")
        
        # Statistics
        print("-" * 80)
        uptime = time.time() - self.stats["start_time"]
        messages_per_sec = self.stats["messages_received"] / uptime if uptime > 0 else 0
        time_since_last = time.time() - self.stats["last_message_time"]
        
        print(f"Stats:     Messages: {self.stats['messages_received']} | "
              f"Rate: {messages_per_sec:.2f}/s | "
              f"GPS Fixes: {self.stats['gps_fixes']} | "
              f"IMU Readings: {self.stats['imu_readings']}")
        print(f"           Uptime: {uptime:.0f}s | "
              f"Last Message: {time_since_last:.1f}s ago")
        
        # Connection status
        status_color = "🟢" if time_since_last < 5 else "🟡" if time_since_last < 10 else "🔴"
        print(f"Status:    {status_color} {'Connected' if time_since_last < 5 else 'Warning' if time_since_last < 10 else 'Disconnected'}")
        
        print("=" * 80)
        print("Press Ctrl+C to exit")
    
    def _create_progress_bar(self, value: float, width: int) -> str:
        """Create a text-based progress bar."""
        filled = int((value / 100) * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"
    
    def connect_mqtt(self) -> None:
        """Connect to MQTT broker."""
        self.mqtt_client = self.build_mqtt_client()
        
        try:
            self.mqtt_client.connect(self.broker, self.port, keepalive=30)
            self.mqtt_client.loop_start()
            
            # Wait for connection
            timeout = 10
            start_time = time.time()
            while not self.mqtt_client.is_connected() and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if not self.mqtt_client.is_connected():
                raise Exception("Failed to connect to MQTT broker within timeout")
                
        except Exception as exc:
            logging.error("Failed to connect to MQTT broker: %s", exc)
            raise
    
    def run(self) -> None:
        """Run the telemetry monitor."""
        logging.info("Starting telemetry monitor for device: %s", self.device_id)
        
        try:
            # Connect to MQTT
            self.connect_mqtt()
            
            # Main loop
            while self.running:
                time.sleep(0.1)
                
                # Check for connection issues
                if not self.mqtt_client.is_connected():
                    logging.warning("MQTT connection lost, attempting to reconnect...")
                    try:
                        self.mqtt_client.reconnect()
                    except Exception as exc:
                        logging.error("Failed to reconnect: %s", exc)
                        time.sleep(5)
        
        except KeyboardInterrupt:
            logging.info("Monitor interrupted by user")
        except Exception as exc:
            logging.exception("Monitor failed: %s", exc)
        finally:
            # Cleanup
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            
            # Print final stats
            self._print_final_stats()
    
    def _print_final_stats(self) -> None:
        """Print final statistics."""
        print("\n" + "=" * 80)
        print("FINAL STATISTICS")
        print("=" * 80)
        
        uptime = time.time() - self.stats["start_time"]
        messages_per_sec = self.stats["messages_received"] / uptime if uptime > 0 else 0
        
        print(f"Total Messages:     {self.stats['messages_received']}")
        print(f"GPS Fixes:          {self.stats['gps_fixes']}")
        print(f"IMU Readings:       {self.stats['imu_readings']}")
        print(f"Average Rate:       {messages_per_sec:.2f} messages/second")
        print(f"Total Uptime:       {uptime:.1f} seconds")
        print("=" * 80)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Monitor drone telemetry")
    parser.add_argument("--broker", default="localhost", help="MQTT broker hostname")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--device-id", default="pi-drone-01", help="Device ID to monitor")
    parser.add_argument("--username", help="MQTT username")
    parser.add_argument("--password", help="MQTT password")
    
    args = parser.parse_args()
    
    # Load credentials from environment if not provided
    username = args.username or os.getenv("MQTT_USERNAME")
    password = args.password or os.getenv("MQTT_PASSWORD")
    
    # Create monitor
    monitor = TelemetryMonitor(args.broker, args.port, args.device_id, username, password)
    monitor.setup_logging()
    
    try:
        monitor.run()
    except Exception as exc:
        logging.exception("Monitor failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
