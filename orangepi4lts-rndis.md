# Turning Orange Pi 4 LTS into a USB Network Gadget: A Deep Dive into DWC3 Peripheral Mode

## Introduction

The Orange Pi 4 LTS, powered by the Rockchip RK3399 SoC, has a powerful USB Type-C port that can function as either a host or a device. However, getting it to work reliably as a USB network adapter (RNDIS/Ethernet Gadget) on macOS requires understanding and working around a subtle hardware initialization bug. This guide will walk you through the complete setup process and explain the underlying technical details.

## The Challenge: DWC3 Controller and OTG Mode Issues

The RK3399 SoC uses a DesignWare Core SuperSpeed USB 3.0 Controller (DWC3) for its Type-C port. This controller supports OTG (On-The-Go) functionality, meaning it can dynamically switch between host and device modes. However, there's a critical issue with the Type-C controller initialization on the Orange Pi 4 LTS:

### The Bug

The FUSB302 Type-C controller chip (responsible for USB-C role detection) doesn't properly communicate with the DWC3 driver during boot. When the controller fails to detect the role through the CC (Configuration Channel) pins, it defaults to host mode. This manifests as:

- The Orange Pi trying to charge your Mac instead of appearing as a network device
- The FUSB302 showing all zero states when queried via I2C
- The extcon (external connector) framework failing to trigger role switches

### The Hardware Setup

The Orange Pi 4 LTS has two DWC3 controllers:
- **fe800000.usb**: Type-C OTG port (what we need to configure)
- **fe900000.usb**: Standard USB 3.0 host port

## The Solution: Forcing Peripheral Mode

Since OTG auto-detection is unreliable, we need to force the Type-C port into peripheral (device) mode. This involves creating a Device Tree overlay that overrides the default configuration.

## Step-by-Step Setup Guide

### Prerequisites

- Orange Pi 4 LTS running Armbian (kernel 6.6.x or later)
- Root access to the device
- A proper USB-C data cable (not charge-only)

### Step 1: Create the Device Tree Overlay

First, create a DTS file that forces the DWC3 controller into peripheral mode:

```bash
cat > /tmp/dwc3-peripheral.dts << 'EOF'
/dts-v1/;
/plugin/;

/ {
    compatible = "rockchip,rk3399";
    
    fragment@0 {
        target-path = "/usb@fe800000/dwc3@fe800000";
        __overlay__ {
            compatible = "snps,dwc3";
            dr_mode = "peripheral";
            status = "okay";
            reg = <0x0 0xfe800000 0x0 0x100000>;
            phys = <&tcphy0_usb3>;
            phy-names = "usb3-phy";
            phy_type = "utmi_wide";
            snps,dis_enblslpm_quirk;
            snps,dis-u2-freeclk-exists-quirk;
            snps,dis_u2_susphy_quirk;
            snps,dis-del-phy-power-chg-quirk;
            snps,xhci-slow-suspend-quirk;
        };
    };
};
EOF
```

### Step 2: Compile and Install the Overlay

```bash
# Install device tree compiler if not present
apt-get update && apt-get install -y device-tree-compiler

# Compile the overlay
dtc -O dtb -o /boot/overlay-user/dwc3-peripheral.dtbo /tmp/dwc3-peripheral.dts

# Add the overlay to boot configuration
echo "user_overlays=dwc3-peripheral" >> /boot/armbianEnv.txt
```

### Step 3: Configure Kernel Modules

Create module loading configuration to ensure the gadget drivers load at boot:

```bash
cat > /etc/modules-load.d/usb_gadget.conf << 'EOF'
# DWC3 core driver for USB-C controller
dwc3
# Ethernet gadget (includes RNDIS)
g_ether
EOF
```

### Step 4: Configure Module Parameters

Configure the modules for better compatibility:

```bash
# DWC3 module configuration
cat > /etc/modprobe.d/dwc3.conf << 'EOF'
# Force DWC3 to peripheral mode
options dwc3 role=device
EOF

# G_ether module configuration for macOS
cat > /etc/modprobe.d/g_ether.conf << 'EOF'
# Use CDC-ECM mode for better macOS compatibility
options g_ether use_eem=0 use_ecm=1
EOF

# FUSB302 Type-C controller configuration
cat > /etc/modprobe.d/fusb302.conf << 'EOF'
# Force FUSB302 to sink role
options fusb302 port_type=2
options tcpm tcpm_log_level=1
EOF
```

### Step 5: Configure Network Interface with Netplan

Armbian uses Netplan with NetworkManager as the renderer. Create a configuration for the USB interface:

```bash
cat > /etc/netplan/40-usb0.yaml << 'EOF'
network:
  version: 2
  ethernets:
    usb0:
      addresses:
        - 192.168.64.1/24
      optional: true
EOF

# Apply the netplan configuration
netplan apply
```

### Step 6: The Critical Boot Sequence

**Important**: Due to the initialization bug, the connection timing matters:

1. Power off the Orange Pi completely
2. Connect the power supply to the Orange Pi
3. **Immediately** connect the USB-C cable to your Mac
4. Power on the Orange Pi

This sequence ensures the DWC3 controller initializes in peripheral mode before any host mode detection can occur.

## Verifying the Setup

After boot, verify the configuration:

```bash
# Check USB mode (should show "device" or "peripheral")
cat /sys/kernel/debug/usb/fe800000.usb/mode

# Check if UDC is active
ls -la /sys/class/udc/

# Check network interface
ip addr show usb0

# Check loaded modules
lsmod | grep g_ether
```

## macOS Configuration

On your Mac, the Orange Pi should appear as a new network interface:

1. Open System Preferences → Network
2. You should see a new "RNDIS/Ethernet Gadget" interface
3. Configure it with:
   - IP Address: 192.168.7.2
   - Subnet Mask: 255.255.255.0
   - Router: 192.168.7.1 (optional)

Or configure via command line:

```bash
# Find the interface (usually en5, en6, etc.)
ifconfig | grep -B 2 "b2:57:b6"

# Configure it (replace enX with your interface)
sudo ifconfig enX 192.168.7.2 netmask 255.255.255.0
```

## Troubleshooting

### Device Shows as "Charging" Instead of Network Adapter

This means the controller is in host mode. Solutions:
- Ensure you're using a data cable, not charge-only
- Try flipping the USB-C connector
- Follow the boot sequence timing exactly
- Force peripheral mode manually: `echo peripheral > /sys/kernel/debug/usb/fe800000.usb/mode`

### No usb0 Interface on Orange Pi

Check if modules are loaded:
```bash
modprobe dwc3
modprobe g_ether
```

### Interface Exists but No Connection

- Verify the device tree overlay is applied: `ls /sys/firmware/devicetree/base/usb@fe800000/`
- Check dmesg for errors: `dmesg | grep -E "dwc3|g_ether|gadget"`

## Technical Deep Dive: Why This Works

The Device Tree overlay bypasses the broken OTG detection by:

1. **Overriding dr_mode**: Forces "peripheral" instead of "otg" or "host"
2. **Disabling USB2 suspend quirks**: Prevents power management issues
3. **Setting phy_type**: Ensures proper PHY initialization
4. **Targeting the correct controller**: Specifically configures fe800000.usb, not fe900000.usb

The timing workaround exploits the fact that early VBUS detection during boot can influence the controller's initialization path, making it more likely to accept the peripheral mode configuration.

## Alternative: Runtime Mode Switching

If you can't reboot with the specific timing, you can create a script for runtime switching:

```bash
#!/bin/bash
# Force USB peripheral mode
echo peripheral > /sys/kernel/debug/usb/fe800000.usb/mode

# Reload gadget driver
modprobe -r g_ether
modprobe g_ether

# Configure network
ip addr add 192.168.7.1/24 dev usb0
ip link set usb0 up
```

## Conclusion

While the Orange Pi 4 LTS's Type-C controller has OTG detection issues, forcing it into peripheral mode via Device Tree overlays provides a reliable solution for USB networking. This setup is particularly useful for creating portable routers, network bridges, or development devices that need to be accessed via USB networking.

The key insights are:
- The FUSB302 Type-C controller doesn't properly negotiate roles
- The DWC3 controller defaults to host mode when role detection fails
- Device Tree overlays can force the correct mode at boot
- Proper timing during initialization can work around hardware bugs

With this configuration, your Orange Pi 4 LTS becomes a reliable USB network gadget that works seamlessly with macOS and other operating systems.

## References

- [DWC3 USB Controller Documentation](https://www.kernel.org/doc/Documentation/devicetree/bindings/usb/dwc3.txt)
- [Linux USB Gadget API](https://www.kernel.org/doc/html/latest/usb/gadget.html)
- [Rockchip RK3399 Technical Reference Manual](http://opensource.rock-chips.com/wiki_RK3399)