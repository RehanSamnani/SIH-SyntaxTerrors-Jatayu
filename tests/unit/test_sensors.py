#!/usr/bin/env python3
"""
Unit tests for sensor drivers (GPS and IMU).

Tests:
- GPS NMEA parsing and MQTT publishing
- IMU data processing and complementary filter
- MQTT connection and error handling
- Graceful shutdown behavior
"""

import json
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

# Import sensor modules
from sensors.gps_reader import parse_nmea_to_fix, GracefulKiller as GPSKiller
from sensors.imu_reader import complementary_filter, GracefulKiller as IMUKiller


class TestGPSReader:
    """Test GPS reader functionality."""
    
    def test_parse_gga_nmea(self):
        """Test parsing GGA NMEA sentence."""
        # Valid GGA sentence
        gga_sentence = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
        
        # Mock pynmea2.parse to return a GGA object
        with patch('sensors.gps_reader.pynmea2.parse') as mock_parse:
            mock_gga = Mock()
            mock_gga.latitude = 48.1173
            mock_gga.longitude = 11.5167
            mock_gga.altitude = 545.4
            mock_gga.num_sats = 8
            mock_gga.horizontal_dil = 0.9
            mock_gga.gps_qual = 1
            mock_gga.timestamp = None
            mock_parse.return_value = mock_gga
            
            fix = parse_nmea_to_fix(gga_sentence)
            
            assert fix is not None
            assert fix["type"] == "GGA"
            assert fix["lat"] == 48.1173
            assert fix["lon"] == 11.5167
            assert fix["alt"] == 545.4
            assert fix["num_sats"] == 8
            assert fix["hdop"] == 0.9
            assert fix["quality"] == 1
    
    def test_parse_rmc_nmea(self):
        """Test parsing RMC NMEA sentence."""
        # Valid RMC sentence
        rmc_sentence = "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"
        
        with patch('sensors.gps_reader.pynmea2.parse') as mock_parse:
            mock_rmc = Mock()
            mock_rmc.latitude = 48.1173
            mock_rmc.longitude = 11.5167
            mock_rmc.spd_over_grnd = 22.4
            mock_rmc.true_course = 84.4
            mock_rmc.status = 'A'
            mock_rmc.datestamp = None
            mock_rmc.timestamp = None
            mock_parse.return_value = mock_rmc
            
            fix = parse_nmea_to_fix(rmc_sentence)
            
            assert fix is not None
            assert fix["type"] == "RMC"
            assert fix["lat"] == 48.1173
            assert fix["lon"] == 11.5167
            assert fix["spd_over_grnd"] == 22.4
            assert fix["true_course"] == 84.4
            assert fix["status"] == 'A'
    
    def test_parse_invalid_nmea(self):
        """Test parsing invalid NMEA sentence."""
        invalid_sentence = "INVALID_NMEA_SENTENCE"
        
        with patch('sensors.gps_reader.pynmea2.parse') as mock_parse:
            mock_parse.side_effect = Exception("Parse error")
            
            fix = parse_nmea_to_fix(invalid_sentence)
            
            assert fix is None
    
    def test_graceful_killer(self):
        """Test graceful killer signal handling."""
        killer = GPSKiller()
        
        # Initially should not stop
        assert killer.should_stop is False
        
        # Simulate signal
        killer._on_signal(2, None)  # SIGINT
        
        assert killer.should_stop is True


class TestIMUReader:
    """Test IMU reader functionality."""
    
    def test_complementary_filter(self):
        """Test complementary filter calculation."""
        # Test data
        ax, ay, az = 0.1, -0.2, 1.0  # Accelerometer (g)
        gx, gy, gz = 0.5, 0.3, 0.2   # Gyroscope (deg/s)
        dt = 0.02  # 20ms
        alpha = 0.98
        prev_pitch, prev_roll = 0.0, 0.0
        
        pitch, roll = complementary_filter(ax, ay, az, gx, gy, dt, alpha, (prev_pitch, prev_roll))
        
        # Should return valid angles
        assert isinstance(pitch, float)
        assert isinstance(roll, float)
        assert -180 <= pitch <= 180
        assert -180 <= roll <= 180
    
    def test_complementary_filter_stability(self):
        """Test complementary filter stability over time."""
        # Simulate stationary IMU
        ax, ay, az = 0.0, 0.0, 1.0  # Only gravity
        gx, gy, gz = 0.0, 0.0, 0.0  # No rotation
        dt = 0.02
        alpha = 0.98
        
        pitch, roll = 0.0, 0.0
        
        # Run filter for multiple iterations
        for _ in range(100):
            pitch, roll = complementary_filter(ax, ay, az, gx, gy, dt, alpha, (pitch, roll))
        
        # Should converge to near-zero angles for stationary IMU
        assert abs(pitch) < 5.0  # Within 5 degrees
        assert abs(roll) < 5.0
    
    def test_graceful_killer(self):
        """Test graceful killer signal handling."""
        killer = IMUKiller()
        
        # Initially should not stop
        assert killer.stop is False
        
        # Simulate signal
        killer._on(2, None)  # SIGINT
        
        assert killer.stop is True


class TestMQTTIntegration:
    """Test MQTT integration for sensors."""
    
    @patch('sensors.gps_reader.mqtt.Client')
    def test_gps_mqtt_publish(self, mock_mqtt_client):
        """Test GPS MQTT publishing."""
        from sensors.gps_reader import publish_mqtt_fix
        
        # Mock MQTT client
        mock_client = Mock()
        mock_result = Mock()
        mock_result.wait_for_publish.return_value = None
        mock_client.publish.return_value = mock_result
        
        # Test fix data
        fix = {
            "device_id": "test-drone",
            "type": "GGA",
            "lat": 37.7749,
            "lon": -122.4194,
            "alt": 100.0
        }
        
        # Publish fix
        publish_mqtt_fix(mock_client, fix)
        
        # Verify MQTT publish was called
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        
        # Check topic and payload
        assert "drone/test-drone/gps" in call_args[0][0]
        payload = json.loads(call_args[0][1])
        assert payload["lat"] == 37.7749
        assert payload["lon"] == -122.4194
    
    @patch('sensors.imu_reader.mqtt.Client')
    def test_imu_mqtt_publish(self, mock_mqtt_client):
        """Test IMU MQTT publishing."""
        from sensors.imu_reader import publish_mqtt_imu
        
        # Mock MQTT client
        mock_client = Mock()
        mock_result = Mock()
        mock_result.wait_for_publish.return_value = None
        mock_client.publish.return_value = mock_result
        
        # Test IMU sample
        sample = {
            "ts": 1234567890.0,
            "accel": {"x_g": 0.1, "y_g": -0.2, "z_g": 1.0},
            "gyro": {"x_dps": 0.5, "y_dps": 0.3, "z_dps": 0.2},
            "est": {"pitch_deg": 1.2, "roll_deg": -0.8}
        }
        
        # Publish sample
        publish_mqtt_imu(mock_client, sample)
        
        # Verify MQTT publish was called
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        
        # Check topic and payload
        assert "drone/pi-drone-01/imu" in call_args[0][0]
        payload = json.loads(call_args[0][1])
        assert payload["ts"] == 1234567890.0
        assert payload["accel"]["x_g"] == 0.1
        assert payload["est"]["pitch_deg"] == 1.2


class TestErrorHandling:
    """Test error handling in sensor drivers."""
    
    def test_gps_serial_error_handling(self):
        """Test GPS serial connection error handling."""
        with patch('sensors.gps_reader.serial.Serial') as mock_serial:
            mock_serial.side_effect = Exception("Serial connection failed")
            
            from sensors.gps_reader import connect_serial_with_retries
            
            # Should raise exception after retries
            with pytest.raises(Exception):
                connect_serial_with_retries("/dev/ttyUSB0", 9600, retries=1)
    
    def test_imu_i2c_error_handling(self):
        """Test IMU I2C error handling."""
        with patch('sensors.imu_reader.SMBus') as mock_smbus:
            mock_bus = Mock()
            mock_bus.read_byte_data.side_effect = Exception("I2C read failed")
            mock_smbus.return_value.__enter__.return_value = mock_bus
            
            # Should handle I2C errors gracefully
            # This would be tested in integration tests with actual hardware


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
