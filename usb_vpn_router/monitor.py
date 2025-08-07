"""
USB VPN Router Monitor
VPN failover monitoring service (replaces usb-router-vpn-monitor bash script).
"""

import time
import json
import subprocess
import signal
import sys
import click
from datetime import datetime
from .utils import run_command, log_info, log_warn, log_error, check_interface_exists


class VPNMonitor:
    """VPN failover monitor for USB router."""
    
    def __init__(self, check_interval=30, ping_timeout=5, test_host="1.1.1.1"):
        self.check_interval = check_interval
        self.ping_timeout = ping_timeout
        self.test_host = test_host
        self.running = False
        
        # Configuration
        self.usb_network = "192.168.64.0/24"
        self.tailscale_interface = "tailscale0"
        self.openvpn_interface = "tun0"
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        log_info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def _log_with_timestamp(self, level, message):
        """Log message with timestamp."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] {message}"
        
        if level == 'info':
            log_info(log_message)
        elif level == 'warn':
            log_warn(log_message)
        elif level == 'error':
            log_error(log_message)
    
    def check_interface_connectivity(self, interface):
        """Check if interface exists and has connectivity."""
        if not check_interface_exists(interface):
            return False
        
        # Check if interface has IP address
        try:
            result = run_command(['ip', 'addr', 'show', interface], capture_output=True)
            if 'inet ' not in result.stdout:
                return False
        except Exception:
            return False
        
        # Test connectivity through interface
        try:
            result = run_command([
                'ping', '-I', interface, '-c', '1', '-W', str(self.ping_timeout), self.test_host
            ], capture_output=True, check=False)
            return result.returncode == 0
        except Exception:
            return False
    
    def get_current_vpn(self):
        """Check which VPN is currently routing USB traffic."""
        try:
            result = run_command(['ip', 'route', 'show', 'table', 'usb_vpn'], 
                                capture_output=True, check=False)
            
            if result.returncode == 0 and result.stdout:
                if self.tailscale_interface in result.stdout:
                    return 'tailscale'
                elif self.openvpn_interface in result.stdout:
                    return 'openvpn'
            
            return 'none'
        except Exception:
            return 'none'
    
    def switch_to_tailscale(self):
        """Switch USB routing to Tailscale."""
        self._log_with_timestamp('info', 'Switching USB routing to Tailscale...')
        
        try:
            # Update routing table
            run_command(['ip', 'route', 'del', 'default', 'table', 'usb_vpn'], check=False)
            
            # Get Tailscale gateway
            result = run_command(['ip', 'route', 'show', 'dev', self.tailscale_interface], 
                                capture_output=True)
            
            # Extract gateway from Tailscale routes
            import re
            gateway_match = re.search(r'^100\.[\d\.]+', result.stdout, re.MULTILINE)
            
            if gateway_match:
                gateway = gateway_match.group(0)
                run_command(['ip', 'route', 'add', 'default', 'via', gateway, 
                           'dev', self.tailscale_interface, 'table', 'usb_vpn'])
            else:
                run_command(['ip', 'route', 'add', 'default', 'dev', self.tailscale_interface, 
                           'table', 'usb_vpn'])
            
            # Update iptables NAT
            run_command(['iptables', '-t', 'nat', '-D', 'POSTROUTING', 
                        '-o', self.openvpn_interface, '-s', self.usb_network, '-j', 'MASQUERADE'], 
                       check=False)
            
            # Ensure Tailscale NAT rule exists
            try:
                run_command(['iptables', '-t', 'nat', '-C', 'POSTROUTING', 
                           '-o', self.tailscale_interface, '-s', self.usb_network, '-j', 'MASQUERADE'])
            except subprocess.CalledProcessError:
                run_command(['iptables', '-t', 'nat', '-A', 'POSTROUTING', 
                           '-o', self.tailscale_interface, '-s', self.usb_network, '-j', 'MASQUERADE'])
            
            self._log_with_timestamp('info', 'Switched to Tailscale successfully')
            return True
            
        except Exception as e:
            self._log_with_timestamp('error', f'Failed to switch to Tailscale: {e}')
            return False
    
    def switch_to_openvpn(self):
        """Switch USB routing to OpenVPN."""
        self._log_with_timestamp('info', 'Switching USB routing to OpenVPN...')
        
        try:
            # Update routing table
            run_command(['ip', 'route', 'del', 'default', 'table', 'usb_vpn'], check=False)
            run_command(['ip', 'route', 'add', 'default', 'dev', self.openvpn_interface, 
                        'table', 'usb_vpn'])
            
            # Update iptables NAT
            run_command(['iptables', '-t', 'nat', '-D', 'POSTROUTING', 
                        '-o', self.tailscale_interface, '-s', self.usb_network, '-j', 'MASQUERADE'], 
                       check=False)
            
            # Ensure OpenVPN NAT rule exists
            try:
                run_command(['iptables', '-t', 'nat', '-C', 'POSTROUTING', 
                           '-o', self.openvpn_interface, '-s', self.usb_network, '-j', 'MASQUERADE'])
            except subprocess.CalledProcessError:
                run_command(['iptables', '-t', 'nat', '-A', 'POSTROUTING', 
                           '-o', self.openvpn_interface, '-s', self.usb_network, '-j', 'MASQUERADE'])
            
            self._log_with_timestamp('info', 'Switched to OpenVPN successfully')
            return True
            
        except Exception as e:
            self._log_with_timestamp('error', f'Failed to switch to OpenVPN: {e}')
            return False
    
    def monitor_loop(self):
        """Main monitoring loop."""
        self._log_with_timestamp('info', 'VPN failover monitor started')
        self.running = True
        
        while self.running:
            try:
                current_vpn = self.get_current_vpn()
                tailscale_up = self.check_interface_connectivity(self.tailscale_interface)
                openvpn_up = self.check_interface_connectivity(self.openvpn_interface)
                
                # Implement failover logic
                if current_vpn == 'tailscale':
                    if not tailscale_up and openvpn_up:
                        self._log_with_timestamp('warn', 'Tailscale down, failing over to OpenVPN')
                        self.switch_to_openvpn()
                
                elif current_vpn == 'openvpn':
                    if tailscale_up:
                        self._log_with_timestamp('info', 'Tailscale is back up, switching back from OpenVPN')
                        self.switch_to_tailscale()
                    elif not openvpn_up:
                        self._log_with_timestamp('error', 'WARNING: OpenVPN is down and Tailscale unavailable!')
                
                elif current_vpn == 'none':
                    if tailscale_up:
                        self._log_with_timestamp('info', 'Tailscale available, enabling VPN routing')
                        self.switch_to_tailscale()
                    elif openvpn_up:
                        self._log_with_timestamp('info', 'OpenVPN available, enabling VPN routing')
                        self.switch_to_openvpn()
                    else:
                        self._log_with_timestamp('warn', 'WARNING: No VPN connections available!')
                
                # Sleep before next check
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                self._log_with_timestamp('error', f'Monitor error: {e}')
                time.sleep(self.check_interval)
        
        self._log_with_timestamp('info', 'VPN failover monitor stopped')
    
    def get_status(self):
        """Get current monitor status."""
        current_vpn = self.get_current_vpn()
        tailscale_status = 'UP' if self.check_interface_connectivity(self.tailscale_interface) else 'DOWN'
        openvpn_status = 'UP' if self.check_interface_connectivity(self.openvpn_interface) else 'DOWN'
        
        return {
            'current_vpn': current_vpn,
            'tailscale': tailscale_status,
            'openvpn': openvpn_status,
            'monitor_running': self.running
        }


@click.command()
@click.option('--check-interval', default=30, help='Check interval in seconds')
@click.option('--ping-timeout', default=5, help='Ping timeout in seconds')
@click.option('--test-host', default='1.1.1.1', help='Host to test connectivity')
@click.option('--status-only', is_flag=True, help='Show status and exit')
def main(check_interval, ping_timeout, test_host, status_only):
    """USB VPN Router failover monitor."""
    
    monitor = VPNMonitor(
        check_interval=check_interval,
        ping_timeout=ping_timeout,
        test_host=test_host
    )
    
    if status_only:
        # Show status and exit
        status = monitor.get_status()
        click.echo(f"Current VPN: {status['current_vpn']}")
        click.echo(f"Tailscale: {status['tailscale']}")
        click.echo(f"OpenVPN: {status['openvpn']}")
        return
    
    try:
        # Start monitoring
        monitor.monitor_loop()
    except KeyboardInterrupt:
        log_info("Monitor stopped by user")
    except Exception as e:
        log_error(f"Monitor failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()