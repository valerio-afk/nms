#!/usr/bin/env bash

set -o errexit      # Exit on error
set -o nounset      # Error on undefined variables

#Globals
PYTHON_VENV_PATH="/opt/python3"
LOG_FILE="/var/log/nms.log"
REPO_URL="https://github.com/valerio-afk/nms"
DEST_DIR="/nms"

#IFM_REPO_URL="https://github.com/misterunknown/ifm.git"
#IFM_REPO_DIR="/opt/ifm"

PACKAGES=(
    python3-full
    network-manager
    nginx
    sudo
    docker.io
    smartmontools
    "linux-headers-$(uname -r)"
    zfs-dkms
    zfsutils-linux
    openssh-server
    vsftpd
    samba
    nfs-kernel-server
    wireguard
    rsync
    unp
    nodejs
    npm
    git
)

SERVICES_TO_DISABLE=(
    vsftpd
    smbd
    nmbd
    rpcbind
    nfs-server
    networking
)

# ----- Colour codes -----
BLUE='\033[1;34m'
YELLOW='\033[1;33m'
RED='\033[1;31m'
NC='\033[0m'  # No Colour


# ----- Logging functions -----

# ----- Logging functions -----
log_info() {
    # Terminal output in blue
    echo -e "${BLUE}[INFO]  $(date '+%Y-%m-%d %H:%M:%S') - $1${NC}"
    # Log file plain text
    echo "[INFO]  $(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]  $(date '+%Y-%m-%d %H:%M:%S') - $1${NC}"
    echo "[WARN]  $(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $1${NC}" >&2
    echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}


# ----- Error handler -----

error_exit() {
    log_error "$1"
    exit 1
}

# ------- APT Wrapper

install_packages() {

    local packages=("$@")

    if [[ ${#packages[@]} -eq 0 ]]; then
        log_warn "No packages provided for installation."
        return 0
    fi

    log_info "Updating apt package index..."
    if ! apt-get update -y >> "$LOG_FILE" 2>&1; then
        error_exit "Failed to update package index."
    fi

    echo "zfs-dkms zfs-dkms/note-incompatible-licenses note" | debconf-set-selections

    log_warn "By installing this software, you are accepting the terms of CDDL license of ZFS and related tools."
    DEBIAN_FRONTEND=noninteractive
    export DEBIAN_FRONTEND

    log_info "Installing packages: ${packages[*]}"
    if ! apt-get install -y "${packages[@]}" >> "$LOG_FILE" 2>&1; then
        error_exit "Package installation failed."
    fi

    log_info "Package installation completed successfully."
}

add_contrib_nonfree() {
    local sources_file="/etc/apt/sources.list"

    log_info "Backing up current sources.list to ${sources_file}.bak"
    if ! cp "$sources_file" "${sources_file}.bak"; then
        error_exit "Failed to backup sources.list"
    fi

    log_info "Adding 'contrib' and 'non-free' to sources.list entries..."
    # Loop through lines starting with deb and not already containing contrib/non-free
    while read -r line; do
        if [[ "$line" =~ ^deb && ! "$line" =~ contrib ]] || [[ "$line" =~ ^deb && ! "$line" =~ non-free ]]; then
            # Add contrib and non-free only if missing
            new_line=$(echo "$line" | sed -E 's/(main)/\1 contrib non-free/')
            # Replace line in file safely
            sed -i "s|^${line}$|${new_line}|" "$sources_file"
        fi
    done < "$sources_file"

    log_info "Updating apt package index after adding contrib/non-free..."
    if ! apt-get update -y >> "$LOG_FILE" 2>&1; then
        error_exit "apt-get update failed after modifying sources.list"
    fi

    log_info "'contrib' and 'non-free' successfully added and package index updated."
}

manage_services() {
    local action="$1"   # "stop" or "disable"
    shift
    local services=("$@")

    for svc in "${services[@]}"; do
        if systemctl list-unit-files | grep -q "^${svc}.service"; then
            if [[ "$action" == "stop" ]]; then
                log_info "Stopping service: $svc"
                if systemctl is-active --quiet "$svc"; then
                    if ! systemctl stop "$svc"; then
                        log_warn "Failed to stop $svc"
                    else
                        log_info "$svc stopped successfully"
                    fi
                else
                    log_info "$svc is not running"
                fi
            elif [[ "$action" == "disable" ]]; then
                log_info "Disabling service: $svc"
                if ! systemctl disable "$svc" >> "$LOG_FILE" 2>&1; then
                    log_warn "Failed to disable $svc"
                else
                    log_info "$svc disabled successfully"
                fi
            else
                log_warn "Unknown action: $action for service $svc"
            fi
        else
            log_warn "Service $svc not found on this system"
        fi
    done
}

# Python stuff
setup_python_venv() {
    local venv_path="$1"
    local python_bin

    if [[ -z "$venv_path" ]]; then
        error_exit "No path provided for Python virtual environment"
    fi

    # Determine python binary
    if command -v python3 &>/dev/null; then
        python_bin=$(command -v python3)
    else
        error_exit "python3 is not installed, cannot create virtual environment"
    fi

    log_info "Setting up Python virtual environment at $venv_path using $python_bin"

    # Create target directory if it doesn't exist
    if [[ ! -d "$venv_path" ]]; then
        if ! mkdir -p "$venv_path"; then
            error_exit "Failed to create directory $venv_path"
        fi
        log_info "Created directory $venv_path"
    else
        log_info "Directory $venv_path already exists"
    fi

    # Check if venv already exists
    if [[ -f "$venv_path/bin/activate" ]]; then
        log_warn "Virtual environment already exists at $venv_path"
    else
        if ! "$python_bin" -m venv "$venv_path" >> "$LOG_FILE" 2>&1; then
            error_exit "Failed to create Python virtual environment"
        fi
        log_info "Python virtual environment created successfully at $venv_path"
    fi

    # Upgrade pip inside the venv
    log_info "Upgrading pip in virtual environment..."
    if ! "$venv_path/bin/pip" install --upgrade pip >> "$LOG_FILE" 2>&1; then
        log_warn "Failed to upgrade pip in $venv_path"
    else
        log_info "pip upgraded successfully in $venv_path"
    fi
}

install_requirements() {
    local repo_dir="$1"          # Parent directory containing requirements.txt
    local venv_path="$2"         # Path to Python virtual environment

    if [[ -z "$repo_dir" || -z "$venv_path" ]]; then
        log_error "Both repository directory and Python venv path must be provided"
        return 1
    fi

    local req_file="$repo_dir/requirements.txt"

    if [[ ! -f "$req_file" ]]; then
        log_warn "requirements.txt not found at $req_file. Skipping pip install."
        return 0
    fi

    # Use pip from the virtual environment
    local pip_bin="$venv_path/bin/pip"

    if [[ ! -x "$pip_bin" ]]; then
        log_error "pip executable not found in virtual environment at $pip_bin"
        return 1
    fi

    log_info "Installing Python packages from $req_file into venv $venv_path..."

    if ! "$pip_bin" install -r "$req_file" >> "$LOG_FILE" 2>&1; then
        log_error "Failed to install Python packages from $req_file"
        return 1
    fi

    log_info "Python packages from $req_file installed successfully"
}

install_editable_package() {
    local package_dir="$1"    # Path to the Python package (e.g., /nms/nms_shared)
    local venv_path="$2"      # Path to Python virtual environment

    if [[ -z "$package_dir" || -z "$venv_path" ]]; then
        log_error "Both package directory and Python venv path must be provided"
        return 1
    fi

    if [[ ! -d "$package_dir" ]]; then
        log_warn "Package directory '$package_dir' does not exist. Skipping editable install."
        return 0
    fi

    local pip_bin="$venv_path/bin/pip"

    if [[ ! -x "$pip_bin" ]]; then
        log_error "pip executable not found in virtual environment at $pip_bin"
        return 1
    fi

    log_info "Installing Python package in editable mode from $package_dir..."

    if ! "$pip_bin" install -e "$package_dir" >> "$LOG_FILE" 2>&1; then
        log_error "Failed to install package in editable mode from $package_dir"
        return 1
    fi

    log_info "Editable Python package installed successfully from $package_dir"
}

#Git stuff
clone_git_repo() {
    local repo_url="$1"
    local dest_dir="$2"   # Where to clone the repo

    if [[ -z "$repo_url" ]]; then
        log_info "No Git repository URL provided, skipping clone."
        return 0
    fi

    if [[ -z "$dest_dir" ]]; then
        error_exit "No destination directory provided for git clone."
    fi

    log_info "Cloning Git repository $repo_url into $dest_dir..."

    # If directory exists and is not empty, skip or warn
    if [[ -d "$dest_dir" && "$(ls -A "$dest_dir")" ]]; then
        log_warn "Destination directory $dest_dir already exists and is not empty. Skipping clone."
        return 0
    fi

    # Attempt the clone
    if ! git clone "$repo_url" "$dest_dir" >> "$LOG_FILE" 2>&1; then
        log_error "Failed to clone repository $repo_url"
    else
        log_info "Repository cloned successfully into $dest_dir"
    fi
}

# Raspberry Pi stuff

debian_network_manager() {
  local NM_CONF="/etc/NetworkManager/NetworkManager.conf"

  if [[ -z "$NM_CONF" ]]; then
      log_error "Network Manager Configuration file not found. Skipping..."
      return 0
  fi

  cat <<EOF | tee "$NM_CONF" >/dev/null
[main]
plugins=ifupdown,keyfile

[ifupdown]
managed=true
EOF

  systemctl restart NetworkManager

  log_info "NetworkManager configured successfully"
}

enable_network_manager() {
    log_info "Enabling NetworkManager via raspi-config..."

    # Check if raspi-config is installed
    if ! command -v raspi-config &>/dev/null; then
        log_warn "raspi-config is not installed. Trying another way."
        debian_network_manager
        return 0
    fi

    # Non-interactive mode to enable NetworkManager
    if ! raspi-config nonint do_network_manager 0 >> "$LOG_FILE" 2>&1; then
        log_error "Failed to enable NetworkManager via raspi-config"
        return 1
    else
        log_info "NetworkManager enabled successfully via raspi-config"
    fi

    # Optional: restart NetworkManager to apply changes
    if systemctl is-active --quiet NetworkManager; then
        log_info "Restarting NetworkManager service..."
        if ! systemctl restart NetworkManager >> "$LOG_FILE" 2>&1; then
            log_warn "Failed to restart NetworkManager service"
        else
            log_info "NetworkManager service restarted successfully"
        fi
    else
        log_info "NetworkManager service is not running yet, it will start at next boot"
    fi
}

# Docker stuff
install_redis_docker() {
    local container_name="redis-server"
    local image_name="redis"
    local port_mapping="6379:6379"
    local restart_policy="unless-stopped"

    # Check if Docker is installed
    if ! command -v docker &>/dev/null; then
        log_error "Docker is not installed. Cannot run Redis container."
        return 1
    fi

    log_info "Pulling Redis Docker image ($image_name)..."
    if ! docker pull "$image_name" >> "$LOG_FILE" 2>&1; then
        log_error "Failed to pull Redis image $image_name"
        return 1
    fi

    # Check if container already exists
    if docker ps -a --format '{{.Names}}' | grep -qw "$container_name"; then
        log_warn "Container $container_name already exists. Attempting to start it..."
        if ! docker start "$container_name" >> "$LOG_FILE" 2>&1; then
            log_error "Failed to start existing container $container_name"
            return 1
        fi
        log_info "Container $container_name started successfully"
    else
        log_info "Creating and starting Redis container $container_name..."
        if ! docker run -d \
            --name "$container_name" \
            -p "$port_mapping" \
            --restart "$restart_policy" \
            "$image_name" >> "$LOG_FILE" 2>&1; then
            log_error "Failed to create and run Redis container $container_name"
            return 1
        fi
        log_info "Redis container $container_name is running on port $port_mapping with restart policy '$restart_policy'"
    fi
}

build_docker_image() {
    local repo_dir="$1"     # Path to the repository to build from
    local image_name="$2"   # Docker image name with optional tag

    if [[ -z "$repo_dir" || -z "$image_name" ]]; then
        log_error "Directory and image name must be provided."
        return 1
    fi

    if [[ ! -d "$repo_dir" ]]; then
        log_error "Directory '$repo_dir' does not exist."
        return 1
    fi

    # Check if Docker is installed
    if ! command -v docker &>/dev/null; then
        log_error "Docker is not installed. Cannot build Docker image."
        return 1
    fi

    log_info "Building Docker image '$image_name' from repository at $repo_dir..."

    if ! docker build -t "$image_name" "$repo_dir" >> "$LOG_FILE" 2>&1; then
        log_error "Failed to build Docker image '$image_name' from $repo_dir"
        return 1
    fi

    log_info "Docker image '$image_name' built successfully from $repo_dir"
}


# Sysadmin stuff

create_group() {
    local GROUP_NAME="$1"

    if [[ -z "$GROUP_NAME" ]]; then
        log_error "No group name provided to create_group"
        return 1
    fi

    if getent group "$GROUP_NAME" >/dev/null 2>&1; then
        log_info "Group '$GROUP_NAME' already exists. Skipping creation."
        return 0
    fi

    log_info "Creating group '$GROUP_NAME'..."

    if groupadd "$GROUP_NAME" >> "$LOG_FILE" 2>&1; then
        log_info "Group '$GROUP_NAME' created successfully."
    else
        log_error "Failed to create group '$GROUP_NAME'."
        return 1
    fi
}


manage_users() {
    log_info "Starting user management..."

    # --- 1. www-data ---
    if id "www-data" &>/dev/null; then
        log_info "User 'www-data' already exists"
        usermod -s /usr/sbin/nologin www-data
        log_info "Login shell for www-data has been changed to nologin"
    else
        log_info "Creating user 'www-data' with no login..."
        if ! useradd -M -r -s /usr/sbin/nologin www-data >> "$LOG_FILE" 2>&1; then
            log_warn "Failed to create user 'www-data'"
        else
            log_info "User 'www-data' created successfully"
        fi
    fi

    # --- 2. backend ---
    if id "backend" &>/dev/null; then
        log_info "User 'backend' already exists"
    else
        log_info "Creating user 'backend' with no login and sudo group..."
        if ! useradd -M -s /usr/sbin/nologin -G sudo backend >> "$LOG_FILE" 2>&1; then
            log_warn "Failed to create user 'backend'"
        else
            log_info "User 'backend' created successfully and added to sudo group"
        fi
    fi

    # --- 2.5 create users and sambashare groups
    create_group "users"
    create_group "sambashare"

    # --- 3. Check UID 1000 ---
    uid1000_user=$(getent passwd 1000 | cut -d: -f1 || true)

    if [[ -z "$uid1000_user" ]]; then
        log_info "No user with UID 1000 found. Creating user 'user'..."
        if ! useradd -M -s /bin/bash user >> "$LOG_FILE" 2>&1; then
            log_warn "Failed to create user 'user'"
        else
            log_info "User 'user' created successfully"
        fi
    else
        log_info "User with UID 1000 found: $uid1000_user. Renaming to 'user'..."
        if ! usermod -l user "$uid1000_user" >> "$LOG_FILE" 2>&1; then
            log_warn "Failed to rename $uid1000_user to 'user'"
        else
            log_info "User $uid1000_user renamed to 'user'"

            uid1000_homedir=$(getent passwd 1000 | cut -d: -f6 || true)

            if [[ -d "$uid1000_homedir" ]]; then
              rm -rf ${uid1000_homedir}
              log_warn "Home directory ${uid1000_homedir} deleted"
            fi

        fi

        log_info "Adding 'user' to group 'users'..."
        if ! usermod -aG users user >> "$LOG_FILE" 2>&1; then
            log_warn "Failed to add 'user' to group 'users'"
        else
            log_info "'user' added to group 'users' successfully"
        fi
    fi


    log_info "User management completed."
}

add_nopasswd_sudo() {
    local user="$1"
    local file="/etc/sudoers.d/$user"

    log_info "Adding backend to sudoers"

    # Create the sudoers file safely
    echo "$user ALL=(ALL) NOPASSWD: ALL" | tee "$file" > /dev/null

    # Set the correct permissions
    chmod 440 "$file"

    log_info "Passwordless sudo enabled for user '$user'."
}

set_repo_permissions_wwwdata() {
    local repo_dir="$1"
    local backend_user="backend"
    local group_name="www-data"

    if [[ ! -d "$repo_dir" ]]; then
        log_warn "Repository directory '$repo_dir' does not exist. Skipping permission setup."
        return 0
    fi

    # Add backend to www-data group
    if id "$backend_user" &>/dev/null; then
        log_info "Adding user '$backend_user' to group '$group_name'"
        if ! usermod -aG "$group_name" "$backend_user" >> "$LOG_FILE" 2>&1; then
            log_warn "Failed to add user '$backend_user' to group '$group_name'"
        else
            log_info "User '$backend_user' added to group '$group_name' successfully"
        fi
    else
        log_warn "User '$backend_user' does not exist, skipping"
    fi

    # Set ownership and group permissions on /nms
    log_info "Setting ownership to root:$group_name and read access for group on $repo_dir"
    if ! chown -R root:"$group_name" "$repo_dir" >> "$LOG_FILE" 2>&1; then
        log_warn "Failed to change ownership of $repo_dir"
    fi

    # Set permissions: owner rwx, group rwx, others ---
    if ! chmod -R 770 "$repo_dir" >> "$LOG_FILE" 2>&1; then
        log_warn "Failed to set permissions on $repo_dir"
    else
        log_info "Permissions set: owner=root, group=$group_name, mode=750"
    fi
}

set_nms_json_permissions() {
    local file_path="$1/nms.json"
    local backend_user="backend"

    if [[ ! -f "$file_path" ]]; then
        log_warn "File $file_path does not exist. Skipping special permissions setup."
        return 0
    fi

    log_info "Setting exclusive read/write access for '$backend_user' on $file_path"

    # Change ownership to backend
    if ! chown "$backend_user":"$backend_user" "$file_path" >> "$LOG_FILE" 2>&1; then
        log_warn "Failed to set owner of $file_path to $backend_user"
    else
        log_info "Owner of $file_path set to $backend_user successfully"
    fi

    # Set file permissions to 600 (rw for owner only)
    if ! chmod 600 "$file_path" >> "$LOG_FILE" 2>&1; then
        log_warn "Failed to set permissions on $file_path"
    else
        log_info "Permissions set: owner=rwx, others=no access for $file_path"
    fi
}

generate_secret_key() {
    # Generate a 32-character random alphanumeric string
    NMS_SECRET_KEY=$(openssl rand -base64 45 | tr -dc 'A-Za-z0-9')
    log_info "Generated random NMS_SECRET_KEY"
}

create_frontend_service() {
    local venv_path="$2"   # e.g., /opt/python3
    local app_dir="$1"
    local service_file="/usr/lib/systemd/system/nmswebapp.service"

    generate_secret_key  # Populate $NMS_SECRET_KEY

    log_info "Creating systemd service for frontend Flask app at $service_file"

    cat <<EOF | tee "$service_file" >/dev/null
[Unit]
Description=NMS Web App Service
After=nmsbackend.service
Requires=nmsbackend.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=$app_dir
Environment="PATH=$venv_path/bin:$PATH"
Environment="NMS_SECRET_KEY=$NMS_SECRET_KEY"
ExecStart=$venv_path/bin/uvicorn frontend.app:frontend_app --host 127.0.0.1 --port 8080 --reload
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    log_info "Reloading systemd daemon..."
    systemctl daemon-reload >> "$LOG_FILE" 2>&1

    log_info "Enabling and starting nmswebapp service..."
    systemctl enable nmswebapp >> "$LOG_FILE" 2>&1
    systemctl restart nmswebapp >> "$LOG_FILE" 2>&1

    log_info "Frontend Flask service setup complete"
}

create_backend_service() {
    local venv_path="$2"    # Path to virtualenv
    local app_dir="$1"
    local service_file="/usr/lib/systemd/system/nmsbackend.service"

    generate_secret_key  # Populate $NMS_SECRET_KEY

    log_info "Creating systemd service for backend FastAPI app at $service_file"

    cat <<EOF | tee "$service_file" >/dev/null
[Unit]
Description=NMS Backend FastAPI Service
After=docker.service
Requires=docker.service

[Service]
User=backend
Group=backend
WorkingDirectory=$app_dir
Environment="PATH=$venv_path/bin:$PATH"
Environment="NMS_SECRET_KEY=$NMS_SECRET_KEY"
ExecStart=$venv_path/bin/uvicorn backend_server.backend:app --host 127.0.0.1 --port 8081 --reload
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    log_info "Reloading systemd daemon..."
    systemctl daemon-reload >> "$LOG_FILE" 2>&1

    log_info "Enabling and starting nms-backend service..."
    systemctl enable nmsbackend >> "$LOG_FILE" 2>&1
    systemctl restart nmsbackend >> "$LOG_FILE" 2>&1

    log_info "Backend FastAPI service setup complete with NMS_SECRET_KEY"
}

# Network Stuff

configure_wireguard() {
    local WG_DIR="/etc/wireguard"
    local WG_CONF="$WG_DIR/wg0.conf"
    local SERVER_PRIVATE_KEY_FILE="/root/vpn_private.key"
    local SERVER_PUBLIC_KEY_FILE="/root/vpn_public.key"

    log_info "Generating WireGuard server keys..."

    umask 077

    if ! wg genkey | tee "$SERVER_PRIVATE_KEY_FILE" | wg pubkey > "$SERVER_PUBLIC_KEY_FILE" 2>>"$LOG_FILE"; then
        log_error "Failed to generate WireGuard keys"
        return 1
    fi

    chmod 600 "$SERVER_PRIVATE_KEY_FILE" "$SERVER_PUBLIC_KEY_FILE"

    local SERVER_PRIVATE_KEY
    SERVER_PRIVATE_KEY=$(cat "$SERVER_PRIVATE_KEY_FILE")

    log_info "Creating WireGuard configuration at $WG_CONF"

    mkdir -p "$WG_DIR"
    chmod 700 "$WG_DIR"

    cat <<EOF | tee "$WG_CONF" >/dev/null
[Interface]
Address = 10.0.0.1/24
PrivateKey = $SERVER_PRIVATE_KEY
ListenPort = 51820
EOF

    chmod 600 "$WG_CONF"

    systemctl daemon-reload >> "$LOG_FILE" 2>&1

    log_info "WireGuard configuration created."
}

install_noip_duc() {
    local DOWNLOAD_URL="https://www.noip.com/download/linux/latest"
    local TMP_DIR="/tmp/noip-install"

    log_info "Installing No-IP Dynamic Update Client..."

    mkdir -p "$TMP_DIR"

    cd "$TMP_DIR" || {
        log_error "Failed to enter temporary directory $TMP_DIR"
        return 1
    }

    log_info "Downloading latest No-IP package..."
    if ! wget --content-disposition "$DOWNLOAD_URL" >> "$LOG_FILE" 2>&1; then
        log_error "Failed to download No-IP DUC"
        return 1
    fi

    # Detect extracted tar file
    local TAR_FILE
    TAR_FILE=$(ls noip-duc_*.tar.gz 2>/dev/null | head -n1)

    if [[ -z "$TAR_FILE" ]]; then
        log_error "Downloaded archive not found"
        return 1
    fi

    log_info "Extracting $TAR_FILE..."
    if ! tar xf "$TAR_FILE" >> "$LOG_FILE" 2>&1; then
        log_error "Failed to extract No-IP archive"
        return 1
    fi

    local EXTRACTED_DIR
    EXTRACTED_DIR=$(basename "$TAR_FILE" .tar.gz)

    local ARCH=$(dpkg --print-architecture)
    local DEB_FILE="$TMP_DIR/$EXTRACTED_DIR/binaries/${EXTRACTED_DIR}_${ARCH}.deb"

    if [[ ! -f "$DEB_FILE" ]]; then
        log_error "No-IP .deb package not found at $DEB_FILE"
        return 1
    fi

    log_info "Installing No-IP DUC package..."
    if ! apt-get install -y "$DEB_FILE" >> "$LOG_FILE" 2>&1; then
        log_error "Failed to install No-IP DUC"
        return 1
    fi

    log_info "Cleaning up temporary installation files..."
    rm -rf "$TMP_DIR"

    log_info "No-IP Dynamic Update Client installed successfully"
}

configure_nginx_nms() {
    local NGINX_CONF="/etc/nginx/sites-available/nms"
    local NGINX_ENABLED="/etc/nginx/sites-enabled/nms"

    log_info "Configuring nginx for NMS..."

    log_info "Writing nginx configuration to $NGINX_CONF"
    cat <<'EOF' | tee "$NGINX_CONF" >/dev/null
server
{
    listen 80;
    server_name _;

    location /
    {
        proxy_pass http://127.0.0.1:8080;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-ForwardedProto $scheme;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /api/
    {
        proxy_pass http://127.0.0.1:8081;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-ForwardedProto $scheme;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /box
    {
      return 301 /box/;
    }

    location /box/
    {
      alias /nms/box/dist/;
      try_files $uri $uri/ /index.html;
    }

}
EOF

    log_info "Removing default site from sites-enabled if it exists..."
    if [[ -f /etc/nginx/sites-enabled/default ]]; then
        rm -f /etc/nginx/sites-enabled/default >> "$LOG_FILE" 2>&1
        log_info "Default site removed"
    fi

    log_info "Enabling NMS site..."
    ln -sf "$NGINX_CONF" "$NGINX_ENABLED"

    log_info "Testing nginx configuration..."
    if nginx -t >> "$LOG_FILE" 2>&1; then
        log_info "Nginx configuration test passed"
    else
        log_error "Nginx configuration test failed. Check $LOG_FILE"
        return 1
    fi

    log_info "Restarting nginx..."
    if systemctl restart nginx >> "$LOG_FILE" 2>&1; then
        log_info "Nginx restarted successfully"
    else
        log_error "Failed to restart nginx"
        return 1
    fi
}

# Build stuff
build_box_app() {
    local APP_DIR="$1"

    if [[ -z "$APP_DIR" ]]; then
        log_error "No application directory provided to build Box"
        return 1
    fi

    if [[ ! -d "$APP_DIR" ]]; then
        log_error "Directory '$APP_DIR' does not exist"
        return 1
    fi

    log_info "Building Box application in $APP_DIR..."

    cd "$APP_DIR" || {
        log_error "Failed to enter directory $APP_DIR"
        return 1
    }

    log_info "Installing npm dependencies..."
    if ! npm install >> "$LOG_FILE" 2>&1; then
        log_error "npm install failed"
        return 1
    fi

    log_info "Auditing dependencies..."
    if ! npm audit fix >> "$LOG_FILE" 2>&1; then
        log_error "npm audit fix failed"
        return 1
    fi

    log_info "Running Box production build..."
    if ! npm run build >> "$LOG_FILE" 2>&1; then
        log_error "Box build failed"
        return 1
    fi

    log_info "Box build completed successfully"
}



# Check if the script is run by root
if [[ "$EUID" -ne 0 ]]; then
    error_exit "This script must be run as root."
fi

# Step 1 --- Update source.list
add_contrib_nonfree

# Step 2 --- Install packages
install_packages "${PACKAGES[@]}"
modprobe zfs

# Step 3 --- Disable systemctl services
manage_services stop "${SERVICES_TO_DISABLE[@]}"
manage_services disable "${SERVICES_TO_DISABLE[@]}"
enable_network_manager

# Step 3.5 --- Configure network manager

# Step 4 --- Create python virtual environment
setup_python_venv "$PYTHON_VENV_PATH"

# Step 5 --- Cloning NMS git repository
clone_git_repo "$REPO_URL" "$DEST_DIR"

# Step 7 --- Install redis
install_redis_docker

# Step 8 ---

#Step 9 --- Configure users
manage_users
set_repo_permissions_wwwdata "$DEST_DIR"
add_nopasswd_sudo "backend"
#set_nms_json_permissions "$DEST_DIR"

#Step 10 --- Python configuration
install_requirements "$DEST_DIR" "$PYTHON_VENV_PATH"
install_editable_package "$DEST_DIR/nms_shared" "$PYTHON_VENV_PATH"

#Step 11 --- Systemctl
create_backend_service "$DEST_DIR" "$PYTHON_VENV_PATH"
create_frontend_service "$DEST_DIR" "$PYTHON_VENV_PATH"

#Step 12 --- Wireguard configuration
configure_wireguard

#Step 13 --- Noip dynamic updater script
install_noip_duc

#Step 14 --- Configure nginx as a reverse proxy
configure_nginx_nms
