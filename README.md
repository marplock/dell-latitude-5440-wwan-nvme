# Dell Latitude 5440 WWAN Slot NVMe SSD Research & Mod Guide

> Reverse-engineering the M.2 Key-B cellular slot on the 13th-Gen Dell Latitude 5440 to enable secondary internal NVMe SSD storage.

---

Overview

It is widely claimed on forums (Reddit, Dell Community) that 12th- and 13th-Gen Dell Latitude laptops cannot run an NVMe SSD in the internal WWAN (cellular) slot, assuming the lanes are dead, unrouted, or permanently locked by firmware.

**This research disproves that assumption.** 

Through pinout masking, PCIe register manipulation, ACPI DSDT disassembly, and kernel parameter tuning, we confirmed that:
1. **PCIe lanes are physically wired:** The slot connects directly to **Intel PCH Root Port 2 (`00:1c.0`)**.
2. **PCIe Gen 3 Link Trains Successfully:** The link trains at full **8.0 GT/s (x1 width)** with `DLActive+`.
3. **Bridge Forwarding Works:** With `pci=realloc`, Linux allocates a 1MB MMIO forwarding window (`0x9de00000`) to BAR0.
4. **Direct Register Communication is 100% Functional:** Live 32-bit MMIO reads/writes over PCIe directly configure the controller's Capabilities (`CAP`) and Configuration (`CC`) registers.

---

Tested Hardware & Environment

* **Laptop:** Dell Latitude 5440 (13th Gen Intel Raptor Lake-P)
* **Root Port:** `0000:00:1c.0` PCI Express Root Port 2 (`8086:51b9`)
* **Slot Key:** M.2 Key-B (Socket 2, 3042/3052 form factor)
* **Tested SSD:** Western Digital / SanDisk PC SN520 B+M Key NVMe SSD (`15b7:5004`)
* **Operating System:** Linux (Kernel 6.x / 7.x, Limine / systemd-boot / GRUB)

---
Breakthroughs:

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
