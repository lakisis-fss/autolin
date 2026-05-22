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
        
        # 1. 힙 메모리에서 WEIGHT=35, FOOD=62 조합 전수조사
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
                # Static module이 아닌 동적 메모리 영역만 조사
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
            print("[-] No heap matches found. Are you logged in and values are WEIGHT=35, FOOD=62?")
            return
            
        # 2. 정적 모듈 바이트 중 Readable한 페이지들만 선별적으로 로드
        print(f"[*] 2. Scanning readable static module regions...")
        static_ptrs = {} # ptr_val -> static_address list
        
        address = base
        loaded_bytes = 0
        while address < limit:
            if kernel32.VirtualQueryEx(process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)) > 0:
                reg_start = address
                reg_size = mbi.RegionSize
                reg_end = reg_start + reg_size
                
                # 정적 모듈 내부에 포함되고, Readable한 Protect를 가진 경우에만 읽음
                if reg_start >= base and reg_start < limit:
                    # PAGE_NOACCESS(0x01)나 PAGE_GUARD(0x100) 등 제외, Readable한 경우만
                    if mbi.State == 0x1000 and mbi.Protect in (0x02, 0x04, 0x20, 0x40):
                        # 실제 limit를 초과하지 않도록 크기 보정
                        read_size = min(reg_size, limit - reg_start)
                        try:
                            page_bytes = pm.read_bytes(reg_start, read_size)
                            loaded_bytes += read_size
                            for idx in range(0, read_size - 8, 8):
                                val = struct.unpack("<Q", page_bytes[idx:idx+8])[0]
                                if 0x10000 <= val <= 0x7fffffffffff:
                                    if val not in static_ptrs:
                                        static_ptrs[val] = []
                                    static_ptrs[val].append(reg_start + idx)
                        except Exception:
                            pass
                address = reg_end
            else:
                break
                
        print(f"[+] Successfully loaded {loaded_bytes} bytes from static module.")
        print(f"[+] Static pointers cataloged: {len(static_ptrs)}")
        
        # 힙 매칭 주소 주변을 가리키는 포인터 조회
        print("\n[*] Checking for matching pointers...")
        found_count = 0
        for w_addr, f_addr in heap_matches:
            # 구조체의 베이스 주소가 w_addr로부터 최대 64KB(0x10000) 범위 앞까지 있을 수 있음
            # 정렬을 감안해서 8바이트 간격으로 루프 돌며 static_ptrs 에 있는지 매칭
            aligned_w = w_addr & ~7
            for offset_val in range(0, 0x10000, 8):
                target_base = aligned_w - offset_val
                if target_base in static_ptrs:
                    for s_addr in static_ptrs[target_base]:
                        static_offset = s_addr - base
                        print(f"\n[!!! FOUND STATIC POINTER !!!]")
                        print(f"    Static Address: LC.exe + {hex(static_offset)} ({hex(s_addr)})")
                        print(f"    Points to Heap Base: {hex(target_base)}")
                        print(f"    Heap WEIGHT Addr: {hex(w_addr)} (offset +{hex(w_addr - target_base)})")
                        print(f"    Heap FOOD Addr:   {hex(f_addr)} (offset +{hex(f_addr - target_base)})")
                        print(f"    Pointer chain -> WEIGHT: [LC.exe + {hex(static_offset)}] + {hex(w_addr - target_base)}")
                        print(f"    Pointer chain -> FOOD:   [LC.exe + {hex(static_offset)}] + {hex(f_addr - target_base)}")
                        found_count += 1
                        
        print(f"\n[+] Scan completed. Total static paths found: {found_count}")
        
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
