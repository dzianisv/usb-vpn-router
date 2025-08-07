#!/bin/bash
#
# Ajenti Plugins Installation Script
# Installs custom USB Router plugins for Ajenti
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

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGINS_SOURCE_DIR="$SCRIPT_DIR/ajenti-plugins"
PLUGINS_TARGET_DIR="/var/lib/ajenti/plugins"

# Install plugins
install_plugins() {
    log_info "Installing Ajenti USB Router plugins..."
    
    # Create target directory if it doesn't exist
    mkdir -p "$PLUGINS_TARGET_DIR"
    
    # Copy plugins
    if [ -d "$PLUGINS_SOURCE_DIR" ]; then
        log_info "Copying plugins from $PLUGINS_SOURCE_DIR to $PLUGINS_TARGET_DIR"
        
        # Copy each plugin directory
        for plugin_dir in "$PLUGINS_SOURCE_DIR"/*; do
            if [ -d "$plugin_dir" ]; then
                plugin_name=$(basename "$plugin_dir")
                log_info "Installing plugin: $plugin_name"
                
                # Remove existing plugin if it exists
                rm -rf "$PLUGINS_TARGET_DIR/$plugin_name"
                
                # Copy new plugin
                cp -r "$plugin_dir" "$PLUGINS_TARGET_DIR/"
                
                # Set proper permissions
                chown -R root:root "$PLUGINS_TARGET_DIR/$plugin_name"
                chmod -R 755 "$PLUGINS_TARGET_DIR/$plugin_name"
                
                log_info "Plugin $plugin_name installed successfully"
            fi
        done
    else
        log_error "Plugins source directory not found: $PLUGINS_SOURCE_DIR"
        exit 1
    fi
}

# Create plugin configuration
configure_plugins() {
    log_info "Configuring plugins..."
    
    # Create plugins configuration file
    cat > /etc/ajenti/plugins.yml << 'EOF'
# USB Router Plugins Configuration
plugins:
  usb_router_status:
    enabled: true
    category: "System"
    icon: "fa fa-router"
    
  vpn_manager:
    enabled: true
    category: "Network"
    icon: "fa fa-shield-alt"
EOF
    
    log_info "Plugin configuration created"
}

# Restart Ajenti service
restart_ajenti() {
    log_info "Restarting Ajenti service..."
    
    if systemctl is-active ajenti >/dev/null 2>&1; then
        systemctl restart ajenti
        
        # Wait a moment for service to start
        sleep 3
        
        if systemctl is-active ajenti >/dev/null 2>&1; then
            log_info "Ajenti restarted successfully"
        else
            log_error "Failed to restart Ajenti service"
            exit 1
        fi
    else
        log_warn "Ajenti service is not running. Start it with: systemctl start ajenti"
    fi
}

# Verify installation
verify_installation() {
    log_info "Verifying plugin installation..."
    
    # Check if plugin directories exist
    local plugins_found=0
    
    for plugin in usb_router_status vpn_manager; do
        if [ -d "$PLUGINS_TARGET_DIR/$plugin" ]; then
            log_info "✓ Plugin $plugin installed"
            plugins_found=$((plugins_found + 1))
        else
            log_error "✗ Plugin $plugin not found"
        fi
    done
    
    if [ $plugins_found -eq 2 ]; then
        log_info "All plugins installed successfully!"
        return 0
    else
        log_error "Some plugins failed to install"
        return 1
    fi
}

# Main installation function
main() {
    log_info "Starting Ajenti USB Router plugins installation..."
    
    check_root
    install_plugins
    configure_plugins
    restart_ajenti
    verify_installation
    
    log_info ""
    log_info "Installation complete!"
    log_info ""
    log_info "Access your USB Router dashboard at:"
    log_info "  http://192.168.0.226:8000"
    log_info ""
    log_info "Available plugins:"
    log_info "  • USB Router Status - System monitoring and control"
    log_info "  • VPN Manager - Tailscale and OpenVPN management"
    log_info ""
    log_info "Default login: admin/admin"
    log_warn "Change the default password immediately after first login!"
}

# Run main function
main "$@"