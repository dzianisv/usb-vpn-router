"""
USB VPN Router CLI Commands
Command-line interface for router management (replaces bash scripts).
"""

import json
import subprocess
import click
import psutil
from .utils import run_command, log_info, log_warn, log_error, check_interface_exists


@click.group()
def cli():
    """USB VPN Router command-line interface."""
    pass


@cli.command()
def status():
    """Show comprehensive router status (replaces usb-router-status)."""
    click.echo("=== USB Router Status ===")
    click.echo()
    
    # USB Interface Status
    click.echo("USB Interface:")
    if check_interface_exists('usb0'):
        try:
            result = run_command(['ip', 'addr', 'show', 'usb0'], capture_output=True)
            click.echo(f"  Status: UP")
            # Extract IP from output
            import re
            ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+/\d+)', result.stdout)
            if ip_match:
                click.echo(f"  IP: {ip_match.group(1)}")
        except Exception:
            click.echo("  Status: DOWN")
    else:
        click.echo("  Interface not found")
    
    click.echo()
    
    # DHCP Leases
    click.echo("DHCP Leases:")
    try:
        with open('/var/lib/misc/dnsmasq.leases', 'r') as f:
            leases = f.read().strip()
            if leases:
                for line in leases.split('\n'):
                    parts = line.split()
                    if len(parts) >= 4:
                        click.echo(f"  {parts[2]} - {parts[3]} ({parts[1]})")
            else:
                click.echo("  No active leases")
    except FileNotFoundError:
        click.echo("  No lease file found")
    
    click.echo()
    
    # VPN Status
    click.echo("VPN Status:")
    
    # Tailscale
    try:
        result = run_command(['tailscale', 'status'], capture_output=True, check=False)
        if result.returncode == 0:
            click.echo("  Tailscale: UP")
            # Get exit node info
            try:
                json_result = run_command(['tailscale', 'status', '--json'], capture_output=True)
                data = json.loads(json_result.stdout)
                for peer_id, peer_data in data.get('Peer', {}).items():
                    if peer_data.get('ExitNode', False):
                        click.echo(f"    Exit Node: {peer_data.get('HostName', 'Unknown')}")
                        break
                else:
                    click.echo("    Exit Node: None")
            except Exception:
                pass
        else:
            click.echo("  Tailscale: DOWN")
    except Exception:
        click.echo("  Tailscale: Error checking status")
    
    # OpenVPN
    if check_interface_exists('tun0'):
        click.echo("  OpenVPN: UP")
    else:
        click.echo("  OpenVPN: DOWN")
    
    click.echo()
    
    # System Metrics
    click.echo("System Metrics:")
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        click.echo(f"  CPU: {cpu_percent:.1f}%")
        click.echo(f"  Memory: {memory.percent:.1f}% ({memory.used // 1024**2}MB / {memory.total // 1024**2}MB)")
        click.echo(f"  Disk: {(disk.used / disk.total * 100):.1f}% ({disk.used // 1024**3}GB / {disk.total // 1024**3}GB)")
    except Exception as e:
        click.echo(f"  Error getting metrics: {e}")


@cli.command()
def reset():
    """Reset USB interface (replaces usb-router-reset)."""
    click.echo("Resetting USB router...")
    
    try:
        # Restart networking
        run_command(['systemctl', 'restart', 'systemd-networkd'])
        
        # Reload USB gadget module
        run_command(['modprobe', '-r', 'g_ether'])
        run_command(['modprobe', 'g_ether', 'use_eem=0'])
        
        # Wait and configure interface
        import time
        time.sleep(2)
        
        run_command(['ip', 'link', 'set', 'usb0', 'up'])
        run_command(['ip', 'addr', 'add', '192.168.64.1/24', 'dev', 'usb0'])
        
        # Restart DHCP
        run_command(['systemctl', 'restart', 'dnsmasq'])
        
        click.echo("✅ USB router reset complete")
        
    except Exception as e:
        click.echo(f"❌ Reset failed: {e}")


@cli.group()
def tailscale_control():
    """Tailscale VPN control (replaces usb-router-tailscale)."""
    pass


@tailscale_control.command('on')
def tailscale_on():
    """Enable Tailscale VPN routing for USB clients."""
    click.echo("Enabling Tailscale split routing (USB clients only)...")
    
    try:
        # Check Tailscale status
        result = run_command(['tailscale', 'status'], capture_output=True, check=False)
        if result.returncode != 0:
            click.echo("❌ Tailscale is not authenticated. Run 'tailscale up' first")
            return
        
        # Enable local network access
        run_command(['tailscale', 'set', '--exit-node-allow-lan-access=true'])
        
        # Setup routing table
        _setup_vpn_routing()
        
        click.echo("✅ Split routing enabled:")
        click.echo("  - USB clients (192.168.64.0/24) → Tailscale VPN only")
        click.echo("  - Orange Pi device → Local network (SSH access maintained)")
        
    except Exception as e:
        click.echo(f"❌ Failed to enable Tailscale routing: {e}")


@tailscale_control.command('off')
def tailscale_off():
    """Disable Tailscale VPN routing (use local WAN)."""
    click.echo("Disabling Tailscale routing...")
    
    try:
        _setup_local_routing()
        click.echo("✅ USB traffic now routed through local WAN")
        
    except Exception as e:
        click.echo(f"❌ Failed to disable Tailscale routing: {e}")


@tailscale_control.command('status')
def tailscale_status():
    """Show current routing status."""
    click.echo("Current routing configuration:")
    
    try:
        # Check NAT rules
        result = run_command(['iptables', '-t', 'nat', '-L', 'POSTROUTING', '-n'], capture_output=True)
        
        if 'tailscale0' in result.stdout:
            click.echo("  USB traffic is routed through Tailscale")
            
            # Check for exit node
            try:
                ts_result = run_command(['tailscale', 'status'], capture_output=True)
                if 'offers exit node' in ts_result.stdout:
                    click.echo("  Exit node configured")
                else:
                    click.echo("  ⚠️  No exit node configured")
            except Exception:
                pass
        else:
            wan_interface = _get_wan_interface()
            click.echo(f"  USB traffic is routed through local WAN ({wan_interface})")
            
    except Exception as e:
        click.echo(f"❌ Error checking status: {e}")


def _setup_vpn_routing():
    """Setup VPN routing for USB clients."""
    USB_NETWORK = "192.168.64.0/24"
    USB_INTERFACE = "usb0"
    TAILSCALE_INTERFACE = "tailscale0"
    OPENVPN_INTERFACE = "tun0"
    
    # Create routing table if not exists
    try:
        with open('/etc/iproute2/rt_tables', 'r') as f:
            if 'usb_vpn' not in f.read():
                with open('/etc/iproute2/rt_tables', 'a') as f:
                    f.write('200 usb_vpn\n')
    except Exception:
        pass
    
    # Setup routing rules
    try:
        run_command(['ip', 'rule', 'del', 'from', USB_NETWORK, 'table', 'usb_vpn'], check=False)
        run_command(['ip', 'rule', 'add', 'from', USB_NETWORK, 'table', 'usb_vpn', 'priority', '200'])
    except Exception:
        pass
    
    # Clear and setup iptables
    run_command(['iptables', '-F', 'FORWARD'])
    run_command(['iptables', '-t', 'nat', '-F', 'POSTROUTING'])
    
    # Add NAT rules
    for interface in [TAILSCALE_INTERFACE, OPENVPN_INTERFACE]:
        run_command(['iptables', '-t', 'nat', '-A', 'POSTROUTING', 
                    '-o', interface, '-s', USB_NETWORK, '-j', 'MASQUERADE'])
    
    # Add forward rules
    for interface in [TAILSCALE_INTERFACE, OPENVPN_INTERFACE]:
        run_command(['iptables', '-A', 'FORWARD', '-i', USB_INTERFACE, 
                    '-o', interface, '-j', 'ACCEPT'])
        run_command(['iptables', '-A', 'FORWARD', '-i', interface, 
                    '-o', USB_INTERFACE, '-m', 'state', 
                    '--state', 'RELATED,ESTABLISHED', '-j', 'ACCEPT'])
    
    # Save rules
    _save_iptables()


def _setup_local_routing():
    """Setup local WAN routing."""
    USB_NETWORK = "192.168.64.0/24"
    USB_INTERFACE = "usb0"
    wan_interface = _get_wan_interface()
    
    # Clear existing rules
    run_command(['iptables', '-F', 'FORWARD'])
    run_command(['iptables', '-t', 'nat', '-F', 'POSTROUTING'])
    
    # Add local routing
    run_command(['iptables', '-t', 'nat', '-A', 'POSTROUTING', 
                '-o', wan_interface, '-s', USB_NETWORK, '-j', 'MASQUERADE'])
    run_command(['iptables', '-A', 'FORWARD', '-i', USB_INTERFACE, 
                '-o', wan_interface, '-j', 'ACCEPT'])
    run_command(['iptables', '-A', 'FORWARD', '-i', wan_interface, 
                '-o', USB_INTERFACE, '-m', 'state', 
                '--state', 'RELATED,ESTABLISHED', '-j', 'ACCEPT'])
    
    # Save rules
    _save_iptables()


def _get_wan_interface():
    """Get WAN interface name."""
    # Try common interface names
    for interface in ['wlan0', 'eth0', 'enp0s3']:
        if check_interface_exists(interface):
            return interface
    return 'wlan0'  # Default fallback


def _save_iptables():
    """Save iptables rules."""
    try:
        run_command(['netfilter-persistent', 'save'])
    except Exception:
        try:
            run_command(['iptables-save'], stdout_file='/etc/iptables/rules.v4')
        except Exception:
            pass


# Add commands to main CLI
cli.add_command(status)
cli.add_command(reset)
cli.add_command(tailscale_control, name='tailscale')


if __name__ == '__main__':
    cli()