import pymem
import pymem.process
import ctypes
import struct
import sys

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        process_handle = pm.process_handle
        
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        size = module.SizeOfImage
        limit = base + size
        print(f"[+] Static module LC.exe range: {hex(base)} ~ {hex(limit)}")
        
        target_weight = 35
        target_food = 62
        
        print(f"[*] 1. Scanning heap for WEIGHT={target_weight} and FOOD={target_food}...")
        
        kernel32 = ctypes.windll.kernel32
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
            
        mbi = MEMORY_BASIC_INFORMATION()
        address = 0
        
        weight_pattern = struct.pack("<i", target_weight)
        
        heap_matches = []
        
        # 힙 메모리 리딩
        while kernel32.VirtualQueryEx(process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)) > 0:
            if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40):
                reg_start = address
                reg_size = mbi.RegionSize
                
                # 정적 모듈 바깥만
                if not (base <= reg_start < limit):
                    try:
                        region_bytes = pm.read_bytes(reg_start, reg_size)
                        
                        offset = 0
                        w_offsets = []
                        while True:
                            idx = region_bytes.find(weight_pattern, offset)
                            if idx == -1:
                                break
                            w_offsets.append(idx)
                            offset = idx + 4
                            
                        for w_idx in w_offsets:
                            w_addr = reg_start + w_idx
                            f_addr = w_addr + 8
                            
                            if w_idx + 12 <= reg_size:
                                f_val = struct.unpack("<i", region_bytes[w_idx + 8:w_idx + 12])[0]
                                if f_val == target_food:
                                    heap_matches.append((w_addr, f_addr))
                    except Exception:
                        pass
            address += mbi.RegionSize
            
        print(f"[+] Found {len(heap_matches)} WEIGHT/FOOD heap matches.")
        if not heap_matches:
            print("[-] Heap에서 WEIGHT=35, FOOD=62 매칭 쌍을 찾지 못했습니다.")
            return
            
        print(f"\n[*] 2. Loading committed static regions and parsing pointers...")
        
        # static_pointers: { value: [list of static_addresses] }
        static_pointers = {}
        
        address = base
        loaded_pages = 0
        parsed_pointers = 0
        
        while address < limit:
            if kernel32.VirtualQueryEx(process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)) > 0:
                reg_start = max(base, address)
                reg_end = min(limit, address + mbi.RegionSize)
                reg_size = reg_end - reg_start
                
                if mbi.State == 0x1000 and mbi.Protect in (0x02, 0x04, 0x20, 0x40) and reg_size > 0:
                    try:
                        page_bytes = pm.read_bytes(reg_start, reg_size)
                        loaded_pages += 1
                        
                        # 8바이트 정렬 기준으로 포인터 파싱
                        for idx in range(0, reg_size - 8, 8):
                            val = struct.unpack("<Q", page_bytes[idx:idx+8])[0]
                            if val != 0:
                                static_addr = reg_start + idx
                                if val not in static_pointers:
                                    static_pointers[val] = []
                                static_pointers[val].append(static_addr)
                                parsed_pointers += 1
                    except Exception:
                        pass
                address = mbi.BaseAddress + mbi.RegionSize
            else:
                break
                
        print(f"[+] Loaded {loaded_pages} regions and parsed {parsed_pointers} unique pointers.")
        
        print(f"\n[*] 3. Searching for matches...")
        offsets_to_try = [
            0, 4, 8, 0xc, 0x10, 0x14, 0x18, 0x1c, 0x20, 0x24, 0x28, 0x2c, 0x30, 0x34, 0x38, 0x3c,
            0x40, 0x48, 0x50, 0x58, 0x60, 0x70, 0x80, 0x90, 0xa0, 0xb0, 0xc0, 0xd0, 0xe0, 0xf0
        ]
        
        found_count = 0
        
        for w_addr, f_addr in heap_matches:
            aligned_base = w_addr & ~7
            
            for offset_val in offsets_to_try:
                candidate_struct_base = aligned_base - offset_val
                
                if candidate_struct_base in static_pointers:
                    static_addresses = static_pointers[candidate_struct_base]
                    for static_ptr_addr in static_addresses:
                        static_offset = static_ptr_addr - base
                        print(f"\n[FOUND POINTER!]")
                        print(f"    Static Address: LC.exe + {hex(static_offset)} ({hex(static_ptr_addr)})")
                        print(f"    Points to Heap: {hex(candidate_struct_base)}")
                        print(f"    Weight address: {hex(w_addr)} (offset in struct: +{hex(w_addr - candidate_struct_base)})")
                        print(f"    Food address:   {hex(f_addr)} (offset in struct: +{hex(f_addr - candidate_struct_base)})")
                        
                        # 검증 리드
                        try:
                            val_at_ptr = pm.read_longlong(static_ptr_addr)
                            if val_at_ptr == candidate_struct_base:
                                w_val = pm.read_int(candidate_struct_base + (w_addr - candidate_struct_base))
                                f_val = pm.read_int(candidate_struct_base + (f_addr - candidate_struct_base))
                                print(f"    [VERIFIED] Weight value={w_val}, Food value={f_val}")
                                found_count += 1
                        except Exception as e:
                            print(f"    [VERIFY ERROR] {e}")
                            
        print(f"\n[+] Done. Found {found_count} verified pointer paths.")
        
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
