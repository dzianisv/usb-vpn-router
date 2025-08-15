#!/usr/bin/env bash
# Board-specific setup for Orange Pi Zero (Allwinner H2+/H3)
# Sourced by the top-level setup script.
# Provides: detection, DTS overlay application, gadget/module configuration.

set -euo pipefail

BOARD_NAME="orangepizero"
BOARD_OVERRIDES_GADGET=true

board_detect() {
  # Chroot-friendly detection
  # 1) Explicit override
  case "${BOARD:-${FORCE_BOARD:-}}" in
    orangepizero|orangepi-zero|opi-zero|opizero)
      return 0 ;;
  esac

  # 2) Armbian metadata
  if [ -f /etc/armbian-release ]; then
    if grep -qiE 'BOARD=orangepizero' /etc/armbian-release; then
      return 0
    fi
    if grep -qiE 'FAMILY=.*sun8i' /etc/armbian-release; then
      # Many H2+/H3 belong to sun8i family
      return 0
    fi
  fi

  # 3) Boot DTBs commonly used for OPi Zero (H2+/H3)
  if [ -f /boot/dtb/allwinner/sun8i-h3-orangepi-zero.dtb ] || \
     [ -f /boot/dtb/allwinner/sun8i-h2-plus-orangepi-zero.dtb ] || \
     ls /boot/dtb/*orangepi*zero*.dtb >/dev/null 2>&1 ; then
    return 0
  fi

  # 4) Runtime DT fallback (non-chroot)
  if [ -r /proc/device-tree/compatible ] && tr -d '\0' </proc/device-tree/compatible | grep -qiE 'sun8i-h3|sun8i-h2\+'; then
    return 0
  fi

  return 1
}

board_required_packages() {
  echo "device-tree-compiler"
}

board_apply_dts_overlay() {
  # Force USB OTG controller into peripheral mode and disable host on PHY0
  local BOOT="/boot"
  [ -d "$BOOT" ] || { echo "[BOARD:$BOARD_NAME] /boot not found"; return 0; }

  local ARMBIAN_ENV="$BOOT/armbianEnv.txt"
  local OPI_ENV="$BOOT/orangepiEnv.txt"
  local EXTLINUX_CONF="$BOOT/extlinux/extlinux.conf"

  local ODIR="$BOOT/overlay-user"
  mkdir -p "$ODIR"

  # Some builds require this symlink for overlays
  if [ -d "$BOOT/dtb/allwinner/overlay" ] && [ ! -e "$BOOT/dtb/overlay" ]; then
    (cd "$BOOT/dtb" && ln -sf ./allwinner/overlay overlay) || true
  fi

  local DTS="$ODIR/usb0-device.dts"
  local DTBO="$ODIR/usb0-device.dtbo"

  cat >"$DTS" <<'EOF'
/dts-v1/;
/plugin/;
/ {
  compatible = "allwinner,sun8i-h3", "allwinner,sun8i-h2+";

  /* Prefer label if present; most Armbian H3 DTs use usb_otg/usbphy */
  fragment@0 { target = <&usb_otg>; __overlay__ { dr_mode = "peripheral"; status = "okay"; }; };
  fragment@1 { target = <&usbphy>;   __overlay__ { status = "okay"; }; };
  /* Prevent host controllers from grabbing PHY0 */
  fragment@2 { target = <&ehci0>;   __overlay__ { status = "disabled"; }; };
  fragment@3 { target = <&ohci0>;   __overlay__ { status = "disabled"; }; };
};
EOF

  echo "[BOARD:$BOARD_NAME] Compiling USB gadget overlay -> $DTBO"
  dtc -@ -I dts -O dtb -o "$DTBO" "$DTS"

  echo "[BOARD:$BOARD_NAME] Enabling overlay in boot config"
  if   [ -f "$ARMBIAN_ENV" ]; then
    touch "$ARMBIAN_ENV"
    if grep -q '^user_overlays=' "$ARMBIAN_ENV"; then
      grep -E '^user_overlays=.*\busb0-device\b' "$ARMBIAN_ENV" >/dev/null || \
        sed -i 's/^user_overlays=.*/& usb0-device/' "$ARMBIAN_ENV"
    else
      printf "\nuser_overlays=usb0-device\n" >> "$ARMBIAN_ENV"
    fi
    sed -i 's/user_overlays= \+/user_overlays=/; s/  \+/ /g' "$ARMBIAN_ENV"
  elif [ -f "$OPI_ENV" ]; then
    touch "$OPI_ENV"
    if grep -q '^overlays=' "$OPI_ENV"; then
      grep -E '^overlays=.*\busb0-device\b' "$OPI_ENV" >/dev/null || \
        sed -i 's/^overlays=.*/& usb0-device/' "$OPI_ENV"
    else
      printf "\noverlays=usb0-device\n" >> "$OPI_ENV"
    fi
    sed -i 's/overlays= \+/overlays=/; s/  \+/ /g' "$OPI_ENV"
  elif [ -f "$EXTLINUX_CONF" ]; then
    local def
    def="$(awk '/^DEFAULT/{print $2}' "$EXTLINUX_CONF" || true)"
    if [ -n "$def" ]; then
      awk -v def="$def" -v path="$DTBO" '
        BEGIN{IN=0; added=0}
        /^LABEL[ \t]+/ {IN = ($2==def)}
        IN && /^ *FDT / {print; if (!added){print "  FDTOOVERLAYS " path; added=1}; next}
        {print}
        END{ if (!added && IN){ print "  FDTOOVERLAYS " path } }
      ' "$EXTLINUX_CONF" > "$EXTLINUX_CONF.new" && mv "$EXTLINUX_CONF.new" "$EXTLINUX_CONF"
    else
      grep -qF "FDTOOVERLAYS $DTBO" "$EXTLINUX_CONF" || printf "\nFDTOOVERLAYS %s\n" "$DTBO" >> "$EXTLINUX_CONF"
    fi
  else
    echo "[BOARD:$BOARD_NAME] WARNING: No known boot config found; overlay installed but not enabled"
  fi

  REBOOT_REQUIRED=true
}

board_setup_gadget() {
  # Provide a composite gadget (ACM + ECM) using configfs and a oneshot service
  local GADGET_SH="/usr/local/sbin/setup-usb-gadget.sh"
  mkdir -p /usr/local/sbin
  cat >"$GADGET_SH" <<'EOSH'
#!/bin/sh
set -e
modprobe libcomposite 2>/dev/null || true
# Mount configfs if not already
mountpoint -q /sys/kernel/config || mount -t configfs none /sys/kernel/config
G=/sys/kernel/config/usb_gadget/pi
[ -d "$G" ] || mkdir -p "$G"
cd "$G"
# Linux Foundation IDs (gadget)
echo 0x1d6b > idVendor
echo 0x0104 > idProduct
mkdir -p strings/0x409
echo "OrangePi"      > strings/0x409/manufacturer
echo "Zero Gadget"   > strings/0x409/product
echo "0001"         > strings/0x409/serialnumber
mkdir -p configs/c.1/strings/0x409
echo "ACM+ECM" > configs/c.1/strings/0x409/configuration
mkdir -p functions/acm.usb0
mkdir -p functions/ecm.usb0
# Optional MACs can be provided via environment
[ -n "$DEV_MAC" ]  && echo "$DEV_MAC"  > functions/ecm.usb0/dev_addr || true
[ -n "$HOST_MAC" ] && echo "$HOST_MAC" > functions/ecm.usb0/host_addr || true
ln -sf functions/acm.usb0 configs/c.1/
ln -sf functions/ecm.usb0 configs/c.1/
UDC=$(ls /sys/class/udc 2>/dev/null | head -n1 || true)
[ -n "$UDC" ] && echo "$UDC" > UDC || true
# Bring up usb0 with STATIC_IP if present
if [ -n "$STATIC_IP" ] && ip link show usb0 >/dev/null 2>&1; then
  ip addr add "$STATIC_IP" dev usb0 2>/dev/null || true
  ip link set usb0 up || true
fi
EOSH
  chmod +x "$GADGET_SH"

  # systemd unit to run gadget setup early
  mkdir -p /etc/systemd/system
  cat >/etc/systemd/system/usb-gadget.service <<'EOF'
[Unit]
Description=USB Gadget (ACM + ECM) bringup
DefaultDependencies=no
After=local-fs.target
Before=sysinit.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/setup-usb-gadget.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
  ln -sf ../usb-gadget.service /etc/systemd/system/multi-user.target.wants/usb-gadget.service

  # Enable login on USB serial (ttyGS0) when available
  local GETTY_TEMPLATE=""
  for p in /lib/systemd/system/serial-getty@.service /usr/lib/systemd/system/serial-getty@.service; do
    [ -f "$p" ] && GETTY_TEMPLATE="$p" && break
  done
  if [ -n "$GETTY_TEMPLATE" ]; then
    mkdir -p /etc/systemd/system/getty.target.wants
    ln -sf "$GETTY_TEMPLATE" /etc/systemd/system/getty.target.wants/serial-getty@ttyGS0.service
  fi
}
