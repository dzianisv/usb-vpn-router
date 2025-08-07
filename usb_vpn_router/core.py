"""
USB VPN Router Core Module
Contains the main router setup and configuration logic.
"""

import os
import subprocess
import time
from pathlib import Path
from .utils import run_command, log_info, log_warn, log_error


class USBRouterCore:
    """Core USB VPN Router functionality."""
    
    def __init__(self, config):
        self.config = config
        
    def setup_usb_gadget(self):
        """Configure USB gadget modules."""
        log_info("Configuring USB gadget modules...")
        
        # Create modprobe configuration
        modprobe_config = """
# Configuration for USB Ethernet Gadget
# use_eem=0 ensures compatibility with Windows and macOS
options g_ether use_eem=0 dev_addr=02:00:00:00:00:01 host_addr=02:00:00:00:00:02
"""
        
        with open('/etc/modprobe.d/g_ether.conf', 'w') as f:
            f.write(modprobe_config)
        
        # Ensure g_ether loads at boot
        with open('/etc/modules-load.d/g_ether.conf', 'w') as f:
            f.write('g_ether\n')
        
        # Load module now if not already loaded
        try:
            result = subprocess.run(['lsmod'], capture_output=True, text=True)
            if 'g_ether' not in result.stdout:
                run_command(['modprobe', 'g_ether', 'use_eem=0'])
                time.sleep(2)
        except Exception as e:
            log_warn(f"Could not load g_ether module: {e}")
    
    def setup_network_interface(self):
        """Configure network interface for USB."""
        log_info(f"Configuring network interface for {self.config.usb_interface}...")
        
        # Check if using netplan or traditional networking
        if Path('/etc/netplan').exists():
            self._setup_netplan_interface()
        else:
            self._setup_traditional_interface()
        
        # Bring up interface if it exists
        try:
            run_command(['ip', 'link', 'show', self.config.usb_interface])
            run_command(['ip', 'link', 'set', self.config.usb_interface, 'up'])
            run_command(['ip', 'addr', 'add', f'{self.config.usb_ip}/24', 
                        'dev', self.config.usb_interface])
        except subprocess.CalledProcessError:
            log_warn(f"Interface {self.config.usb_interface} not available yet")
    
    def _setup_netplan_interface(self):
        """Setup interface using netplan."""
        netplan_config = f"""
network:
  version: 2
  ethernets:
    {self.config.usb_interface}:
      addresses:
        - {self.config.usb_ip}/24
      optional: true
"""
        
        with open('/etc/netplan/40-usb0.yaml', 'w') as f:
            f.write(netplan_config)
        
        os.chmod('/etc/netplan/40-usb0.yaml', 0o600)
        
        try:
            run_command(['netplan', 'apply'])
        except subprocess.CalledProcessError:
            log_warn("Netplan apply failed - interface may not be ready")
    
    def _setup_traditional_interface(self):
        """Setup interface using /etc/network/interfaces."""
        interface_config = f"""

# USB Ethernet Gadget Interface
auto {self.config.usb_interface}
iface {self.config.usb_interface} inet static
    address {self.config.usb_ip}
    netmask 255.255.255.0
"""
        
        # Check if already configured
        try:
            with open('/etc/network/interfaces', 'r') as f:
                content = f.read()
                if self.config.usb_interface not in content:
                    with open('/etc/network/interfaces', 'a') as f:
                        f.write(interface_config)
        except FileNotFoundError:
            with open('/etc/network/interfaces', 'w') as f:
                f.write(interface_config)
    
    def setup_dhcp_server(self):
        """Configure DHCP server."""
        log_info("Configuring DHCP server...")
        
        # Backup original dnsmasq config
        if Path('/etc/dnsmasq.conf').exists():
            run_command(['cp', '/etc/dnsmasq.conf', '/etc/dnsmasq.conf.bak'])
        
        # Create USB interface DHCP configuration
        dhcp_config = f"""
# DHCP Configuration for USB Ethernet Gadget
interface={self.config.usb_interface}
bind-interfaces
dhcp-range={self.config.usb_dhcp_start},{self.config.usb_dhcp_end},12h
dhcp-option=3,{self.config.usb_ip}    # Default gateway
dhcp-option=6,{self.config.usb_ip}     # DNS server

# Enable DNS service
port=53
# Use Google and Cloudflare as upstream DNS servers
server=8.8.8.8
server=8.8.4.4
server=1.1.1.1

# Cache DNS queries
cache-size=150
# Don't forward local domains upstream
local=/local/
domain-needed
bogus-priv

# Logging for debugging
log-dhcp
log-queries

# Prevent DNS rebinding attacks
stop-dns-rebind
"""
        
        Path('/etc/dnsmasq.d').mkdir(exist_ok=True)
        with open('/etc/dnsmasq.d/usb0.conf', 'w') as f:
            f.write(dhcp_config)
        
        # Create systemd override
        override_dir = Path('/etc/systemd/system/dnsmasq.service.d')
        override_dir.mkdir(exist_ok=True)
        
        override_config = f"""
[Unit]
After=sys-subsystem-net-devices-{self.config.usb_interface}.device
Wants=sys-subsystem-net-devices-{self.config.usb_interface}.device

[Service]
Restart=on-failure
RestartSec=5s
"""
        
        with open(override_dir / 'wait-for-usb0.conf', 'w') as f:
            f.write(override_config)
        
        run_command(['systemctl', 'daemon-reload'])
        run_command(['systemctl', 'enable', 'dnsmasq'])
    
    def setup_nat_and_routing(self):
        """Configure NAT and routing."""
        log_info("Configuring IP forwarding and NAT...")
        
        # Enable IP forwarding
        with open('/etc/sysctl.d/30-ip-forward.conf', 'w') as f:
            f.write('net.ipv4.ip_forward=1\n')
        
        run_command(['sysctl', '-w', 'net.ipv4.ip_forward=1'])
        
        # Configure iptables rules
        self._setup_iptables_rules()
        
        # Save iptables rules
        self._save_iptables_rules()
    
    def _setup_iptables_rules(self):
        """Setup iptables rules for routing."""
        # Set default policies
        run_command(['iptables', '-P', 'FORWARD', 'DROP'])
        run_command(['ip6tables', '-P', 'FORWARD', 'DROP'])
        
        # Clear existing rules
        run_command(['iptables', '-F', 'FORWARD'])
        run_command(['ip6tables', '-F', 'FORWARD'])
        run_command(['iptables', '-t', 'nat', '-F', 'POSTROUTING'])
        
        if self.config.use_tailscale_exit:
            self._setup_vpn_routing()
        else:
            self._setup_local_routing()
    
    def _setup_vpn_routing(self):
        """Setup VPN-only routing for USB clients."""
        log_info("Setting up VPN-only routing for USB clients")
        
        # Create custom routing table
        if not self._routing_table_exists('usb_vpn'):
            with open('/etc/iproute2/rt_tables', 'a') as f:
                f.write('200 usb_vpn\n')
        
        # Route USB traffic through VPN table
        try:
            run_command(['ip', 'rule', 'del', 'from', self.config.usb_network, 'table', 'usb_vpn'])
        except subprocess.CalledProcessError:
            pass
        
        run_command(['ip', 'rule', 'add', 'from', self.config.usb_network, 
                    'table', 'usb_vpn', 'priority', '200'])
        
        # NAT rules for VPN interfaces
        for interface in [self.config.tailscale_interface, self.config.openvpn_interface]:
            run_command(['iptables', '-t', 'nat', '-A', 'POSTROUTING', 
                        '-o', interface, '-s', self.config.usb_network, '-j', 'MASQUERADE'])
        
        # Forward rules (only allow VPN)
        for interface in [self.config.tailscale_interface, self.config.openvpn_interface]:
            run_command(['iptables', '-A', 'FORWARD', '-i', self.config.usb_interface, 
                        '-o', interface, '-j', 'ACCEPT'])
            run_command(['iptables', '-A', 'FORWARD', '-i', interface, 
                        '-o', self.config.usb_interface, '-m', 'state', 
                        '--state', 'RELATED,ESTABLISHED', '-j', 'ACCEPT'])
    
    def _setup_local_routing(self):
        """Setup local WAN routing."""
        log_info("Setting up local WAN routing")
        
        # NAT through WAN interface
        run_command(['iptables', '-t', 'nat', '-A', 'POSTROUTING', 
                    '-o', self.config.wan_interface, '-s', self.config.usb_network, '-j', 'MASQUERADE'])
        
        # Forward rules
        run_command(['iptables', '-A', 'FORWARD', '-i', self.config.usb_interface, 
                    '-o', self.config.wan_interface, '-j', 'ACCEPT'])
        run_command(['iptables', '-A', 'FORWARD', '-i', self.config.wan_interface, 
                    '-o', self.config.usb_interface, '-m', 'state', 
                    '--state', 'RELATED,ESTABLISHED', '-j', 'ACCEPT'])
    
    def _routing_table_exists(self, table_name):
        """Check if routing table exists."""
        try:
            with open('/etc/iproute2/rt_tables', 'r') as f:
                return table_name in f.read()
        except FileNotFoundError:
            return False
    
    def _save_iptables_rules(self):
        """Save iptables rules."""
        try:
            run_command(['netfilter-persistent', 'save'])
        except subprocess.CalledProcessError:
            try:
                Path('/etc/iptables').mkdir(exist_ok=True)
                run_command(['iptables-save'], stdout_file='/etc/iptables/rules.v4')
                run_command(['ip6tables-save'], stdout_file='/etc/iptables/rules.v6')
            except Exception as e:
                log_warn(f"Could not save iptables rules: {e}")
    
    def setup_openvpn(self):
        """Setup OpenVPN client configuration."""
        log_info("Setting up OpenVPN client...")
        
        # Create client config directory
        Path('/etc/openvpn/client').mkdir(parents=True, exist_ok=True)
        
        # Create systemd service template
        service_config = """
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
"""
        
        with open('/etc/systemd/system/openvpn-client@.service', 'w') as f:
            f.write(service_config)
        
        run_command(['systemctl', 'daemon-reload'])
    
    def setup_tailscale(self):
        """Setup Tailscale VPN."""
        log_info("Installing Tailscale...")
        
        try:
            # Install Tailscale
            self._install_tailscale()
            
            # Configure Tailscale
            self._configure_tailscale()
            
        except Exception as e:
            log_warn(f"Tailscale installation failed: {e}")
    
    def _install_tailscale(self):
        """Install Tailscale package."""
        # Add Tailscale repository and install
        run_command(['curl', '-fsSL', 'https://pkgs.tailscale.com/stable/debian/bullseye.noarmor.gpg'],
                   stdout_file='/usr/share/keyrings/tailscale-archive-keyring.gpg')
        
        repo_config = 'deb [signed-by=/usr/share/keyrings/tailscale-archive-keyring.gpg] ' \
                     'https://pkgs.tailscale.com/stable/debian bullseye main'
        
        with open('/etc/apt/sources.list.d/tailscale.list', 'w') as f:
            f.write(repo_config)
        
        run_command(['apt-get', 'update'])
        run_command(['apt-get', 'install', '-y', 'tailscale'])
    
    def _configure_tailscale(self):
        """Configure Tailscale settings."""
        # Enable IP forwarding for Tailscale
        tailscale_sysctl = """
# Enable IP forwarding for Tailscale
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
"""
        
        with open('/etc/sysctl.d/99-tailscale.conf', 'w') as f:
            f.write(tailscale_sysctl)
        
        run_command(['sysctl', '-p', '/etc/sysctl.d/99-tailscale.conf'])
        
        # Enable and start Tailscale
        run_command(['systemctl', 'enable', 'tailscaled'])
        run_command(['systemctl', 'start', 'tailscaled'])
    
    def create_helper_scripts(self):
        """Create helper scripts for router management."""
        log_info("Creating helper scripts...")
        
        # The CLI commands will be handled by the Python package entry points
        # This method can be used for any additional script creation
        pass
    
    def create_systemd_services(self):
        """Create additional systemd services."""
        log_info("Creating systemd services...")
        
        if self.config.enable_vpn_failover:
            self._create_vpn_monitor_service()
        
        self._create_usb_watchdog_service()
    
    def _create_vpn_monitor_service(self):
        """Create VPN failover monitor service."""
        service_config = """
[Unit]
Description=USB Router VPN Failover Monitor
After=network.target tailscaled.service
Wants=tailscaled.service

[Service]
Type=simple
ExecStart=/usr/local/bin/usb-router-vpn-monitor
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        
        with open('/etc/systemd/system/usb-router-vpn-monitor.service', 'w') as f:
            f.write(service_config)
        
        run_command(['systemctl', 'daemon-reload'])
        run_command(['systemctl', 'enable', 'usb-router-vpn-monitor'])
    
    def _create_usb_watchdog_service(self):
        """Create USB interface watchdog service."""
        service_config = """
[Unit]
Description=USB Interface Watchdog for macOS Permission Delays
After=network.target
Before=dnsmasq.service

[Service]
Type=simple
ExecStart=/usr/local/bin/usb-interface-watchdog
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        
        with open('/etc/systemd/system/usb-interface-watchdog.service', 'w') as f:
            f.write(service_config)
        
        run_command(['systemctl', 'daemon-reload'])
        run_command(['systemctl', 'enable', 'usb-interface-watchdog'])
    
    def start_services(self):
        """Start all router services."""
        log_info("Starting router services...")
        
        # Restart networking
        try:
            run_command(['systemctl', 'restart', 'systemd-networkd'])
        except subprocess.CalledProcessError:
            log_warn("Could not restart systemd-networkd")
        
        # Start USB interface if available
        try:
            run_command(['ip', 'link', 'set', self.config.usb_interface, 'up'])
            time.sleep(2)
            run_command(['systemctl', 'restart', 'dnsmasq'])
        except subprocess.CalledProcessError:
            log_warn("USB interface not ready - services will start when available")
        
        # Start monitoring services
        if self.config.enable_vpn_failover:
            try:
                run_command(['systemctl', 'start', 'usb-router-vpn-monitor'])
            except subprocess.CalledProcessError:
                log_warn("Could not start VPN monitor")
        
        try:
            run_command(['systemctl', 'start', 'usb-interface-watchdog'])
        except subprocess.CalledProcessError:
            log_warn("Could not start USB watchdog")