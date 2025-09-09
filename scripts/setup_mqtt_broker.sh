#!/bin/bash
"""
Setup script for local Mosquitto MQTT broker on Raspberry Pi.

This script:
- Installs Mosquitto MQTT broker
- Configures basic security settings
- Creates systemd service
- Sets up log rotation
- Provides testing commands

Usage:
    bash scripts/setup_mqtt_broker.sh [--with-auth] [--with-tls]
"""

set -euo pipefail

# Configuration
MQTT_USERNAME="${MQTT_USERNAME:-drone}"
MQTT_PASSWORD="${MQTT_PASSWORD:-$(openssl rand -base64 32)}"
MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_TLS_PORT="${MQTT_TLS_PORT:-8883}"

# Parse arguments
WITH_AUTH=false
WITH_TLS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --with-auth)
            WITH_AUTH=true
            shift
            ;;
        --with-tls)
            WITH_TLS=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--with-auth] [--with-tls]"
            echo "  --with-auth: Enable username/password authentication"
            echo "  --with-tls:  Enable TLS encryption"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "Setting up Mosquitto MQTT broker..."

# Update package list
echo "Updating package list..."
sudo apt update

# Install Mosquitto broker and client tools
echo "Installing Mosquitto MQTT broker..."
sudo apt install -y mosquitto mosquitto-clients

# Create Mosquitto configuration directory
sudo mkdir -p /etc/mosquitto/conf.d

# Create main configuration file
echo "Creating Mosquitto configuration..."
sudo tee /etc/mosquitto/conf.d/drone.conf > /dev/null <<EOF
# Drone telemetry MQTT broker configuration

# Basic settings
listener $MQTT_PORT
max_inflight_messages 20
max_queued_messages 100
message_size_limit 0
persistence true
persistence_location /var/lib/mosquitto/
autosave_interval 1800

# Logging
log_dest file /var/log/mosquitto/mosquitto.log
log_type error
log_type warning
log_type notice
log_type information
log_timestamp true
log_timestamp_format %Y-%m-%dT%H:%M:%S

# Connection settings
max_connections 100
keepalive_interval 60
retry_interval 20

# Security settings
allow_anonymous true
EOF

# Configure authentication if requested
if [[ "$WITH_AUTH" == "true" ]]; then
    echo "Configuring MQTT authentication..."
    
    # Create password file
    sudo touch /etc/mosquitto/passwd
    sudo chmod 600 /etc/mosquitto/passwd
    
    # Add user (mosquitto_passwd will prompt for password)
    echo "Creating MQTT user: $MQTT_USERNAME"
    echo "Password will be: $MQTT_PASSWORD"
    echo "$MQTT_PASSWORD" | sudo mosquitto_passwd -c /etc/mosquitto/passwd "$MQTT_USERNAME"
    
    # Update configuration for authentication
    sudo tee -a /etc/mosquitto/conf.d/drone.conf > /dev/null <<EOF

# Authentication
allow_anonymous false
password_file /etc/mosquitto/passwd
EOF
    
    echo "MQTT credentials:"
    echo "  Username: $MQTT_USERNAME"
    echo "  Password: $MQTT_PASSWORD"
    echo "  Save these credentials for your applications!"
fi

# Configure TLS if requested
if [[ "$WITH_TLS" == "true" ]]; then
    echo "Configuring MQTT TLS..."
    
    # Create certificates directory
    sudo mkdir -p /etc/mosquitto/certs
    
    # Generate self-signed certificate (for development only)
    echo "Generating self-signed certificate..."
    sudo openssl req -x509 -newkey rsa:2048 -keyout /etc/mosquitto/certs/mosquitto.key \
        -out /etc/mosquitto/certs/mosquitto.crt -days 365 -nodes \
        -subj "/C=US/ST=CA/L=San Francisco/O=Drone Project/CN=localhost"
    
    sudo chmod 600 /etc/mosquitto/certs/mosquitto.key
    sudo chmod 644 /etc/mosquitto/certs/mosquitto.crt
    
    # Update configuration for TLS
    sudo tee -a /etc/mosquitto/conf.d/drone.conf > /dev/null <<EOF

# TLS configuration
listener $MQTT_TLS_PORT
cafile /etc/mosquitto/certs/mosquitto.crt
certfile /etc/mosquitto/certs/mosquitto.crt
keyfile /etc/mosquitto/certs/mosquitto.key
EOF
    
    echo "TLS enabled on port $MQTT_TLS_PORT"
fi

# Create log directory and set permissions
sudo mkdir -p /var/log/mosquitto
sudo chown mosquitto:mosquitto /var/log/mosquitto

# Create log rotation configuration
echo "Setting up log rotation..."
sudo tee /etc/logrotate.d/mosquitto > /dev/null <<EOF
/var/log/mosquitto/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 mosquitto mosquitto
    postrotate
        systemctl reload mosquitto > /dev/null 2>&1 || true
    endscript
}
EOF

# Enable and start Mosquitto service
echo "Starting Mosquitto service..."
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto

# Wait for service to start
sleep 2

# Check service status
if sudo systemctl is-active --quiet mosquitto; then
    echo "✅ Mosquitto MQTT broker is running successfully!"
else
    echo "❌ Failed to start Mosquitto service"
    sudo systemctl status mosquitto
    exit 1
fi

# Display configuration summary
echo ""
echo "MQTT Broker Configuration Summary:"
echo "=================================="
echo "Host: localhost"
echo "Port: $MQTT_PORT"
if [[ "$WITH_TLS" == "true" ]]; then
    echo "TLS Port: $MQTT_TLS_PORT"
fi
if [[ "$WITH_AUTH" == "true" ]]; then
    echo "Authentication: Enabled"
    echo "Username: $MQTT_USERNAME"
    echo "Password: $MQTT_PASSWORD"
else
    echo "Authentication: Disabled (anonymous allowed)"
fi
echo ""

# Create environment file for applications
echo "Creating environment configuration..."
cat > ~/.env.mqtt <<EOF
# MQTT Configuration for Drone Telemetry
MQTT_HOST=localhost
MQTT_PORT=$MQTT_PORT
EOF

if [[ "$WITH_TLS" == "true" ]]; then
    echo "MQTT_TLS_PORT=$MQTT_TLS_PORT" >> ~/.env.mqtt
    echo "MQTT_TLS_ENABLED=true" >> ~/.env.mqtt
    echo "MQTT_CA_CERT=/etc/mosquitto/certs/mosquitto.crt" >> ~/.env.mqtt
fi

if [[ "$WITH_AUTH" == "true" ]]; then
    echo "MQTT_USERNAME=$MQTT_USERNAME" >> ~/.env.mqtt
    echo "MQTT_PASSWORD=$MQTT_PASSWORD" >> ~/.env.mqtt
fi

echo "Environment file created: ~/.env.mqtt"
echo ""

# Provide testing commands
echo "Testing Commands:"
echo "================="
echo ""

if [[ "$WITH_AUTH" == "true" ]]; then
    AUTH_ARGS="-u $MQTT_USERNAME -P $MQTT_PASSWORD"
else
    AUTH_ARGS=""
fi

if [[ "$WITH_TLS" == "true" ]]; then
    TLS_ARGS="--cafile /etc/mosquitto/certs/mosquitto.crt"
    echo "# Subscribe to telemetry (TLS):"
    echo "mosquitto_sub -h localhost -p $MQTT_TLS_PORT $AUTH_ARGS $TLS_ARGS -t 'drone/+/telemetry'"
    echo ""
    echo "# Publish test message (TLS):"
    echo "mosquitto_pub -h localhost -p $MQTT_TLS_PORT $AUTH_ARGS $TLS_ARGS -t 'test/topic' -m 'Hello MQTT'"
    echo ""
fi

echo "# Subscribe to telemetry:"
echo "mosquitto_sub -h localhost -p $MQTT_PORT $AUTH_ARGS -t 'drone/+/telemetry'"
echo ""
echo "# Publish test message:"
echo "mosquitto_pub -h localhost -p $MQTT_PORT $AUTH_ARGS -t 'test/topic' -m 'Hello MQTT'"
echo ""
echo "# Monitor broker logs:"
echo "sudo journalctl -u mosquitto -f"
echo ""

# Create test script
echo "Creating MQTT test script..."
cat > scripts/test_mqtt.sh <<'EOF'
#!/bin/bash
# Test MQTT broker connectivity and telemetry topics

set -euo pipefail

# Load environment variables
if [[ -f ~/.env.mqtt ]]; then
    source ~/.env.mqtt
fi

MQTT_HOST="${MQTT_HOST:-localhost}"
MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_USERNAME="${MQTT_USERNAME:-}"
MQTT_PASSWORD="${MQTT_PASSWORD:-}"

if [[ -n "$MQTT_USERNAME" ]]; then
    AUTH_ARGS="-u $MQTT_USERNAME -P $MQTT_PASSWORD"
else
    AUTH_ARGS=""
fi

echo "Testing MQTT broker at $MQTT_HOST:$MQTT_PORT..."

# Test basic connectivity
echo "1. Testing basic connectivity..."
if mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" $AUTH_ARGS -t "test/connectivity" -m "test" -q 1; then
    echo "✅ Basic connectivity test passed"
else
    echo "❌ Basic connectivity test failed"
    exit 1
fi

# Test telemetry topic subscription
echo "2. Testing telemetry topic subscription..."
timeout 5 mosquitto_sub -h "$MQTT_HOST" -p "$MQTT_PORT" $AUTH_ARGS -t "drone/+/telemetry" -C 1 > /dev/null && \
    echo "✅ Telemetry topic subscription test passed" || \
    echo "⚠️  No telemetry messages received (this is normal if no sensors are running)"

echo "3. MQTT broker is ready for telemetry service!"
EOF

chmod +x scripts/test_mqtt.sh

echo "✅ MQTT broker setup complete!"
echo ""
echo "Next steps:"
echo "1. Test the broker: bash scripts/test_mqtt.sh"
echo "2. Start your telemetry service: python src/telemetry_service.py --dry-run"
echo "3. Monitor telemetry: mosquitto_sub -h localhost -p $MQTT_PORT $AUTH_ARGS -t 'drone/+/telemetry'"
