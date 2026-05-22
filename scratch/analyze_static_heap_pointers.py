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
                if not (base <= reg_start < base + module.SizeOfImage):
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
            print("[-] Heap matches not found.")
            return
            
        print(f"\n[*] 2. Reading heap pointers inside static character structure (LC.exe + 0x149b350 ~ 0x149b550)...")
        start_static = base + 0x149b350
        static_ptrs = []
        
        # 8바이트 정렬된 64비트 포인터 리드
        for off in range(0, 0x200, 8):
            ptr_addr = start_static + off
            val = pm.read_longlong(ptr_addr)
            if val != 0 and (val & 0x7fffffffffff) == val: # 유효한 64비트 주소 형태인 경우
                static_ptrs.append((off, ptr_addr, val))
                
        print(f"[+] Found {len(static_ptrs)} non-zero 64-bit values inside static structure:")
        for off, ptr_addr, val in static_ptrs:
            print(f"    Offset +{hex(off)} (LC.exe + {hex(ptr_addr - base)}): Points to {hex(val)}")
            
        print(f"\n[*] 3. Searching for 1-level or 2-level paths from these static pointers to weight/food...")
        
        # 1단계 체크: static_ptr가 가리키는 힙 객체 내부에 weight/food가 있는지
        # 힙 객체의 범위는 대략 [val, val + 0x200]으로 상정
        for off, ptr_addr, heap_ptr in static_ptrs:
            # heap_ptr 자체가 weight/food를 가리키는지 혹은 인접해 있는지
            for w_addr, f_addr in heap_matches:
                # 1단계 직접 매칭: heap_ptr에서 weight/food가 적절한 오프셋에 있는가?
                dist = w_addr - heap_ptr
                if 0 <= dist < 0x200:
                    print(f"    [FOUND 1-LEVEL PATH!]")
                    print(f"        Static pointer: LC.exe + {hex(ptr_addr - base)}")
                    print(f"        Heap pointer points to: {hex(heap_ptr)}")
                    print(f"        WEIGHT is at: +{hex(dist)} (Address: {hex(w_addr)})")
                    print(f"        FOOD is at:   +{hex(dist + 8)} (Address: {hex(f_addr)})")
                    
        # 2단계 체크: static_ptr가 가리키는 힙 객체 내의 8바이트 정렬된 값이 또 다른 힙 주소(weight/food가 있는 곳)를 가리키는지
        for off, ptr_addr, heap_ptr in static_ptrs:
            try:
                # static_ptr가 가리키는 힙 메모리 512바이트 읽기
                heap_data = pm.read_bytes(heap_ptr, 512)
                for h_off in range(0, 512 - 8, 8):
                    inner_ptr = struct.unpack("<Q", heap_data[h_off:h_off+8])[0]
                    # 이 inner_ptr가 weight/food가 있는 힙 주소 범위에 있는지 확인
                    for w_addr, f_addr in heap_matches:
                        dist2 = w_addr - inner_ptr
                        if 0 <= dist2 < 0x200:
                            print(f"    [FOUND 2-LEVEL PATH!]")
                            print(f"        Static pointer: LC.exe + {hex(ptr_addr - base)}")
                            print(f"        First heap ptr: {hex(heap_ptr)}")
                            print(f"        Inner heap ptr (at offset +{hex(h_off)}): {hex(inner_ptr)}")
                            print(f"        WEIGHT is at: Inner pointer +{hex(dist2)} (Address: {hex(w_addr)})")
                            print(f"        FOOD is at:   Inner pointer +{hex(dist2 + 8)} (Address: {hex(f_addr)})")
            except Exception:
                pass
                
        print("\n[*] Analysis complete.")
        
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
