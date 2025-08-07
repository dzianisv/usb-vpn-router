"""
USB VPN Router Web Dashboard
Lightweight Flask-based alternative to Ajenti for router management.
"""

import json
import subprocess
import psutil
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from datetime import datetime
from .utils import run_command, check_interface_exists, get_interface_ip, check_service_status


def create_app():
    """Create Flask application."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'usb-router-secret-key-change-me'
    
    # Initialize SocketIO for real-time updates
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    return app, socketio


app, socketio = create_app()


class RouterStatus:
    """Router status information provider."""
    
    @staticmethod
    def get_system_metrics():
        """Get system metrics."""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory': {
                    'total': psutil.virtual_memory().total,
                    'used': psutil.virtual_memory().used,
                    'percent': psutil.virtual_memory().percent
                },
                'disk': {
                    'total': psutil.disk_usage('/').total,
                    'used': psutil.disk_usage('/').used,
                    'percent': (psutil.disk_usage('/').used / psutil.disk_usage('/').total) * 100
                },
                'uptime': subprocess.run(['uptime'], capture_output=True, text=True).stdout.strip(),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {'error': str(e)}
    
    @staticmethod
    def get_usb_interface_status():
        """Get USB interface status."""
        try:
            if check_interface_exists('usb0'):
                ip = get_interface_ip('usb0')
                result = run_command(['ip', 'link', 'show', 'usb0'], capture_output=True)
                
                return {
                    'status': 'UP' if 'UP' in result.stdout else 'DOWN',
                    'ip_address': ip or 'Not assigned',
                    'state': 'UP' if 'UP' in result.stdout else 'DOWN'
                }
            else:
                return {
                    'status': 'NOT_FOUND',
                    'ip_address': 'N/A',
                    'state': 'DOWN'
                }
        except Exception as e:
            return {'status': 'ERROR', 'error': str(e)}
    
    @staticmethod
    def get_dhcp_leases():
        """Get DHCP lease information."""
        try:
            leases = []
            with open('/var/lib/misc/dnsmasq.leases', 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        leases.append({
                            'expiry': parts[0],
                            'mac': parts[1],
                            'ip': parts[2],
                            'hostname': parts[3],
                            'client_id': parts[4] if len(parts) > 4 else ''
                        })
            return leases
        except FileNotFoundError:
            return []
        except Exception as e:
            return [{'error': str(e)}]
    
    @staticmethod
    def get_vpn_status():
        """Get VPN status information."""
        vpn_status = {}
        
        # Tailscale status
        try:
            result = run_command(['tailscale', 'status', '--json'], capture_output=True, check=False)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                current_exit_node = None
                
                # Find current exit node
                for peer_id, peer_data in data.get('Peer', {}).items():
                    if peer_data.get('ExitNode', False):
                        current_exit_node = {
                            'hostname': peer_data.get('HostName', 'Unknown'),
                            'ip': peer_data.get('TailscaleIPs', [])[0] if peer_data.get('TailscaleIPs') else 'Unknown'
                        }
                        break
                
                vpn_status['tailscale'] = {
                    'status': 'UP',
                    'backend_state': data.get('BackendState', 'Unknown'),
                    'current_exit_node': current_exit_node,
                    'peer_count': len(data.get('Peer', {}))
                }
            else:
                vpn_status['tailscale'] = {'status': 'DOWN'}
        except Exception:
            vpn_status['tailscale'] = {'status': 'ERROR'}
        
        # OpenVPN status
        vpn_status['openvpn'] = {
            'status': 'UP' if check_interface_exists('tun0') else 'DOWN'
        }
        
        # Monitor service status
        vpn_status['monitor'] = check_service_status('usb-router-vpn-monitor')
        
        return vpn_status
    
    @staticmethod
    def get_services_status():
        """Get status of key services."""
        services = [
            'dnsmasq',
            'tailscaled', 
            'usb-router-vpn-monitor',
            'usb-interface-watchdog'
        ]
        
        return {service: check_service_status(service) for service in services}


# Web Routes
@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('dashboard.html')


@app.route('/api/status')
def api_status():
    """API endpoint for complete router status."""
    try:
        status = {
            'system': RouterStatus.get_system_metrics(),
            'usb_interface': RouterStatus.get_usb_interface_status(),
            'dhcp_leases': RouterStatus.get_dhcp_leases(),
            'vpn': RouterStatus.get_vpn_status(),
            'services': RouterStatus.get_services_status(),
            'timestamp': datetime.now().isoformat()
        }
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/vpn/switch-routing', methods=['POST'])
def api_switch_routing():
    """Switch between local and VPN routing."""
    try:
        data = request.get_json()
        mode = data.get('mode', '')
        
        if mode == 'local':
            result = run_command(['usb-router-tailscale', 'off'], capture_output=True)
        elif mode == 'vpn':
            result = run_command(['usb-router-tailscale', 'on'], capture_output=True)
        else:
            return jsonify({'success': False, 'error': 'Invalid mode'}), 400
        
        return jsonify({
            'success': result.returncode == 0,
            'message': f'Routing switched to {mode}',
            'output': result.stdout if result.returncode == 0 else result.stderr
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/vpn/tailscale/exit-nodes')
def api_tailscale_exit_nodes():
    """Get available Tailscale exit nodes."""
    try:
        result = run_command(['tailscale', 'status', '--json'], capture_output=True)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            exit_nodes = []
            
            for peer_id, peer_data in data.get('Peer', {}).items():
                if peer_data.get('ExitNodeOption', False):
                    exit_nodes.append({
                        'id': peer_id,
                        'hostname': peer_data.get('HostName', 'Unknown'),
                        'ip': peer_data.get('TailscaleIPs', [])[0] if peer_data.get('TailscaleIPs') else 'Unknown',
                        'online': peer_data.get('Online', False),
                        'current': peer_data.get('ExitNode', False)
                    })
            
            return jsonify({'success': True, 'exit_nodes': exit_nodes})
        else:
            return jsonify({'success': False, 'error': 'Tailscale not connected'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/vpn/tailscale/switch-exit-node', methods=['POST'])
def api_switch_exit_node():
    """Switch Tailscale exit node."""
    try:
        data = request.get_json()
        hostname = data.get('hostname', '')
        
        if hostname == 'none':
            result = run_command(['tailscale', 'up', '--exit-node='], capture_output=True)
        else:
            result = run_command(['tailscale', 'up', f'--exit-node={hostname}'], capture_output=True)
        
        return jsonify({
            'success': result.returncode == 0,
            'message': f'Exit node switched to {hostname if hostname != "none" else "disabled"}',
            'output': result.stdout if result.returncode == 0 else result.stderr
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/system/restart-service', methods=['POST'])
def api_restart_service():
    """Restart system service."""
    try:
        data = request.get_json()
        service = data.get('service', '')
        
        allowed_services = ['dnsmasq', 'usb-router-vpn-monitor', 'usb-interface-watchdog']
        if service not in allowed_services:
            return jsonify({'success': False, 'error': 'Service not allowed'}), 400
        
        result = run_command(['systemctl', 'restart', service], capture_output=True)
        
        return jsonify({
            'success': result.returncode == 0,
            'message': f'Service {service} restarted',
            'output': result.stdout if result.returncode == 0 else result.stderr
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/system/reset-usb', methods=['POST'])
def api_reset_usb():
    """Reset USB interface."""
    try:
        result = run_command(['usb-router-reset'], capture_output=True)
        
        return jsonify({
            'success': result.returncode == 0,
            'message': 'USB interface reset',
            'output': result.stdout if result.returncode == 0 else result.stderr
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# SocketIO Events for real-time updates
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    emit('status', RouterStatus.get_system_metrics())


@socketio.on('request_status')
def handle_status_request():
    """Handle status update request."""
    status = {
        'system': RouterStatus.get_system_metrics(),
        'usb_interface': RouterStatus.get_usb_interface_status(),
        'vpn': RouterStatus.get_vpn_status(),
        'services': RouterStatus.get_services_status(),
    }
    emit('status_update', status)


# Background task for periodic updates
def background_status_updates():
    """Send periodic status updates to connected clients."""
    import time
    while True:
        time.sleep(30)  # Update every 30 seconds
        status = RouterStatus.get_system_metrics()
        socketio.emit('status_update', status, broadcast=True)


import click

@click.command()
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--port', default=8000, help='Port to bind to')
@click.option('--debug', is_flag=True, help='Enable debug mode')
def main(host, port, debug):
    """Start USB Router web dashboard."""
    click.echo(f"Starting USB Router Dashboard on http://{host}:{port}")
    
    # Start background task
    if not debug:
        import threading
        update_thread = threading.Thread(target=background_status_updates, daemon=True)
        update_thread.start()
    
    # Start web server
    socketio.run(app, host=host, port=port, debug=debug)


if __name__ == '__main__':
    main()