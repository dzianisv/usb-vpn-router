#\!/bin/bash
# Orange Pi 4 LTS USB Gadget Setup Script
# This shows all the modifications made to get USB gadget working with macOS

echo "=== Orange Pi 4 LTS USB Gadget Setup ==="

# 1. DEVICE TREE MODIFICATION - Force USB controller to peripheral mode
echo "1. Modifying device tree to force peripheral mode..."
for dtb in /boot/dtb*/rockchip/rk3399-orangepi-4-lts.dtb; do
    echo "   Modifying $dtb"
    # Backup original
    cp "$dtb" "$dtb.backup" 2>/dev/null
    # Decompile, change dr_mode from "otg" to "peripheral", recompile
    dtc -I dtb -O dts "$dtb" 2>/dev/null | \
    sed 's/dr_mode = "otg"/dr_mode = "peripheral"/g' | \
    dtc -I dts -O dtb -o "$dtb" 2>/dev/null
done

# 2. CREATE DEVICE TREE OVERLAY (attempted but didn't work with Armbian)
echo "2. Creating device tree overlay (for reference)..."
cat > /tmp/dwc3-peripheral.dts << 'DTS'
/dts-v1/;
/plugin/;

/ {
    compatible = "rockchip,rk3399";

    fragment@0 {
        target-path = "/usb@fe800000/dwc3@fe800000";
        __overlay__ {
            compatible       = "snps,dwc3";
            dr_mode          = "peripheral";
            status           = "okay";
            reg              = <0x0 0xfe800000 0x0 0x100000>;
            phys             = <&tcphy0_usb3>;
            phy-names        = "usb3-phy";
            phy_type         = "utmi_wide";
            snps,dis_enblslpm_quirk;
            snps,dis-u2-freeclk-exists-quirk;
            snps,dis_u2_susphy_quirk;
            snps,dis-del-phy-power-chg-quirk;
            snps,xhci-slow-suspend-quirk;
        };
    };
};
DTS
dtc -@ -I dts -O dtb -o /boot/overlay-user/dwc3-peripheral.dtbo /tmp/dwc3-peripheral.dts 2>/dev/null

# 3. UPDATE BOOT CONFIGURATION
echo "3. Updating boot configuration..."
# Add overlay to armbianEnv.txt (didn't actually work, but we tried)
grep -q "user_overlays=" /boot/armbianEnv.txt || echo "user_overlays=dwc3-peripheral" >> /boot/armbianEnv.txt
sed -i 's/user_overlays=.*/user_overlays=dwc3-peripheral/' /boot/armbianEnv.txt

# 4. CONFIGURE MODULE LOADING
echo "4. Configuring USB gadget modules..."
# Load dwc3 and g_ether at boot
cat > /etc/modules-load.d/usb-gadget.conf << 'MODULES'
# USB gadget modules
dwc3
g_ether
usb_f_rndis
MODULES

# Configure g_ether to use CDC-ECM mode for macOS compatibility
cat > /etc/modprobe.d/g_ether.conf << 'MODPROBE'
# Use CDC-ECM mode for better macOS compatibility
options g_ether use_eem=0 use_ecm=1
MODPROBE

# 5. NETWORK CONFIGURATION
echo "5. Setting up network configuration..."
# Configure network interface
cat > /usr/local/bin/setup-usb-network.sh << 'NETSCRIPT'
#\!/bin/bash
# Wait for usb0 and configure it
for i in {1..10}; do
    if ip link show usb0 &>/dev/null; then
        ip addr add 192.168.7.1/24 dev usb0 2>/dev/null
        ip link set usb0 up
        echo "usb0 configured"
        break
    fi
    sleep 1
done
NETSCRIPT
chmod +x /usr/local/bin/setup-usb-network.sh

# Create systemd service for network setup
cat > /etc/systemd/system/usb-network.service << 'SERVICE'
[Unit]
Description=Configure USB gadget network interface
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/setup-usb-network.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable usb-network.service

# 6. DHCP SERVER CONFIGURATION
echo "6. Configuring DHCP server..."
cat > /etc/dnsmasq.d/usb0.conf << 'DHCP'
# DHCP configuration for USB gadget interface
interface=usb0
dhcp-range=192.168.7.100,192.168.7.200,12h
dhcp-option=3,192.168.7.1
dhcp-option=6,8.8.8.8,8.8.4.4
DHCP

# 7. ROUTING AND NAT
echo "7. Setting up routing..."
cat > /usr/local/bin/setup-usb-routing.sh << 'ROUTING'
#\!/bin/bash
# Enable IP forwarding
sysctl -w net.ipv4.ip_forward=1
# Get default interface
DEFAULT_IF=$(ip route | grep default | awk '{print $5}' | head -1)
# Setup NAT
iptables -t nat -A POSTROUTING -o $DEFAULT_IF -j MASQUERADE
iptables -A FORWARD -i usb0 -o $DEFAULT_IF -j ACCEPT
iptables -A FORWARD -i $DEFAULT_IF -o usb0 -m state --state RELATED,ESTABLISHED -j ACCEPT
ROUTING
chmod +x /usr/local/bin/setup-usb-routing.sh

# Make IP forwarding permanent
echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-usb-routing.conf

echo "=== Setup Complete ==="
echo "The key changes that made it work:"
echo "1. Modified DTB files directly to force peripheral mode"
echo "2. Switched from RNDIS to CDC-ECM protocol for macOS"
echo "3. DWC3 driver loads instead of xhci-hcd"
echo ""
echo "After reboot, the Orange Pi will be in USB gadget mode."
echo "Connect via USB-C cable to use as network device."
