#!/usr/bin/env python3
"""
Integration tests for telemetry system.

Tests:
- End-to-end telemetry flow (GPS + IMU → MQTT → Aggregator)
- MQTT message format validation
- Service integration and error recovery
- Performance and reliability
"""

import json
import pytest
import time
import threading
from pathlib import Path
from unittest.mock import Mock, patch
import paho.mqtt.client as mqtt

import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from telemetry_service import TelemetryAggregator


class MockMQTTBroker:
    """Mock MQTT broker for testing."""
    
    def __init__(self):
        self.clients = {}
        self.messages = []
        self.subscriptions = {}
    
    def connect_client(self, client_id: str, client: mqtt.Client):
        """Connect a client to the mock broker."""
        self.clients[client_id] = client
        client._connected_flag = True
        client._on_connect(client, None, None, 0)
    
    def publish_message(self, topic: str, payload: str, qos: int = 0):
        """Publish a message to all subscribed clients."""
        self.messages.append((topic, payload, qos))
        
        # Find subscribers
        for client_id, client in self.clients.items():
            if topic in self.subscriptions.get(client_id, []):
                msg = Mock()
                msg.topic = topic
                msg.payload = payload.encode('utf-8')
                client._on_message(client, None, msg)
    
    def subscribe_client(self, client_id: str, topic: str):
        """Subscribe a client to a topic."""
        if client_id not in self.subscriptions:
            self.subscriptions[client_id] = []
        self.subscriptions[client_id].append(topic)


class TestTelemetryIntegration:
    """Test telemetry system integration."""
    
    @pytest.fixture
    def mock_broker(self):
        """Create a mock MQTT broker."""
        return MockMQTTBroker()
    
    @pytest.fixture
    def telemetry_aggregator(self):
        """Create a telemetry aggregator for testing."""
        aggregator = TelemetryAggregator(dry_run=False)
        aggregator.setup_logging("WARNING")  # Reduce log noise
        return aggregator
    
    def test_telemetry_packet_creation(self, telemetry_aggregator):
        """Test telemetry packet creation with sensor data."""
        # Set up mock sensor data
        telemetry_aggregator.latest_gps = {
            "device_id": "test-drone",
            "type": "GGA",
            "lat": 37.7749,
            "lon": -122.4194,
            "alt": 100.0,
            "num_sats": 8,
            "hdop": 1.2,
            "quality": 1
        }
        
        telemetry_aggregator.latest_imu = {
            "ts": 1234567890.0,
            "accel": {"x_g": 0.1, "y_g": -0.2, "z_g": 1.0},
            "gyro": {"x_dps": 0.5, "y_dps": 0.3, "z_dps": 0.2},
            "est": {"pitch_deg": 1.2, "roll_deg": -0.8}
        }
        
        # Create telemetry packet
        packet = telemetry_aggregator.create_telemetry_packet()
        
        # Validate packet structure
        assert packet["device_id"] == "pi-drone-01"
        assert "timestamp" in packet
        assert "timestamp_iso" in packet
        assert "battery" in packet
        assert "camera" in packet
        assert "gps" in packet
        assert "imu" in packet
        
        # Validate GPS data
        assert packet["gps"]["lat"] == 37.7749
        assert packet["gps"]["lon"] == -122.4194
        assert packet["gps"]["alt"] == 100.0
        assert packet["gps"]["num_sats"] == 8
        
        # Validate IMU data
        assert packet["imu"]["pitch_deg"] == 1.2
        assert packet["imu"]["roll_deg"] == -0.8
        assert packet["imu"]["accel"]["x_g"] == 0.1
        assert packet["imu"]["gyro"]["x_dps"] == 0.5
        
        # Validate battery data
        assert "voltage" in packet["battery"]
        assert "percentage" in packet["battery"]
        assert 0 <= packet["battery"]["percentage"] <= 100
    
    def test_telemetry_packet_without_sensors(self, telemetry_aggregator):
        """Test telemetry packet creation without sensor data."""
        # No sensor data set
        telemetry_aggregator.latest_gps = None
        telemetry_aggregator.latest_imu = None
        
        # Create telemetry packet
        packet = telemetry_aggregator.create_telemetry_packet()
        
        # Validate packet structure
        assert packet["device_id"] == "pi-drone-01"
        assert packet["gps"] is None
        assert packet["imu"] is None
        assert "battery" in packet
        assert "camera" in packet
    
    def test_battery_estimation(self, telemetry_aggregator):
        """Test battery estimation over time."""
        # Get initial battery level
        initial_voltage, initial_percentage = telemetry_aggregator.estimate_battery()
        
        # Simulate time passing
        with patch('time.time') as mock_time:
            mock_time.return_value = time.time() + 3600  # 1 hour later
            
            # Get battery level after time
            later_voltage, later_percentage = telemetry_aggregator.estimate_battery()
            
            # Battery should have discharged
            assert later_voltage < initial_voltage
            assert later_percentage < initial_percentage
            assert later_percentage >= 0  # Should not go below 0%
    
    def test_camera_status(self, telemetry_aggregator):
        """Test camera status reporting."""
        status = telemetry_aggregator.get_camera_status()
        
        assert "available" in status
        assert "resolution" in status
        assert "fps" in status
        assert "recording" in status
        assert isinstance(status["available"], bool)
        assert isinstance(status["recording"], bool)
    
    @patch('telemetry_service.mqtt.Client')
    def test_mqtt_message_handling(self, mock_mqtt_client, telemetry_aggregator):
        """Test MQTT message handling."""
        # Mock MQTT client
        mock_client = Mock()
        telemetry_aggregator.mqtt_client = mock_client
        
        # Create test messages
        gps_message = {
            "device_id": "test-drone",
            "type": "GGA",
            "lat": 37.7749,
            "lon": -122.4194,
            "alt": 100.0
        }
        
        imu_message = {
            "ts": 1234567890.0,
            "accel": {"x_g": 0.1, "y_g": -0.2, "z_g": 1.0},
            "gyro": {"x_dps": 0.5, "y_dps": 0.3, "z_dps": 0.2},
            "est": {"pitch_deg": 1.2, "roll_deg": -0.8}
        }
        
        # Simulate GPS message
        msg = Mock()
        msg.topic = "drone/test-drone/gps"
        msg.payload = json.dumps(gps_message).encode('utf-8')
        telemetry_aggregator._on_mqtt_message(mock_client, None, msg)
        
        # Verify GPS data was stored
        assert telemetry_aggregator.latest_gps is not None
        assert telemetry_aggregator.latest_gps["lat"] == 37.7749
        
        # Simulate IMU message
        msg.topic = "drone/test-drone/imu"
        msg.payload = json.dumps(imu_message).encode('utf-8')
        telemetry_aggregator._on_mqtt_message(mock_client, None, msg)
        
        # Verify IMU data was stored
        assert telemetry_aggregator.latest_imu is not None
        assert telemetry_aggregator.latest_imu["est"]["pitch_deg"] == 1.2
    
    def test_dry_run_mode(self):
        """Test telemetry aggregator in dry-run mode."""
        aggregator = TelemetryAggregator(dry_run=True)
        aggregator.setup_logging("WARNING")
        
        # Should start with no sensor data
        assert aggregator.latest_gps is None
        assert aggregator.latest_imu is None
        
        # Simulate sensor data
        aggregator.simulate_sensor_data()
        
        # Should have simulated data
        assert aggregator.latest_gps is not None
        assert aggregator.latest_imu is not None
        assert aggregator.latest_gps["type"] == "GGA"
        assert "lat" in aggregator.latest_gps
        assert "est" in aggregator.latest_imu
    
    def test_telemetry_publishing(self, telemetry_aggregator):
        """Test telemetry packet publishing."""
        # Mock MQTT client
        mock_client = Mock()
        mock_result = Mock()
        mock_result.wait_for_publish.return_value = None
        mock_client.publish.return_value = mock_result
        telemetry_aggregator.mqtt_client = mock_client
        
        # Create test packet
        packet = {
            "device_id": "test-drone",
            "timestamp": 1234567890.0,
            "battery": {"voltage": 12.4, "percentage": 85.0},
            "gps": {"lat": 37.7749, "lon": -122.4194},
            "imu": {"pitch_deg": 1.2, "roll_deg": -0.8}
        }
        
        # Publish packet
        telemetry_aggregator.publish_telemetry(packet)
        
        # Verify MQTT publish was called
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        
        # Check topic and payload
        assert "drone/pi-drone-01/telemetry" in call_args[0][0]
        published_packet = json.loads(call_args[0][1])
        assert published_packet["device_id"] == "test-drone"
        assert published_packet["battery"]["percentage"] == 85.0


class TestPerformanceAndReliability:
    """Test performance and reliability aspects."""
    
    def test_telemetry_rate_limiting(self):
        """Test telemetry rate limiting."""
        aggregator = TelemetryAggregator(dry_run=True)
        aggregator.setup_logging("WARNING")
        
        # Set up sensor data
        aggregator.simulate_sensor_data()
        
        # Create multiple packets quickly
        packets = []
        for _ in range(10):
            packet = aggregator.create_telemetry_packet()
            packets.append(packet)
            time.sleep(0.01)  # Small delay
        
        # All packets should have valid timestamps
        timestamps = [p["timestamp"] for p in packets]
        assert len(set(timestamps)) == len(timestamps)  # All unique
    
    def test_error_recovery(self, telemetry_aggregator):
        """Test error recovery mechanisms."""
        # Test with invalid sensor data
        telemetry_aggregator.latest_gps = {"invalid": "data"}
        telemetry_aggregator.latest_imu = None
        
        # Should not crash
        packet = telemetry_aggregator.create_telemetry_packet()
        assert packet is not None
        assert packet["gps"] is None  # Should handle invalid data gracefully
    
    def test_memory_usage(self):
        """Test memory usage with large number of packets."""
        aggregator = TelemetryAggregator(dry_run=True)
        aggregator.setup_logging("WARNING")
        
        # Create many packets
        for _ in range(1000):
            aggregator.simulate_sensor_data()
            packet = aggregator.create_telemetry_packet()
            aggregator.log_writer.write_packet(packet)
        
        # Should not exceed buffer limits
        assert len(aggregator.log_writer.packet_buffer) <= 500  # MAX_LOG_PACKETS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
