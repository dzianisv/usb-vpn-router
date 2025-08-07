# USB VPN Router

Turn your Orange Pi into a secure USB ethernet gadget that routes all connected device traffic through VPN with automatic failover.

![Orange Pi Zero USB VPN Router Setup](images/orangepi-zero-setup.webp)

## Installation

```bash
# One-line install with web dashboard
curl -sSL https://raw.githubusercontent.com/dzianisv/usb-vpn-router/main/install.sh | sudo bash -s -- --enable-dashboard
```

**Alternative:**
```bash
# Python package install
sudo pip3 install git+https://github.com/dzianisv/usb-vpn-router.git
sudo usb-router-setup --enable-dashboard
```

## Usage

1. Connect USB cable to your computer
2. Computer gets IP via DHCP (192.168.64.50-150) 
3. Configure VPN: `tailscale up`
4. Web dashboard: `http://192.168.64.1:8000` (admin/admin)

## Features

- **VPN-Only Routing**: USB traffic forced through Tailscale/OpenVPN (no leaks)
- **Automatic Failover**: Switches between VPNs when one fails
- **Web Dashboard**: Real-time monitoring and VPN management
- **Split Routing**: Device keeps local access, clients use VPN
- **Kill Switch**: Blocks traffic when all VPNs are down

## Supported Devices

- Orange Pi Zero/One/PC/4 LTS
- Raspberry Pi Zero W/2W  
- Any Linux SBC with USB OTG

## Commands

- `usb-router-status` - Check status
- `usb-router-tailscale on/off` - Control VPN routing
- `usb-router-reset` - Reset USB interface

## License

MIT License - see LICENSE file for details