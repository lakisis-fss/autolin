import sys
import struct
import ctypes
import pymem
import pymem.process

MEM_COMMIT = 0x1000
PAGE_READWRITE = 0x04
PAGE_EXECUTE_READWRITE = 0x40

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_ulong),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.c_ulong),
        ("Protect", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
    ]

def get_readable_regions(pm):
    kernel32 = ctypes.windll.kernel32
    process_handle = pm.process_handle
    mbi = MEMORY_BASIC_INFORMATION()
    address = 0
    regions = []
    while kernel32.VirtualQueryEx(process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)) > 0:
        if mbi.State == MEM_COMMIT and mbi.Protect in (PAGE_READWRITE, PAGE_EXECUTE_READWRITE):
            regions.append((address, mbi.RegionSize))
        address += mbi.RegionSize
    return regions

def scan_heap_for_pairs(pm, regions, target_w, target_f_min, target_f_max):
    matched_addresses = []
    w_pattern = struct.pack("<i", target_w)
    print(f"Scanning for WT={target_w} and FD between {target_f_min} and {target_f_max}...")
    for reg_start, reg_size in regions:
        try:
            region_bytes = pm.read_bytes(reg_start, reg_size)
            offset = 0
            while True:
                idx = region_bytes.find(w_pattern, offset)
                if idx == -1:
                    break
                addr = reg_start + idx
                if addr % 4 == 0:
                    # Check near for FD
                    for j in range(max(0, idx - 64), min(len(region_bytes) - 4, idx + 64), 4):
                        if idx == j: continue
                        f_val = struct.unpack("<i", region_bytes[j:j+4])[0]
                        if target_f_min <= f_val <= target_f_max:
                            matched_addresses.append((addr, reg_start + j, f_val))
                offset = idx + 4
        except:
            pass
    return matched_addresses

def pointer_scan(pm, base, limit, char_base, golden_addr):
    # Get pointers from char_base first (L1)
    print(f"\nTracing pointers to {hex(golden_addr)} from char_base ({hex(char_base)})")
    
    char_ptrs = {}
    for off in range(0, 0x1000, 8):
        try:
            val = pm.read_longlong(char_base + off)
            if val > 0x10000000 and (val & 0x7fffffffffff) == val:
                char_ptrs[off] = val
        except: pass

    # L1 Check
    for off, val in char_ptrs.items():
        if 0 <= golden_addr - val < 0x4000:
            print(f"[FOUND L1] char_base + {hex(off)} -> {hex(val)} + {hex(golden_addr - val)} == Target")
            return

    # L2 Check
    print("Checking L2...")
    for off1, lvl1 in char_ptrs.items():
        try:
            lvl1_data = pm.read_bytes(lvl1, 0x3000)
            for i in range(0, len(lvl1_data)-8, 8):
                val2 = struct.unpack("<Q", lvl1_data[i:i+8])[0]
                if val2 > 0x10000000 and (val2 & 0x7fffffffffff) == val2:
                    if 0 <= golden_addr - val2 < 0x4000:
                        print(f"[FOUND L2] char_base + {hex(off1)} -> lvl1 + {hex(i)} -> lvl2 + {hex(golden_addr - val2)} == Target")
                        return
        except: pass

    # L3 Check
    print("Checking L3...")
    for off1, lvl1 in char_ptrs.items():
        try:
            lvl1_data = pm.read_bytes(lvl1, 0x3000)
            for i in range(0, len(lvl1_data)-8, 8):
                val2 = struct.unpack("<Q", lvl1_data[i:i+8])[0]
                if val2 > 0x10000000 and (val2 & 0x7fffffffffff) == val2:
                    try:
                        lvl2_data = pm.read_bytes(val2, 0x3000)
                        for j in range(0, len(lvl2_data)-8, 8):
                            val3 = struct.unpack("<Q", lvl2_data[j:j+8])[0]
                            if val3 > 0x10000000 and (val3 & 0x7fffffffffff) == val3:
                                if 0 <= golden_addr - val3 < 0x4000:
                                    print(f"[FOUND L3] char_base + {hex(off1)} -> lvl1 + {hex(i)} -> lvl2 + {hex(j)} -> lvl3 + {hex(golden_addr - val3)} == Target")
                                    return
                    except: pass
        except: pass
        
    print("Not found in char_base tree. Searching global static pointers...")
    # Just do a 1-level static scan from base to limit
    static_ptrs = []
    addr = base
    mbi = MEMORY_BASIC_INFORMATION()
    kernel32 = ctypes.windll.kernel32
    while addr < limit:
        if kernel32.VirtualQueryEx(pm.process_handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)) > 0:
            if mbi.State == MEM_COMMIT and mbi.Protect in (0x02, 0x04, 0x20, 0x40):
                try:
                    data = pm.read_bytes(addr, min(mbi.RegionSize, limit - addr))
                    extra = len(data) % 8
                    d2 = data[:-extra] if extra else data
                    for idx, (val,) in enumerate(struct.iter_unpack("<Q", d2)):
                        if 0 <= golden_addr - val < 0x3000:
                            print(f"[FOUND GLOBAL STATIC L1] base + {hex((addr - base) + idx*8)} -> {hex(val)} + {hex(golden_addr - val)} == Target")
                except: pass
            addr += mbi.RegionSize
        else:
            break

def main():
    pm = pymem.Pymem("LC.exe")
    module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
    base = module.lpBaseOfDll
    char_base = base + 0x149b350
    limit = base + module.SizeOfImage
    print(f"Base: {hex(base)}, Char Base: {hex(char_base)}")
    
    regions = get_readable_regions(pm)
    pairs = scan_heap_for_pairs(pm, regions, 30, 168, 175)
    
    print(f"Found {len(pairs)} pairs!")
    for wt_addr, fd_addr, f_val in pairs:
        print(f"Candidate: WT at {hex(wt_addr)}, FD at {hex(fd_addr)} (val={f_val})")
        pointer_scan(pm, base, limit, char_base, wt_addr)
        print("-" * 50)

if __name__ == "__main__":
    main()
