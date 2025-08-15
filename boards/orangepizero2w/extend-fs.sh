#!/usr/bin/env bash
# grow-part.sh — extend partition to fill disk + grow FS; then remount chroot.
# Defaults: DEV=/dev/vdb PART=2 MNT=/mnt
set -euo pipefail

DEV="${DEV:-/dev/vdb}"
PART="${PART:-2}"
MNT="${MNT:-/mnt}"

# Handle mmcblk/nvme naming
PARTDEV="${DEV}${PART}"
if [[ "$DEV" =~ (mmcblk|nvme).*[0-9]$ ]]; then
  PARTDEV="${DEV}p${PART}"
fi

echo "== Target: $PARTDEV  mountpoint: $MNT =="

# 0) Unbind typical chroot mounts (ignore errors)
for p in run/systemd/resolve run dev/pts dev proc sys; do
  umount -l "$MNT/$p" 2>/dev/null || true
done
umount -l "$MNT" 2>/dev/null || true

# 1) Make kernel re-read the partition table (after qemu-img resize)
partprobe "$DEV" 2>/dev/null || true
udevadm settle || true

# 2) Grow the partition to 100% of the disk
echo "== Current table =="
parted -s "$DEV" unit % print
echo "== Resizing partition $PART to 100% =="
parted -s "$DEV" resizepart "$PART" 100%

# Refresh again
partprobe "$DEV" 2>/dev/null || true
udevadm settle || true

# 3) Grow the filesystem
FSTYPE="$(blkid -o value -s TYPE "$PARTDEV" || true)"
echo "== Filesystem on $PARTDEV: ${FSTYPE:-unknown} =="

case "$FSTYPE" in
  ext2|ext3|ext4)
    # Safe to fsck before resize (non-interactive first; fallback to manual if needed)
    e2fsck -f -p "$PARTDEV" || e2fsck -f "$PARTDEV" || true
    resize2fs "$PARTDEV"
    ;;
  xfs)
    mkdir -p "$MNT"
    mount "$PARTDEV" "$MNT"
    xfs_growfs "$MNT"
    umount "$MNT"
    ;;
  btrfs)
    mkdir -p "$MNT"
    mount "$PARTDEV" "$MNT"
    btrfs filesystem resize max "$MNT"
    umount "$MNT"
    ;;
  *)
    echo "Unknown/unsupported FS '$FSTYPE'. Grow it manually."
    exit 1
    ;;
esac

# 4) Remount your chroot stack
mkdir -p "$MNT"
mount "$PARTDEV" "$MNT"
mount --bind /dev  "$MNT/dev"
mount --bind /dev/pts "$MNT/dev/pts"
mount --bind /proc "$MNT/proc"
mount --bind /sys  "$MNT/sys"
mkdir -p "$MNT/run/systemd/resolve" || true
mount --bind /run/systemd/resolve "$MNT/run/systemd/resolve" 2>/dev/null || true
cp -a /etc/resolv.conf "$MNT/etc/resolv.conf" 2>/dev/null || true

echo "== Done. New layout =="
lsblk -e7 -o NAME,SIZE,FSTYPE,MOUNTPOINT "$DEV"

