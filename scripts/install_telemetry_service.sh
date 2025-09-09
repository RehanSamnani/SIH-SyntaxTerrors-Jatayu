#!/bin/bash
"""
Installation script for telemetry service systemd unit.

This script:
- Copies the systemd unit file to the correct location
- Creates necessary directories
- Sets up log rotation
- Enables and starts the service
- Provides management commands

Usage:
    bash scripts/install_telemetry_service.sh [--enable] [--start]
"""

set -euo pipefail

# Parse arguments
ENABLE_SERVICE=false
START_SERVICE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --enable)
            ENABLE_SERVICE=true
            shift
            ;;
        --start)
            START_SERVICE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--enable] [--start]"
            echo "  --enable: Enable the service to start on boot"
            echo "  --start:  Start the service immediately"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "Installing telemetry service..."

# Check if running as root or with sudo
if [[ $EUID -eq 0 ]]; then
    echo "❌ Do not run this script as root. Use sudo only when necessary."
    exit 1
fi

# Verify we're in the project directory
if [[ ! -f "src/telemetry_service.py" ]]; then
    echo "❌ Please run this script from the project root directory"
    exit 1
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p /home/pi/drone/telemetry
mkdir -p /home/pi/drone/logs
mkdir -p /home/pi/sih

# Copy systemd unit file
echo "Installing systemd unit file..."
sudo cp scripts/telemetry.service /etc/systemd/system/

# Set proper permissions
sudo chmod 644 /etc/systemd/system/telemetry.service
sudo chown root:root /etc/systemd/system/telemetry.service

# Reload systemd daemon
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Create log rotation configuration
echo "Setting up log rotation..."
sudo tee /etc/logrotate.d/telemetry-service > /dev/null <<EOF
/home/pi/drone/telemetry/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 pi pi
    postrotate
        systemctl reload telemetry.service > /dev/null 2>&1 || true
    endscript
}

/home/pi/drone/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 pi pi
}
EOF

# Enable service if requested
if [[ "$ENABLE_SERVICE" == "true" ]]; then
    echo "Enabling telemetry service..."
    sudo systemctl enable telemetry.service
    echo "✅ Service enabled to start on boot"
fi

# Start service if requested
if [[ "$START_SERVICE" == "true" ]]; then
    echo "Starting telemetry service..."
    sudo systemctl start telemetry.service
    
    # Wait a moment and check status
    sleep 2
    if sudo systemctl is-active --quiet telemetry.service; then
        echo "✅ Telemetry service started successfully!"
    else
        echo "❌ Failed to start telemetry service"
        echo "Service status:"
        sudo systemctl status telemetry.service --no-pager
        exit 1
    fi
fi

# Display service information
echo ""
echo "Telemetry Service Installation Summary:"
echo "======================================"
echo "Service file: /etc/systemd/system/telemetry.service"
echo "Log directory: /home/pi/drone/telemetry/"
echo "Service logs: /home/pi/drone/logs/"
echo ""

# Display management commands
echo "Service Management Commands:"
echo "============================"
echo ""
echo "# Check service status:"
echo "sudo systemctl status telemetry.service"
echo ""
echo "# View service logs:"
echo "sudo journalctl -u telemetry.service -f"
echo ""
echo "# Start service:"
echo "sudo systemctl start telemetry.service"
echo ""
echo "# Stop service:"
echo "sudo systemctl stop telemetry.service"
echo ""
echo "# Restart service:"
echo "sudo systemctl restart telemetry.service"
echo ""
echo "# Enable service (start on boot):"
echo "sudo systemctl enable telemetry.service"
echo ""
echo "# Disable service:"
echo "sudo systemctl disable telemetry.service"
echo ""

# Create management script
echo "Creating management script..."
cat > scripts/manage_telemetry.sh <<'EOF'
#!/bin/bash
# Telemetry service management script

set -euo pipefail

SERVICE_NAME="telemetry.service"

case "${1:-status}" in
    status)
        echo "Telemetry Service Status:"
        sudo systemctl status "$SERVICE_NAME" --no-pager
        ;;
    start)
        echo "Starting telemetry service..."
        sudo systemctl start "$SERVICE_NAME"
        ;;
    stop)
        echo "Stopping telemetry service..."
        sudo systemctl stop "$SERVICE_NAME"
        ;;
    restart)
        echo "Restarting telemetry service..."
        sudo systemctl restart "$SERVICE_NAME"
        ;;
    enable)
        echo "Enabling telemetry service..."
        sudo systemctl enable "$SERVICE_NAME"
        ;;
    disable)
        echo "Disabling telemetry service..."
        sudo systemctl disable "$SERVICE_NAME"
        ;;
    logs)
        echo "Following telemetry service logs (Ctrl+C to exit):"
        sudo journalctl -u "$SERVICE_NAME" -f
        ;;
    logs-tail)
        echo "Last 50 lines of telemetry service logs:"
        sudo journalctl -u "$SERVICE_NAME" -n 50 --no-pager
        ;;
    test)
        echo "Testing telemetry service in dry-run mode..."
        cd /home/pi/sih
        source .venv/bin/activate
        python src/telemetry_service.py --dry-run --log-level DEBUG
        ;;
    *)
        echo "Usage: $0 {status|start|stop|restart|enable|disable|logs|logs-tail|test}"
        echo ""
        echo "Commands:"
        echo "  status     - Show service status"
        echo "  start      - Start the service"
        echo "  stop       - Stop the service"
        echo "  restart    - Restart the service"
        echo "  enable     - Enable service to start on boot"
        echo "  disable    - Disable service from starting on boot"
        echo "  logs       - Follow service logs in real-time"
        echo "  logs-tail  - Show last 50 lines of logs"
        echo "  test       - Run service in dry-run mode for testing"
        exit 1
        ;;
esac
EOF

chmod +x scripts/manage_telemetry.sh

echo "✅ Telemetry service installation complete!"
echo ""
echo "Quick start:"
echo "1. Test the service: bash scripts/manage_telemetry.sh test"
echo "2. Start the service: bash scripts/manage_telemetry.sh start"
echo "3. Monitor logs: bash scripts/manage_telemetry.sh logs"
