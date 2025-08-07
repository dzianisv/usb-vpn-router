#!/bin/bash
#
# USB Router Setup Script
# Configures an Orange Pi (or similar SBC) as a USB ethernet router with VPN support
# Features: RNDIS/CDC ethernet gadget, DHCP server, NAT, OpenVPN, Tailscale
#
# Usage: sudo bash setup-usb-router.sh
#

set -e

# Configuration variables
USB_NETWORK="192.168.64.0/24"
USB_IP="192.168.64.1"
USB_DHCP_START="192.168.64.50"
USB_DHCP_END="192.168.64.150"
USB_INTERFACE="usb0"
WAN_INTERFACE="${WAN_INTERFACE:-wlan0}"  # Can be overridden by environment variable
TAILSCALE_INTERFACE="tailscale0"
OPENVPN_INTERFACE="tun0"
USE_TAILSCALE_EXIT="${USE_TAILSCALE_EXIT:-true}"  # Default: route through VPN only
USE_VPN_FAILOVER="${USE_VPN_FAILOVER:-true}"  # Enable automatic VPN failover

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

# Detect the distribution
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    else
        log_error "Cannot detect OS distribution"
        exit 1
    fi
    log_info "Detected OS: $OS $VER"
}

# Install required packages
install_packages() {
    log_info "Checking and installing required packages..."
    
    case $OS in
        debian|ubuntu|armbian)
            # List of required packages
            local packages=(
                dnsmasq
                iptables-persistent
                tcpdump
                curl
                wget
                gnupg
                lsb-release
                ca-certificates
                openvpn
                jq
            )
            
            # Check which packages need to be installed
            local to_install=()
            for pkg in "${packages[@]}"; do
                if ! dpkg -l "$pkg" 2>/dev/null | grep -q "^ii"; then
                    to_install+=("$pkg")
                fi
            done
            
            # Only run apt if there are packages to install
            if [ ${#to_install[@]} -gt 0 ]; then
                log_info "Need to install: ${to_install[*]}"
                apt-get update
                apt-get install -y "${to_install[@]}"
            else
                log_info "All required packages are already installed"
            fi
            ;;
        *)
            log_error "Unsupported distribution: $OS"
            exit 1
            ;;
    esac
}

# Configure USB gadget modules
setup_usb_gadget() {
    log_info "Configuring USB gadget modules..."
    
    # Detect if this is RK3399 (OrangePi 4 LTS)
    if grep -q "rk3399" /proc/device-tree/compatible 2>/dev/null || [ -f /boot/dtb/rockchip/rk3399-orangepi-4-lts.dtb ]; then
        log_info "Detected RK3399 board (OrangePi 4 LTS), applying specific configuration..."
        
        # Create proper DTS overlay for RK3399 USB-C peripheral mode
        # IMPORTANT: Must target /usb@fe800000/dwc3@fe800000 (the DWC3 controller node)
        # The DWC3 driver reads dr_mode from this specific node path
        cat > /tmp/dwc3-peripheral.dts << 'DTSEOF'
/dts-v1/;
/plugin/;

/ {
    compatible = "rockchip,rk3399";

    fragment@0 {
        target-path = "/usb@fe800000/dwc3@fe800000";
        __overlay__ {
            compatible = "snps,dwc3";
            dr_mode = "peripheral";
            status = "okay";
            reg = <0x0 0xfe800000 0x0 0x100000>;
            phys = <&tcphy0_usb3>;
            phy-names = "usb3-phy";
            phy_type = "utmi_wide";
            snps,dis_enblslpm_quirk;
            snps,dis-u2-freeclk-exists-quirk;
            snps,dis_u2_susphy_quirk;
            snps,dis-del-phy-power-chg-quirk;
            snps,xhci-slow-suspend-quirk;
        };
    };
};
DTSEOF
        
        # Apply overlay using armbian-add-overlay if available
        if command -v armbian-add-overlay &>/dev/null; then
            log_info "Applying USB peripheral mode overlay..."
            
            # Clean up any old/conflicting overlays
            for old_overlay in dwc3-0-device usb-peripheral usb-peripheral-simple usb-gadget-fixed dwc3-peripheral-full dwc3-peripheral-simple dwc3-correct-path dwc3-peripheral; do
                if [ -f "/boot/overlay-user/${old_overlay}.dtbo" ]; then
                    log_info "Removing old overlay: ${old_overlay}"
                    rm -f "/boot/overlay-user/${old_overlay}.dtbo"
                    # Remove from armbianEnv.txt
                    sed -i "s/${old_overlay}//g" /boot/armbianEnv.txt
                    sed -i 's/  */ /g' /boot/armbianEnv.txt  # Clean up multiple spaces
                fi
            done
            
            armbian-add-overlay /tmp/dwc3-peripheral.dts
            REBOOT_REQUIRED=true
        fi
        
        # Configure modules to load at boot for RK3399
        cat > /etc/modules-load.d/usb_gadget.conf << EOF
# DWC3 core driver for USB-C controller
dwc3
# Ethernet gadget (includes RNDIS)
g_ether
EOF
        
        # Configure module parameters for RK3399
        cat > /etc/modprobe.d/dwc3.conf << EOF
# Force DWC3 to peripheral mode
options dwc3 role=device
EOF
        
        # Configure FUSB302 Type-C controller
        cat > /etc/modprobe.d/fusb302.conf << EOF
# Force FUSB302 to sink role
options fusb302 port_type=2
options tcpm tcpm_log_level=1
EOF
        
        # Blacklist conflicting drivers
        cat > /etc/modprobe.d/usb_gadget-blacklist.conf << EOF
# Prevent other USB network drivers from interfering
blacklist cdc_ncm
EOF
    else
        # Standard configuration for other boards
        cat > /etc/modules-load.d/usb_gadget.conf << EOF
# USB Ethernet Gadget
g_ether
EOF
    fi
    
    # Create modprobe configuration for g_ether
    cat > /etc/modprobe.d/g_ether.conf << EOF
# Use CDC-ECM mode for better macOS compatibility
options g_ether use_eem=0 use_ecm=1
EOF

    # Load the module now if not already loaded
    if ! lsmod | grep -q g_ether; then
        # Load without parameters so it uses /etc/modprobe.d/g_ether.conf
        modprobe g_ether
        sleep 2
    else
        log_info "g_ether already loaded - may need reboot for new options to take effect"
    fi
}

# Configure network interface
setup_network_interface() {
    log_info "Configuring network interface for $USB_INTERFACE..."
    
    # Check if using systemd-networkd (preferred on modern systems)
    if systemctl is-enabled systemd-networkd &>/dev/null || [ -d /etc/systemd/network ]; then
        log_info "Configuring via systemd-networkd..."
        # Remove any old configs with wrong IP
        rm -f /etc/systemd/network/*usb0*.network 2>/dev/null
        
        cat > /etc/systemd/network/20-usb0.network << EOF
[Match]
Name=$USB_INTERFACE

[Network]
Address=$USB_IP/24
ConfigureWithoutCarrier=yes

[Link]
RequiredForOnline=no
EOF
        systemctl enable systemd-networkd 2>/dev/null || true
        systemctl restart systemd-networkd || true
    elif [ -d /etc/netplan ]; then
        # Netplan configuration
        cat > /etc/netplan/40-usb0.yaml << EOF
network:
  version: 2
  ethernets:
    $USB_INTERFACE:
      addresses:
        - $USB_IP/24
      optional: true
EOF
        chmod 600 /etc/netplan/40-usb0.yaml
        netplan apply || true
    else
        # Traditional /etc/network/interfaces
        if ! grep -q "$USB_INTERFACE" /etc/network/interfaces; then
            cat >> /etc/network/interfaces << EOF

# USB Ethernet Gadget Interface
auto $USB_INTERFACE
iface $USB_INTERFACE inet static
    address $USB_IP
    netmask 255.255.255.0
EOF
        fi
    fi
    
    # Bring up the interface immediately if it exists
    if ip link show $USB_INTERFACE &>/dev/null; then
        ip link set $USB_INTERFACE up
        ip addr add $USB_IP/24 dev $USB_INTERFACE 2>/dev/null || true
    fi
}

# Configure DHCP server
setup_dhcp_server() {
    log_info "Configuring DHCP server..."
    
    # Stop and disable systemd-resolved to avoid port 53 conflicts
    if systemctl is-active systemd-resolved &>/dev/null; then
        log_info "Disabling systemd-resolved to avoid conflicts..."
        systemctl stop systemd-resolved
        systemctl disable systemd-resolved
    fi
    
    # Backup original dnsmasq config if exists
    [ -f /etc/dnsmasq.conf ] && cp /etc/dnsmasq.conf /etc/dnsmasq.conf.bak
    
    # Clear any existing dnsmasq.d configs that might conflict
    rm -f /etc/dnsmasq.d/*.conf 2>/dev/null
    
    # Create main dnsmasq configuration
    cat > /etc/dnsmasq.conf << EOF
# DHCP Configuration for USB Ethernet Gadget
interface=$USB_INTERFACE
bind-interfaces
except-interface=lo
dhcp-range=$USB_DHCP_START,$USB_DHCP_END,12h
dhcp-option=3,$USB_IP
dhcp-option=6,$USB_IP

# DNS Configuration
port=53
server=8.8.8.8
server=1.1.1.1
cache-size=150
domain-needed
bogus-priv

# Logging
log-dhcp
log-queries
log-facility=/var/log/dnsmasq.log
EOF

    # Create systemd override to ensure dnsmasq starts after usb0
    mkdir -p /etc/systemd/system/dnsmasq.service.d
    cat > /etc/systemd/system/dnsmasq.service.d/wait-for-usb0.conf << EOF
[Unit]
After=sys-subsystem-net-devices-$USB_INTERFACE.device
Wants=sys-subsystem-net-devices-$USB_INTERFACE.device

[Service]
# Restart if it fails (in case usb0 isn't ready yet)
Restart=on-failure
RestartSec=5s
EOF

    systemctl daemon-reload
    systemctl enable dnsmasq
}

# Configure IP forwarding and NAT
setup_nat() {
    log_info "Configuring IP forwarding and NAT..."
    
    # Enable IP forwarding
    echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/30-ip-forward.conf
    sysctl -w net.ipv4.ip_forward=1
    
    # Set default FORWARD policy to REJECT (fail-safe)
    log_info "Setting default FORWARD policy to REJECT"
    iptables -P FORWARD DROP
    ip6tables -P FORWARD DROP
    
    # Clear existing FORWARD rules to start fresh
    iptables -F FORWARD
    ip6tables -F FORWARD
    
    # Clear existing NAT rules
    iptables -t nat -F POSTROUTING
    
    if [ "$USE_TAILSCALE_EXIT" = "true" ]; then
        log_info "Setting up VPN-only routing for USB clients"
        
        # Create custom routing table for USB clients
        if ! grep -q "usb_vpn" /etc/iproute2/rt_tables; then
            echo "200 usb_vpn" >> /etc/iproute2/rt_tables
        fi
        
        # Only route USB client traffic through VPN, not the device's own traffic
        ip rule del from $USB_NETWORK table usb_vpn 2>/dev/null || true
        ip rule add from $USB_NETWORK table usb_vpn priority 200
        
        # Wait for Tailscale interface
        local attempts=0
        while [ $attempts -lt 10 ] && ! ip link show $TAILSCALE_INTERFACE &>/dev/null; do
            log_info "Waiting for Tailscale interface..."
            sleep 2
            ((attempts++))
        done
        
        # Add default route through Tailscale for USB clients only
        if ip link show $TAILSCALE_INTERFACE &>/dev/null; then
            local ts_gateway=$(ip route show dev $TAILSCALE_INTERFACE | grep -E '^100\.' | head -1 | awk '{print $1}')
            if [ -n "$ts_gateway" ]; then
                ip route add default via $ts_gateway dev $TAILSCALE_INTERFACE table usb_vpn 2>/dev/null || true
            fi
        fi
        
        # NAT for USB clients through both VPN interfaces (failover support)
        iptables -t nat -A POSTROUTING -o $TAILSCALE_INTERFACE -s $USB_NETWORK -j MASQUERADE
        iptables -t nat -A POSTROUTING -o $OPENVPN_INTERFACE -s $USB_NETWORK -j MASQUERADE
        
        # With default DROP policy, only allow specific VPN routes
        log_info "Allowing ONLY USB to VPN forwarding (default DROP for everything else)"
        
        # IPv4: Allow ONLY USB to VPN interfaces
        iptables -A FORWARD -i $USB_INTERFACE -o $TAILSCALE_INTERFACE -j ACCEPT
        iptables -A FORWARD -i $USB_INTERFACE -o $OPENVPN_INTERFACE -j ACCEPT
        iptables -A FORWARD -i $TAILSCALE_INTERFACE -o $USB_INTERFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
        iptables -A FORWARD -i $OPENVPN_INTERFACE -o $USB_INTERFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
        
        # IPv6: Allow ONLY USB to VPN interfaces
        ip6tables -A FORWARD -i $USB_INTERFACE -o $TAILSCALE_INTERFACE -j ACCEPT
        ip6tables -A FORWARD -i $USB_INTERFACE -o $OPENVPN_INTERFACE -j ACCEPT
        ip6tables -A FORWARD -i $TAILSCALE_INTERFACE -o $USB_INTERFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
        ip6tables -A FORWARD -i $OPENVPN_INTERFACE -o $USB_INTERFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
        
        # Ensure local traffic is not affected
        ip rule add from 192.168.0.0/16 to 192.168.0.0/16 table main priority 50
        ip rule add from 10.0.0.0/8 to 10.0.0.0/8 table main priority 50
        
        log_info "USB clients can ONLY route through VPN interfaces (no leaks possible)"
    else
        log_info "Setting up local WAN routing"
        
        # Standard NAT through WAN interface
        iptables -t nat -A POSTROUTING -o $WAN_INTERFACE -s $USB_NETWORK -j MASQUERADE
        iptables -A FORWARD -i $USB_INTERFACE -o $WAN_INTERFACE -j ACCEPT
        iptables -A FORWARD -i $WAN_INTERFACE -o $USB_INTERFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
    fi
    
    # Save iptables rules
    if command -v netfilter-persistent &>/dev/null; then
        netfilter-persistent save
    else
        iptables-save > /etc/iptables/rules.v4
    fi
}

# Install and configure OpenVPN
setup_openvpn() {
    log_info "Setting up OpenVPN client..."
    
    # Create OpenVPN client config directory
    mkdir -p /etc/openvpn/client
    
    # Create a template systemd service for OpenVPN clients
    cat > /etc/systemd/system/openvpn-client@.service << EOF
[Unit]
Description=OpenVPN client for %i
After=network.target

[Service]
Type=notify
PrivateTmp=true
ExecStart=/usr/sbin/openvpn --config /etc/openvpn/client/%i.ovpn
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    
    log_info "OpenVPN client installed. Place your .ovpn files in /etc/openvpn/client/"
    log_info "Start with: systemctl start openvpn-client@configname"
}

# Install and configure Tailscale
setup_tailscale() {
    log_info "Installing Tailscale..."
    
    # Add Tailscale's GPG key and repository
    case $OS in
        debian|ubuntu|armbian)
            # Install dependencies including jq for JSON parsing
            apt-get install -y jq
            
            curl -fsSL https://pkgs.tailscale.com/stable/debian/bullseye.noarmor.gpg | tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
            curl -fsSL https://pkgs.tailscale.com/stable/debian/bullseye.tailscale-keyring.list | tee /etc/apt/sources.list.d/tailscale.list
            
            apt-get update
            apt-get install -y tailscale
            ;;
    esac
    
    systemctl enable tailscaled
    systemctl start tailscaled
    
    # Configure Tailscale to accept subnet routes and act as exit node
    mkdir -p /etc/sysctl.d
    cat > /etc/sysctl.d/99-tailscale.conf << EOF
# Enable IP forwarding for Tailscale
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
EOF
    sysctl -p /etc/sysctl.d/99-tailscale.conf
    
    # If USE_TAILSCALE_EXIT is true, we'll use split routing (USB clients only)
    if [ "$USE_TAILSCALE_EXIT" = "true" ]; then
        log_info "Checking Tailscale authentication status..."
        if tailscale status &>/dev/null; then
            log_info "Tailscale is authenticated"
            log_info "Split routing will be configured - USB clients through VPN, device keeps local access"
            
            # Make sure we allow local network access
            tailscale set --exit-node-allow-lan-access=true 2>/dev/null || true
        else
            log_warn "Tailscale not authenticated yet. Run 'tailscale up' first"
        fi
    fi
    
    log_info "Tailscale installed. Commands:"
    log_info "  tailscale up                    - Authenticate with Tailscale"
    log_info "  usb-router-tailscale on         - Route USB clients through Tailscale"
    log_info "  usb-router-tailscale off        - Route USB clients through local internet"
    log_info "  tailscale up --advertise-exit-node  - Make this device an exit node"
}

# Main setup function
main() {
    log_info "Starting USB Router Setup..."
    
    check_root
    detect_distro
    install_packages
    setup_usb_gadget
    setup_network_interface
    setup_dhcp_server
    setup_nat
    setup_openvpn
    setup_tailscale
    
    # Restart services
    log_info "Restarting services..."
    systemctl restart systemd-networkd || true
    
    # Try to bring up usb0 if module is loaded
    if lsmod | grep -q g_ether; then
        sleep 2
        ip link set $USB_INTERFACE up 2>/dev/null || true
        systemctl restart dnsmasq || true
    fi
    
    # Check if reboot is required (for RK3399 boards)
    if [ "${REBOOT_REQUIRED:-false}" = "true" ]; then
        log_warn "IMPORTANT: REBOOT REQUIRED!"
        log_warn "The USB device tree overlay has been applied."
        log_warn "You must reboot for USB peripheral mode to work."
        log_warn ""
        log_warn "For Orange Pi 4 LTS: Due to a FUSB302 initialization bug,"
        log_warn "connect power AND USB-C cable simultaneously during boot"
        log_warn "for best results. This ensures peripheral mode is properly set."
        log_info ""
        read -p "Reboot now? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            reboot
        fi
    else
        # Check if UDC is available (for boards that don't need reboot)
        if ls /sys/class/udc/ 2>/dev/null | grep -q .; then
            log_info "USB Device Controller found: $(ls /sys/class/udc/)"
            log_info "USB gadget should be working!"
        else
            log_warn "No USB Device Controller found. You may need to reboot."
        fi
    fi
}

# Run main function
main "$@"