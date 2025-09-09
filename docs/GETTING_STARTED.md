# Getting Started Guide - AI-Enabled Drone Companion System

This comprehensive guide will walk you through setting up, running, and testing the entire AI-enabled drone companion system from scratch. Follow these steps to get everything working on your Raspberry Pi.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Phase 0: Preparation & Safety](#phase-0-preparation--safety)
4. [Phase 1: Sensor Integration](#phase-1-sensor-integration)
5. [Phase 2: Telemetry System](#phase-2-telemetry-system)
6. [Phase 3: Mission Runner](#phase-3-mission-runner)
7. [Integration Testing](#integration-testing)
8. [Troubleshooting](#troubleshooting)
9. [Next Steps](#next-steps)

## Prerequisites

### Hardware Requirements
- **Raspberry Pi 4** (4GB RAM recommended)
- **MicroSD Card** (32GB+ Class 10)
- **GPS Module**: NEO-6M
- **IMU Sensor**: MPU-6050
- **Camera**: Raspberry Pi Camera Module
- **Servo Motor**: Micro servo for payload release
- **Power Supply**: 5V 3A for Pi + external 5V for servo
- **Jumper Wires** and breadboard
- **Heatsinks/Fan** (recommended for Pi)

### Software Requirements
- **Raspberry Pi OS 64-bit** (latest version)
- **Python 3.9+**
- **Git**

## Initial Setup

### 1. Flash Raspberry Pi OS

1. Download **Raspberry Pi Imager** from [rpi.org](https://www.raspberrypi.org/downloads/)
2. Flash **Raspberry Pi OS (64-bit)** to your microSD card
3. **Enable SSH** in Imager advanced options
4. Set hostname: `pi-drone-01` (or your preferred name)
5. Set username: `pi` (or your preferred username)
6. **Do NOT enable serial console** (we'll use UART for GPS)

### 2. First Boot and Network Setup

1. Insert microSD card and power on Pi
2. Connect to network (Ethernet or Wi-Fi)
3. SSH into your Pi:
   ```bash
   ssh pi@pi-drone-01.local
   # or
   ssh pi@<pi-ip-address>
   ```

### 3. System Updates

```bash
# Update system packages
sudo apt update && sudo apt full-upgrade -y
sudo reboot

# After reboot, install required tools
sudo apt install -y python3-venv python3-pip git i2c-tools mosquitto mosquitto-clients
```

### 4. Enable Required Interfaces

```bash
# Run raspi-config
sudo raspi-config

# Navigate to: Interface Options
# Enable: Camera, I2C
# For Serial: disable login shell on serial; enable serial hardware
# Save and reboot
sudo reboot
```

### 5. Clone Project Repository

```bash
# Create project directory
mkdir -p ~/sih
cd ~/sih

# Clone repository (replace with your actual repo URL)
git clone <your-repo-url> .

# Or if you have the files locally, copy them to ~/sih/
```

### 6. Python Environment Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt

# Verify installation
python -c "import paho.mqtt.client, pynmea2, smbus2, cv2; print('All dependencies installed successfully')"
```

## Phase 0: Preparation & Safety

### Hardware Wiring

**⚠️ IMPORTANT: Double-check all connections before powering on!**

#### GPS Module (NEO-6M) Wiring
```
NEO-6M → Raspberry Pi
VCC    → 5V (Pin 2)
GND    → GND (Pin 6)
TX     → GPIO15/RXD (Pin 10)
RX     → GPIO14/TXD (Pin 8)
```

#### IMU Module (MPU-6050) Wiring
```
MPU-6050 → Raspberry Pi
VCC      → 3.3V (Pin 1)
GND      → GND (Pin 9)
SDA      → GPIO2/SDA1 (Pin 3)
SCL      → GPIO3/SCL1 (Pin 5)
```

#### Servo Motor Wiring
```
Servo → External 5V Supply + Pi
Signal → GPIO18 (Pin 12)
Power  → External 5V Supply +
Ground → Common ground (Pi GND + External Supply GND)
```

#### Camera Module
- Connect CSI ribbon cable firmly
- Ensure camera is enabled in raspi-config

### Hardware Verification

```bash
# Check I2C devices (should show MPU-6050 at address 0x68)
sudo i2cdetect -y 1

# Check serial port (should show /dev/serial0)
ls -la /dev/serial*

# Check camera
libcamera-hello --list-cameras

# Test camera capture
libcamera-still -o test.jpg
```

### Security Setup

```bash
# Change default password
passwd

# Disable password authentication (use SSH keys only)
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh

# Configure UFW firewall (optional)
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 1883  # MQTT
```

## Phase 1: Sensor Integration

### 1. Test GPS Reader

```bash
# Activate virtual environment
source .venv/bin/activate

# Test GPS reader (will show NMEA data)
python src/sensors/gps_reader.py

# Expected output:
# 2023-12-21 10:30:00 [INFO] Starting gps_reader (device_id=pi-drone-01, port=/dev/serial0)
# 2023-12-21 10:30:01 [INFO] GPS fix: lat=37.7749 lon=-122.4194 alt=100.0 sats=8

# Check GPS data file
cat /home/pi/drone/telemetry/gps_latest.json
```

### 2. Test IMU Reader

```bash
# Test IMU reader (will show accelerometer/gyroscope data)
python src/sensors/imu_reader.py

# Expected output:
# 2023-12-21 10:30:00 [INFO] Starting imu_reader (MPU-6050 at 0x68)
# 2023-12-21 10:30:01 [INFO] pitch=-2.50 roll=1.80 ax=0.10 ay=-0.20 az=1.00

# Check IMU log file
tail -f /home/pi/drone/telemetry/imu_log.jsonl
```

### 3. Test Servo Control

```bash
# Test servo release mechanism
python src/actuators/servo_release.py

# Expected output:
# 2023-12-21 10:30:00 [INFO] Servo release test completed
```

## Phase 2: Telemetry System

### 1. Setup MQTT Broker

```bash
# Install and configure Mosquitto MQTT broker
bash scripts/setup_mqtt_broker.sh

# Expected output:
# ✅ Mosquitto MQTT broker is running successfully!
# MQTT Broker Configuration Summary:
# Host: localhost
# Port: 1883
# Authentication: Disabled (anonymous allowed)

# Test MQTT connectivity
bash scripts/test_mqtt.sh
```

### 2. Test Telemetry Service (Dry-Run)

```bash
# Test telemetry service with simulated data
python src/telemetry_service.py --dry-run --log-level INFO

# Expected output:
# 2023-12-21 10:30:00 [INFO] Starting telemetry service (device_id=pi-drone-01, dry_run=True)
# 2023-12-21 10:30:01 [INFO] Telemetry: GPS IMU bat=100.0% lat=37.774900 lon=-122.419400 pitch=-2.50 roll=1.80

# In another terminal, monitor telemetry
python scripts/monitor_telemetry.py
```

### 3. Test Real Sensor Integration

```bash
# Terminal 1: Start GPS reader
python src/sensors/gps_reader.py &

# Terminal 2: Start IMU reader
python src/sensors/imu_reader.py &

# Terminal 3: Start telemetry service
python src/telemetry_service.py

# Terminal 4: Monitor telemetry
python scripts/monitor_telemetry.py
```

### 4. Install Telemetry Service

```bash
# Install as systemd service
bash scripts/install_telemetry_service.sh --enable --start

# Check service status
sudo systemctl status telemetry.service

# View service logs
sudo journalctl -u telemetry.service -f
```

### 5. Validate Phase 2

```bash
# Run comprehensive Phase 2 validation
python scripts/validate_phase2.py

# Expected output:
# ============================================================
# PHASE 2 VALIDATION SUMMARY
# ============================================================
# ✅ PASS MQTT Broker: Broker is accessible on localhost:1883
# ✅ PASS Telemetry Service File: Service file exists and contains main class
# ✅ PASS Telemetry Dry-Run: Service started and ran successfully in dry-run mode
# ✅ PASS Telemetry Message Format: Received 5 messages with correct format
# ✅ PASS Log Files: Log directory exists (file will be created when service runs)
# ✅ PASS Script Files: All 4 required scripts exist
# ✅ PASS Dependencies: All required Python modules are available
# ============================================================
# Overall Result: 7/7 tests passed
# 🎉 Phase 2 validation PASSED! All components are working correctly.
```

## Phase 3: Mission Runner

### 1. Test Mission Runner (Dry-Run)

```bash
# Test with default mission
python src/mission_runner.py --dry-run --log-level INFO

# Expected output:
# 2023-12-21 10:30:00 [INFO] Starting mission runner (device_id=pi-drone-01, dry_run=True)
# 2023-12-21 10:30:00 [INFO] Loaded mission: Disaster Relief Supply Drop (10 waypoints)
# 2023-12-21 10:30:01 [INFO] State changed: IDLE → TAKEOFF
# 2023-12-21 10:30:06 [INFO] State changed: TAKEOFF → ENROUTE
```

### 2. Test Different Mission Types

```bash
# Test disaster relief mission
python src/mission_runner.py --mission data/sample_missions/sample_mission.json --dry-run

# Test aerial survey mission
python src/mission_runner.py --mission data/sample_missions/survey_mission.json --dry-run

# Test emergency response mission
python src/mission_runner.py --mission data/sample_missions/emergency_mission.json --dry-run
```

### 3. Test Mission Control via MQTT

```bash
# Terminal 1: Start mission runner
python src/mission_runner.py --mission data/sample_missions/sample_mission.json

# Terminal 2: Monitor mission status
mosquitto_sub -h localhost -p 1883 -t "drone/+/mission/status"

# Terminal 3: Start mission
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
  -m '{"type": "start", "mission_id": "disaster_relief_001"}'

# Terminal 4: Test pause/resume
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
  -m '{"type": "pause"}'

mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
  -m '{"type": "resume"}'
```

### 4. Test Obstacle Handling

```bash
# Terminal 1: Start mission runner
python src/mission_runner.py --mission data/sample_missions/sample_mission.json

# Terminal 2: Send obstacle detection
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/obstacles" \
  -m '{"type": "building", "confidence": 0.9, "lat": 37.7751, "lon": -122.4196, "alt": 50.0}'

# Terminal 3: Monitor status (should show PAUSED state)
mosquitto_sub -h localhost -p 1883 -t "drone/+/mission/status" -C 1

# Terminal 4: Resume mission
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
  -m '{"type": "resume"}'
```

### 5. Test Delivery Simulation

```bash
# Terminal 1: Start mission runner
python src/mission_runner.py --mission data/sample_missions/sample_mission.json

# Terminal 2: Monitor servo commands
mosquitto_sub -h localhost -p 1883 -t "drone/+/servo/command"

# Terminal 3: Start mission and wait for delivery waypoints
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
  -m '{"type": "start", "mission_id": "disaster_relief_001"}'

# Expected servo command:
# {
#   "device_id": "pi-drone-01",
#   "timestamp": 1703123456.789,
#   "command": "release",
#   "waypoint": 3,
#   "payload_metadata": {...}
# }
```

### 6. Run Mission Runner Tests

```bash
# Run unit tests
python -m pytest tests/test_mission_runner.py -v

# Expected output:
# ========================== test session starts ==========================
# tests/test_mission_runner.py::TestWaypoint::test_waypoint_creation PASSED
# tests/test_mission_runner.py::TestMission::test_mission_creation PASSED
# tests/test_mission_runner.py::TestMissionRunner::test_load_mission PASSED
# tests/test_mission_runner.py::TestMissionRunner::test_start_mission PASSED
# tests/test_mission_runner.py::TestMissionRunner::test_pause_resume_mission PASSED
# tests/test_mission_runner.py::TestMissionRunner::test_obstacle_handling PASSED
# ========================== 15 passed in 2.34s ==========================
```

## Integration Testing

### 1. Full System Integration Test

```bash
# Terminal 1: Start MQTT broker (if not already running)
sudo systemctl start mosquitto

# Terminal 2: Start GPS reader
python src/sensors/gps_reader.py &

# Terminal 3: Start IMU reader
python src/sensors/imu_reader.py &

# Terminal 4: Start telemetry service
python src/telemetry_service.py &

# Terminal 5: Start mission runner
python src/mission_runner.py --mission data/sample_missions/sample_mission.json &

# Terminal 6: Monitor everything
mosquitto_sub -h localhost -p 1883 -t "drone/+/telemetry" -t "drone/+/mission/status" -t "drone/+/servo/command"
```

### 2. End-to-End Mission Test

```bash
# Start mission
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
  -m '{"type": "start", "mission_id": "disaster_relief_001"}'

# Monitor mission progress
watch -n 1 'mosquitto_sub -h localhost -p 1883 -t "drone/+/mission/status" -C 1 | jq .'

# Test obstacle handling mid-mission
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/obstacles" \
  -m '{"type": "building", "confidence": 0.9, "lat": 37.7751, "lon": -122.4196, "alt": 50.0}'

# Resume after obstacle
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
  -m '{"type": "resume"}'
```

### 3. Performance Testing

```bash
# Test with different mission speeds
python src/mission_runner.py --mission data/sample_missions/sample_mission.json --speed 1.0 --dry-run
python src/mission_runner.py --mission data/sample_missions/sample_mission.json --speed 5.0 --dry-run
python src/mission_runner.py --mission data/sample_missions/sample_mission.json --speed 10.0 --dry-run

# Test long mission (survey)
python src/mission_runner.py --mission data/sample_missions/survey_mission.json --dry-run

# Monitor system resources
htop
```

### 4. Stress Testing

```bash
# Test rapid mission commands
for i in {1..10}; do
  mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
    -m '{"type": "start", "mission_id": "disaster_relief_001"}'
  sleep 1
  mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
    -m '{"type": "pause"}'
  sleep 1
  mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/mission/command" \
    -m '{"type": "resume"}'
done
```

## Troubleshooting

### Common Issues and Solutions

#### 1. GPS Not Working

**Symptoms**: No GPS data, "No fix" messages

**Solutions**:
```bash
# Check serial port
ls -la /dev/serial*

# Check GPS wiring
sudo dmesg | grep tty

# Test with different baud rates
python -c "
import serial
try:
    ser = serial.Serial('/dev/serial0', 9600, timeout=1)
    print('GPS connected at 9600 baud')
    ser.close()
except Exception as e:
    print(f'GPS connection failed: {e}')
"

# Check if serial console is disabled
sudo raspi-config
# Interface Options → Serial → No (disable login shell)
```

#### 2. IMU Not Detected

**Symptoms**: I2C device not found, "No IMU data"

**Solutions**:
```bash
# Check I2C is enabled
sudo raspi-config
# Interface Options → I2C → Yes

# Check I2C devices
sudo i2cdetect -y 1
# Should show 0x68 for MPU-6050

# Check wiring
# VCC → 3.3V, GND → GND, SDA → GPIO2, SCL → GPIO3

# Test I2C communication
sudo i2cget -y 1 0x68 0x75
# Should return 0x68 (MPU-6050 WHO_AM_I register)
```

#### 3. MQTT Connection Failed

**Symptoms**: "Failed to connect to MQTT broker"

**Solutions**:
```bash
# Check Mosquitto status
sudo systemctl status mosquitto

# Restart Mosquitto
sudo systemctl restart mosquitto

# Check Mosquitto logs
sudo journalctl -u mosquitto -f

# Test MQTT connectivity
mosquitto_pub -h localhost -p 1883 -t "test" -m "test"
mosquitto_sub -h localhost -p 1883 -t "test" -C 1

# Check firewall
sudo ufw status
sudo ufw allow 1883
```

#### 4. Mission Not Loading

**Symptoms**: "Failed to load mission", "Mission file not found"

**Solutions**:
```bash
# Check mission files exist
ls -la data/sample_missions/

# Validate JSON syntax
python -c "
import json
try:
    with open('data/sample_missions/sample_mission.json') as f:
        json.load(f)
    print('Mission JSON is valid')
except Exception as e:
    print(f'Mission JSON error: {e}')
"

# Check file permissions
chmod 644 data/sample_missions/*.json
```

#### 5. Service Not Starting

**Symptoms**: Systemd service fails to start

**Solutions**:
```bash
# Check service status
sudo systemctl status telemetry.service

# Check service logs
sudo journalctl -u telemetry.service -f

# Check service file
sudo systemctl cat telemetry.service

# Reload systemd
sudo systemctl daemon-reload

# Restart service
sudo systemctl restart telemetry.service
```

#### 6. High CPU/Memory Usage

**Symptoms**: System becomes slow, high resource usage

**Solutions**:
```bash
# Check resource usage
htop
top -p $(pgrep -f telemetry_service)

# Check service limits
sudo systemctl show telemetry.service | grep -E "(MemoryMax|CPUQuota)"

# Adjust limits if needed
sudo systemctl edit telemetry.service
# Add:
# [Service]
# MemoryMax=256M
# CPUQuota=50%
```

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
# Telemetry service debug
python src/telemetry_service.py --log-level DEBUG

# Mission runner debug
python src/mission_runner.py --log-level DEBUG

# GPS reader debug
python src/sensors/gps_reader.py  # Add logging.basicConfig(level=logging.DEBUG)

# IMU reader debug
python src/sensors/imu_reader.py  # Add logging.basicConfig(level=logging.DEBUG)
```

### Log Files

Check log files for detailed error information:

```bash
# Telemetry service logs
tail -f /home/pi/drone/logs/telemetry_service.log

# Mission runner logs
tail -f /home/pi/drone/logs/mission_runner.log

# Systemd service logs
sudo journalctl -u telemetry.service -f
sudo journalctl -u mosquitto -f

# System logs
sudo journalctl -f
```

## Next Steps

### Phase 4: Vision System Integration
- Integrate obstacle detection from camera
- Add real-time vision processing
- Implement advanced obstacle avoidance

### Phase 5: Backend Integration
- Connect to Supabase database
- Implement mission upload/download
- Add real-time dashboard

### Production Deployment
- Set up proper authentication
- Configure TLS encryption
- Implement monitoring and alerting
- Add backup and recovery procedures

### Hardware Integration
- Test with actual drone hardware
- Implement flight controller integration
- Add safety systems and failsafes

## Support and Resources

### Documentation
- **Phase 2**: `docs/phase2_telemetry.md`
- **Phase 3**: `docs/phase3_mission_runner.md`
- **Code Review**: `docs/features/2_REVIEW.md`

### Quick References
- **Phase 2 Quickstart**: `docs/phase2_quickstart.md`
- **Phase 3 Quickstart**: `docs/phase3_quickstart.md`

### Testing Scripts
- **Phase 2 Validation**: `python scripts/validate_phase2.py`
- **Telemetry Testing**: `python scripts/test_telemetry.py`
- **Mission Testing**: `python -m pytest tests/test_mission_runner.py`

### Management Scripts
- **Telemetry Service**: `bash scripts/manage_telemetry.sh`
- **MQTT Broker**: `bash scripts/setup_mqtt_broker.sh`

## Conclusion

This guide provides a complete walkthrough of setting up and testing the AI-enabled drone companion system. By following these steps, you should have a fully functional system capable of:

- ✅ Reading GPS and IMU sensor data
- ✅ Aggregating telemetry and publishing via MQTT
- ✅ Running waypoint missions with state machine
- ✅ Handling obstacles with pause/resume logic
- ✅ Simulating payload delivery
- ✅ Comprehensive testing and validation

The system is now ready for integration with vision systems and backend services in subsequent phases.

**Happy flying! 🚁**
