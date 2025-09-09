# Phase 3 Quick Start Guide

This guide provides step-by-step instructions to quickly set up and test the mission runner system.

## Prerequisites

- Phase 2 telemetry system running
- MQTT broker operational
- Python virtual environment activated
- Project dependencies installed

## Quick Setup (5 minutes)

### 1. Test Mission Runner (Dry-Run Mode)
```bash
# Run mission runner with default mission
python src/mission_runner.py --dry-run --log-level INFO
```

### 2. Test with Specific Mission
```bash
# Run disaster relief mission
python src/mission_runner.py --mission data/sample_missions/sample_mission.json --dry-run

# Run survey mission
python src/mission_runner.py --mission data/sample_missions/survey_mission.json --dry-run

# Run emergency mission
python src/mission_runner.py --mission data/sample_missions/emergency_mission.json --dry-run
```

### 3. Monitor Mission Status (In Another Terminal)
```bash
# Monitor mission status
mosquitto_sub -h localhost -p 1883 -t "drone/+/mission/status"

# Monitor telemetry
mosquitto_sub -h localhost -p 1883 -t "drone/+/telemetry"

# Monitor servo commands
mosquitto_sub -h localhost -p 1883 -t "drone/+/servo/command"
```

## Expected Output

### Mission Runner Console Output
```
2023-12-21 10:30:00 [INFO] Starting mission runner (device_id=pi-drone-01, dry_run=True)
2023-12-21 10:30:00 [INFO] Loaded mission: Disaster Relief Supply Drop (10 waypoints)
2023-12-21 10:30:01 [INFO] State changed: IDLE → TAKEOFF
2023-12-21 10:30:06 [INFO] State changed: TAKEOFF → ENROUTE
2023-12-21 10:30:11 [INFO] State changed: ENROUTE → HOLD
2023-12-21 10:30:16 [INFO] State changed: HOLD → DELIVERY
2023-12-21 10:30:16 [INFO] Payload delivery executed at waypoint 3
2023-12-21 10:30:16 [INFO] State changed: DELIVERY → ENROUTE
```

### Mission Status Messages
```json
{
  "mission_id": "disaster_relief_001",
  "state": "ENROUTE",
  "current_waypoint": 3,
  "total_waypoints": 10,
  "progress_percent": 30.0,
  "estimated_time_remaining": 120.5,
  "current_position": [37.7800, -122.4200, 50.0],
  "target_position": [37.7850, -122.4250, 50.0],
  "speed": 5.0,
  "timestamp": 1703123456.789
}
```

### Telemetry Messages
```json
{
  "device_id": "pi-drone-01",
  "timestamp": 1703123456.789,
  "gps": {
    "lat": 37.7800,
    "lon": -122.4200,
    "alt": 50.0
  },
  "mission": {
    "mission_id": "disaster_relief_001",
    "state": "ENROUTE",
    "waypoint": 3,
    "progress_percent": 30.0
  }
}
```

## Mission Control Testing

### 1. Start Mission via MQTT
```bash
# Start disaster relief mission
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
  -m '{"type": "start", "mission_id": "disaster_relief_001"}'
```

### 2. Test Pause/Resume
```bash
# Pause mission
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
  -m '{"type": "pause"}'

# Resume mission
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
  -m '{"type": "resume"}'
```

### 3. Test Abort
```bash
# Abort mission
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
  -m '{"type": "abort"}'
```

## Obstacle Handling Testing

### 1. Simulate Obstacle Detection
```bash
# Send obstacle detection event
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/obstacles" \
  -m '{"type": "building", "confidence": 0.9, "lat": 37.7751, "lon": -122.4196, "alt": 50.0}'
```

### 2. Verify Mission Pause
```bash
# Check mission status (should show PAUSED state)
mosquitto_sub -h localhost -p 1883 -t "drone/+/mission/status" -C 1
```

### 3. Resume After Obstacle
```bash
# Resume mission
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
  -m '{"type": "resume"}'
```

## Delivery Testing

### 1. Monitor Delivery Commands
```bash
# Watch for servo commands during mission
mosquitto_sub -h localhost -p 1883 -t "drone/+/servo/command"
```

### 2. Expected Delivery Command
```json
{
  "device_id": "pi-drone-01",
  "timestamp": 1703123456.789,
  "command": "release",
  "waypoint": 3,
  "payload_metadata": {
    "type": "emergency_supplies",
    "weight_kg": 2.5,
    "contents": ["water", "food", "medical_supplies"]
  }
}
```

## Custom Mission Testing

### 1. Create Custom Mission
```bash
# Create simple test mission
cat > data/sample_missions/test_mission.json << 'EOF'
{
  "mission_id": "test_mission_001",
  "name": "Test Mission",
  "default_altitude": 30.0,
  "max_speed": 3.0,
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
      "alt": 30.0,
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
EOF
```

### 2. Run Custom Mission
```bash
# Run custom mission
python src/mission_runner.py --mission data/sample_missions/test_mission.json --dry-run
```

## Integration Testing

### 1. Test with Telemetry Service
```bash
# Terminal 1: Start telemetry service
python src/telemetry_service.py --dry-run

# Terminal 2: Start mission runner
python src/mission_runner.py --mission data/sample_missions/sample_mission.json

# Terminal 3: Monitor both
mosquitto_sub -h localhost -p 1883 -t "drone/+/telemetry" -t "drone/+/mission/status"
```

### 2. Test Full Integration
```bash
# Terminal 1: GPS reader
python src/sensors/gps_reader.py &

# Terminal 2: IMU reader
python src/sensors/imu_reader.py &

# Terminal 3: Telemetry service
python src/telemetry_service.py &

# Terminal 4: Mission runner
python src/mission_runner.py --mission data/sample_missions/sample_mission.json
```

## Validation Tests

### Automated Testing
```bash
# Run unit tests
python -m pytest tests/test_mission_runner.py -v

# Run specific test
python -m pytest tests/test_mission_runner.py::TestMissionRunner::test_load_mission -v

# Run with coverage
python -m pytest tests/test_mission_runner.py --cov=src/mission_runner --cov-report=html
```

### Manual Validation
1. **Mission Loading**: Verify mission JSON loads correctly
2. **State Transitions**: Check state machine transitions
3. **Waypoint Navigation**: Verify position interpolation
4. **Obstacle Handling**: Test pause/resume on obstacle
5. **Delivery Commands**: Verify servo commands published
6. **MQTT Integration**: Check all topics and message formats

## Troubleshooting

### Mission Not Loading
```bash
# Check mission file exists
ls -la data/sample_missions/

# Validate JSON syntax
python -c "import json; json.load(open('data/sample_missions/sample_mission.json'))"

# Check file permissions
chmod 644 data/sample_missions/*.json
```

### MQTT Connection Issues
```bash
# Check MQTT broker
sudo systemctl status mosquitto

# Test MQTT connectivity
mosquitto_pub -h localhost -p 1883 -t "test" -m "test"

# Check MQTT logs
sudo journalctl -u mosquitto -f
```

### State Machine Issues
```bash
# Check mission runner logs
tail -f /home/pi/drone/logs/mission_runner.log

# Run with debug logging
python src/mission_runner.py --log-level DEBUG

# Monitor state transitions
mosquitto_sub -h localhost -p 1883 -t "drone/+/mission/status" | jq '.state'
```

### Obstacle Handling Problems
```bash
# Test obstacle message format
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/obstacles" \
  -m '{"type": "test", "confidence": 0.9, "lat": 37.7751, "lon": -122.4196, "alt": 50.0}'

# Check obstacle handling
mosquitto_sub -h localhost -p 1883 -t "drone/+/mission/status" -C 1 | jq '.state'
```

## Performance Testing

### Speed Testing
```bash
# Test different speeds
python src/mission_runner.py --speed 1.0 --dry-run  # Very slow
python src/mission_runner.py --speed 5.0 --dry-run  # Normal
python src/mission_runner.py --speed 10.0 --dry-run # Fast
```

### Long Mission Testing
```bash
# Test with survey mission (longer)
python src/mission_runner.py --mission data/sample_missions/survey_mission.json --dry-run
```

## Next Steps

Once Phase 3 is working correctly:

1. **Phase 4**: Integrate vision system for obstacle detection
2. **Phase 5**: Connect to Supabase backend for mission management
3. **Real Hardware**: Test with actual drone hardware
4. **Mission Planning**: Create GUI for mission design

## Support

- **Documentation**: See `docs/phase3_mission_runner.md` for detailed information
- **Logs**: Check mission runner logs for error details
- **Testing**: Use provided test scripts for validation
- **Debugging**: Run with `--log-level DEBUG` for verbose output
