#!/usr/bin/env bash
#
# Helper script to trigger PCIe bus rescanning and NVMe driver binding
# for secondary WWAN SSDs.
#
set -e

if [[ $EUID -ne 0 ]]; then
   echo "[-] Please run this script with sudo: sudo $0"
   exit 1
fi

DEV="0000:72:00.0"

echo "[*] Setting nvme_core default_ps_max_latency_us to 0 (disabling deep power states)..."
if [[ -f /sys/module/nvme_core/parameters/default_ps_max_latency_us ]]; then
    echo 0 > /sys/module/nvme_core/parameters/default_ps_max_latency_us
    echo "[+] Done."
fi

if [[ -d "/sys/bus/pci/devices/$DEV" ]]; then
    echo "[*] Attempting to bind NVMe driver to $DEV..."
    if [[ -d "/sys/bus/pci/drivers/nvme" ]]; then
        echo "$DEV" > /sys/bus/pci/drivers/nvme/bind 2>/dev/null || true
    fi
else
    echo "[-] Device $DEV not found on PCI bus. Rescanning PCI bus..."
    echo 1 > /sys/bus/pci/rescan
    sleep 1
fi

echo ""
echo "[*] Checking block devices (lsblk)..."
echo "------------------------------------------------------"
lsblk -o NAME,SIZE,TYPE,TRAN,MODEL,VENDOR,SERIAL,FSTYPE,MOUNTPOINTS
echo "------------------------------------------------------"

echo ""
echo "[*] Recent NVMe kernel messages:"
echo "------------------------------------------------------"
dmesg | grep -i nvme | tail -n 10
echo "------------------------------------------------------"
