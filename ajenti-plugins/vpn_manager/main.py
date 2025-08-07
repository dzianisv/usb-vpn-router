import subprocess
import json
import time
from aj.api import *
from aj.plugins.main.api import SectionPlugin


@component(SectionPlugin)
class VPNManagerPlugin(SectionPlugin):
    def __init__(self, context):
        self.context = context
        self.title = 'VPN Manager'
        self.icon = 'fa fa-shield-alt'
        self.category = 'Network'

    def init(self):
        self.title = 'VPN Manager'
        self.icon = 'fa fa-shield-alt'
        self.category = 'Network'

    @on('initial-load')
    def on_initial_load(self):
        pass

    def get_tailscale_status(self):
        """Get detailed Tailscale status"""
        try:
            result = subprocess.run(['tailscale', 'status', '--json'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return {
                    'connected': True,
                    'backend_state': data.get('BackendState', 'Unknown'),
                    'self': data.get('Self', {}),
                    'peers': data.get('Peer', {}),
                    'current_exit_node': self._get_current_exit_node(data),
                    'available_exit_nodes': self._get_available_exit_nodes(data)
                }
            else:
                return {
                    'connected': False,
                    'error': result.stderr.strip(),
                    'peers': {},
                    'available_exit_nodes': []
                }
                
        except Exception as e:
            return {
                'connected': False,
                'error': str(e),
                'peers': {},
                'available_exit_nodes': []
            }

    def _get_current_exit_node(self, tailscale_data):
        """Extract current exit node from Tailscale status"""
        try:
            peers = tailscale_data.get('Peer', {})
            for peer_id, peer_data in peers.items():
                if peer_data.get('ExitNode', False):
                    return {
                        'id': peer_id,
                        'hostname': peer_data.get('HostName', 'Unknown'),
                        'tailscale_ip': peer_data.get('TailscaleIPs', [])[0] if peer_data.get('TailscaleIPs') else 'Unknown',
                        'location': peer_data.get('Location', {}),
                        'online': peer_data.get('Online', False)
                    }
            return None
        except Exception:
            return None

    def _get_available_exit_nodes(self, tailscale_data):
        """Get list of available exit nodes"""
        try:
            exit_nodes = []
            peers = tailscale_data.get('Peer', {})
            
            for peer_id, peer_data in peers.items():
                if peer_data.get('ExitNodeOption', False):
                    exit_nodes.append({
                        'id': peer_id,
                        'hostname': peer_data.get('HostName', 'Unknown'),
                        'tailscale_ip': peer_data.get('TailscaleIPs', [])[0] if peer_data.get('TailscaleIPs') else 'Unknown',
                        'location': peer_data.get('Location', {}),
                        'online': peer_data.get('Online', False),
                        'is_current': peer_data.get('ExitNode', False)
                    })
            
            return sorted(exit_nodes, key=lambda x: x['hostname'])
            
        except Exception:
            return []

    def get_openvpn_status(self):
        """Get OpenVPN connection status"""
        try:
            # Check if tun0 interface exists and is up
            result = subprocess.run(['ip', 'link', 'show', 'tun0'], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                # Get interface details
                addr_result = subprocess.run(['ip', 'addr', 'show', 'tun0'], 
                                           capture_output=True, text=True, timeout=5)
                
                # Check service status
                service_result = subprocess.run(['systemctl', 'status', 'openvpn-client@*'], 
                                              capture_output=True, text=True, timeout=5)
                
                return {
                    'connected': 'UP' in result.stdout,
                    'interface_details': addr_result.stdout if addr_result.returncode == 0 else 'Error getting details',
                    'service_status': service_result.stdout if service_result.returncode == 0 else 'No OpenVPN services running'
                }
            else:
                return {
                    'connected': False,
                    'error': 'tun0 interface not found',
                    'interface_details': '',
                    'service_status': ''
                }
                
        except Exception as e:
            return {
                'connected': False,
                'error': str(e),
                'interface_details': '',
                'service_status': ''
            }

    def get_routing_mode(self):
        """Get current routing mode (local WAN vs VPN)"""
        try:
            # Check if VPN routing table exists and has routes
            result = subprocess.run(['ip', 'route', 'show', 'table', 'usb_vpn'], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0 and result.stdout.strip():
                # Check which VPN interface is being used
                if 'tailscale0' in result.stdout:
                    return {
                        'mode': 'tailscale',
                        'description': 'USB clients routed through Tailscale VPN',
                        'routes': result.stdout
                    }
                elif 'tun0' in result.stdout:
                    return {
                        'mode': 'openvpn',
                        'description': 'USB clients routed through OpenVPN',
                        'routes': result.stdout
                    }
                else:
                    return {
                        'mode': 'vpn_configured',
                        'description': 'VPN routing configured but no active VPN',
                        'routes': result.stdout
                    }
            else:
                return {
                    'mode': 'local',
                    'description': 'USB clients routed through local WAN',
                    'routes': 'No VPN routes configured'
                }
                
        except Exception as e:
            return {
                'mode': 'error',
                'description': f'Error checking routing: {str(e)}',
                'routes': ''
            }

    @url(r'/api/vpn/status')
    @endpoint(api=True)
    def handle_api_status(self, http_context):
        """API endpoint for VPN status"""
        return {
            'tailscale': self.get_tailscale_status(),
            'openvpn': self.get_openvpn_status(),
            'routing': self.get_routing_mode()
        }

    @url(r'/api/vpn/tailscale/switch-exit-node')
    @endpoint(api=True)
    def handle_switch_exit_node(self, http_context):
        """API endpoint to switch Tailscale exit node"""
        try:
            data = json.loads(http_context.body.decode())
            node_hostname = data.get('hostname', '')
            
            if not node_hostname:
                return {'success': False, 'error': 'No hostname provided'}
            
            # Use tailscale up to switch exit node
            if node_hostname == 'none':
                # Disable exit node
                result = subprocess.run(['tailscale', 'up', '--exit-node='], 
                                      capture_output=True, text=True, timeout=30)
            else:
                # Switch to specified exit node
                result = subprocess.run(['tailscale', 'up', f'--exit-node={node_hostname}'], 
                                      capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return {
                    'success': True, 
                    'message': f'Exit node switched to {node_hostname if node_hostname != "none" else "disabled"}',
                    'output': result.stdout
                }
            else:
                return {
                    'success': False, 
                    'error': result.stderr or 'Unknown error occurred'
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @url(r'/api/vpn/routing/switch')
    @endpoint(api=True)
    def handle_switch_routing(self, http_context):
        """API endpoint to switch between local and VPN routing"""
        try:
            data = json.loads(http_context.body.decode())
            mode = data.get('mode', '')
            
            if mode == 'local':
                # Switch to local WAN routing
                result = subprocess.run(['/usr/local/bin/usb-router-tailscale', 'off'], 
                                      capture_output=True, text=True, timeout=30)
            elif mode == 'vpn':
                # Switch to VPN routing
                result = subprocess.run(['/usr/local/bin/usb-router-tailscale', 'on'], 
                                      capture_output=True, text=True, timeout=30)
            else:
                return {'success': False, 'error': 'Invalid mode. Use "local" or "vpn"'}
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': f'Routing switched to {mode}',
                    'output': result.stdout
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr or 'Failed to switch routing mode'
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @url(r'/api/vpn/tailscale/authenticate')
    @endpoint(api=True)
    def handle_tailscale_auth(self, http_context):
        """API endpoint to get Tailscale authentication URL"""
        try:
            result = subprocess.run(['tailscale', 'up', '--auth-key='], 
                                  capture_output=True, text=True, timeout=10)
            
            # This will typically fail with auth required, but gives us the URL
            if 'https://' in result.stderr:
                import re
                url_match = re.search(r'https://[^\s]+', result.stderr)
                if url_match:
                    return {
                        'success': True,
                        'auth_url': url_match.group(0),
                        'message': 'Visit the URL to authenticate Tailscale'
                    }
            
            return {
                'success': False,
                'error': 'Could not generate authentication URL',
                'output': result.stderr
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @url(r'/api/vpn/openvpn/restart')
    @endpoint(api=True)
    def handle_openvpn_restart(self, http_context):
        """API endpoint to restart OpenVPN service"""
        try:
            # Get list of OpenVPN client services
            list_result = subprocess.run(['systemctl', 'list-units', '--type=service', '--state=loaded', 'openvpn-client@*'], 
                                       capture_output=True, text=True, timeout=10)
            
            if 'openvpn-client@' in list_result.stdout:
                # Restart all OpenVPN client services
                restart_result = subprocess.run(['systemctl', 'restart', 'openvpn-client@*'], 
                                              capture_output=True, text=True, timeout=30)
                
                if restart_result.returncode == 0:
                    return {
                        'success': True,
                        'message': 'OpenVPN services restarted successfully'
                    }
                else:
                    return {
                        'success': False,
                        'error': restart_result.stderr or 'Failed to restart OpenVPN services'
                    }
            else:
                return {
                    'success': False,
                    'error': 'No OpenVPN client services found'
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @url(r'/api/vpn/monitor/toggle')
    @endpoint(api=True)
    def handle_monitor_toggle(self, http_context):
        """API endpoint to start/stop VPN failover monitor"""
        try:
            # Check current status
            status_result = subprocess.run(['systemctl', 'is-active', 'usb-router-vpn-monitor'], 
                                         capture_output=True, text=True, timeout=5)
            
            if status_result.stdout.strip() == 'active':
                # Stop the monitor
                result = subprocess.run(['systemctl', 'stop', 'usb-router-vpn-monitor'], 
                                      capture_output=True, text=True, timeout=15)
                action = 'stopped'
            else:
                # Start the monitor
                result = subprocess.run(['systemctl', 'start', 'usb-router-vpn-monitor'], 
                                      capture_output=True, text=True, timeout=15)
                action = 'started'
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': f'VPN monitor {action} successfully'
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr or f'Failed to {action.rstrip("ed")} VPN monitor'
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}