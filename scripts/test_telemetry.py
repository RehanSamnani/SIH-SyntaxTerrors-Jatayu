#!/usr/bin/env python3
"""
Test script for telemetry service validation.

This script:
- Tests MQTT broker connectivity
- Validates telemetry message format
- Simulates sensor data publishing
- Monitors telemetry aggregation
- Provides performance metrics

Usage:
    python scripts/test_telemetry.py [--broker localhost] [--port 1883] [--duration 60]
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from typing import Any, Dict, List, Optional

import paho.mqtt.client as mqtt  # type: ignore


class TelemetryTester:
    """Test telemetry service functionality."""
    
    def __init__(self, broker: str, port: int, username: Optional[str] = None, 
                 password: Optional[str] = None) -> None:
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        
        self.device_id = "test-drone-01"
        self.gps_topic = f"drone/{self.device_id}/gps"
        self.imu_topic = f"drone/{self.device_id}/imu"
        self.telemetry_topic = f"drone/{self.device_id}/telemetry"
        
        self.mqtt_client: Optional[mqtt.Client] = None
        self.telemetry_messages: List[Dict[str, Any]] = []
        self.test_results: Dict[str, Any] = {
            "connectivity": False,
            "gps_publish": False,
            "imu_publish": False,
            "telemetry_received": False,
            "message_format_valid": False,
            "performance_metrics": {}
        }
        
        self.running = True
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum: int, frame: Any) -> None:  # noqa: ARG002
        """Handle shutdown signals."""
        logging.info("Received signal %s, stopping test...", signum)
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
        client = mqtt.Client(client_id=f"telemetry-tester-{int(time.time())}")
        
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
            self.test_results["connectivity"] = True
            # Subscribe to telemetry topic
            client.subscribe(self.telemetry_topic, qos=1)
            logging.info("Subscribed to telemetry topic: %s", self.telemetry_topic)
        else:
            logging.error("❌ Failed to connect to MQTT broker: %s", mqtt.connack_string(rc))
    
    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:  # noqa: ARG002
        """Handle MQTT disconnection."""
        if rc != 0:
            logging.warning("Unexpected MQTT disconnection: %s", mqtt.connack_string(rc))
    
    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:  # noqa: ARG002
        """Handle incoming MQTT messages."""
        try:
            data = json.loads(msg.payload.decode("utf-8"))
            self.telemetry_messages.append(data)
            self.test_results["telemetry_received"] = True
            
            # Validate message format
            if self._validate_telemetry_format(data):
                self.test_results["message_format_valid"] = True
                logging.info("✅ Received valid telemetry: bat=%.1f%% lat=%.6f lon=%.6f pitch=%.1f roll=%.1f",
                           data.get("battery", {}).get("percentage", 0),
                           data.get("gps", {}).get("lat", 0) if data.get("gps") else 0,
                           data.get("gps", {}).get("lon", 0) if data.get("gps") else 0,
                           data.get("imu", {}).get("pitch_deg", 0) if data.get("imu") else 0,
                           data.get("imu", {}).get("roll_deg", 0) if data.get("imu") else 0)
            else:
                logging.warning("⚠️  Received telemetry with invalid format")
                
        except Exception as exc:
            logging.error("Failed to parse telemetry message: %s", exc)
    
    def _validate_telemetry_format(self, data: Dict[str, Any]) -> bool:
        """Validate telemetry message format."""
        required_fields = ["device_id", "timestamp", "battery", "camera"]
        
        for field in required_fields:
            if field not in data:
                logging.error("Missing required field: %s", field)
                return False
        
        # Validate battery data
        battery = data.get("battery", {})
        if not isinstance(battery, dict) or "percentage" not in battery:
            logging.error("Invalid battery data format")
            return False
        
        # Validate camera data
        camera = data.get("camera", {})
        if not isinstance(camera, dict) or "available" not in camera:
            logging.error("Invalid camera data format")
            return False
        
        return True
    
    def connect_mqtt(self) -> None:
        """Connect to MQTT broker."""
        self.mqtt_client = self.build_mqtt_client()
        
        try:
            self.mqtt_client.connect(self.broker, self.port, keepalive=30)
            self.mqtt_client.loop_start()
            
            # Wait for connection
            timeout = 10
            start_time = time.time()
            while not self.test_results["connectivity"] and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if not self.test_results["connectivity"]:
                raise Exception("Failed to connect to MQTT broker within timeout")
                
        except Exception as exc:
            logging.error("Failed to connect to MQTT broker: %s", exc)
            raise
    
    def publish_test_gps_data(self) -> None:
        """Publish test GPS data."""
        if not self.mqtt_client:
            return
        
        gps_data = {
            "device_id": self.device_id,
            "type": "GGA",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()),
            "lat": 37.7749,
            "lon": -122.4194,
            "alt": 100.0,
            "num_sats": 8,
            "hdop": 1.2,
            "quality": 1
        }
        
        try:
            payload = json.dumps(gps_data).encode("utf-8")
            result = self.mqtt_client.publish(self.gps_topic, payload=payload, qos=1)
            result.wait_for_publish(2.0)
            self.test_results["gps_publish"] = True
            logging.info("✅ Published test GPS data")
        except Exception as exc:
            logging.error("Failed to publish GPS data: %s", exc)
    
    def publish_test_imu_data(self) -> None:
        """Publish test IMU data."""
        if not self.mqtt_client:
            return
        
        imu_data = {
            "ts": time.time(),
            "accel": {
                "x_g": 0.1,
                "y_g": -0.2,
                "z_g": 1.0
            },
            "gyro": {
                "x_dps": 0.5,
                "y_dps": 0.3,
                "z_dps": 0.2
            },
            "est": {
                "pitch_deg": -2.5,
                "roll_deg": 1.8
            }
        }
        
        try:
            payload = json.dumps(imu_data).encode("utf-8")
            result = self.mqtt_client.publish(self.imu_topic, payload=payload, qos=1)
            result.wait_for_publish(2.0)
            self.test_results["imu_publish"] = True
            logging.info("✅ Published test IMU data")
        except Exception as exc:
            logging.error("Failed to publish IMU data: %s", exc)
    
    def run_test(self, duration: int) -> None:
        """Run telemetry test for specified duration."""
        logging.info("Starting telemetry test for %d seconds...", duration)
        
        start_time = time.time()
        last_gps_publish = 0
        last_imu_publish = 0
        
        while self.running and (time.time() - start_time) < duration:
            now = time.time()
            
            # Publish GPS data every 2 seconds
            if now - last_gps_publish >= 2.0:
                self.publish_test_gps_data()
                last_gps_publish = now
            
            # Publish IMU data every 1 second
            if now - last_imu_publish >= 1.0:
                self.publish_test_imu_data()
                last_imu_publish = now
            
            time.sleep(0.1)
        
        # Calculate performance metrics
        self._calculate_performance_metrics(start_time)
        
        # Disconnect
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
    
    def _calculate_performance_metrics(self, start_time: float) -> None:
        """Calculate performance metrics."""
        duration = time.time() - start_time
        message_count = len(self.telemetry_messages)
        
        self.test_results["performance_metrics"] = {
            "test_duration": duration,
            "telemetry_messages_received": message_count,
            "messages_per_second": message_count / duration if duration > 0 else 0,
            "average_message_interval": duration / message_count if message_count > 0 else 0
        }
    
    def print_results(self) -> None:
        """Print test results summary."""
        print("\n" + "="*60)
        print("TELEMETRY SERVICE TEST RESULTS")
        print("="*60)
        
        # Connectivity tests
        print(f"MQTT Connectivity:     {'✅ PASS' if self.test_results['connectivity'] else '❌ FAIL'}")
        print(f"GPS Data Publishing:   {'✅ PASS' if self.test_results['gps_publish'] else '❌ FAIL'}")
        print(f"IMU Data Publishing:   {'✅ PASS' if self.test_results['imu_publish'] else '❌ FAIL'}")
        print(f"Telemetry Received:    {'✅ PASS' if self.test_results['telemetry_received'] else '❌ FAIL'}")
        print(f"Message Format Valid:  {'✅ PASS' if self.test_results['message_format_valid'] else '❌ FAIL'}")
        
        # Performance metrics
        metrics = self.test_results["performance_metrics"]
        print(f"\nPerformance Metrics:")
        print(f"  Test Duration:        {metrics.get('test_duration', 0):.1f} seconds")
        print(f"  Messages Received:    {metrics.get('telemetry_messages_received', 0)}")
        print(f"  Messages/Second:      {metrics.get('messages_per_second', 0):.2f}")
        print(f"  Avg Message Interval: {metrics.get('average_message_interval', 0):.2f} seconds")
        
        # Overall result
        all_passed = all([
            self.test_results["connectivity"],
            self.test_results["gps_publish"],
            self.test_results["imu_publish"],
            self.test_results["telemetry_received"],
            self.test_results["message_format_valid"]
        ])
        
        print(f"\nOverall Result:        {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
        print("="*60)
        
        if not all_passed:
            print("\nTroubleshooting Tips:")
            if not self.test_results["connectivity"]:
                print("- Check if MQTT broker is running: sudo systemctl status mosquitto")
                print("- Verify broker address and port")
            if not self.test_results["telemetry_received"]:
                print("- Check if telemetry service is running: sudo systemctl status telemetry.service")
                print("- Verify telemetry service is subscribed to GPS/IMU topics")
            if not self.test_results["message_format_valid"]:
                print("- Check telemetry service logs: sudo journalctl -u telemetry.service")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test telemetry service")
    parser.add_argument("--broker", default="localhost", help="MQTT broker hostname")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--username", help="MQTT username")
    parser.add_argument("--password", help="MQTT password")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    
    args = parser.parse_args()
    
    # Load credentials from environment if not provided
    username = args.username or os.getenv("MQTT_USERNAME")
    password = args.password or os.getenv("MQTT_PASSWORD")
    
    # Create tester
    tester = TelemetryTester(args.broker, args.port, username, password)
    tester.setup_logging()
    
    try:
        # Connect to MQTT
        tester.connect_mqtt()
        
        # Run test
        tester.run_test(args.duration)
        
        # Print results
        tester.print_results()
        
    except KeyboardInterrupt:
        logging.info("Test interrupted by user")
    except Exception as exc:
        logging.exception("Test failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
