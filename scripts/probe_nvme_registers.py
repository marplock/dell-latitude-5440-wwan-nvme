#!/usr/bin/env python3
"""
PCIe MMIO Register Probe for Secondary NVMe SSD in Dell Latitude WWAN Slot
Author: Community Hardware Researcher

This script maps physical BAR0 of device 0000:72:00.0 into userspace memory
to inspect and test NVMe hardware registers without requiring an attached driver.
Must be run as root.
"""

import sys
import os
import mmap
import ctypes
import subprocess

DEV_BDF = "0000:72:00.0"
RESOURCE_PATH = f"/sys/bus/pci/devices/{DEV_BDF}/resource0"

def main():
    if os.geteuid() != 0:
        print(f"[-] Please run with sudo: sudo {sys.argv[0]}")
        sys.exit(1)

    if not os.path.exists(RESOURCE_PATH):
        print(f"[-] Device resource path not found: {RESOURCE_PATH}")
        print("    Ensure the card is detected by lspci (0000:72:00.0).")
        sys.exit(1)

    # Ensure Bus Master and Memory Space are enabled in PCI Command register
    subprocess.run(["setpci", "-s", DEV_BDF, "COMMAND=0x0006"], check=True)

    with open(RESOURCE_PATH, "r+b") as f:
        mm = mmap.mmap(f.fileno(), 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
        buf = (ctypes.c_char * 4096).from_buffer(mm)
        addr = ctypes.addressof(buf)

        # Register pointers (Native 32-bit and 64-bit offsets per NVMe 1.3 spec)
        ptr_cap  = ctypes.cast(addr + 0x00, ctypes.POINTER(ctypes.c_uint64))
        ptr_vs   = ctypes.cast(addr + 0x08, ctypes.POINTER(ctypes.c_uint32))
        ptr_cc   = ctypes.cast(addr + 0x14, ctypes.POINTER(ctypes.c_uint32))
        ptr_csts = ctypes.cast(addr + 0x1c, ctypes.POINTER(ctypes.c_uint32))
        ptr_aqa  = ctypes.cast(addr + 0x24, ctypes.POINTER(ctypes.c_uint32))
        ptr_asq  = ctypes.cast(addr + 0x28, ctypes.POINTER(ctypes.c_uint64))
        ptr_acq  = ctypes.cast(addr + 0x30, ctypes.POINTER(ctypes.c_uint64))

        cap_val = ptr_cap.contents.value
        vs_val = ptr_vs.contents.value
        cc_val = ptr_cc.contents.value
        csts_val = ptr_csts.contents.value

        print(f"==================================================")
        print(f" NVMe MMIO Register Dump: {DEV_BDF}")
        print(f"==================================================")
        print(f" Controller Capabilities (CAP):  {hex(cap_val)}")
        print(f"   - Max Queue Entries (MQES):   {(cap_val & 0xFFFF) + 1}")
        print(f"   - Timeout (TO):               {((cap_val >> 24) & 0xFF) * 500} ms")
        print(f"   - Doorbell Stride (DSTRD):    {2 ** (2 + ((cap_val >> 32) & 0xF))} bytes")
        print(f" Version (VS):                   {hex(vs_val)} (v{(vs_val>>16)&0xFF}.{(vs_val>>8)&0xFF}.{vs_val&0xFF})")
        print(f" Controller Config (CC):         {hex(cc_val)}")
        print(f"   - Enabled (EN):               {bool(cc_val & 0x1)}")
        print(f"   - IO SQ Entry Size (IOSQES):  {2 ** ((cc_val >> 16) & 0xF)} bytes")
        print(f"   - IO CQ Entry Size (IOCQES):  {2 ** ((cc_val >> 20) & 0xF)} bytes")
        print(f" Controller Status (CSTS):       {hex(csts_val)}")
        print(f"   - Ready (RDY):                {bool(csts_val & 0x1)}")
        print(f"   - Fatal Status (CFS):         {bool(csts_val & 0x2)}")
        print(f" Admin Queue Attributes (AQA):   {hex(ptr_aqa.contents.value)}")
        print(f" Admin Submission Queue (ASQ):   {hex(ptr_asq.contents.value)}")
        print(f" Admin Completion Queue (ACQ):   {hex(ptr_acq.contents.value)}")
        print(f"==================================================")

if __name__ == "__main__":
    main()
