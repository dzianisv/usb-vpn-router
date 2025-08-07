import subprocess
import json
import psutil
import re
from aj.api import *
from aj.plugins.main.api import SectionPlugin


@component(SectionPlugin)
class USBRouterStatusPlugin(SectionPlugin):
    def __init__(self, context):
        self.context = context
        self.title = 'USB Router'
        self.icon = 'fa fa-router'
        self.category = 'System'

    def init(self):
        self.title = 'USB Router Status'
        self.icon = 'fa fa-router'
        self.category = 'System'

    @on('initial-load')
    def on_initial_load(self):
        pass

    def get_usb_router_status(self):
        """Get comprehensive USB router status"""
        try:
            # Execute the existing usb-router-status script
            result = subprocess.run(['/usr/local/bin/usb-router-status'], 
                                  capture_output=True, text=True, timeout=10)
            
            status = {
                'usb_interface': self._get_usb_interface_status(),
                'dhcp_leases': self._get_dhcp_leases(),
                'vpn_status': self._get_vpn_status(),
                'routing': self._get_routing_info(),
                'services': self._get_service_status(),
                'system': self._get_system_metrics(),
                'raw_output': result.stdout if result.returncode == 0 else result.stderr
            }
            
            return status
            
        except Exception as e:
            return {'error': str(e)}

    def _get_usb_interface_status(self):
        """Get USB interface details"""
        try:
            result = subprocess.run(['ip', 'addr', 'show', 'usb0'], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                # Parse IP address from output
                ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+/\d+)', result.stdout)
                state_match = re.search(r'state (\w+)', result.stdout)
                
                return {
                    'status': 'UP' if 'UP' in result.stdout else 'DOWN',
                    'ip_address': ip_match.group(1) if ip_match else 'Not assigned',
                    'state': state_match.group(1) if state_match else 'UNKNOWN',
                    'details': result.stdout
                }
            else:
                return {
                    'status': 'NOT_FOUND',
                    'ip_address': 'N/A',
                    'state': 'DOWN',
                    'details': 'Interface not found'
                }
                
        except Exception as e:
            return {'status': 'ERROR', 'details': str(e)}

    def _get_dhcp_leases(self):
        """Get DHCP lease information"""
        try:
            leases = []
            lease_file = '/var/lib/misc/dnsmasq.leases'
            
            with open(lease_file, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        leases.append({
                            'expiry': parts[0],
                            'mac': parts[1],
                            'ip': parts[2],
                            'hostname': parts[3] if len(parts) > 3 else 'Unknown',
                            'client_id': parts[4] if len(parts) > 4 else ''
                        })
            
            return leases
            
        except FileNotFoundError:
            return []
        except Exception as e:
            return [{'error': str(e)}]

    def _get_vpn_status(self):
        """Get VPN status information"""
        vpn_status = {}
        
        try:
            # Check Tailscale status
            ts_result = subprocess.run(['tailscale', 'status', '--json'], 
                                     capture_output=True, text=True, timeout=10)
            if ts_result.returncode == 0:
                ts_data = json.loads(ts_result.stdout)
                vpn_status['tailscale'] = {
                    'status': 'UP',
                    'backend_state': ts_data.get('BackendState', 'Unknown'),
                    'self': ts_data.get('Self', {}),
                    'exit_node': self._get_current_exit_node(ts_data),
                    'peers': len(ts_data.get('Peer', {}))
                }
            else:
                vpn_status['tailscale'] = {'status': 'DOWN', 'error': ts_result.stderr}
                
        except Exception as e:
            vpn_status['tailscale'] = {'status': 'ERROR', 'error': str(e)}

        try:
            # Check OpenVPN status
            ovpn_result = subprocess.run(['ip', 'link', 'show', 'tun0'], 
                                       capture_output=True, text=True, timeout=5)
            if ovpn_result.returncode == 0:
                vpn_status['openvpn'] = {
                    'status': 'UP' if 'UP' in ovpn_result.stdout else 'DOWN',
                    'interface': 'tun0'
                }
            else:
                vpn_status['openvpn'] = {'status': 'DOWN'}
                
        except Exception as e:
            vpn_status['openvpn'] = {'status': 'ERROR', 'error': str(e)}

        # Check VPN monitor service
        try:
            monitor_result = subprocess.run(['systemctl', 'is-active', 'usb-router-vpn-monitor'], 
                                          capture_output=True, text=True, timeout=5)
            vpn_status['monitor'] = monitor_result.stdout.strip()
        except Exception:
            vpn_status['monitor'] = 'unknown'

        return vpn_status

    def _get_current_exit_node(self, tailscale_data):
        """Extract current exit node from Tailscale status"""
        try:
            peers = tailscale_data.get('Peer', {})
            for peer_id, peer_data in peers.items():
                if peer_data.get('ExitNode', False):
                    return {
                        'hostname': peer_data.get('HostName', 'Unknown'),
                        'tailscale_ip': peer_data.get('TailscaleIPs', [])[0] if peer_data.get('TailscaleIPs') else 'Unknown'
                    }
            return None
        except Exception:
            return None

    def _get_routing_info(self):
        """Get routing table information"""
        routing = {}
        
        try:
            # Get main routing table
            main_routes = subprocess.run(['ip', 'route', 'show'], 
                                       capture_output=True, text=True, timeout=5)
            routing['main'] = main_routes.stdout if main_routes.returncode == 0 else 'Error'
            
            # Get VPN routing table
            vpn_routes = subprocess.run(['ip', 'route', 'show', 'table', 'usb_vpn'], 
                                      capture_output=True, text=True, timeout=5)
            routing['usb_vpn'] = vpn_routes.stdout if vpn_routes.returncode == 0 else 'No VPN routes'
            
            # Get routing rules
            rules = subprocess.run(['ip', 'rule', 'show'], 
                                 capture_output=True, text=True, timeout=5)
            routing['rules'] = rules.stdout if rules.returncode == 0 else 'Error'
            
        except Exception as e:
            routing['error'] = str(e)
            
        return routing

    def _get_service_status(self):
        """Get status of key services"""
        services = {}
        service_list = ['dnsmasq', 'tailscaled', 'usb-router-vpn-monitor', 'usb-interface-watchdog']
        
        for service in service_list:
            try:
                result = subprocess.run(['systemctl', 'is-active', service], 
                                      capture_output=True, text=True, timeout=5)
                services[service] = result.stdout.strip()
            except Exception:
                services[service] = 'unknown'
                
        return services

    def _get_system_metrics(self):
        """Get basic system metrics"""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory': dict(psutil.virtual_memory()._asdict()),
                'disk': dict(psutil.disk_usage('/')._asdict()),
                'uptime': subprocess.run(['uptime'], capture_output=True, text=True).stdout.strip(),
                'load_avg': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else 'N/A'
            }
        except Exception as e:
            return {'error': str(e)}

    @url(r'/api/usb-router/status')
    @endpoint(api=True)
    def handle_api_status(self, http_context):
        """API endpoint for status data"""
        return self.get_usb_router_status()

    @url(r'/api/usb-router/restart-service/(?P<service>\w+)')
    @endpoint(api=True)
    def handle_restart_service(self, http_context, service=None):
        """API endpoint to restart services"""
        if not service:
            return {'error': 'No service specified'}
            
        allowed_services = ['dnsmasq', 'usb-router-vpn-monitor', 'usb-interface-watchdog']
        if service not in allowed_services:
            return {'error': f'Service {service} not allowed'}
            
        try:
            result = subprocess.run(['systemctl', 'restart', service], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return {'success': True, 'message': f'Service {service} restarted successfully'}
            else:
                return {'success': False, 'error': result.stderr}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @url(r'/api/usb-router/reset-interface')
    @endpoint(api=True)
    def handle_reset_interface(self, http_context):
        """API endpoint to reset USB interface"""
        try:
            result = subprocess.run(['/usr/local/bin/usb-router-reset'], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return {'success': True, 'message': 'USB interface reset successfully', 'output': result.stdout}
            else:
                return {'success': False, 'error': result.stderr}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}