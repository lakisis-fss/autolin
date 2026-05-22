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
            
        # 2. 전역 메모리 포인터 맵 빌드 (모든 Committed & Readable 페이지 대상)
        print(f"\n[*] 2. Building global pointer map from entire committed memory...")
        
        # global_pointers: { value: [list of addresses where this value is stored] }
        global_pointers = {}
        
        address = 0
        loaded_pages = 0
        total_pointers = 0
        
        while kernel32.VirtualQueryEx(process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)) > 0:
            # PAGE_READONLY(0x02), PAGE_READWRITE(0x04), PAGE_EXECUTE_READ(0x20), PAGE_EXECUTE_READWRITE(0x40)
            if mbi.State == 0x1000 and mbi.Protect in (0x02, 0x04, 0x20, 0x40):
                try:
                    page_bytes = pm.read_bytes(address, mbi.RegionSize)
                    loaded_pages += 1
                    
                    # 8바이트 정렬된 64비트 정수 추출
                    for idx in range(0, mbi.RegionSize - 8, 8):
                        val = struct.unpack("<Q", page_bytes[idx:idx+8])[0]
                        if val != 0 and (val & 0x7fffffffffff) == val:
                            ptr_addr = address + idx
                            if val not in global_pointers:
                                global_pointers[val] = []
                            global_pointers[val].append(ptr_addr)
                            total_pointers += 1
                except Exception:
                    pass
            address += mbi.RegionSize
            
        print(f"[+] Parsed {total_pointers} pointers from {loaded_pages} committed memory regions.")
        
        # 3. 다단계 역추적 수행 (최대 3단계)
        print(f"\n[*] 3. Searching for pointer paths from heap matches to LC.exe static module...")
        
        # 구조체의 가능한 오프셋 범위
        offsets_to_try = [
            0, 4, 8, 0xc, 0x10, 0x14, 0x18, 0x1c, 0x20, 0x24, 0x28, 0x2c, 0x30, 0x34, 0x38, 0x3c,
            0x40, 0x48, 0x50, 0x58, 0x60, 0x70, 0x80, 0x90, 0xa0, 0xb0, 0xc0, 0xd0, 0xe0, 0xf0
        ]
        
        paths_found = 0
        
        def trace_back(current_addr, path_so_far, depth):
            nonlocal paths_found
            if depth > 3:
                return
                
            # current_addr가 static module 범위 내에 있는지 확인
            if base <= current_addr < limit:
                static_offset = current_addr - base
                print(f"\n[FOUND STATIC POINTER PATH!]")
                for idx, (p_addr, val, off) in enumerate(path_so_far):
                    is_static = base <= p_addr < limit
                    loc_str = f"LC.exe + {hex(p_addr - base)}" if is_static else hex(p_addr)
                    print(f"    Level {idx + 1}: Address {loc_str} points to {hex(val)} (struct offset +{hex(off)})")
                paths_found += 1
                return
                
            # current_addr 부근의 구조체 베이스 주소들에 대한 포인터 검색
            # (구조체 오프셋 정렬)
            aligned_addr = current_addr & ~7
            for offset_val in offsets_to_try:
                candidate_struct_base = aligned_addr - offset_val
                
                if candidate_struct_base in global_pointers:
                    ptrs = global_pointers[candidate_struct_base]
                    for ptr_addr in ptrs:
                        # 무한 루프(순환 참조) 방지
                        if any(ptr_addr == prev_p for prev_p, _, _ in path_so_far):
                            continue
                            
                        new_path = path_so_far + [(ptr_addr, candidate_struct_base, offset_val)]
                        trace_back(ptr_addr, new_path, depth + 1)
                        
        # 각 힙 매치에서 역추적 시작
        for w_addr, f_addr in heap_matches:
            aligned_base = w_addr & ~7
            trace_back(aligned_base, [], 1)
            
        print(f"\n[+] Recursive search complete. Found {paths_found} path(s).")
        
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
