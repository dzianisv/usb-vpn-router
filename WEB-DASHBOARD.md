# USB VPN Router Web Dashboard

A comprehensive web-based management interface for your USB VPN Router built on Ajenti with custom plugins.

![Dashboard Features](images/dashboard-preview.png)

## Features

### 🖥️ System Monitoring
- **Real-time Metrics**: CPU, memory, disk usage with live charts
- **USB Interface Status**: Monitor usb0 interface state and configuration
- **DHCP Leases**: View connected devices and their IP assignments
- **Service Management**: Monitor and control key system services
- **System Uptime**: Display current system uptime and load averages

### 🛡️ VPN Management
- **Tailscale Control**: 
  - View connection status and peer information
  - Switch between available exit nodes
  - Authenticate new devices
  - Monitor current exit node and location
- **OpenVPN Management**:
  - Monitor connection status and interface details
  - Restart OpenVPN services
  - View service logs and configuration status
- **Automatic Failover**: Control VPN failover monitor service

### 🌐 Network Control
- **Routing Mode Switch**: Toggle between local WAN and VPN routing
- **Routing Tables**: View main and VPN routing table entries
- **Traffic Rules**: Display current iptables rules and routing policies
- **Interface Reset**: Reset USB interface with one-click

### ⚡ Real-time Updates
- **Auto-refresh**: Status updates every 30 seconds
- **Live Controls**: Immediate feedback for all actions
- **Mobile Responsive**: Works on phones, tablets, and desktops
- **REST API**: Full API access for automation and scripting

## Installation

### Prerequisites
- USB VPN Router setup completed (run `setup-usb-router.sh` first)
- Orange Pi with Armbian/Debian
- Root access
- Active internet connection

### Quick Install

```bash
# 1. Install Ajenti web admin panel
sudo bash install-ajenti.sh

# 2. Install custom USB Router plugins
sudo bash install-plugins.sh

# 3. Access web interface
# Open browser to: http://192.168.0.226:8000
# Login: admin/admin (change immediately!)
```

### Manual Installation

```bash
# Install Ajenti dependencies
sudo apt update
sudo apt install python3 python3-pip python3-venv

# Install Ajenti
sudo pip3 install ajenti-panel ajenti.plugin.core ajenti.plugin.dashboard
sudo pip3 install psutil netifaces

# Copy plugins
sudo cp -r ajenti-plugins/* /var/lib/ajenti/plugins/

# Start Ajenti
sudo systemctl enable ajenti
sudo systemctl start ajenti
```

## Configuration

### First-Time Setup

1. **Access Web Interface**
   ```
   http://192.168.0.226:8000
   ```

2. **Login with Default Credentials**
   - Username: `admin`
   - Password: `admin`
   - **⚠️ Change password immediately!**

3. **Configure Security**
   - Go to Settings → Users
   - Change admin password
   - Optionally enable SSL/TLS

### Plugin Configuration

The dashboard automatically integrates with your existing USB router setup:

- **Scripts Integration**: Uses existing helper scripts
  - `/usr/local/bin/usb-router-status`
  - `/usr/local/bin/usb-router-tailscale`
  - `/usr/local/bin/usb-router-vpn-monitor`

- **Service Monitoring**: Monitors system services
  - `dnsmasq` (DHCP server)
  - `tailscaled` (Tailscale daemon)
  - `usb-router-vpn-monitor` (VPN failover)
  - `usb-interface-watchdog` (USB interface monitor)

## Usage Guide

### Dashboard Overview

The main dashboard provides a comprehensive view of your router status:

**System Metrics**
- CPU usage percentage with visual progress bar
- Memory usage (used/total) with percentage
- Disk usage for root filesystem
- System uptime and load averages

**USB Interface Panel**
- Connection status (UP/DOWN)
- IP address assignment (typically 192.168.64.1)
- Interface state and link status
- Quick reset button for troubleshooting

**DHCP Leases**
- List of connected devices
- IP addresses, hostnames, and MAC addresses
- Lease expiration times

### VPN Management

**Tailscale Control**
1. **View Status**: See connection state and backend status
2. **Exit Node Management**:
   - View available exit nodes in your network
   - Switch between exit nodes with one click
   - Disable exit node for direct connection
   - See current node location and status
3. **Authentication**: Get auth URLs for new devices

**OpenVPN Management**
1. **Monitor Connections**: View tun0 interface status
2. **Service Control**: Restart OpenVPN client services
3. **Configuration**: View service status and logs

**Routing Control**
- **Local Mode**: Route USB clients through local WAN
- **VPN Mode**: Route USB clients through Tailscale/OpenVPN
- **Automatic Switching**: Enable/disable VPN failover monitor

### API Endpoints

The dashboard provides REST API access for automation:

```bash
# Get router status
curl http://192.168.0.226:8000/api/usb-router/status

# Get VPN status
curl http://192.168.0.226:8000/api/vpn/status

# Switch routing mode
curl -X POST http://192.168.0.226:8000/api/vpn/routing/switch \
  -H "Content-Type: application/json" \
  -d '{"mode": "vpn"}'

# Switch Tailscale exit node
curl -X POST http://192.168.0.226:8000/api/vpn/tailscale/switch-exit-node \
  -H "Content-Type: application/json" \
  -d '{"hostname": "exit-node-name"}'

# Restart service
curl -X POST http://192.168.0.226:8000/api/usb-router/restart-service/dnsmasq
```

## Troubleshooting

### Common Issues

**Dashboard Not Loading**
```bash
# Check Ajenti service status
sudo systemctl status ajenti

# Check logs
sudo journalctl -u ajenti -f

# Restart service
sudo systemctl restart ajenti
```

**Plugins Not Appearing**
```bash
# Verify plugin installation
ls -la /var/lib/ajenti/plugins/

# Check permissions
sudo chown -R root:root /var/lib/ajenti/plugins/
sudo chmod -R 755 /var/lib/ajenti/plugins/

# Restart Ajenti
sudo systemctl restart ajenti
```

**API Errors**
```bash
# Check script permissions
ls -la /usr/local/bin/usb-router-*

# Test scripts manually
sudo /usr/local/bin/usb-router-status
sudo /usr/local/bin/usb-router-tailscale status
```

**Connection Issues**
```bash
# Check firewall
sudo ufw status
sudo ufw allow 8000

# Check listening ports
sudo netstat -tlnp | grep 8000

# Test from local machine
curl http://localhost:8000
```

### Logs and Debugging

**Ajenti Logs**
```bash
# Service logs
sudo journalctl -u ajenti -f

# Application logs
sudo tail -f /var/log/ajenti.log
```

**Plugin Debugging**
```bash
# Enable debug mode in Ajenti config
sudo nano /etc/ajenti/config.yml
# Add: debug: true

# Restart with debug output
sudo systemctl restart ajenti
```

**Script Testing**
```bash
# Test individual components
sudo /usr/local/bin/usb-router-status
sudo tailscale status --json
sudo ip route show table usb_vpn
```

## Security Considerations

### Access Control
- **Change Default Password**: Critical first step
- **Enable HTTPS**: For secure remote access
- **Firewall Rules**: Restrict access to trusted networks
- **User Management**: Create limited-privilege users

### Network Security
```bash
# Restrict web access to local networks only
sudo ufw allow from 192.168.0.0/16 to any port 8000
sudo ufw allow from 10.0.0.0/8 to any port 8000
```

### SSL/TLS Configuration
```yaml
# /etc/ajenti/config.yml
ssl:
  enable: true
  certificate_path: '/etc/ssl/certs/ajenti.crt'
  fqdn_certificate_path: '/etc/ssl/private/ajenti.key'
```

## Performance

### Resource Usage
- **RAM**: ~150-200MB total (Ajenti + plugins)
- **CPU**: <5% during normal operation
- **Disk**: ~50MB for installation
- **Network**: Minimal overhead for status updates

### Optimization Tips
- **Auto-refresh**: Adjust refresh interval in plugin settings
- **Log Rotation**: Configure log rotation for system logs
- **Cache**: Enable browser caching for static assets

## Advanced Configuration

### Custom Themes
```bash
# Install custom themes in
/var/lib/ajenti/plugins/core/resources/css/
```

### Additional Plugins
```bash
# Plugin development directory
/var/lib/ajenti/plugins/custom_plugin/
```

### Integration with External Systems
The dashboard can be integrated with:
- **Grafana**: For advanced metrics visualization
- **Prometheus**: For metrics collection
- **Home Assistant**: For home automation
- **MQTT**: For IoT integration

## Development

### Plugin Structure
```
ajenti-plugins/
├── usb_router_status/
│   ├── __init__.py          # Plugin metadata
│   ├── main.py              # Backend logic
│   ├── layout.xml           # UI template
│   └── resources/
│       ├── js/controllers.js # Frontend logic
│       └── css/styles.css   # Styling
└── vpn_manager/
    ├── __init__.py
    ├── main.py
    ├── layout.xml
    └── resources/
        ├── js/controllers.js
        └── css/styles.css
```

### API Development
```python
# Example API endpoint
@url(r'/api/custom/endpoint')
@endpoint(api=True)
def handle_custom_api(self, http_context):
    return {'status': 'success', 'data': {...}}
```

## Support

### Getting Help
- **Documentation**: Check existing USB router docs
- **Logs**: Always include relevant log output
- **Configuration**: Share sanitized config files
- **System Info**: Include Orange Pi model and OS version

### Contributing
1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Submit pull request with detailed description

### License
MIT License - see LICENSE file for details