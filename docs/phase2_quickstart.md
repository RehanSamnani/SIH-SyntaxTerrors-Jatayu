# Phase 2 Quick Start Guide

This guide provides step-by-step instructions to quickly set up and test the telemetry aggregator service.

## Prerequisites

- Raspberry Pi 4 with Raspberry Pi OS 64-bit
- Python virtual environment activated
- Project dependencies installed (`pip install -r requirements.txt`)

## Quick Setup (5 minutes)

### 1. Install MQTT Broker
```bash
# Install Mosquitto MQTT broker
bash scripts/setup_mqtt_broker.sh
```

### 2. Test Telemetry Service (Dry-Run Mode)
```bash
# Run telemetry service with simulated data
python src/telemetry_service.py --dry-run --log-level INFO
```

### 3. Monitor Telemetry (In Another Terminal)
```bash
# Real-time telemetry monitoring
python scripts/monitor_telemetry.py
```

## Expected Output

### Telemetry Service Console Output
```
2023-12-21 10:30:00 [INFO] Starting telemetry service (device_id=pi-drone-01, dry_run=True)
2023-12-21 10:30:00 [INFO] Running in dry-run mode - simulating sensor data
2023-12-21 10:30:01 [INFO] Telemetry: GPS IMU bat=100.0% lat=37.774900 lon=-122.419400 pitch=-2.50 roll=1.80
2023-12-21 10:30:02 [INFO] Telemetry: GPS IMU bat=100.0% lat=37.774901 lon=-122.419401 pitch=-2.45 roll=1.85
```

### Monitor Console Output
```
================================================================================
DRONE TELEMETRY MONITOR - Device: pi-drone-01
================================================================================
Timestamp: 2023-12-21T10:30:01.000Z
Battery:   12.60V (100.0%) [████████████████████]
GPS:       Lat: 37.774900° Lon: -122.419400° Alt: 100.0m
           Sats: 8 HDOP: 1.2
IMU:       Pitch: -2.50° Roll: +1.80°
           Accel: X:+0.10 Y:-0.20 Z:+1.00 g
           Gyro:  X:+0.50 Y:+0.30 Z:+0.20 °/s
Camera:    Available 1920x1080@30fps ⚪
--------------------------------------------------------------------------------
Stats:     Messages: 5 | Rate: 1.00/s | GPS Fixes: 5 | IMU Readings: 5
           Uptime: 5s | Last Message: 0.1s ago
Status:    🟢 Connected
================================================================================
Press Ctrl+C to exit
```

## Testing with Real Sensors

### 1. Start GPS Reader
```bash
# In terminal 1
python src/sensors/gps_reader.py
```

### 2. Start IMU Reader
```bash
# In terminal 2  
python src/sensors/imu_reader.py
```

### 3. Start Telemetry Service
```bash
# In terminal 3
python src/telemetry_service.py
```

### 4. Monitor Telemetry
```bash
# In terminal 4
python scripts/monitor_telemetry.py
```

## MQTT Testing

### Subscribe to Telemetry
```bash
# Basic subscription
mosquitto_sub -h localhost -p 1883 -t "drone/+/telemetry"

# Pretty-print JSON
mosquitto_sub -h localhost -p 1883 -t "drone/+/telemetry" | jq .
```

### Test Message Publishing
```bash
# Test GPS data
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/gps" -m '{
  "device_id": "pi-drone-01",
  "type": "GGA", 
  "lat": 37.7749,
  "lon": -122.4194,
  "alt": 100.0,
  "num_sats": 8
}'

# Test IMU data
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/imu" -m '{
  "ts": 1703123456.789,
  "accel": {"x_g": 0.1, "y_g": -0.2, "z_g": 1.0},
  "gyro": {"x_dps": 0.5, "y_dps": 0.3, "z_dps": 0.2},
  "est": {"pitch_deg": -2.5, "roll_deg": 1.8}
}'
```

## Service Installation

### Install as Systemd Service
```bash
# Install and enable service
bash scripts/install_telemetry_service.sh --enable --start

# Check status
sudo systemctl status telemetry.service

# View logs
sudo journalctl -u telemetry.service -f
```

### Service Management
```bash
# Use management script
bash scripts/manage_telemetry.sh status
bash scripts/manage_telemetry.sh logs
bash scripts/manage_telemetry.sh restart
```

## Troubleshooting

### MQTT Broker Issues
```bash
# Check broker status
sudo systemctl status mosquitto

# Restart broker
sudo systemctl restart mosquitto

# Test connectivity
mosquitto_pub -h localhost -p 1883 -t "test" -m "test"
```

### Telemetry Service Issues
```bash
# Check service status
sudo systemctl status telemetry.service

# View service logs
sudo journalctl -u telemetry.service -f

# Run in debug mode
python src/telemetry_service.py --dry-run --log-level DEBUG
```

### No Sensor Data
```bash
# Check if sensors are running
ps aux | grep -E "(gps_reader|imu_reader)"

# Check sensor logs
tail -f /home/pi/drone/telemetry/gps_latest.json
tail -f /home/pi/drone/telemetry/imu_log.jsonl
```

## Validation Tests

### Automated Testing
```bash
# Run comprehensive test suite
python scripts/test_telemetry.py --duration 30

# Expected output:
# ============================================================
# TELEMETRY SERVICE TEST RESULTS
# ============================================================
# MQTT Connectivity:     ✅ PASS
# GPS Data Publishing:   ✅ PASS  
# IMU Data Publishing:   ✅ PASS
# Telemetry Received:    ✅ PASS
# Message Format Valid:  ✅ PASS
# 
# Performance Metrics:
#   Test Duration:        30.0 seconds
#   Messages Received:    30
#   Messages/Second:      1.00
#   Avg Message Interval: 1.00 seconds
# 
# Overall Result:        ✅ ALL TESTS PASSED
# ============================================================
```

### Manual Validation
1. **Telemetry Rate**: Should see ~1 message per second
2. **Data Completeness**: GPS, IMU, battery, camera data present
3. **Log Files**: Check `/home/pi/drone/telemetry/telemetry.log`
4. **MQTT Topics**: Verify messages on `drone/pi-drone-01/telemetry`

## Next Steps

Once Phase 2 is working correctly:

1. **Phase 3**: Integrate vision system for obstacle detection
2. **Phase 4**: Add mission runner for waypoint navigation  
3. **Phase 5**: Connect to Supabase backend for data sync

## Support

- **Documentation**: See `docs/phase2_telemetry.md` for detailed information
- **Logs**: Check service logs for error details
- **Testing**: Use provided test scripts for validation
- **Debugging**: Run with `--log-level DEBUG` for verbose output
