#!/usr/bin/env python3
"""
Unit tests for mission runner functionality.

Tests:
- Mission JSON parsing and validation
- State machine transitions
- Waypoint navigation logic
- Obstacle handling
- Delivery simulation
- MQTT message handling
"""

import json
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.append(str(Path(__file__).parent.parent / "src"))

from mission_runner import (
    MissionRunner, Mission, Waypoint, MissionState, MissionStatus,
    GracefulKiller
)


class TestWaypoint:
    """Test Waypoint dataclass."""
    
    def test_waypoint_creation(self):
        """Test waypoint creation with all parameters."""
        wp = Waypoint(
            lat=37.7749,
            lon=-122.4194,
            alt=50.0,
            hold_seconds=10.0,
            action="deliver",
            metadata={"name": "test"}
        )
        
        assert wp.lat == 37.7749
        assert wp.lon == -122.4194
        assert wp.alt == 50.0
        assert wp.hold_seconds == 10.0
        assert wp.action == "deliver"
        assert wp.metadata == {"name": "test"}
    
    def test_waypoint_defaults(self):
        """Test waypoint creation with default values."""
        wp = Waypoint(lat=37.7749, lon=-122.4194, alt=50.0)
        
        assert wp.hold_seconds == 0.0
        assert wp.action == "none"
        assert wp.metadata == {}


class TestMission:
    """Test Mission dataclass."""
    
    def test_mission_creation(self):
        """Test mission creation with waypoints."""
        waypoints = [
            Waypoint(lat=37.7749, lon=-122.4194, alt=0.0),
            Waypoint(lat=37.7750, lon=-122.4195, alt=50.0)
        ]
        
        mission = Mission(
            mission_id="test_001",
            name="Test Mission",
            waypoints=waypoints,
            payload_metadata={"type": "test"},
            max_speed=5.0,
            default_altitude=50.0
        )
        
        assert mission.mission_id == "test_001"
        assert mission.name == "Test Mission"
        assert len(mission.waypoints) == 2
        assert mission.max_speed == 5.0
        assert mission.default_altitude == 50.0
        assert mission.payload_metadata == {"type": "test"}
    
    def test_mission_defaults(self):
        """Test mission creation with default values."""
        waypoints = [Waypoint(lat=37.7749, lon=-122.4194, alt=50.0)]
        
        mission = Mission(
            mission_id="test_002",
            name="Test Mission 2",
            waypoints=waypoints
        )
        
        assert mission.payload_metadata == {}
        assert mission.max_speed == 5.0
        assert mission.default_altitude == 50.0


class TestMissionRunner:
    """Test MissionRunner class."""
    
    @pytest.fixture
    def sample_mission_data(self):
        """Sample mission data for testing."""
        return {
            "mission_id": "test_mission_001",
            "name": "Test Mission",
            "default_altitude": 50.0,
            "max_speed": 5.0,
            "payload_metadata": {"type": "test"},
            "waypoints": [
                {
                    "lat": 37.7749,
                    "lon": -122.4194,
                    "alt": 0.0,
                    "hold_seconds": 0.0,
                    "action": "none"
                },
                {
                    "lat": 37.7750,
                    "lon": -122.4195,
                    "alt": 50.0,
                    "hold_seconds": 5.0,
                    "action": "deliver"
                },
                {
                    "lat": 37.7749,
                    "lon": -122.4194,
                    "alt": 0.0,
                    "hold_seconds": 0.0,
                    "action": "land"
                }
            ]
        }
    
    @pytest.fixture
    def mission_runner(self):
        """Create a mission runner instance for testing."""
        runner = MissionRunner(dry_run=True)
        runner.setup_logging("WARNING")  # Reduce log noise during tests
        return runner
    
    def test_mission_runner_initialization(self, mission_runner):
        """Test mission runner initialization."""
        assert mission_runner.dry_run is True
        assert mission_runner.state == MissionState.IDLE
        assert mission_runner.current_mission is None
        assert mission_runner.current_waypoint_index == 0
        assert mission_runner.speed == 5.0  # DEFAULT_SPEED
    
    def test_load_mission(self, mission_runner, sample_mission_data):
        """Test mission loading from JSON data."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_mission_data, f)
            temp_path = Path(f.name)
        
        try:
            mission = mission_runner.load_mission(temp_path)
            
            assert mission.mission_id == "test_mission_001"
            assert mission.name == "Test Mission"
            assert len(mission.waypoints) == 3
            assert mission.max_speed == 5.0
            assert mission.default_altitude == 50.0
            
            # Check first waypoint
            wp1 = mission.waypoints[0]
            assert wp1.lat == 37.7749
            assert wp1.lon == -122.4194
            assert wp1.alt == 0.0
            assert wp1.action == "none"
            
            # Check second waypoint
            wp2 = mission.waypoints[1]
            assert wp2.lat == 37.7750
            assert wp2.lon == -122.4195
            assert wp2.alt == 50.0
            assert wp2.hold_seconds == 5.0
            assert wp2.action == "deliver"
            
        finally:
            temp_path.unlink()
    
    def test_load_mission_missing_file(self, mission_runner):
        """Test mission loading with missing file."""
        with pytest.raises(Exception):
            mission_runner.load_mission(Path("nonexistent.json"))
    
    def test_load_mission_invalid_json(self, mission_runner):
        """Test mission loading with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(Exception):
                mission_runner.load_mission(temp_path)
        finally:
            temp_path.unlink()
    
    def test_calculate_distance(self, mission_runner):
        """Test distance calculation between positions."""
        pos1 = (37.7749, -122.4194, 0.0)
        pos2 = (37.7750, -122.4195, 50.0)
        
        distance = mission_runner._calculate_distance(pos1, pos2)
        
        # Should be approximately 111 meters (rough calculation)
        assert distance > 100
        assert distance < 150
    
    def test_interpolate_position(self, mission_runner):
        """Test position interpolation."""
        start = (37.7749, -122.4194, 0.0)
        end = (37.7750, -122.4195, 50.0)
        
        # Test 0% progress
        pos_0 = mission_runner._interpolate_position(start, end, 0.0)
        assert pos_0 == start
        
        # Test 100% progress
        pos_1 = mission_runner._interpolate_position(start, end, 1.0)
        assert pos_1 == end
        
        # Test 50% progress
        pos_05 = mission_runner._interpolate_position(start, end, 0.5)
        assert pos_05[0] == (start[0] + end[0]) / 2
        assert pos_05[1] == (start[1] + end[1]) / 2
        assert pos_05[2] == (start[2] + end[2]) / 2
    
    def test_start_mission(self, mission_runner, sample_mission_data):
        """Test mission start functionality."""
        # Create mission
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_mission_data, f)
            temp_path = Path(f.name)
        
        try:
            mission = mission_runner.load_mission(temp_path)
            mission_runner.current_mission = mission
            
            # Start mission
            mission_runner._start_mission()
            
            assert mission_runner.state == MissionState.TAKEOFF
            assert mission_runner.current_waypoint_index == 0
            assert mission_runner.mission_start_time > 0
            assert mission_runner.speed == 5.0
            
            # Check initial position
            expected_pos = (37.7749, -122.4194, 0.0)
            assert mission_runner.current_position == expected_pos
            
        finally:
            temp_path.unlink()
    
    def test_pause_resume_mission(self, mission_runner, sample_mission_data):
        """Test mission pause and resume functionality."""
        # Create and start mission
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_mission_data, f)
            temp_path = Path(f.name)
        
        try:
            mission = mission_runner.load_mission(temp_path)
            mission_runner.current_mission = mission
            mission_runner._start_mission()
            
            # Set to ENROUTE state
            mission_runner.state = MissionState.ENROUTE
            
            # Pause mission
            mission_runner._pause_mission()
            assert mission_runner.state == MissionState.PAUSED
            
            # Resume mission
            mission_runner._resume_mission()
            assert mission_runner.state == MissionState.ENROUTE
            
        finally:
            temp_path.unlink()
    
    def test_abort_mission(self, mission_runner, sample_mission_data):
        """Test mission abort functionality."""
        # Create and start mission
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_mission_data, f)
            temp_path = Path(f.name)
        
        try:
            mission = mission_runner.load_mission(temp_path)
            mission_runner.current_mission = mission
            mission_runner._start_mission()
            
            # Abort mission
            mission_runner._abort_mission()
            assert mission_runner.state == MissionState.ERROR
            assert mission_runner.mission_status.error_message == "Mission aborted by command"
            
        finally:
            temp_path.unlink()
    
    def test_advance_to_next_waypoint(self, mission_runner, sample_mission_data):
        """Test waypoint advancement logic."""
        # Create mission
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_mission_data, f)
            temp_path = Path(f.name)
        
        try:
            mission = mission_runner.load_mission(temp_path)
            mission_runner.current_mission = mission
            mission_runner.current_waypoint_index = 0
            
            # Advance to next waypoint
            mission_runner._advance_to_next_waypoint()
            assert mission_runner.current_waypoint_index == 1
            assert mission_runner.state == MissionState.ENROUTE
            
            # Advance to last waypoint
            mission_runner.current_waypoint_index = 2
            mission_runner._advance_to_next_waypoint()
            assert mission_runner.current_waypoint_index == 3  # Beyond waypoints
            assert mission_runner.state == MissionState.RETURN
            
        finally:
            temp_path.unlink()
    
    def test_execute_delivery_action(self, mission_runner):
        """Test delivery action execution."""
        waypoint = Waypoint(
            lat=37.7750,
            lon=-122.4195,
            alt=50.0,
            action="deliver",
            metadata={"drop_zone_id": "test_zone"}
        )
        
        # Mock MQTT client
        mission_runner.mqtt_client = Mock()
        mission_runner.current_mission = Mock()
        mission_runner.current_mission.mission_id = "test_001"
        mission_runner.current_mission.payload_metadata = {"type": "test"}
        mission_runner.current_waypoint_index = 1
        
        # Execute delivery
        mission_runner._execute_delivery_action(waypoint)
        
        # Verify servo command was published
        mission_runner.mqtt_client.publish.assert_called_once()
        call_args = mission_runner.mqtt_client.publish.call_args
        assert call_args[0][0] == "drone/pi-drone-01/servo/command"
        
        # Verify command content
        command_data = json.loads(call_args[0][1])
        assert command_data["command"] == "release"
        assert command_data["waypoint"] == 1
    
    def test_execute_photo_action(self, mission_runner):
        """Test photo action execution."""
        waypoint = Waypoint(
            lat=37.7750,
            lon=-122.4195,
            alt=50.0,
            action="photo",
            metadata={"photo_count": 5}
        )
        
        mission_runner.current_position = (37.7750, -122.4195, 50.0)
        mission_runner.current_mission = Mock()
        mission_runner.current_mission.mission_id = "test_001"
        mission_runner.current_waypoint_index = 1
        
        # Execute photo action (should not raise exception)
        mission_runner._execute_delivery_action(waypoint)
    
    @patch('mission_runner.mqtt.Client')
    def test_handle_mission_command(self, mock_mqtt_client, mission_runner):
        """Test MQTT mission command handling."""
        # Mock MQTT client
        mission_runner.mqtt_client = Mock()
        
        # Test start command
        start_command = {
            "type": "start",
            "mission_id": "test_mission"
        }
        
        with patch.object(mission_runner, '_load_and_start_mission') as mock_load:
            mission_runner._handle_mission_command(start_command)
            mock_load.assert_called_once_with("test_mission")
        
        # Test pause command
        mission_runner.state = MissionState.ENROUTE
        pause_command = {"type": "pause"}
        
        with patch.object(mission_runner, '_pause_mission') as mock_pause:
            mission_runner._handle_mission_command(pause_command)
            mock_pause.assert_called_once()
        
        # Test resume command
        mission_runner.state = MissionState.PAUSED
        resume_command = {"type": "resume"}
        
        with patch.object(mission_runner, '_resume_mission') as mock_resume:
            mission_runner._handle_mission_command(resume_command)
            mock_resume.assert_called_once()
        
        # Test abort command
        abort_command = {"type": "abort"}
        
        with patch.object(mission_runner, '_abort_mission') as mock_abort:
            mission_runner._handle_mission_command(abort_command)
            mock_abort.assert_called_once()
    
    def test_handle_obstacle_detection(self, mission_runner):
        """Test obstacle detection handling."""
        # Set up mission in ENROUTE state
        mission_runner.state = MissionState.ENROUTE
        mission_runner.current_position = (37.7750, -122.4195, 50.0)
        
        # High confidence obstacle
        obstacle_data = {
            "type": "building",
            "confidence": 0.9,
            "lat": 37.7751,
            "lon": -122.4196,
            "alt": 50.0
        }
        
        mission_runner._handle_obstacle_detection(obstacle_data)
        
        assert mission_runner.obstacle_detected is True
        assert mission_runner.obstacle_position == (37.7751, -122.4196, 50.0)
        assert mission_runner.state == MissionState.PAUSED
        
        # Low confidence obstacle (should not trigger)
        mission_runner.state = MissionState.ENROUTE
        mission_runner.obstacle_detected = False
        
        low_confidence_obstacle = {
            "type": "bird",
            "confidence": 0.3
        }
        
        mission_runner._handle_obstacle_detection(low_confidence_obstacle)
        
        assert mission_runner.obstacle_detected is False
        assert mission_runner.state == MissionState.ENROUTE
    
    def test_publish_mission_status(self, mission_runner, sample_mission_data):
        """Test mission status publishing."""
        # Create mission
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_mission_data, f)
            temp_path = Path(f.name)
        
        try:
            mission = mission_runner.load_mission(temp_path)
            mission_runner.current_mission = mission
            mission_runner.state = MissionState.ENROUTE
            mission_runner.current_waypoint_index = 1
            mission_runner.current_position = (37.7750, -122.4195, 50.0)
            mission_runner.target_position = (37.7750, -122.4195, 50.0)
            mission_runner.speed = 5.0
            mission_runner.mission_start_time = time.time()
            
            # Mock MQTT client
            mission_runner.mqtt_client = Mock()
            
            # Publish status
            mission_runner._publish_mission_status()
            
            # Verify MQTT publish was called
            mission_runner.mqtt_client.publish.assert_called_once()
            call_args = mission_runner.mqtt_client.publish.call_args
            assert call_args[0][0] == "drone/pi-drone-01/mission/status"
            
            # Verify status content
            status_data = json.loads(call_args[0][1])
            assert status_data["mission_id"] == "test_mission_001"
            assert status_data["state"] == "ENROUTE"
            assert status_data["current_waypoint"] == 1
            assert status_data["total_waypoints"] == 3
            assert "progress_percent" in status_data
            assert "estimated_time_remaining" in status_data
            
        finally:
            temp_path.unlink()
    
    def test_publish_simulated_telemetry(self, mission_runner):
        """Test simulated telemetry publishing."""
        mission_runner.current_position = (37.7750, -122.4195, 50.0)
        mission_runner.current_mission = Mock()
        mission_runner.current_mission.mission_id = "test_001"
        mission_runner.state = MissionState.ENROUTE
        mission_runner.current_waypoint_index = 1
        mission_runner.mission_status = Mock()
        mission_runner.mission_status.progress_percent = 33.3
        
        # Mock MQTT client
        mission_runner.mqtt_client = Mock()
        
        # Publish telemetry
        mission_runner._publish_simulated_telemetry()
        
        # Verify MQTT publish was called
        mission_runner.mqtt_client.publish.assert_called_once()
        call_args = mission_runner.mqtt_client.publish.call_args
        assert call_args[0][0] == "drone/pi-drone-01/telemetry"
        
        # Verify telemetry content
        telemetry_data = json.loads(call_args[0][1])
        assert telemetry_data["device_id"] == "pi-drone-01"
        assert telemetry_data["gps"]["lat"] == 37.7750
        assert telemetry_data["gps"]["lon"] == -122.4195
        assert telemetry_data["gps"]["alt"] == 50.0
        assert telemetry_data["mission"]["mission_id"] == "test_001"
        assert telemetry_data["mission"]["state"] == "ENROUTE"
        assert telemetry_data["mission"]["waypoint"] == 1


class TestGracefulKiller:
    """Test GracefulKiller class."""
    
    def test_graceful_killer_initialization(self):
        """Test graceful killer initialization."""
        killer = GracefulKiller()
        assert killer.should_stop is False
    
    def test_graceful_killer_signal_handling(self):
        """Test graceful killer signal handling."""
        killer = GracefulKiller()
        
        # Simulate signal
        killer._on_signal(signal.SIGINT, None)
        assert killer.should_stop is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
