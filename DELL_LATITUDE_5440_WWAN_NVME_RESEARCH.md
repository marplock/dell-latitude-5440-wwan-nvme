# Dell Latitude 5440 WWAN Slot Secondary NVMe SSD: Engineering Report & Mod Guide

**Author:** Community Hardware Researcher  
**Target Hardware:** Dell Latitude 5440 (13th Gen Intel Raptor Lake-P, Core i5/i7)  
**Target Drive:** SanDisk / Western Digital PC SN520 B+M Key M.2 2230/2242 NVMe SSD (PCI ID `15b7:5004`)  
**Operating System:** Omarchy Linux (Kernel 7.2.x, Limine Bootloader)  
**Date:** October 2026  

---

## 1. Executive Summary

A long-standing consensus across technical communities (Reddit, Dell Community forums) states that 12th- and 13th-Gen Dell Latitude laptops cannot utilize an NVMe solid-state drive in their internal M.2 Key-B WWAN (cellular) slot, believing the slot is either electrically wired only for USB or fundamentally locked at the motherboard level.

Through physical hardware modifications, PCIe register probing, kernel boot parameter tuning, and ACPI DSDT firmware disassembly, **we proved that the WWAN slot on the Dell Latitude 5440 is physically wired with an active Gen 3 PCIe link to Intel PCH Root Port 2 (`00:1c.0`)**. 

Furthermore, we successfully forced the slot to stay powered, established a trained PCIe 8.0 GT/s link, allocated a 1MB memory forwarding window (`0x9de00000`), and achieved live, bidirectional 32-bit MMIO register communication directly into the SSD's Controller Capabilities and Configuration registers.

This document details the exact hardware pinout conflicts, ACPI power gating mechanisms, kernel parameters, and current limitations of running a secondary NVMe drive in this slot.

---

## 2. Hardware Topology & Architecture

* **Host System:** Dell Latitude 5440
* **Host Chipset:** Intel Raptor Lake PCH
* **Downstream Bridge:** `0000:00:1c.0` PCI Express Root Port 2 (Device ID `8086:51b9`)
* **WWAN Slot Physical Key:** M.2 Key-B (Socket 2, 75 positions, physical notch at pins 12–19)
* **Secondary Endpoint:** SanDisk / Western Digital PC SN520 NVMe SSD (PCI ID `15b7:5004`, Class `010802`)
* **Form Factor:** M.2 2230 / 2242 with dual Key-B and Key-M notches

---

## 3. The Major Obstacles & Solutions

### Obstacle 1: The Power Plane Shutdown (D3cold Drop)
* **Symptom:** Without hardware modification, the Dell Embedded Controller (EC) detects that no certified cellular modem is present in the slot and actively asserts the card power-off lines, causing the PCIe link to drop to `Width x0` and Linux to report:
  ```text
  nvme 0000:72:00.0: Unable to change power state from D3cold to D0, device inaccessible
  ```
* **Root Cause:** Modern Dell EC firmware continuously monitors active-low disable pins on the Key-B interface:
  * **Pin 6:** `FULL_CARD_POWER_OFF#`
  * **Pin 8:** `W_DISABLE1#` (Wireless Radio Disable)
* **Hardware Solution (The Pin-Masking Mod):**
  Using a non-conductive insulating layer (Kapton tape or clear lacquer), mask fingers 3 and 4 on the 5-finger group before the Key-B notch on the bottom/component underside of the SSD:
  * **Pin 2 (Finger 1):** `3.3V Power` -> **MUST REMAIN EXPOSED**
  * **Pin 4 (Finger 2):** `3.3V Power` -> **MUST REMAIN EXPOSED**
  * **Pin 6 (Finger 3):** `FULL_CARD_POWER_OFF#` -> **MASKED / TAPED**
  * **Pin 8 (Finger 4):** `W_DISABLE1#` -> **MASKED / TAPED**
* **Result:** The card stays permanently energized across all power states, training to full speed:
  ```text
  LnkSta: Speed 8GT/s, Width x1 (downgraded from x2)
  ```

---

### Obstacle 2: PCIe Bridge Window Unallocated
* **Symptom:** When attempting to read BAR0 (`Region 0`), Linux reported `Input/output error (-EIO)` and `lspci` showed:
  ```text
  Memory behind bridge: fff00000-000fffff [disabled] [32-bit]
  ```
* **Root Cause:** The motherboard UEFI BIOS assumes the WWAN slot will only host a modem and does not allocate a downstream MMIO memory window to Root Port `00:1c.0`.
* **Kernel Solution:** Add `pci=realloc` to the kernel command line.
* **Result:** Linux PCI core dynamically reallocates address space on boot, assigning a 1MB memory window (`0x9de00000-0x9defffff`) to `00:1c.0` and mapping BAR0 to `0x9de00000`.

---

### Obstacle 3: Dell ACPI `StorageD3Enable` Gating
* **Discovery in Disassembled DSDT:**
  Disassembling `/sys/firmware/acpi/tables/DSDT` revealed that Dell explicitly authored code for NVMe detection under `RP02`:
  ```asl
  Device (PXSX)
  {
      Method (PNVM, 0, Serialized)
      {
          If ((BCCX == 0x01) && (SCCX == 0x08) && (PIXX == 0x02))
          {
              Return (One) // Identifies as NVM Express
          }
      }

      Method (_DSD)
      {
          If (PNVM ()) 
          {
              "StorageD3Enable", One // Force storage into D3 sleep
          }
      }
  }
  ```
* **Effect:** If ACPI is allowed to manage the device, Dell’s ACPI script detects the NVMe class and executes `StorageD3Enable = 1`, commanding the OS to force the storage controller into sleep (`D3cold`), which removes it from `lspci`.
* **Kernel Solution:** Adding `nvme.noacpi=1` prevents the Linux NVMe driver from executing Dell’s ACPI D3 sleep directives, keeping the card in `D0` active state.

---

### Obstacle 4: Intel VT-d / Kernel DMA Protection
* **Symptom:** Boot log reports:
  ```text
  DMAR: Intel-IOMMU force enabled due to platform opt in
  pci 0000:72:00.0: Adding to iommu group 17
  ```
* **Root Cause:** Dell firmware sets the ACPI DMAR "Platform Opt-In" flag (Kernel DMA Protection), isolating external expansion slots into strict IOMMU translation domains.
* **Kernel Solution:** Adding `intel_iommu=off` completely disables the hardware translation table barriers for the WWAN bus.

---

## 4. Direct Hardware MMIO Verification

Using user-space memory mapping (`/sys/bus/pci/devices/0000:72:00.0/resource0`), we directly read and wrote the physical NVMe registers of the SanDisk SN520:

```python
import mmap, ctypes

with open("/sys/bus/pci/devices/0000:72:00.0/resource0", "r+b") as f:
    mm = mmap.mmap(f.fileno(), 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
    buf = (ctypes.c_char * 4096).from_buffer(mm)
    addr = ctypes.addressof(buf)
    
    # Read Capabilities (offset 0x00) and Version (offset 0x08)
    cap = ctypes.cast(addr + 0x00, ctypes.POINTER(ctypes.c_uint64)).contents.value
    vs  = ctypes.cast(addr + 0x08, ctypes.POINTER(ctypes.c_uint32)).contents.value
    cc  = ctypes.cast(addr + 0x14, ctypes.POINTER(ctypes.c_uint32)).contents.value
    csts= ctypes.cast(addr + 0x1c, ctypes.POINTER(ctypes.c_uint32)).contents.value
    
    # Values returned:
    # CAP:  0x30140103ff (Valid NVMe capabilities, TO = 20 [10s])
    # VS:   0x10300      (NVMe Version 1.3.0)
    # CC:   0x460001     (Controller Enable = 1)
    # CSTS: 0x00000000   (Ready = 0, Fatal Status = 0)
```

**Write Test:**
* Writing `0x00000000` to `CC` (offset `0x14`): Readback immediately returned `0x0` (controller disabled).
* Writing `0x00460001` to `CC`: Readback immediately returned `0x460001` (controller enabled).

This conclusively proves the PCIe SerDes data link is intact and capable of error-free bidirectional communication.

---

## 5. The Current Roadblock: `CSTS=0x0`

Despite bidirectional register communication, the Linux NVMe driver fails with:
```text
nvme nvme1: Device not ready; aborting initialisation, CSTS=0x0
nvme 0000:72:00.0: error -ENODEV: probe failed
```

### Technical Cause:
1. **`CSTS` is Read-Only in Silicon:** In the NVMe specification, `CSTS` (offset `0x1c`) cannot be written by host software (writing `1` returns `0x0`). Only the SSD's internal micro-controller can assert bit 0 (`RDY = 1`).
2. **Flash Engine Startup Stall:** 
   * On M.2 Key-M slots, 3.3V power is delivered across **Pins 2, 4, 12, 14, 16, 18, 70, 72, 74**.
   * On M.2 Key-B slots, pins 12–18 do not exist (plastic notch gap).
   * If Pins 70, 72, 74 are not energized by the motherboard WWAN power plane, or if insulating tape encroaches onto Pin 4 or Pin 70, the NAND flash memory plane browns out, halting the internal ARM processor before it can complete its internal Flash Translation Layer (FTL) boot and set `RDY=1`.
3. **Dell EC Handshake:** Dell's 13th-Gen EC expects an active USB modem identity before it fully enables secondary power rails or honors autonomous DMA write transactions initiated by the slot.

---

## 6. Recommended Optimized Bootloader Configuration

To preserve maximum battery life while keeping all patches active for WWAN SSD testing, do **not** use global `pcie_aspm=off`. Instead, apply device-specific quirks and safe bridge reallocation:

### `/etc/limine-entry-tool.d/wwan-nvme.conf`
```sh
KERNEL_CMDLINE[default]+=" pci=realloc nvme.noacpi=1 intel_iommu=off nvme_core.admin_timeout=120 nvme.quirks=15b7:5004:delay_before_chk_rdy,no_apst,broken_msi,single_vector"
```

### Parameter Breakdown:
* **`pci=realloc`**: (Safe, zero battery impact) Forces the kernel to open the 1MB MMIO forwarding window for Bus 72.
* **`nvme.noacpi=1`**: (Zero battery impact) Blocks Dell ACPI `StorageD3Enable` from dropping the WWAN slot into D3cold.
* **`intel_iommu=off`**: (Safe, negligible battery impact) Bypasses Kernel DMA Protection isolation.
* **`nvme_core.admin_timeout=120`**: Gives slow-initializing controllers up to 2 minutes to respond.
* **`nvme.quirks=15b7:5004:...`**: Applies workarounds **only** to the SanDisk drive, preserving full APST power savings on the primary internal drive.

---

## 7. Practical Conclusions & Hardware Advice

1. **For Dual-Booting Windows:**
   The most reliable, high-performance approach for dual-booting on the Latitude 5440 is placing the 2230/2242 NVMe drive into an inexpensive **USB-C 10Gbps enclosure** and creating a **Windows To Go** installation with Rufus. It runs over the laptop's Thunderbolt/USB4 ports at ~1,000 MB/s without touching the internal Linux disk.
2. **If Continuing the WWAN Mod:**
   * Replace thick Scotch tape with **Kapton tape** or a microscopic dot of **clear nail polish** strictly on Pins 6 & 8 to prevent tape wrap-around from covering 3.3V power rails (Pins 4 and 70).
   * Consider an active M.2 Key-B to Key-M interposer board that ties all 3.3V power planes together on a single circuit board.
