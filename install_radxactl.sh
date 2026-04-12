#!/usr/bin/env bash

set -e

SERVICE_NAME="radxactl"
INSTALL_DIR="/nms"
SCRIPT_NAME="radxactl.py"
SERVICE_FILE="/usr/lib/systemd/system/${SERVICE_NAME}.service"

# Defaults
SATA_12_ENABLE=25
SATA_34_ENABLE=26
FAN_PWM=13
FAN_SENSING=23

show_help() {
cat <<EOF
Usage: sudo ./install_radxactl.sh [OPTIONS]

Installs the SATA port fan control through Radxa Quad HAT.

Options:
  --sata12=PIN        GPIO pin to enable SATA ports 1-2 (default: 25)
  --sata34=PIN        GPIO pin to enable SATA ports 3-4 (default: 26)
  --fan-pwm=PIN       GPIO pin used for PWM fan control (default: 13)
  --fan-sensing=PIN   GPIO pin used for fan tachometer/sensing (default: 23)

  -h, -?, --help      Show this help message and exit

Examples:
  Install with default GPIO pins:
    sudo ./install_radxactl.sh

  Install with custom GPIO configuration:
    sudo ./install_radxactl.sh \\
      --sata12=17 \\
      --sata34=27 \\
      --fan-pwm=18 \\
      --fan-sensing=24

Notes:
  - The script installs the Python service into ${INSTALL_DIR}
  - Uses system Python (/usr/bin/python3)
  - The service is enabled to start automatically at boot
  - GPIO values are passed via environment variables to systemd
EOF
}

# Parse arguments
for arg in "$@"; do
    case $arg in
         -h|--help|-?)
            show_help
            exit 0
            ;;
        --sata12=*)
            SATA_12_ENABLE="${arg#*=}"
            ;;
        --sata34=*)
            SATA_34_ENABLE="${arg#*=}"
            ;;
        --fan-pwm=*)
            FAN_PWM="${arg#*=}"
            ;;
        --fan-sensing=*)
            FAN_SENSING="${arg#*=}"
            ;;
        *)
            echo "Unknown argument: $arg"
            exit 1
            ;;
    esac
done


if [ "$EUID" -ne 0 ]; then
    echo "Error: this script must be run as root."
    echo "Please run with sudo:"
    echo "  sudo $0 $*"
    exit 1
fi

echo "Installing with configuration:"
echo "  SATA_12_ENABLE=$SATA_12_ENABLE"
echo "  SATA_34_ENABLE=$SATA_34_ENABLE"
echo "  FAN_PWM=$FAN_PWM"
echo "  FAN_SENSING=$FAN_SENSING"

chmod +x "$INSTALL_DIR/$SCRIPT_NAME"

# Create systemd service
cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Radxa Controller Service
DefaultDependencies=no
After=local-fs.target
Before=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/${SCRIPT_NAME}
Restart=always
RestartSec=2

Environment=SATA_12_ENABLE=${SATA_12_ENABLE}
Environment=SATA_34_ENABLE=${SATA_34_ENABLE}
Environment=FAN_PWM=${FAN_PWM}
Environment=FAN_SENSING=${FAN_SENSING}

User=root

[Install]
WantedBy=multi-user.target
EOF

echo "Systemd service created at $SERVICE_FILE"

# Reload systemd
systemctl daemon-reexec
systemctl daemon-reload

# Enable and start
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo "Service enabled and started."

# Show status
systemctl status "$SERVICE_NAME" --no-pager