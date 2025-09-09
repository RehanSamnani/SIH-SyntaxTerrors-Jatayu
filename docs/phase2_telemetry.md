# Phase 2 — Telemetry Aggregator & Local Messaging

This document describes the implementation of the telemetry aggregator service and local MQTT messaging system for the AI-enabled drone companion prototype.

## Overview

The telemetry service acts as a central hub that:
- Subscribes to GPS and IMU sensor data via MQTT
- Aggregates sensor readings into unified telemetry packets
- Publishes telemetry to `drone/<id>/telemetry` topic every 1 second
- Writes last 500 packets to rotating `telemetry.log` files
- Supports dry-run mode for testing without physical sensors
- Includes battery estimation and camera status monitoring

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────────┐
│ GPS Reader  │───▶│             │    │                 │
│ (UART)      │    │   MQTT      │    │  Telemetry      │
└─────────────┘    │   Broker    │    │  Service        │
                   │ (Mosquitto) │◀───│                 │
┌─────────────┐    │             │    │                 │
│ IMU Reader  │───▶│             │    │                 │
│ (I2C)       │    └─────────────┘    └─────────────────┘
└─────────────┘                              │
                                             ▼
                                    ┌─────────────────┐
                                    │  Telemetry      │
                                    │  Logs & MQTT    │
                                    │  Publishing     │
                                    └─────────────────┘
```

## Components

### 1. Telemetry Service (`src/telemetry_service.py`)

**Features:**
- MQTT-based sensor data aggregation
- Rotating log files with size limits (10MB max, 7 days retention)
- Battery voltage/percentage estimation
- Camera status monitoring
- Graceful shutdown handling
- Configurable via environment variables
- Systemd service ready

**Key Classes:**
- `TelemetryAggregator`: Main service class
- `RotatingLogWriter`: Handles log rotation and size limits
- `GracefulKiller`: Manages shutdown signals

**Configuration:**
```bash
# Environment variables
DEVICE_ID=pi-drone-01
MQTT_HOST=localhost
MQTT_PORT=1883
TELEMETRY_INTERVAL=1.0
MAX_LOG_PACKETS=500
MAX_LOG_SIZE_MB=10
```

### 2. MQTT Broker Setup (`scripts/setup_mqtt_broker.sh`)

**Features:**
- Installs and configures Mosquitto MQTT broker
- Optional authentication (username/password)
- Optional TLS encryption
- Log rotation configuration
- Systemd service management
- Test connectivity scripts

**Usage:**
```bash
# Basic setup (no auth, no TLS)
bash scripts/setup_mqtt_broker.sh

# With authentication
bash scripts/setup_mqtt_broker.sh --with-auth

# With authentication and TLS
bash scripts/setup_mqtt_broker.sh --with-auth --with-tls
```

### 3. Systemd Service (`scripts/telemetry.service`)

**Features:**
- Automatic startup on boot
- Restart on failure
- Resource limits (256MB RAM, 50% CPU)
- Security hardening
- Environment variable configuration
- Log management

**Installation:**
```bash
bash scripts/install_telemetry_service.sh --enable --start
```

### 4. Testing & Monitoring Scripts

#### `scripts/test_telemetry.py`
- Validates MQTT connectivity
- Tests telemetry message format
- Simulates sensor data publishing
- Provides performance metrics
- Comprehensive test reporting

#### `scripts/monitor_telemetry.py`
- Real-time telemetry display
- Data visualization
- Connection status monitoring
- Statistics tracking
- Terminal-based dashboard

## Telemetry Message Format

```json
{
  "device_id": "pi-drone-01",
  "timestamp": 1703123456.789,
  "timestamp_iso": "2023-12-21T10:30:56.789Z",
  "battery": {
    "voltage": 12.4,
    "percentage": 85.2
  },
  "camera": {
    "available": true,
    "resolution": "1920x1080",
    "fps": 30,
    "recording": false
  },
  "gps": {
    "lat": 37.7749,
    "lon": -122.4194,
    "alt": 100.0,
    "num_sats": 8,
    "hdop": 1.2,
    "quality": 1,
    "gps_timestamp": "2023-12-21T10:30:56.000Z"
  },
  "imu": {
    "pitch_deg": -2.5,
    "roll_deg": 1.8,
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
    "imu_timestamp": 1703123456.789
  }
}
```

## MQTT Topics

- `drone/<device_id>/gps` - GPS sensor data
- `drone/<device_id>/imu` - IMU sensor data  
- `drone/<device_id>/telemetry` - Aggregated telemetry
- `drone/<device_id>/obstacles` - Obstacle detection (future)
- `drone/<device_id>/mission` - Mission commands (future)

## Installation & Setup

### 1. Install MQTT Broker
```bash
# On Raspberry Pi
bash scripts/setup_mqtt_broker.sh --with-auth
```

### 2. Install Telemetry Service
```bash
# Install as systemd service
bash scripts/install_telemetry_service.sh --enable --start
```

### 3. Test the System
```bash
# Test MQTT connectivity
bash scripts/test_mqtt.sh

# Test telemetry service
python scripts/test_telemetry.py --duration 30

# Monitor telemetry in real-time
python scripts/monitor_telemetry.py
```

## Usage Examples

### Dry-Run Mode (Testing Without Sensors)
```bash
# Run telemetry service with simulated data
python src/telemetry_service.py --dry-run --log-level DEBUG

# Monitor the simulated telemetry
python scripts/monitor_telemetry.py
```

### Production Mode (With Real Sensors)
```bash
# Start GPS reader
python src/sensors/gps_reader.py &

# Start IMU reader  
python src/sensors/imu_reader.py &

# Start telemetry service
python src/telemetry_service.py
```

### Service Management
```bash
# Check service status
sudo systemctl status telemetry.service

# View logs
sudo journalctl -u telemetry.service -f

# Restart service
sudo systemctl restart telemetry.service

# Use management script
bash scripts/manage_telemetry.sh status
bash scripts/manage_telemetry.sh logs
bash scripts/manage_telemetry.sh restart
```

## MQTT Testing Commands

### Subscribe to Telemetry
```bash
# Basic subscription
mosquitto_sub -h localhost -p 1883 -t "drone/+/telemetry"

# With authentication
mosquitto_sub -h localhost -p 1883 -u drone -P <password> -t "drone/+/telemetry"

# With TLS
mosquitto_sub -h localhost -p 8883 -u drone -P <password> --cafile /etc/mosquitto/certs/mosquitto.crt -t "drone/+/telemetry"
```

### Publish Test Messages
```bash
# Test message
mosquitto_pub -h localhost -p 1883 -t "test/topic" -m "Hello MQTT"

# Test GPS data
mosquitto_pub -h localhost -p 1883 -t "drone/pi-drone-01/gps" -m '{"device_id":"pi-drone-01","type":"GGA","lat":37.7749,"lon":-122.4194,"alt":100.0}'
```

## Log Files

### Telemetry Logs
- **Location**: `/home/pi/drone/telemetry/telemetry.log`
- **Format**: JSON Lines (one JSON object per line)
- **Rotation**: Daily, 7 days retention, 10MB max size
- **Backup**: `telemetry.log.1`, `telemetry.log.2.gz`, etc.

### Service Logs
- **Location**: `/home/pi/drone/logs/telemetry_service.log`
- **Format**: Standard logging format
- **Rotation**: 5MB max size, 3 backups
- **Systemd**: `sudo journalctl -u telemetry.service`

## Performance Considerations

### Raspberry Pi Optimization
- **Memory**: Service limited to 256MB RAM
- **CPU**: Service limited to 50% CPU usage
- **Logging**: Rotating logs prevent disk space issues
- **MQTT**: QoS 1 for reliable message delivery
- **Intervals**: 1-second telemetry publishing rate

### Network Optimization
- **Local MQTT**: Reduces network latency
- **Message Size**: Compact JSON format
- **Connection Pooling**: Persistent MQTT connections
- **Retry Logic**: Automatic reconnection on failures

## Security Features

### MQTT Security
- **Authentication**: Username/password support
- **TLS Encryption**: Optional TLS 1.2+ encryption
- **Access Control**: Topic-based permissions
- **Certificate Management**: Self-signed certs for development

### Service Security
- **User Isolation**: Runs as non-root user
- **File Permissions**: Restricted log file access
- **Systemd Security**: NoNewPrivileges, PrivateTmp
- **Resource Limits**: Memory and CPU constraints

## Troubleshooting

### Common Issues

#### MQTT Connection Failed
```bash
# Check broker status
sudo systemctl status mosquitto

# Check broker logs
sudo journalctl -u mosquitto -f

# Test connectivity
mosquitto_pub -h localhost -p 1883 -t "test" -m "test"
```

#### No Telemetry Messages
```bash
# Check telemetry service status
sudo systemctl status telemetry.service

# Check service logs
sudo journalctl -u telemetry.service -f

# Verify sensor services are running
ps aux | grep -E "(gps_reader|imu_reader)"
```

#### High CPU/Memory Usage
```bash
# Check resource usage
top -p $(pgrep -f telemetry_service)

# Adjust service limits in systemd unit
sudo systemctl edit telemetry.service
```

### Debug Mode
```bash
# Run with debug logging
python src/telemetry_service.py --log-level DEBUG

# Test with dry-run mode
python src/telemetry_service.py --dry-run --log-level DEBUG
```

## Future Enhancements

### Planned Features
- **Obstacle Detection Integration**: Subscribe to vision system topics
- **Mission Command Interface**: Handle waypoint and command messages
- **Backend Sync**: Automatic upload to Supabase
- **Health Monitoring**: System resource monitoring
- **Alert System**: Critical condition notifications

### Performance Improvements
- **Message Compression**: Gzip compression for large payloads
- **Batch Publishing**: Multiple messages per MQTT packet
- **Caching**: In-memory telemetry history
- **Async Processing**: Asyncio-based implementation

## Integration with Other Phases

### Phase 1 (Sensors)
- GPS reader publishes to `drone/<id>/gps`
- IMU reader publishes to `drone/<id>/imu`
- Telemetry service subscribes and aggregates

### Phase 3 (Vision System)
- Obstacle detector will publish to `drone/<id>/obstacles`
- Telemetry service will include obstacle data
- Mission runner will subscribe to telemetry

### Phase 4 (Mission Control)
- Mission runner subscribes to telemetry
- Command interface publishes to `drone/<id>/commands`
- Waypoint navigation uses telemetry data

### Phase 5 (Backend Integration)
- Telemetry service uploads to Supabase
- Real-time dashboard consumes MQTT data
- Historical data analysis from logs

## Testing Checklist

- [ ] MQTT broker installation and configuration
- [ ] Telemetry service installation and startup
- [ ] GPS sensor data publishing and aggregation
- [ ] IMU sensor data publishing and aggregation
- [ ] Telemetry message format validation
- [ ] Log file rotation and size limits
- [ ] Dry-run mode functionality
- [ ] Systemd service management
- [ ] Performance under load
- [ ] Error handling and recovery
- [ ] Security configuration
- [ ] Integration with existing sensor scripts

## Conclusion

The telemetry aggregator service provides a robust foundation for data collection and messaging in the drone companion system. It successfully decouples sensor data collection from telemetry aggregation, enabling modular development and testing. The MQTT-based architecture supports real-time monitoring and future integration with mission control and backend systems.

The implementation includes comprehensive testing tools, monitoring capabilities, and production-ready features like log rotation, systemd integration, and security hardening. This phase establishes the data flow infrastructure needed for subsequent phases of the project.
