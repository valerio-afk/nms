#!/usr/bin/env bash

set -o errexit
set -o pipefail
set -o nounset

# ---------- Configuration ----------
SCRIPT_NAME="$(basename "$0")"
TIMESTAMP() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }    # UTC ISO timestamp
LOGFILE_DEFAULT="/var/log/system-setup.log"     # preferred location when run as root
LOGFILE_USER="$HOME/system-setup.log"           # fallback for non-root
# -----------------------------------

# Determine logfile based on privileges
if [ "$(id -u)" -eq 0 ]; then
  LOGFILE="$LOGFILE_DEFAULT"
else
  LOGFILE="$LOGFILE_USER"
fi

# Ensure logfile directory exists (if running as root) and touch file
mkdir -p "$(dirname "$LOGFILE")" 2>/dev/null || true
: >"$LOGFILE" 2>/dev/null || true

# Logging function
# Usage: log LEVEL "message"
# LEVEL is one of: INFO, WARN, ERROR, DEBUG
log() {
  local level="${1:-INFO}"
  shift
  local msg="$*"
  local ts
  ts="$(TIMESTAMP)"
  # add colors for interactive terminals (not in logfile)
  local color_reset="\033[0m"
  local color_info="\033[1;34m"   # bold blue
  local color_warn="\033[1;33m"   # bold yellow
  local color_err="\033[1;31m"    # bold red
  local color_dbg="\033[1;35m"    # bold magenta

  # choose color
  local color="$color_info"
  case "$level" in
    INFO) color="$color_info" ;;
    WARN) color="$color_warn" ;;
    ERROR) color="$color_err" ;;
    DEBUG) color="$color_dbg" ;;
    *) color="$color_info" ;;
  esac

  # Compose line
  local line="[$ts] [$SCRIPT_NAME] [$level] $msg"

  # Print to stdout/stderr with color if interactive
  if [ -t 1 ]; then
    if [ "$level" = "ERROR" ]; then
      printf "%b\n" "${color}${line}${color_reset}" >&2
    else
      printf "%b\n" "${color}${line}${color_reset}"
    fi
  else
    # non-interactive: no color
    if [ "$level" = "ERROR" ]; then
      printf "%s\n" "$line" >&2
    else
      printf "%s\n" "$line"
    fi
  fi

  # Append plain line to logfile
  printf "%s\n" "$line" >>"$LOGFILE" 2>/dev/null || true
}

# Run a command, log start/end and capture output to logfile
# Usage: run_and_log "description" command [args...]
run_and_log() {
  local desc="$1"; shift
  local cmd=( "$@" )
  log INFO "START: $desc — ${cmd[*]}"
  # run command, tee stdout+stderr to logfile while allowing user to see it
  if "${cmd[@]}" 2>&1 | tee -a "$LOGFILE"; then
    log INFO "OK: $desc"
    return 0
  else
    local rc=$?
    log ERROR "FAILED ($rc): $desc — see $LOGFILE for details"
    return $rc
  fi
}

# Trap unhandled errors
on_error() {
  local exit_code=$?
  log ERROR "Script exited abnormally with status $exit_code"
  exit "$exit_code"
}
trap on_error ERR

# ---------- Main Steps ----------
log INFO "Script started. Logfile: $LOGFILE"

# Detect apt command
if ! command -v apt-get >/dev/null 2>&1 && ! command -v apt >/dev/null 2>&1; then
  log ERROR "No apt/apt-get found. This script targets Debian/Ubuntu systems with apt."
  exit 2
fi

# Ensure package lists are up to date
DEBIAN_FRONTEND=noninteractive run_and_log "apt-get update" apt-get update

#---------------------------------------------------------------------
# python3 venv
#---------------------------------------------------------------------
VENV_DIR="/opt/python3"

log INFO "Installing python3-full package"
DEBIAN_FRONTEND=noninteractive run_and_log "apt-get install python3-full" \
  apt-get install -y python3-full

log INFO "Setting up Python virtual environment in $VENV_DIR"

if [ ! -d "$VENV_DIR" ]; then
  run_and_log "Creating directory $VENV_DIR" mkdir -p "$VENV_DIR"
else
  log INFO "Directory $VENV_DIR already exists"
fi

# Create virtual environment only if not present
if [ ! -f "$VENV_DIR/bin/activate" ]; then
  run_and_log "Creating virtual environment at $VENV_DIR" python3 -m venv "$VENV_DIR"
else
  log INFO "Virtual environment already exists at $VENV_DIR"
fi
#---------------------------------------------------------------------

#---------------------------------------------------------------------
# remote access services (ftp, sshd, etc...)
#---------------------------------------------------------------------
declare -a PKGS=(openssh-server vsftpd samba nfs-kernel-server)

log INFO "Planned server packages: ${PKGS[*]}"

# Map packages -> candidate systemd services to stop/disable/mask.
# We'll attempt to operate on each candidate service; failing to find one is fine.
declare -A SERVICES_MAP
SERVICES_MAP[openssh-server]="ssh.service ssh.socket"
SERVICES_MAP[vsftpd]="vsftpd.service"
# samba provides smbd and nmbd; modern Debian may use samba.service which manages both.
SERVICES_MAP[samba]="smbd.service nmbd.service samba-ad-dc.service samba.service winbind.service"
# nfs: handle common names
SERVICES_MAP[nfs-kernel-server]="nfs-server.service nfs-kernel-server.service rpcbind.service"

# Create temporary policy-rc.d to prevent packages from starting services at install time.
POLICY_RC_D="/usr/sbin/policy-rc.d"
POLICY_BACKUP=""
cleanup_policy() {
  # remove the temporary policy hook if we created it (and restore backup if existed)
  if [ -f "${POLICY_RC_D}.tmp_created" ]; then
    rm -f "$POLICY_RC_D" || true
    rm -f "${POLICY_RC_D}.tmp_created" || true
    log INFO "Removed temporary $POLICY_RC_D"
  elif [ -n "$POLICY_BACKUP" ] && [ -f "$POLICY_BACKUP" ]; then
    mv -f "$POLICY_BACKUP" "$POLICY_RC_D" || true
    log INFO "Restored original $POLICY_RC_D from backup"
  fi
}
trap cleanup_policy EXIT

# If policy-rc.d exists, back it up; otherwise create minimal hook to block starts.
if [ -e "$POLICY_RC_D" ]; then
  POLICY_BACKUP="$(mktemp --tmpdir policyrcd.backup.XXXX)"
  cp -a "$POLICY_RC_D" "$POLICY_BACKUP"
  log INFO "Existing $POLICY_RC_D backed up to $POLICY_BACKUP"
else
  cat >"$POLICY_RC_D" <<'EOF'
#!/bin/sh
# policy-rc.d to prevent packages from starting services during apt install
# Return 101 to indicate action is not allowed.
exit 101
EOF
  chmod +x "$POLICY_RC_D"
  # mark that we created it so cleanup removes it
  touch "${POLICY_RC_D}.tmp_created"
  log INFO "Temporary $POLICY_RC_D created to prevent auto-start of services"
fi

# Update package lists
DEBIAN_FRONTEND=noninteractive run_and_log "apt-get update" apt-get update -y

# Install packages (no recommends for minimal footprint)
DEBIAN_FRONTEND=noninteractive run_and_log "apt-get install ${PKGS[*]}" \
  apt-get install --no-install-recommends -y "${PKGS[@]}"

# Now ensure we explicitly stop/disable/mask relevant services so they cannot run
log INFO "Stopping/disabling/masking related systemd services"

for pkg in "${PKGS[@]}"; do
  svc_list="${SERVICES_MAP[$pkg]:-}"
  if [ -z "$svc_list" ]; then
    log WARN "No service list known for package: $pkg — skipping service mask step for it"
    continue
  fi

  for svc in $svc_list; do
    # check if system knows this unit; if not, still attempt to mask (mask will create symlink)
    if systemctl list-unit-files --type=service --no-legend | grep -q -F "$svc"; then
      log INFO "Unit $svc found; stopping, disabling and masking it"
    else
      log INFO "Unit $svc may not exist on this system; we will still attempt to stop/disable/mask (safe no-op)"
    fi

    # stop if active (ignore failures)
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
      run_and_log "systemctl stop $svc" systemctl stop "$svc" || true
    else
      log DEBUG "$svc not active"
    fi

    # disable (ignore failures)
    run_and_log "systemctl disable --now $svc" systemctl disable --now "$svc" || true

    # mask to prevent any manual or indirect starts (can be undone with 'systemctl unmask')
    run_and_log "systemctl mask $svc" systemctl mask "$svc" || true
  done
done

# As a belt-and-braces: ensure SSH (if installed) is not set to start by default via update-rc.d
if command -v update-rc.d >/dev/null 2>&1; then
  for pkg in "${PKGS[@]}"; do
    # best-effort: remove any init scripts symlinks (no-op if none)
    run_and_log "update-rc.d -f ${pkg} remove (best-effort)" update-rc.d -f "${pkg}" remove || true
  done
fi

# Remove the temporary policy-rc.d (or restore original). cleanup_policy will be run by trap on EXIT,
# but call explicitly now to restore system state before script finishes.
cleanup_policy
#---------------------------------------------------------------------

#---------------------------------------------------------------------
# network-manager
#--------------------------------------------------------------------
log INFO "Installing network-manager and setting raspi-config to use it"

# Install network-manager
DEBIAN_FRONTEND=noninteractive run_and_log "apt-get install network-manager" \
  apt-get install -y network-manager

# Run raspi-config to set network configuration mode to Network Manager (option 2)
if command -v raspi-config >/dev/null 2>&1; then
  run_and_log "raspi-config nonint do_netconf 2" raspi-config nonint do_netconf 2
  log INFO "raspi-config network mode set to Network Manager"
else
  log WARN "raspi-config not found — skipping raspi network configuration"
fi


#---------------------------------------------------------------------
# Install Docker and pull Redis image
#--------------------------------------------------------------------

log INFO "Installing Docker engine and pulling Redis image"

# Install Docker (minimal)
DEBIAN_FRONTEND=noninteractive run_and_log "apt-get install docker.io" \
  apt-get install -y docker.io

# Pull Redis container image
if command -v docker >/dev/null 2>&1; then
  run_and_log "Pulling Redis Docker image" docker pull redis
  log INFO "Redis image downloaded successfully"
else
  log ERROR "Docker not found after installation — cannot pull Redis image"
fi


# ---------- Run Redis Docker container with restart policy ----------
CONTAINER_NAME="redis-server"
IMAGE_NAME="redis"
PORT_MAPPING="6379:6379"

log INFO "Checking if Docker container '$CONTAINER_NAME' is already running"

if command -v docker >/dev/null 2>&1; then
  if docker ps --filter "name=^/${CONTAINER_NAME}$" --filter "status=running" --format '{{.Names}}' | grep -qw "$CONTAINER_NAME"; then
    log INFO "Docker container '$CONTAINER_NAME' is already running, skipping start"
  else
    # Check if container exists but is stopped (to avoid naming conflicts)
    if docker ps -a --filter "name=^/${CONTAINER_NAME}$" --format '{{.Names}}' | grep -qw "$CONTAINER_NAME"; then
      log INFO "Docker container '$CONTAINER_NAME' exists but not running, removing it first"
      run_and_log "docker rm $CONTAINER_NAME" docker rm "$CONTAINER_NAME"
    fi

    log INFO "Starting Docker container '$CONTAINER_NAME' with restart=unless-stopped"
    run_and_log "docker run -d --name $CONTAINER_NAME -p $PORT_MAPPING --restart unless-stopped $IMAGE_NAME" \
      docker run -d --name "$CONTAINER_NAME" -p "$PORT_MAPPING" --restart unless-stopped "$IMAGE_NAME"
  fi
else
  log ERROR "Docker command not found; cannot run Redis container"
fi

#---------------------------------------------------------------------
# Create www-data user/group for web server with docker access
#--------------------------------------------------------------------

log INFO "Creating www-data user and group with no login and docker group access"

# Create www-data group if it doesn't exist
if ! getent group www-data >/dev/null; then
  run_and_log "Creating group www-data" groupadd --system www-data
else
  log INFO "Group www-data already exists"
fi

# Create www-data user if it doesn't exist
if ! id -u www-data >/dev/null 2>&1; then
  run_and_log "Creating system user www-data with no login shell and no home directory" \
    useradd --system --no-create-home --shell /usr/sbin/nologin --gid www-data www-data
else
  log INFO "User www-data already exists"
fi

# Add www-data user to docker group if docker group exists
if getent group docker >/dev/null; then
  if id -nG www-data | grep -qw docker; then
    log INFO "User www-data is already in docker group"
  else
    run_and_log "Adding www-data user to docker group" usermod -aG docker www-data
  fi
else
  log WARN "Docker group does not exist yet. Make sure docker package is installed first."
fi


#---------------------------------------------------------------------
# Create sudodaemon user with passwordless sudo and no login
#--------------------------------------------------------------------

log INFO "Creating sudodaemon user with no login, no home, and passwordless sudo"

# Create sudodaemon group if it doesn't exist (system group)
if ! getent group sudodaemon >/dev/null; then
  run_and_log "Creating group sudodaemon" groupadd --system sudodaemon
else
  log INFO "Group sudodaemon already exists"
fi

# Create sudodaemon user if it doesn't exist
if ! id -u sudodaemon >/dev/null 2>&1; then
  run_and_log "Creating system user sudodaemon with no login shell and no home directory" \
    useradd --system --no-create-home --shell /usr/sbin/nologin --gid sudodaemon -G www-data sudodaemon
else
  log INFO "User sudodaemon already exists"
fi

# Setup passwordless sudo for sudodaemon via sudoers.d file
SUDOERS_FILE="/etc/sudoers.d/sudodaemon"
if [ ! -f "$SUDOERS_FILE" ]; then
  echo "sudodaemon ALL=(ALL) NOPASSWD:ALL" > "$SUDOERS_FILE"
  chmod 440 "$SUDOERS_FILE"
  log INFO "Passwordless sudo configured for sudodaemon in $SUDOERS_FILE"
else
  log INFO "Passwordless sudo file $SUDOERS_FILE already exists"
fi

#---------------------------------------------------------------------
# Installing python3 requirements
#--------------------------------------------------------------------

REQ_FILE="/nms/requirements.txt"
if [ -f "$REQ_FILE" ]; then
  if [ -f "$VENV_DIR/bin/pip" ]; then
    log INFO "Installing Python packages from $REQ_FILE inside virtualenv at $VENV_DIR"
    run_and_log "Virtualenv pip install" "$VENV_DIR/bin/pip" install -r "$REQ_FILE"
  else
    log ERROR "pip not found inside virtualenv at $VENV_DIR"
  fi
else
  log WARN "Requirements file $REQ_FILE not found, skipping virtualenv pip install"
fi


#---------------------------------------------------------------------
# Configuring systemd
#--------------------------------------------------------------------

# ---------- Create systemd service for nmswebapp ----------
SERVICE_NAME="nmswebapp"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

log INFO "Creating systemd service for $SERVICE_NAME"

# Write the service file (overwrite if exists)
SECRET_KEY=$(openssl rand -hex 32)
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=NMS Web App Service
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/nms
Environment="NMS_SECRET_KEY=${SECRET_KEY}"
ExecStart=/opt/python3/bin/python app.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF


run_and_log "systemctl daemon-reload" systemctl daemon-reload
run_and_log "systemctl enable $SERVICE_NAME" systemctl enable "$SERVICE_NAME"
run_and_log "systemctl start $SERVICE_NAME" systemctl start "$SERVICE_NAME"

log INFO "Systemd service $SERVICE_NAME created and enabled "

# ---------- Create systemd service for celeryworker ----------
SERVICE_NAME="celeryworker"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

log INFO "Creating systemd service for $SERVICE_NAME"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Celery Worker Service for NMS
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/nms
ExecStart=/opt/python3/bin/celery -A app.celery_app worker
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

run_and_log "systemctl daemon-reload" systemctl daemon-reload
run_and_log "systemctl enable $SERVICE_NAME" systemctl enable "$SERVICE_NAME"
run_and_log "systemctl start $SERVICE_NAME" systemctl start "$SERVICE_NAME"

log INFO "Systemd service $SERVICE_NAME created and enabled "

# ---------- Create systemd service for sudo_daemon ----------
SERVICE_NAME="sudodaemon"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

log INFO "Creating systemd service for $SERVICE_NAME"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Sudo Daemon Service
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=sudodaemon
Group=sudodaemon
WorkingDirectory=/nms
ExecStart=/opt/python3/bin/python sudo_daemon.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

run_and_log "systemctl daemon-reload" systemctl daemon-reload
run_and_log "systemctl enable $SERVICE_NAME" systemctl enable "$SERVICE_NAME"
run_and_log "systemctl start $SERVICE_NAME" systemctl start "$SERVICE_NAME"

log INFO "Systemd service $SERVICE_NAME created and enabled "

#---------------------------------------------------------------------
# Setting the right permissions to /nms
#--------------------------------------------------------------------


DIR="/nms"

if [ -d "$DIR" ]; then
  log INFO "Setting ownership of $DIR to root:www-data"
  run_and_log "chown root:www-data $DIR" chown root:www-data "$DIR"

  log INFO "Setting permissions of $DIR to 770"
  run_and_log "chmod 770 $DIR" chmod 770 "$DIR"
else
  log WARN "Directory $DIR does not exist, skipping permission and ownership changes"
fi


is_virtualbox() {
    if command -v dmidecode >/dev/null 2>&1; then
        local product_name
        product_name=$(dmidecode -s system-product-name 2>/dev/null || true)
        if [[ "$product_name" == *"VirtualBox"* ]]; then
            return 0
        fi
    fi
    return 1
}

if is_virtualbox; then
    log INFO "Running inside VirtualBox - adding www-data to vboxsf group"
    run_and_log "Add www-data to vboxsf group" usermod -aG vboxsf www-data
    run_and_log "Add sudodaemon to vboxsf group" usermod -aG vboxsf sudodaemon
else
    log INFO "Not running inside VirtualBox - skipping group modification"
fi


#---------------------------------------------------------------------
# ZFS
#--------------------------------------------------------------------

# ---------- Enable contrib and non-free repositories if not enabled ----------
log INFO "Adding contrib and non-free components  in apt sources"

if grep -E '^[^#]*deb ' /etc/apt/sources.list | grep -vqE 'contrib'; then
  log INFO "Adding contrib and non-free to sources.list entries"
  sed -i -r 's/^(deb\s+[^ ]+\s+[^ ]+\s+)(main)(.*)/\1main contrib non-free\3/' /etc/apt/sources.list
else
  log INFO "contrib and non-free components already enabled"
fi

apt update

log INFO "Installing ZFS packages"

DEBIAN_FRONTEND=noninteractive run_and_log "apt-get install zfs-dkms zfsutils-linux" \
  apt-get install -y zfs-dkms zfsutils-linux

log INFO "Loading ZFS kernel module with modprobe"
if modprobe zfs; then
  log INFO "ZFS kernel module loaded successfully"
else
  log ERROR "Failed to load ZFS kernel module via modprobe"
fi

exit 0
