import pymem
import pymem.process
import ctypes
import struct

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
        
        while kernel32.VirtualQueryEx(process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)) > 0:
            if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40):
                reg_start = address
                reg_size = mbi.RegionSize
                if not (base <= reg_start < limit):
                    try:
                        region_bytes = pm.read_bytes(reg_start, reg_size)
                        offset = 0
                        while True:
                            idx = region_bytes.find(weight_pattern, offset)
                            if idx == -1:
                                break
                            w_addr = reg_start + idx
                            f_addr = w_addr + 8
                            if idx + 12 <= reg_size:
                                f_val = struct.unpack("<i", region_bytes[idx + 8:idx + 12])[0]
                                if f_val == target_food:
                                    heap_matches.append((w_addr, f_addr))
                            offset = idx + 4
                    except Exception:
                        pass
            address += mbi.RegionSize
            
        print(f"[+] Found {len(heap_matches)} WEIGHT/FOOD heap matches.")
        if not heap_matches:
            return
            
        # 2. 전역 메모리 포인터 범위 스캔
        print(f"\n[*] 2. Scanning all committed memory for pointers to vicinity of found heap matches...")
        
        # 모든 Committed & Readable 페이지 대상
        committed_regions = []
        address = 0
        while kernel32.VirtualQueryEx(process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)) > 0:
            if mbi.State == 0x1000 and mbi.Protect in (0x02, 0x04, 0x20, 0x40):
                try:
                    # 페이지 바이트를 리드해서 저장
                    page_bytes = pm.read_bytes(address, mbi.RegionSize)
                    committed_regions.append((address, page_bytes))
                except Exception:
                    pass
            address += mbi.RegionSize
            
        print(f"[+] Loaded {len(committed_regions)} committed regions for pointer range scanning.")
        
        # 3. 범위 스캔 매칭 수행
        found_paths = 0
        
        # 대표적인 힙 매치들 10개 검사
        for w_addr, f_addr in heap_matches[:10]:
            print(f"\n[*] Target Heap: WEIGHT={hex(w_addr)}, FOOD={hex(f_addr)}")
            
            # 구조체 베이스 주소 범위: w_addr 기준 16KB 앞 ~ w_addr
            target_range_start = w_addr - 0x4000
            target_range_end = w_addr
            
            for reg_start, page_bytes in committed_regions:
                # 8바이트 정렬된 64비트 정수 체크
                for idx in range(0, len(page_bytes) - 8, 8):
                    val = struct.unpack("<Q", page_bytes[idx:idx+8])[0]
                    
                    if target_range_start <= val <= target_range_end:
                        ptr_addr = reg_start + idx
                        offset_in_struct = w_addr - val
                        is_static = base <= ptr_addr < limit
                        
                        loc_str = f"LC.exe + {hex(ptr_addr - base)}" if is_static else hex(ptr_addr)
                        print(f"    [POINTER FOUND] Address {loc_str} points to {hex(val)} (WEIGHT offset: +{hex(offset_in_struct)})")
                        found_paths += 1
                        
        print(f"\n[+] Scan finished. Found {found_paths} range pointers.")
        
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
