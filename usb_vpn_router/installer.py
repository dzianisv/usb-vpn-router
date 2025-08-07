#!/usr/bin/env python3
"""
USB VPN Router Installer
Main installation script that replaces the bash setup script.
"""

import os
import sys
import subprocess
import shutil
import platform
import click
from pathlib import Path
from .core import USBRouterCore
from .config import RouterConfig
from .utils import run_command, check_root, log_info, log_warn, log_error


@click.command()
@click.option('--use-tailscale-exit', is_flag=True, default=False,
              help='Route USB clients through Tailscale exit node')
@click.option('--enable-vpn-failover', is_flag=True, default=True,
              help='Enable automatic VPN failover monitoring')
@click.option('--enable-dashboard', is_flag=True, default=False,
              help='Install web dashboard (Ajenti-based)')
@click.option('--wan-interface', default='wlan0',
              help='WAN interface name (default: wlan0)')
@click.option('--usb-network', default='192.168.64.0/24',
              help='USB client network (default: 192.168.64.0/24)')
@click.option('--skip-packages', is_flag=True, default=False,
              help='Skip package installation (for testing)')
def main(use_tailscale_exit, enable_vpn_failover, enable_dashboard, 
         wan_interface, usb_network, skip_packages):
    """Install and configure USB VPN Router."""
    
    log_info("Starting USB VPN Router installation...")
    
    # Check prerequisites
    check_root()
    check_platform()
    
    # Create configuration
    config = RouterConfig(
        use_tailscale_exit=use_tailscale_exit,
        enable_vpn_failover=enable_vpn_failover,
        wan_interface=wan_interface,
        usb_network=usb_network
    )
    
    # Initialize core router
    router = USBRouterCore(config)
    
    try:
        # Installation steps
        if not skip_packages:
            install_packages()
        
        router.setup_usb_gadget()
        router.setup_network_interface()
        router.setup_dhcp_server()
        router.setup_nat_and_routing()
        router.setup_openvpn()
        router.setup_tailscale()
        router.create_helper_scripts()
        router.create_systemd_services()
        
        if enable_dashboard:
            install_web_dashboard()
        
        # Start services
        router.start_services()
        
        log_info("✅ USB VPN Router installation completed successfully!")
        print_success_message(config, enable_dashboard)
        
    except Exception as e:
        log_error(f"Installation failed: {str(e)}")
        sys.exit(1)


def check_platform():
    """Check if running on supported platform."""
    if platform.system() != 'Linux':
        log_error("USB VPN Router only supports Linux systems")
        sys.exit(1)
    
    # Check for ARM architecture (typical for Orange Pi/Raspberry Pi)
    arch = platform.machine()
    if arch not in ['armv7l', 'aarch64', 'x86_64']:
        log_warn(f"Platform {arch} may not be fully supported")


def install_packages():
    """Install required system packages."""
    log_info("Installing required packages...")
    
    # Detect package manager
    if shutil.which('apt-get'):
        install_debian_packages()
    elif shutil.which('yum'):
        install_redhat_packages()
    elif shutil.which('pacman'):
        install_arch_packages()
    else:
        log_error("Unsupported package manager")
        sys.exit(1)


def install_debian_packages():
    """Install packages on Debian/Ubuntu systems."""
    packages = [
        'dnsmasq',
        'iptables-persistent',
        'tcpdump',
        'curl',
        'wget',
        'gnupg',
        'lsb-release',
        'ca-certificates',
        'openvpn',
        'jq',
        'python3-pip',
        'python3-venv'
    ]
    
    # Update package list
    run_command(['apt-get', 'update'])
    
    # Install packages
    cmd = ['apt-get', 'install', '-y'] + packages
    run_command(cmd)


def install_redhat_packages():
    """Install packages on Red Hat/CentOS systems."""
    packages = [
        'dnsmasq',
        'iptables-services',
        'tcpdump',
        'curl',
        'wget',
        'gnupg2',
        'ca-certificates',
        'openvpn',
        'jq',
        'python3-pip'
    ]
    
    cmd = ['yum', 'install', '-y'] + packages
    run_command(cmd)


def install_arch_packages():
    """Install packages on Arch Linux systems."""
    packages = [
        'dnsmasq',
        'iptables',
        'tcpdump',
        'curl',
        'wget',
        'gnupg',
        'ca-certificates',
        'openvpn',
        'jq',
        'python-pip'
    ]
    
    cmd = ['pacman', '-S', '--noconfirm'] + packages
    run_command(cmd)


def install_web_dashboard():
    """Install Ajenti web dashboard with custom plugins."""
    log_info("Installing web dashboard...")
    
    try:
        # Install Ajenti and dependencies
        run_command([sys.executable, '-m', 'pip', 'install', 
                    'ajenti-panel', 'ajenti.plugin.core', 'ajenti.plugin.dashboard'])
        
        # Install custom plugins
        install_ajenti_plugins()
        
        # Configure Ajenti
        configure_ajenti()
        
        # Create and enable systemd service
        create_ajenti_service()
        
        log_info("✅ Web dashboard installed successfully")
        
    except Exception as e:
        log_error(f"Failed to install web dashboard: {str(e)}")
        raise


def install_ajenti_plugins():
    """Install custom Ajenti plugins."""
    plugin_dir = Path('/var/lib/ajenti/plugins')
    plugin_dir.mkdir(parents=True, exist_ok=True)
    
    # Get package directory
    package_dir = Path(__file__).parent
    plugins_source = package_dir / 'ajenti_plugins'
    
    if plugins_source.exists():
        # Copy plugins
        for plugin in plugins_source.iterdir():
            if plugin.is_dir():
                dest = plugin_dir / plugin.name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(plugin, dest)
                
        # Set permissions
        run_command(['chown', '-R', 'root:root', str(plugin_dir)])
        run_command(['chmod', '-R', '755', str(plugin_dir)])
        
        log_info("Custom plugins installed")
    else:
        log_warn("Plugin source directory not found")


def configure_ajenti():
    """Configure Ajenti web panel."""
    config_dir = Path('/etc/ajenti')
    config_dir.mkdir(exist_ok=True)
    
    # Main configuration
    config_content = """
name: orangepi-router
max_sessions: 9
session_max_time: 3600
bind:
  host: 0.0.0.0
  port: 8000
ssl:
  enable: false
color: default
language: en
"""
    
    with open(config_dir / 'config.yml', 'w') as f:
        f.write(config_content)
    
    # Users configuration (default admin/admin)
    users_content = """
users:
  admin:
    password: admin
    permissions: []
"""
    
    with open(config_dir / 'users.yml', 'w') as f:
        f.write(users_content)


def create_ajenti_service():
    """Create systemd service for Ajenti."""
    service_content = """
[Unit]
Description=Ajenti USB Router Dashboard
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/ajenti-panel -c /etc/ajenti/config.yml --stock-plugins
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    with open('/etc/systemd/system/ajenti.service', 'w') as f:
        f.write(service_content)
    
    # Enable and start service
    run_command(['systemctl', 'daemon-reload'])
    run_command(['systemctl', 'enable', 'ajenti'])


def print_success_message(config, dashboard_enabled):
    """Print installation success message."""
    print("\n" + "="*60)
    print("🎉 USB VPN Router Installation Complete!")
    print("="*60)
    
    print("\n📋 Configuration:")
    print(f"  • USB Network: {config.usb_network}")
    print(f"  • WAN Interface: {config.wan_interface}")
    print(f"  • Tailscale Exit: {'Enabled' if config.use_tailscale_exit else 'Disabled'}")
    print(f"  • VPN Failover: {'Enabled' if config.enable_vpn_failover else 'Disabled'}")
    
    if dashboard_enabled:
        print(f"  • Web Dashboard: Enabled (http://192.168.0.226:8000)")
        print("    Default login: admin/admin (⚠️  CHANGE IMMEDIATELY!)")
    
    print("\n🚀 Next Steps:")
    print("1. Connect USB cable to host computer")
    print("2. Host should receive IP via DHCP (192.168.64.50-150)")
    
    if config.use_tailscale_exit:
        print("3. Configure Tailscale: tailscale up")
        print("4. Check status: usb-router-status")
    else:
        print("3. Configure VPN as needed")
        print("4. Enable VPN routing: usb-router-tailscale on")
    
    print("\n📚 Commands:")
    print("  usb-router-status     - Check router status")
    print("  usb-router-reset      - Reset USB interface")
    print("  usb-router-tailscale  - Manage VPN routing")
    
    if dashboard_enabled:
        print("\n🌐 Web Dashboard:")
        print("  URL: http://192.168.0.226:8000")
        print("  Features: System monitoring, VPN management, routing control")
    
    print("\n" + "="*60)


if __name__ == '__main__':
    main()