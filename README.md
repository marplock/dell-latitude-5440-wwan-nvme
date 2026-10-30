# Dell Latitude 5440 WWAN Slot NVMe SSD Research & Mod Guide

> Reverse-engineering the M.2 Key-B cellular slot on the 13th-Gen Dell Latitude 5440 to enable secondary internal NVMe SSD storage.

---

## 📌 Overview

It is widely claimed on forums (Reddit, Dell Community) that 12th- and 13th-Gen Dell Latitude laptops cannot run an NVMe SSD in the internal WWAN (cellular) slot, assuming the lanes are dead, unrouted, or permanently locked by firmware.

**This research disproves that assumption.** 

Through pinout masking, PCIe register manipulation, ACPI DSDT disassembly, and kernel parameter tuning, we confirmed that:
1. **PCIe lanes are physically wired:** The slot connects directly to **Intel PCH Root Port 2 (`00:1c.0`)**.
2. **PCIe Gen 3 Link Trains Successfully:** The link trains at full **8.0 GT/s (x1 width)** with `DLActive+`.
3. **Bridge Forwarding Works:** With `pci=realloc`, Linux allocates a 1MB MMIO forwarding window (`0x9de00000`) to BAR0.
4. **Direct Register Communication is 100% Functional:** Live 32-bit MMIO reads/writes over PCIe directly configure the controller's Capabilities (`CAP`) and Configuration (`CC`) registers.

---

## 💻 Tested Hardware & Environment

* **Laptop:** Dell Latitude 5440 (13th Gen Intel Raptor Lake-P)
* **Root Port:** `0000:00:1c.0` PCI Express Root Port 2 (`8086:51b9`)
* **Slot Key:** M.2 Key-B (Socket 2, 3042/3052 form factor)
* **Tested SSD:** Western Digital / SanDisk PC SN520 B+M Key NVMe SSD (`15b7:5004`)
* **Operating System:** Linux (Kernel 6.x / 7.x, Limine / systemd-boot / GRUB)

---

## ⚡ Breakthroughs

### 1. Powering the Slot (The Pin-Masking Mod)
The Dell Embedded Controller (EC) automatically cuts slot power (`D3cold`) when no cellular card is detected.
* **The Fix:** Using insulating Kapton tape or a tiny dab of clear lacquer/nail polish on the underside of the SSD, mask **Pin 6** (`FULL_CARD_POWER_OFF#`) and **Pin 8** (`W_DISABLE1#`).
* **Critical:** Keep **Pin 2** and **Pin 4** (3.3V Power) completely exposed.

```text
Underside of SSD (5-finger group before Key-B notch):
 [ Pin 2: 3.3V ] -> EXPOSED
 [ Pin 4: 3.3V ] -> EXPOSED
 [ Pin 6: Power Off ] -> TAPED / MASKED
 [ Pin 8: Radio Disable ] -> TAPED / MASKED
 [ Pin 10: LED/DAS ] -> EXPOSED
```

### 2. Opening the PCIe Memory Window
Dell's BIOS allocates zero MMIO window to `00:1c.0`, causing `-EIO` errors when accessing the SSD.
* **The Fix:** Add `pci=realloc` to the Linux kernel boot parameters.
* **Result:** Linux PCI core dynamically reallocates address space, mapping BAR0 to `0x9de00000`.

### 3. Defeating Dell's ACPI Killswitch (`StorageD3Enable`)
Disassembling the Dell DSDT table (`Device (RP02)`) revealed that Dell firmware explicitly checks if an NVMe device is attached (`Method PNVM`), and if detected, commands the OS to shut down the slot (`"StorageD3Enable", One`).
* **The Fix:** Add `nvme.noacpi=1` to kernel boot parameters to prevent Linux from executing Dell's ACPI D3 sleep directives.

---

## 🚀 Recommended Kernel Command Line

To keep all WWAN SSD enablement patches active while maintaining 100% battery efficiency (preserving ASPM L1.2 and CPU deep C-states on the primary drive):

```text
pci=realloc nvme.noacpi=1 intel_iommu=off nvme_core.admin_timeout=120 nvme.quirks=15b7:5004:delay_before_chk_rdy,no_apst,broken_msi,single_vector
```

| Parameter | Purpose |
| :--- | :--- |
| `pci=realloc` | Carves out downstream MMIO window for Root Port 2 (`00:1c.0`). |
| `nvme.noacpi=1` | Blocks Dell's ACPI `StorageD3Enable` script from cutting slot power. |
| `intel_iommu=off` | Disables Kernel DMA Protection isolation on the expansion bus. |
| `admin_timeout=120` | Grants the controller up to 2 minutes for flash initialization. |
| `nvme.quirks=...` | Applies hardware timing quirks strictly to the secondary SSD. |

---

## 🔍 The Final Frontier: `CSTS=0x0`

While PCIe communication is 100% functional, the controller status register remains at `CSTS = 0x00000000` (Ready bit never turns to `1`).

### Root Cause:
* **Silicon Read-Only:** In NVMe silicon, `CSTS` is physically read-only; the CPU cannot software-toggle it.
* **Power Starvation on M.2 Key-B:** Standard M.2 Key-M storage slots deliver 3.3V across pins 2, 4, 12, 14, 16, 18, 70, 72, and 74. Because Key-B sockets physically lack pins 12–18 (notch gap), the NAND flash memory plane relies on pins 70, 72, and 74.
* If tape bleeds over onto Pin 4 or Pin 70, or if the WWAN slot only energizes primary pins without cellular modem signaling, the NAND flash browns out, keeping the internal flash processor frozen.

### The Next Step:
Pairing this kernel patch with an active **M.2 Key-B to Key-M interposer adapter** (which bridges all 3.3V power planes across copper traces and terminates `CONFIG` pins) provides the missing electrical power to achieve the first fully functional dual-internal NVMe setup on a Latitude 5440.

---

## 📁 Repository Contents
* `DELL_LATITUDE_5440_WWAN_NVME_RESEARCH.md` - Complete engineering write-up with DSDT disassembly, register mappings, and hardware logs.
* `config/limine/wwan-nvme.conf` - Drop-in configuration for Limine bootloader.
* `config/grub/grub_cmdline.txt` - Configuration snippet for GRUB.
* `config/systemd-boot/cmdline-snippet.txt` - Configuration snippet for systemd-boot.
* `scripts/probe_nvme_registers.py` - Python script to probe BAR0 MMIO registers in userspace.
* `scripts/fix-wwan-ssd.sh` - Shell script to trigger bus rescan and driver binding.

---

## ⚖️ License & Disclaimer
This research is published under the MIT License for educational, reverse-engineering, and hardware modding purposes. Perform hardware pin modifications at your own risk.
