# USB VPN Router - One-Line Installation

## 🚀 Quick Install

```bash
# One-line installation from GitHub
curl -sSL https://raw.githubusercontent.com/dzianisv/usb-vpn-router/main/install.sh | sudo bash
```

## 🐍 Python Package Installation

```bash
# Install directly from GitHub using pip
sudo pip3 install git+https://github.com/dzianisv/usb-vpn-router.git

# Run the installer
sudo usb-router-setup --enable-dashboard
```

## ⚙️ Installation Options

### Basic Installation (Router Only)
```bash
sudo usb-router-setup
```

### Full Installation (Router + Web Dashboard)
```bash
sudo usb-router-setup --enable-dashboard
```

### Custom Installation
```bash
sudo usb-router-setup \
  --use-tailscale-exit \
  --enable-dashboard \
  --wan-interface eth0 \
  --usb-network 10.0.64.0/24
```

### Available Options
- `--use-tailscale-exit` - Route USB clients through Tailscale exit node
- `--enable-vpn-failover` - Enable automatic VPN failover (default: true)
- `--enable-dashboard` - Install web dashboard
- `--wan-interface IFACE` - WAN interface name (default: wlan0)
- `--usb-network CIDR` - USB client network (default: 192.168.64.0/24)
- `--skip-packages` - Skip package installation (for testing)

## 📋 Requirements

- **Hardware**: Orange Pi Zero/One/PC, Raspberry Pi Zero W/2W, or any SBC with USB OTG
- **OS**: Debian/Ubuntu/Armbian (ARM or x86_64)
- **Access**: Root privileges
- **Network**: Internet connection for initial setup

## 🔧 Post-Installation

### 1. Connect USB Cable
Connect the micro-USB port to your computer (not the USB-A port).

### 2. Configure Tailscale (Optional)
```bash
# Authenticate with Tailscale
sudo tailscale up

# Enable VPN routing for USB clients
sudo usb-router-tailscale on
```

### 3. Access Web Dashboard (If Enabled)
Open browser to: `http://192.168.0.226:8000`
- Default login: admin/admin
- **⚠️ Change password immediately!**

### 4. Verify Installation
```bash
# Check router status
usb-router-status

# Check services
systemctl status dnsmasq
systemctl status tailscaled
systemctl status usb-router-vpn-monitor
```

## 🛠️ Management Commands

After installation, these commands are available:

```bash
usb-router-status          # Show comprehensive status
usb-router-reset           # Reset USB interface
usb-router-tailscale on    # Enable VPN routing
usb-router-tailscale off   # Disable VPN routing
usb-router-vpn-monitor     # VPN failover monitor
usb-router-dashboard       # Start web dashboard
```

## 🌐 Web Dashboard Features

If you installed with `--enable-dashboard`:

- **Real-time Monitoring**: CPU, memory, disk usage
- **USB Interface Control**: Status and reset functionality
- **VPN Management**: Tailscale exit node switching
- **Service Control**: Restart services with one click
- **Network Overview**: DHCP leases and routing information

## 🔍 Troubleshooting

### Installation Issues
```bash
# Check Python and pip
python3 --version
pip3 --version

# Manual package installation
sudo apt update
sudo apt install python3-pip git

# Install with verbose output
sudo pip3 install -v git+https://github.com/yourusername/usb-vpn-router.git
```

### Runtime Issues
```bash
# Check logs
journalctl -u usb-router-vpn-monitor -f
tail -f /var/log/syslog | grep usb-router

# Verify USB gadget module
lsmod | grep g_ether
modprobe g_ether use_eem=0

# Check network interfaces
ip link show
ip addr show usb0
```

### macOS Connection Issues
- When first connecting, macOS shows "Allow Accessory to Connect" prompt
- Click "Allow" - the interface won't appear until you approve it
- The USB watchdog service handles this delay automatically
- Check status: `systemctl status usb-interface-watchdog`

## 🔄 Updates

```bash
# Update to latest version
sudo pip3 install --upgrade git+https://github.com/dzianisv/usb-vpn-router.git

# Reinstall configuration
sudo usb-router-setup --enable-dashboard
```

## 🗑️ Uninstallation

```bash
# Stop services
sudo systemctl stop usb-router-vpn-monitor
sudo systemctl stop usb-interface-watchdog
sudo systemctl stop dnsmasq

# Disable services
sudo systemctl disable usb-router-vpn-monitor
sudo systemctl disable usb-interface-watchdog

# Remove package
sudo pip3 uninstall usb-vpn-router

# Clean up configuration (optional)
sudo rm -rf /etc/dnsmasq.d/usb0.conf
sudo rm -rf /etc/systemd/system/usb-router-*
sudo systemctl daemon-reload
```

## 📖 Documentation

- **Full Documentation**: [README.md](README.md)
- **Web Dashboard Guide**: [WEB-DASHBOARD.md](WEB-DASHBOARD.md)
- **API Reference**: Available at `/api/status` on your dashboard
- **Troubleshooting**: Check service logs and system status

## 🆘 Support

- **Issues**: Report at GitHub Issues
- **Documentation**: Complete guides in repository
- **Logs**: Always include relevant log output when reporting issues