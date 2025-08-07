#!/bin/bash
#
# Ajenti Installation Script for USB VPN Router
# Installs Ajenti web admin panel with custom plugins
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

# Install Ajenti
install_ajenti() {
    log_info "Installing Ajenti web admin panel..."
    
    # Install required packages
    apt-get update
    apt-get install -y python3 python3-pip python3-venv wget curl
    
    # Install Ajenti
    pip3 install ajenti-panel ajenti.plugin.core ajenti.plugin.dashboard ajenti.plugin.settings ajenti.plugin.plugins
    
    # Install additional Python packages for our plugins
    pip3 install psutil netifaces
    
    log_info "Ajenti installed successfully"
}

# Configure Ajenti
configure_ajenti() {
    log_info "Configuring Ajenti..."
    
    # Create Ajenti configuration directory
    mkdir -p /etc/ajenti
    
    # Create basic Ajenti configuration
    cat > /etc/ajenti/config.yml << 'EOF'
name: orangepi-router
max_sessions: 9
session_max_time: 3600
bind:
  host: 0.0.0.0
  port: 8000
ssl:
  enable: false
  certificate_path: ''
  fqdn_certificate_path: ''
  client_certificate_path: ''
  cipher: ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384
color: default
language: en
EOF
    
    # Create users configuration
    cat > /etc/ajenti/users.yml << 'EOF'
users:
  admin:
    password: admin
    permissions: []
EOF
    
    log_info "Ajenti configuration created"
    log_warn "Default credentials: admin/admin - Change after first login!"
}

# Create systemd service
create_service() {
    log_info "Creating Ajenti systemd service..."
    
    cat > /etc/systemd/system/ajenti.service << 'EOF'
[Unit]
Description=Ajenti panel
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/ajenti-panel -c /etc/ajenti/config.yml --stock-plugins
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable ajenti
    
    log_info "Ajenti service created and enabled"
}

# Create plugin directory structure
setup_plugins() {
    log_info "Setting up custom plugin directory..."
    
    # Create plugin directory
    mkdir -p /var/lib/ajenti/plugins/usb_router
    
    # Create plugin structure
    mkdir -p /var/lib/ajenti/plugins/usb_router/{resources,templates}
    
    log_info "Plugin directory structure created"
}

# Main installation function
main() {
    log_info "Starting Ajenti installation for USB VPN Router..."
    
    check_root
    install_ajenti
    configure_ajenti
    create_service
    setup_plugins
    
    log_info "Ajenti installation complete!"
    log_info ""
    log_info "Next steps:"
    log_info "1. Install custom USB Router plugins"
    log_info "2. Start Ajenti: systemctl start ajenti"
    log_info "3. Access web interface: http://192.168.0.226:8000"
    log_info "4. Login with admin/admin (change password immediately)"
    log_info ""
    log_info "Custom plugins will be installed in: /var/lib/ajenti/plugins/"
}

# Run main function
main "$@"