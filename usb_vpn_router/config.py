"""
USB VPN Router Configuration
Manages router configuration settings and validation.
"""

import ipaddress
from dataclasses import dataclass
from typing import Optional


@dataclass
class RouterConfig:
    """Configuration for USB VPN Router."""
    
    # Network settings
    usb_network: str = "192.168.64.0/24"
    usb_ip: str = "192.168.64.1"
    usb_dhcp_start: str = "192.168.64.50"
    usb_dhcp_end: str = "192.168.64.150"
    wan_interface: str = "wlan0"
    
    # Interface names
    usb_interface: str = "usb0"
    tailscale_interface: str = "tailscale0"
    openvpn_interface: str = "tun0"
    
    # VPN settings
    use_tailscale_exit: bool = False
    enable_vpn_failover: bool = True
    
    # Web dashboard settings
    dashboard_enabled: bool = False
    dashboard_port: int = 8000
    dashboard_host: str = "0.0.0.0"
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self.validate()
    
    def validate(self):
        """Validate configuration parameters."""
        # Validate network CIDR
        try:
            network = ipaddress.IPv4Network(self.usb_network, strict=False)
            self.usb_network = str(network)
        except ValueError as e:
            raise ValueError(f"Invalid USB network: {e}")
        
        # Validate IP addresses
        try:
            usb_ip = ipaddress.IPv4Address(self.usb_ip)
            dhcp_start = ipaddress.IPv4Address(self.usb_dhcp_start)
            dhcp_end = ipaddress.IPv4Address(self.usb_dhcp_end)
            
            # Check if IPs are in the network
            if usb_ip not in network:
                raise ValueError(f"USB IP {self.usb_ip} not in network {self.usb_network}")
            
            if dhcp_start not in network:
                raise ValueError(f"DHCP start {self.usb_dhcp_start} not in network {self.usb_network}")
            
            if dhcp_end not in network:
                raise ValueError(f"DHCP end {self.usb_dhcp_end} not in network {self.usb_network}")
            
            # Check DHCP range
            if dhcp_start >= dhcp_end:
                raise ValueError("DHCP start must be less than DHCP end")
                
        except ValueError as e:
            raise ValueError(f"Invalid IP configuration: {e}")
        
        # Validate port range
        if not (1 <= self.dashboard_port <= 65535):
            raise ValueError(f"Invalid dashboard port: {self.dashboard_port}")
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> 'RouterConfig':
        """Create configuration from dictionary."""
        return cls(**config_dict)
    
    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            'usb_network': self.usb_network,
            'usb_ip': self.usb_ip,
            'usb_dhcp_start': self.usb_dhcp_start,
            'usb_dhcp_end': self.usb_dhcp_end,
            'wan_interface': self.wan_interface,
            'usb_interface': self.usb_interface,
            'tailscale_interface': self.tailscale_interface,
            'openvpn_interface': self.openvpn_interface,
            'use_tailscale_exit': self.use_tailscale_exit,
            'enable_vpn_failover': self.enable_vpn_failover,
            'dashboard_enabled': self.dashboard_enabled,
            'dashboard_port': self.dashboard_port,
            'dashboard_host': self.dashboard_host,
        }
    
    def get_network_info(self) -> dict:
        """Get network information."""
        network = ipaddress.IPv4Network(self.usb_network)
        return {
            'network': str(network.network_address),
            'netmask': str(network.netmask),
            'broadcast': str(network.broadcast_address),
            'prefix_length': network.prefixlen,
            'host_count': network.num_addresses - 2,  # Exclude network and broadcast
        }