#!/usr/bin/env bash
# Board-specific setup for Orange Pi 4 LTS (RK3399)
# Sourced by the top-level setup script.
# Provides: detection, DTS overlay application, gadget/module configuration.

set -euo pipefail

BOARD_NAME="orangepi4lts"
BOARD_OVERRIDES_GADGET=true

board_detect() {
  # Chroot-friendly detection (no reliance on /proc exclusively)
  # 1) Explicit override
  case "${BOARD:-${FORCE_BOARD:-}}" in
    orangepi4lts|orangepi4-lts|opi4lts|opi4-lts)
      return 0 ;;
  esac

  # 2) Armbian metadata
  if [ -f /etc/armbian-release ]; then
    if grep -qiE 'BOARD=orangepi4-lts' /etc/armbian-release; then
      return 0
    fi
    if grep -qiE 'FAMILY=.*rk3399' /etc/armbian-release; then
      # Likely rk3399 family; still safe to match
      return 0
    fi
  fi

  # 3) Boot files
  if [ -f /boot/dtb/rockchip/rk3399-orangepi-4-lts.dtb ]; then
    return 0
  fi
  if [ -f /boot/armbianEnv.txt ] && grep -qi 'rk3399-orangepi-4-lts' /boot/armbianEnv.txt 2>/dev/null; then
    return 0
  fi

  # 4) Runtime DT (only if available; not in chroot)
  if [ -r /proc/device-tree/compatible ] && tr -d '\0' </proc/device-tree/compatible | grep -qi 'rk3399'; then
    return 0
  fi

  return 1
}

board_required_packages() {
  echo "device-tree-compiler"
}

board_apply_dts_overlay() {
  # Create and enable a DTS overlay to force DWC3 into peripheral mode
  local BOOT="/boot"
  [ -d "$BOOT" ] || { echo "[BOARD:$BOARD_NAME] /boot not found"; return 0; }

  local ODIR="$BOOT/overlay-user"
  mkdir -p "$ODIR"

  local DTS="$ODIR/dwc3-peripheral.dts"
  local DTBO="$ODIR/dwc3-peripheral.dtbo"

  cat >"$DTS" <<'DTSEOF'
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
DTSEOF

  echo "[BOARD:$BOARD_NAME] Compiling DWC3 peripheral overlay -> $DTBO"
  dtc -@ -I dts -O dtb -o "$DTBO" "$DTS"

  local ARMBIAN_ENV="$BOOT/armbianEnv.txt"
  if [ -f "$ARMBIAN_ENV" ]; then
    touch "$ARMBIAN_ENV"
    if grep -q '^user_overlays=' "$ARMBIAN_ENV"; then
      grep -E '^user_overlays=.*\bdwc3-peripheral\b' "$ARMBIAN_ENV" >/dev/null || \
        sed -i 's/^user_overlays=.*/& dwc3-peripheral/' "$ARMBIAN_ENV"
    else
      printf "\nuser_overlays=dwc3-peripheral\n" >> "$ARMBIAN_ENV"
    fi
    sed -i 's/user_overlays= \+/user_overlays=/; s/  \+/ /g' "$ARMBIAN_ENV"
  else
    # extlinux or other bootloaders can be supported later if needed
    echo "[BOARD:$BOARD_NAME] NOTE: armbianEnv.txt not found, ensure overlay is loaded via your boot config"
  fi

  REBOOT_REQUIRED=true
}

board_setup_gadget() {
  # Configure modules for RK3399 and gadget behavior
  # Load modules at boot
  cat > /etc/modules-load.d/usb_gadget.conf << 'EOF'
# DWC3 core driver for USB-C controller
dwc3
# Ethernet gadget (includes RNDIS)
g_ether
EOF

  # Force DWC3 peripheral role
  cat > /etc/modprobe.d/dwc3.conf << 'EOF'
# Force DWC3 to peripheral mode
options dwc3 role=device
EOF

  # Configure FUSB302 Type-C controller
  cat > /etc/modprobe.d/fusb302.conf << 'EOF'
# Force FUSB302 to sink role
options fusb302 port_type=2
options tcpm tcpm_log_level=1
EOF

  # Blacklist conflicting drivers
  cat > /etc/modprobe.d/usb_gadget-blacklist.conf << 'EOF'
# Prevent other USB network drivers from interfering
blacklist cdc_ncm
EOF

  # Prefer ECM mode for macOS compatibility
  cat > /etc/modprobe.d/g_ether.conf << 'EOF'
# Use CDC-ECM mode for better macOS compatibility
options g_ether use_eem=0 use_ecm=1
EOF

  # Load gadget now (uses modprobe.d options)
  if ! lsmod | grep -q '^g_ether'; then
    modprobe g_ether || true
    sleep 2
  fi
}
