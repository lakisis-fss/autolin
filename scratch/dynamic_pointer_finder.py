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
        food_pattern = struct.pack("<i", target_food)
        
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
                                    # 너무 많을 수 있으므로 첫 10개만 디버그 출력
                                    if len(heap_matches) <= 10:
                                        print(f"    Found Heap Match -> WEIGHT: {hex(w_addr)}, FOOD: {hex(f_addr)}")
                    except Exception:
                        pass
            address += mbi.RegionSize
            
        print(f"[+] Found {len(heap_matches)} WEIGHT/FOOD heap matches.")
        if not heap_matches:
            print("[-] Heap에서 WEIGHT=35, FOOD=62 매칭 쌍을 찾지 못했습니다.")
            return
            
        # 모든 힙 매치에 대해 포인터 스캔 진행
        representative_matches = heap_matches
        
        print(f"\n[*] 2. Safely scanning LC.exe committed static regions for pointers pointing to these heap matches...")
        
        # 정적 모듈 범위 내의 Committed & Readable 페이지들만 읽기
        static_pages = []
        address = base
        while address < limit:
            if kernel32.VirtualQueryEx(process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)) > 0:
                reg_start = max(base, address)
                reg_end = min(limit, address + mbi.RegionSize)
                reg_size = reg_end - reg_start
                
                # PAGE_READONLY(0x02), PAGE_READWRITE(0x04), PAGE_EXECUTE_READ(0x20), PAGE_EXECUTE_READWRITE(0x40)
                if mbi.State == 0x1000 and mbi.Protect in (0x02, 0x04, 0x20, 0x40) and reg_size > 0:
                    try:
                        page_bytes = pm.read_bytes(reg_start, reg_size)
                        static_pages.append((reg_start, page_bytes))
                    except Exception as e:
                        pass
                address = mbi.BaseAddress + mbi.RegionSize
            else:
                break
                
        print(f"[+] Loaded {len(static_pages)} committed static regions for scanning.")
        
        # 포인터 탐색
        offsets_to_try = [0, 4, 8, 0x10, 0x18, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80, 0x90, 0xa0, 0xb0, 0xc0, 0xd0, 0xe0, 0xf0]
        
        found_pointers_count = 0
        
        for w_addr, f_addr in representative_matches:
            aligned_base = w_addr & ~7
            
            for offset_val in offsets_to_try:
                candidate_struct_base = aligned_base - offset_val
                pointer_pattern = struct.pack("<Q", candidate_struct_base)
                
                for reg_start, page_bytes in static_pages:
                    idx_offset = 0
                    while True:
                        idx = page_bytes.find(pointer_pattern, idx_offset)
                        if idx == -1:
                            break
                        
                        static_ptr_addr = reg_start + idx
                        static_offset = static_ptr_addr - base
                        print(f"    [FOUND POINTER!]")
                        print(f"        Heap Target Address: {hex(candidate_struct_base)} (Struct Base Candidate with offset {hex(offset_val)})")
                        print(f"        Static Pointer Address: {hex(static_ptr_addr)} (LC.exe + {hex(static_offset)})")
                        print(f"        Weight offset in struct: {hex(w_addr - candidate_struct_base)}")
                        print(f"        Food offset in struct: {hex(f_addr - candidate_struct_base)}")
                        
                        # 다단계 오프셋 체크용 덤프 검증
                        try:
                            val_at_ptr = pm.read_longlong(static_ptr_addr)
                            print(f"        Verified Value at Pointer: {hex(val_at_ptr)}")
                            if val_at_ptr == candidate_struct_base:
                                print("        [SUCCESS] Direct static pointer verified!")
                                found_pointers_count += 1
                        except Exception:
                            pass
                            
                        idx_offset = idx + 8
                        
        print(f"\n[+] Scanning finished. Verified pointers found: {found_pointers_count}")
        
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
