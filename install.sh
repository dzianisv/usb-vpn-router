#!/bin/bash
#
# USB VPN Router One-Line Installer
# Downloads and installs the USB VPN Router Python package
#
# Usage: curl -sSL https://raw.githubusercontent.com/yourusername/usb-vpn-router/main/install.sh | sudo bash
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default settings
ENABLE_DASHBOARD=false
USE_TAILSCALE_EXIT=false
WAN_INTERFACE="wlan0"
USB_NETWORK="192.168.64.0/24"
GITHUB_REPO="yourusername/usb-vpn-router"
BRANCH="main"

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

log_header() {
    echo -e "${BLUE}$1${NC}"
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --enable-dashboard)
                ENABLE_DASHBOARD=true
                shift
                ;;
            --use-tailscale-exit)
                USE_TAILSCALE_EXIT=true
                shift
                ;;
            --wan-interface)
                WAN_INTERFACE="$2"
                shift 2
                ;;
            --usb-network)
                USB_NETWORK="$2"
                shift 2
                ;;
            --repo)
                GITHUB_REPO="$2"
                shift 2
                ;;
            --branch)
                BRANCH="$2"
                shift 2
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Show help
show_help() {
    cat << EOF
USB VPN Router One-Line Installer

Usage: $0 [OPTIONS]

Options:
    --enable-dashboard      Install web dashboard
    --use-tailscale-exit    Route USB clients through Tailscale exit node
    --wan-interface IFACE   WAN interface name (default: wlan0)
    --usb-network CIDR      USB client network (default: 192.168.64.0/24)
    --repo REPO            GitHub repository (default: yourusername/usb-vpn-router)
    --branch BRANCH        Git branch (default: main)
    --help                 Show this help message

Examples:
    # Basic installation
    $0

    # Full installation with dashboard
    $0 --enable-dashboard --use-tailscale-exit

    # Custom network configuration
    $0 --wan-interface eth0 --usb-network 10.0.64.0/24
EOF
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        log_info "Try: curl -sSL <url> | sudo bash"
        exit 1
    fi
}

# Detect OS and package manager
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    else
        log_error "Cannot detect OS distribution"
        exit 1
    fi
    
    log_info "Detected OS: $OS $VER"
    
    # Check if supported
    case $OS in
        debian|ubuntu|armbian)
            PACKAGE_MANAGER="apt"
            ;;
        centos|rhel|fedora)
            PACKAGE_MANAGER="yum"
            ;;
        arch)
            PACKAGE_MANAGER="pacman"
            ;;
        *)
            log_warn "OS $OS may not be fully supported"
            PACKAGE_MANAGER="apt"  # Default fallback
            ;;
    esac
}

# Install system dependencies
install_dependencies() {
    log_info "Installing system dependencies..."
    
    case $PACKAGE_MANAGER in
        apt)
            apt-get update
            apt-get install -y python3 python3-pip git curl wget
            ;;
        yum)
            yum install -y python3 python3-pip git curl wget
            ;;
        pacman)
            pacman -Sy --noconfirm python python-pip git curl wget
            ;;
    esac
    
    # Verify Python installation
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 installation failed"
        exit 1
    fi
    
    if ! command -v pip3 &> /dev/null; then
        log_error "pip3 installation failed"
        exit 1
    fi
    
    log_info "✅ Dependencies installed successfully"
}

# Install USB VPN Router package
install_package() {
    log_info "Installing USB VPN Router package from GitHub..."
    
    # Install package from GitHub
    pip3 install "git+https://github.com/${GITHUB_REPO}.git@${BRANCH}"
    
    # Verify installation
    if ! command -v usb-router-setup &> /dev/null; then
        log_error "Package installation failed - usb-router-setup command not found"
        exit 1
    fi
    
    log_info "✅ Package installed successfully"
}

# Run the router setup
run_setup() {
    log_info "Configuring USB VPN Router..."
    
    # Build setup command
    setup_cmd="usb-router-setup"
    
    if $USE_TAILSCALE_EXIT; then
        setup_cmd="$setup_cmd --use-tailscale-exit"
    fi
    
    if $ENABLE_DASHBOARD; then
        setup_cmd="$setup_cmd --enable-dashboard"
    fi
    
    setup_cmd="$setup_cmd --wan-interface $WAN_INTERFACE --usb-network $USB_NETWORK"
    
    log_info "Running: $setup_cmd"
    
    # Run setup
    eval $setup_cmd
    
    log_info "✅ Router configuration completed"
}

# Print success message
print_success() {
    echo
    log_header "🎉 USB VPN Router Installation Complete!"
    echo
    log_info "📋 Configuration:"
    log_info "  • USB Network: $USB_NETWORK"
    log_info "  • WAN Interface: $WAN_INTERFACE"
    log_info "  • Tailscale Exit: $([ $USE_TAILSCALE_EXIT = true ] && echo 'Enabled' || echo 'Disabled')"
    log_info "  • Web Dashboard: $([ $ENABLE_DASHBOARD = true ] && echo 'Enabled' || echo 'Disabled')"
    
    if $ENABLE_DASHBOARD; then
        echo
        log_info "🌐 Web Dashboard:"
        log_info "  URL: http://$(hostname -I | awk '{print $1}'):8000"
        log_info "  Default login: admin/admin"
        log_warn "  ⚠️  Change password immediately!"
    fi
    
    echo
    log_info "🚀 Next Steps:"
    log_info "1. Connect USB cable to host computer"
    log_info "2. Host should receive IP via DHCP (192.168.64.50-150)"
    
    if $USE_TAILSCALE_EXIT; then
        log_info "3. Configure Tailscale: tailscale up"
        log_info "4. Check status: usb-router-status"
    else
        log_info "3. Configure VPN as needed"
        log_info "4. Enable VPN routing: usb-router-tailscale on"
    fi
    
    echo
    log_info "📚 Available Commands:"
    log_info "  usb-router-status     - Check router status"
    log_info "  usb-router-reset      - Reset USB interface"
    log_info "  usb-router-tailscale  - Manage VPN routing"
    
    if $ENABLE_DASHBOARD; then
        log_info "  usb-router-dashboard  - Start web dashboard"
    fi
    
    echo
    log_info "📖 Documentation: https://github.com/${GITHUB_REPO}"
    echo
}

# Main installation function
main() {
    log_header "========================================"
    log_header "   USB VPN Router One-Line Installer"
    log_header "========================================"
    echo
    
    parse_args "$@"
    check_root
    detect_os
    install_dependencies
    install_package
    run_setup
    print_success
}

# Handle errors
trap 'log_error "Installation failed at line $LINENO. Exit code: $?"; exit 1' ERR

# Run main function with all arguments
main "$@"