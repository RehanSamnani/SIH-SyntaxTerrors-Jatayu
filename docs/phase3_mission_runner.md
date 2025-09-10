# Phase 3 — Mission Runner (Simulator-First)

This document describes the implementation of the mission runner system for the AI-enabled drone companion prototype. The mission runner provides waypoint navigation, state machine management, and obstacle handling in a simulator-first approach.

## Overview

The mission runner system:
- Loads mission definitions from JSON files
- Simulates waypoint navigation with configurable speed
- Implements reactive state machine for mission execution
- Handles obstacle detection with pause/resume logic
- Simulates payload delivery with servo commands
- Publishes mission status and simulated telemetry
- Logs mission states and events

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Mission JSON  │───▶│  Mission Runner │───▶│   MQTT Broker   │
│   (Waypoints)   │    │  (State Machine)│    │   (Commands)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │  Telemetry      │    │  Obstacle       │
                       │  Publishing     │    │  Detection      │
                       └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │  Servo Commands │    │  Pause/Resume   │
                       │  (Delivery)     │    │  Logic          │
                       └─────────────────┘    └─────────────────┘
```

## Components

### 1. Mission Runner (`src/mission_runner.py`)

**Features:**
- Mission JSON parsing and validation
- State machine implementation
- Waypoint interpolation and navigation
- Obstacle detection and handling
- Payload delivery simulation
- MQTT integration for commands and status
- Comprehensive logging and error handling

**Key Classes:**
- `MissionRunner`: Main mission execution engine
- `Mission`: Mission definition container
- `Waypoint`: Individual waypoint definition
- `MissionStatus`: Current mission state
- `MissionState`: Enumeration of mission states

### 2. Mission JSON Format

**Structure:**
```json
{
  "mission_id": "unique_mission_identifier",
  "name": "Human-readable mission name",
  "description": "Mission description",
  "default_altitude": 50.0,
  "max_speed": 5.0,
  "payload_metadata": {
    "type": "payload_type",
    "weight_kg": 2.5,
    "contents": ["item1", "item2"],
    "priority": "high"
  },
  "waypoints": [
    {
      "lat": 37.7749,
      "lon": -122.4194,
      "alt": 50.0,
      "hold_seconds": 10.0,
      "action": "deliver",
      "metadata": {
        "name": "Drop Zone Alpha",
        "description": "Emergency supply drop location"
      }
    }
  ]
}
```

**Waypoint Actions:**
- `none`: Standard navigation waypoint
- `deliver`: Execute payload delivery
- `photo`: Capture aerial photograph
- `land`: Landing waypoint

### 3. State Machine

**States:**
- `IDLE`: Mission not started
- `TAKEOFF`: Climbing to mission altitude
- `ENROUTE`: Navigating between waypoints
- `HOLD`: Holding at waypoint
- `DELIVERY`: Executing delivery action
- `RETURN`: Returning to launch point
- `LANDED`: Mission complete
- `ERROR`: Mission error state
- `PAUSED`: Mission paused (obstacle or command)

**State Transitions:**
```
IDLE → TAKEOFF → ENROUTE → HOLD → DELIVERY → ENROUTE → ... → RETURN → LANDED
  ↓       ↓         ↓       ↓        ↓
ERROR ← PAUSED ← PAUSED ← PAUSED ← PAUSED
```

### 4. Sample Missions

#### Disaster Relief Mission (`data/sample_missions/sample_mission.json`)
- **Purpose**: Deliver emergency supplies to multiple locations
- **Waypoints**: 10 waypoints with 3 delivery zones
- **Speed**: 5.0 m/s
- **Altitude**: 50.0 meters
- **Payload**: Emergency supplies (water, food, medical)

#### Aerial Survey Mission (`data/sample_missions/survey_mission.json`)
- **Purpose**: Photographic survey for damage assessment
- **Waypoints**: 13 waypoints with 5 photo capture points
- **Speed**: 3.0 m/s (slower for photo quality)
- **Altitude**: 75.0 meters
- **Payload**: High-resolution camera with gimbal

#### Emergency Response Mission (`data/sample_missions/emergency_mission.json`)
- **Purpose**: Rapid response with critical medical supplies
- **Waypoints**: 6 waypoints with direct route
- **Speed**: 8.0 m/s (high speed for emergency)
- **Altitude**: 30.0 meters
- **Payload**: Medical emergency kit

## MQTT Integration

### Topics

**Mission Commands:**
- `drone/<id>/mission/command` - Mission control commands
- `drone/<id>/mission/status` - Mission status updates
- `drone/<id>/obstacles` - Obstacle detection events
- `drone/<id>/servo/command` - Servo control commands
- `drone/<id>/telemetry` - Simulated telemetry data

### Command Messages

**Start Mission:**
```json
{
  "type": "start",
  "mission_id": "disaster_relief_001"
}
```

**Pause Mission:**
```json
{
  "type": "pause"
}
```

**Resume Mission:**
```json
{
  "type": "resume"
}
```

**Abort Mission:**
```json
{
  "type": "abort"
}
```

### Status Messages

**Mission Status:**
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
  "timestamp": 1703123456.789,
  "error_message": null
}
```

### Obstacle Messages

**Obstacle Detection:**
```json
{
  "type": "building",
  "confidence": 0.9,
  "lat": 37.7751,
  "lon": -122.4196,
  "alt": 50.0,
  "distance": 25.5,
  "timestamp": 1703123456.789
}
```

## Usage Examples

### Basic Mission Execution
```bash
# Run with default mission
python src/mission_runner.py

# Run with specific mission
python src/mission_runner.py --mission data/sample_missions/survey_mission.json

# Run with custom speed
python src/mission_runner.py --speed 3.0

# Run in dry-run mode (no MQTT)
python src/mission_runner.py --dry-run
```

### Mission Control via MQTT
```bash
# Start mission
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
  -m '{"type": "start", "mission_id": "disaster_relief_001"}'

# Pause mission
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
  -m '{"type": "pause"}'

# Resume mission
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
  -m '{"type": "resume"}'

# Abort mission
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
  -m '{"type": "abort"}'
```

### Monitor Mission Status
```bash
# Subscribe to mission status
mosquitto_sub -h localhost -p 1883 -t "drone/+/mission/status"

# Subscribe to telemetry
mosquitto_sub -h localhost -p 1883 -t "drone/+/telemetry"

# Subscribe to servo commands
mosquitto_sub -h localhost -p 1883 -t "drone/+/servo/command"
```

## Obstacle Handling

### Detection and Response
1. **Obstacle Detection**: Vision system publishes obstacle events to `drone/<id>/obstacles`
2. **Confidence Threshold**: Only obstacles with confidence > 0.7 trigger response
3. **Mission Pause**: Mission automatically pauses when obstacle detected
4. **Position Recording**: Obstacle position and original waypoint index stored
5. **Manual Resume**: Mission resumes when resume command received
6. **Obstacle Clearance**: Obstacle flag cleared on resume

### Phase 4 Integration

With Phase 4 obstacle detection implemented, the mission runner now receives real-time obstacle events from the TFLite detector:

#### Obstacle Event Format
```json
{
  "timestamp_ms": 1703123456789,
  "drone_id": "pi01",
  "event": "obstacle",
  "label": "person",
  "confidence": 0.85,
  "bbox": {"x": 100, "y": 120, "w": 80, "h": 160},
  "severity": "warning",
  "distance_m": 8.5
}
```

#### Response Thresholds
- **Confidence Threshold**: 0.7 (configurable)
- **Severity Levels**: 
  - `critical`: Distance < 5m
  - `warning`: Distance < 15m OR confidence ≥ 0.6
  - `info`: All other detections

#### Integration Flow
1. **Detector** publishes obstacle events to `drone/<id>/obstacles`
2. **Mission Runner** receives events and evaluates confidence
3. **State Transition** to PAUSED if obstacle is significant
4. **Recovery** when obstacle clears or confidence drops

#### Testing Integration
```bash
# Start mission runner
python src/mission_runner.py --dry-run

# Start obstacle detector
python src/vision/detector.py --drone_id pi01

# Monitor obstacle events
mosquitto_sub -h localhost -p 1883 -t "drone/+/obstacles" -v

# Monitor mission status
mosquitto_sub -h localhost -p 1883 -t "drone/+/mission/status" -v
```

### Obstacle Avoidance Strategies
- **Pause and Wait**: Simple pause until obstacle clears
- **Altitude Change**: Future enhancement - change altitude to avoid obstacle
- **Waypoint Insertion**: Future enhancement - insert temporary waypoint around obstacle
- **Route Recalculation**: Future enhancement - recalculate entire route

## Delivery Simulation

### Payload Delivery Process
1. **Waypoint Reached**: Mission runner reaches delivery waypoint
2. **Hold Period**: Holds at waypoint for specified duration
3. **Servo Command**: Publishes servo release command to MQTT
4. **Delivery Confirmation**: Logs delivery execution
5. **Next Waypoint**: Advances to next waypoint in mission

### Servo Commands
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

## Testing

### Unit Tests
```bash
# Run all tests
python -m pytest tests/test_mission_runner.py -v

# Run specific test
python -m pytest tests/test_mission_runner.py::TestMissionRunner::test_load_mission -v

# Run with coverage
python -m pytest tests/test_mission_runner.py --cov=src/mission_runner --cov-report=html
```

### Integration Testing
```bash
# Test mission loading
python src/mission_runner.py --mission data/sample_missions/sample_mission.json --dry-run

# Test with MQTT
python src/mission_runner.py --mission data/sample_missions/survey_mission.json

# Test obstacle handling
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/obstacles" \
  -m '{"type": "building", "confidence": 0.9, "lat": 37.7751, "lon": -122.4196, "alt": 50.0}'
```

## Configuration

### Environment Variables
```bash
# Device identification
DEVICE_ID=pi-drone-01

# MQTT configuration
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_USERNAME=drone
MQTT_PASSWORD=secure_password

# Mission defaults
MISSION_SPEED=5.0
MISSION_ALTITUDE=50.0
```

### Mission Parameters
- **Speed**: Configurable via `--speed` argument or mission JSON
- **Altitude**: Default altitude for waypoints without explicit altitude
- **Hold Times**: Configurable hold duration at each waypoint
- **Actions**: Customizable actions per waypoint

## Performance Considerations

### Simulation Accuracy
- **Position Interpolation**: Linear interpolation between waypoints
- **Speed Control**: Configurable speed with realistic acceleration
- **Timing**: Precise timing for hold periods and state transitions
- **Distance Calculation**: Simplified distance calculation (not accounting for Earth's curvature)

### Resource Usage
- **Memory**: Bounded by mission size (typically < 1MB)
- **CPU**: Low CPU usage for simulation
- **Network**: MQTT messages at 1-2 Hz
- **Storage**: Mission logs with rotation

## Security Features

### Mission Validation
- **JSON Schema**: Validates mission structure
- **Waypoint Bounds**: Checks for reasonable coordinates
- **Speed Limits**: Enforces maximum speed constraints
- **Altitude Limits**: Validates safe altitude ranges

### Command Authentication
- **MQTT Auth**: Username/password authentication
- **TLS Encryption**: Optional TLS for command channels
- **Command Validation**: Validates command structure and parameters

## Troubleshooting

### Common Issues

#### Mission Not Starting
```bash
# Check mission file exists
ls -la data/sample_missions/

# Validate mission JSON
python -c "import json; json.load(open('data/sample_missions/sample_mission.json'))"

# Check MQTT connection
mosquitto_pub -h localhost -p 1883 -t "test" -m "test"
```

#### State Machine Issues
```bash
# Check mission runner logs
tail -f /home/pi/drone/logs/mission_runner.log

# Monitor state transitions
mosquitto_sub -h localhost -p 1883 -t "drone/+/mission/status"
```

#### Obstacle Handling Problems
```bash
# Test obstacle detection
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/obstacles" \
  -m '{"type": "test", "confidence": 0.9, "lat": 37.7751, "lon": -122.4196, "alt": 50.0}'

# Check pause/resume
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
  -m '{"type": "resume"}'
```

### Debug Mode
```bash
# Run with debug logging
python src/mission_runner.py --log-level DEBUG

# Run with specific mission and debug
python src/mission_runner.py --mission data/sample_missions/sample_mission.json --log-level DEBUG
```

## Future Enhancements

### Planned Features
- **Real GPS Integration**: Replace simulation with actual GPS data
- **Advanced Obstacle Avoidance**: Dynamic waypoint insertion
- **Mission Planning**: GUI for mission creation and editing
- **Backend Integration**: Mission upload to Supabase
- **Real-time Monitoring**: Web dashboard for mission tracking

### Performance Improvements
- **3D Path Planning**: Account for terrain and obstacles
- **Fuel Management**: Battery and fuel consumption modeling
- **Weather Integration**: Wind and weather condition handling
- **Multi-drone Support**: Coordinated multi-drone missions

## Integration with Other Phases

### Phase 1 (Sensors)
- **GPS Integration**: Real GPS data for position updates
- **IMU Integration**: Attitude data for flight dynamics
- **Telemetry Aggregation**: Mission data in telemetry stream

### Phase 2 (Telemetry)
- **Status Publishing**: Mission status in telemetry packets
- **Progress Tracking**: Mission progress in real-time
- **Error Reporting**: Mission errors in telemetry

### Phase 4 (Vision System)
- **Obstacle Detection**: Vision system obstacle events
- **Delivery Confirmation**: Visual confirmation of payload delivery
- **Landing Assistance**: Visual landing guidance

### Phase 5 (Backend Integration)
- **Mission Upload**: Mission definitions to Supabase
- **Status Sync**: Real-time mission status to backend
- **Historical Data**: Mission logs and performance data

## Conclusion

The mission runner system provides a robust foundation for autonomous drone mission execution. The simulator-first approach allows for comprehensive testing and validation before actual flight operations. The modular design supports easy integration with sensor systems, vision processing, and backend services.

The state machine ensures reliable mission execution with proper error handling and recovery mechanisms. The MQTT-based architecture enables real-time monitoring and control, while the JSON mission format provides flexibility for different mission types and requirements.

This implementation successfully meets the Phase 3 requirements for waypoint navigation, obstacle handling, and delivery simulation, providing a solid foundation for the complete drone companion system.
