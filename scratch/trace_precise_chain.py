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
        limit = base + module.SizeOfImage
        print(f"[+] Static module LC.exe range: {hex(base)} ~ {hex(limit)}")
        
        # dynamic_stat_tracker에서 감지한 변화 주소
        target_w_addr = 0x2a455667a80
        target_f_addr = 0x2a455667a88
        print(f"[*] Target Heap WEIGHT Addr: {hex(target_w_addr)}")
        print(f"[*] Target Heap FOOD Addr:   {hex(target_f_addr)}")
        
        # 1. 전역 메모리 포인터 맵 빌드 (초고속으로 수행하기 위해 64비트 정수 목록만 미리 로드)
        print("[*] Building memory pointer map...")
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
        
        # global_ptrs: { value: [list of addresses where this value is stored] }
        global_ptrs = {}
        
        while kernel32.VirtualQueryEx(process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)) > 0:
            if mbi.State == 0x1000 and mbi.Protect in (0x02, 0x04, 0x20, 0x40):
                try:
                    page_bytes = pm.read_bytes(address, mbi.RegionSize)
                    for idx in range(0, len(page_bytes) - 8, 8):
                        val = struct.unpack("<Q", page_bytes[idx:idx+8])[0]
                        # 64비트 유효한 포인터 영역 필터링
                        if 0x10000 <= val <= 0x7fffffffffff:
                            ptr_addr = address + idx
                            if val not in global_ptrs:
                                global_ptrs[val] = []
                            global_ptrs[val].append(ptr_addr)
                except Exception:
                    pass
            address += mbi.RegionSize
            
        print(f"[+] Loaded {len(global_ptrs)} unique pointer destinations.")
        
        # 2. 다단계 역추적 수행
        # 구조체의 시작점 오프셋 후보군 (0부터 0x4000까지 8바이트 간격으로 전수조사!)
        print("[*] Searching for pointer chains from target address to static module...")
        
        paths = []
        
        # 재귀 역추적 함수 (최대 4단계)
        def trace(current_val, current_offset_in_struct, path_so_far, depth):
            if depth > 4:
                return
                
            # current_val이 static module 범위 내에 있는지 확인
            if base <= current_val < limit:
                paths.append((current_offset_in_struct, path_so_far))
                static_offset = current_val - base
                print(f"\n[!!! FOUND STATIC POINTER CHAIN !!!]")
                print(f"    Static Pointer: LC.exe + {hex(static_offset)}")
                for lvl, (p_addr, target_val, struct_off) in enumerate(path_so_far):
                    is_static = base <= p_addr < limit
                    loc_str = f"LC.exe + {hex(p_addr - base)}" if is_static else hex(p_addr)
                    print(f"        Level {lvl+1}: Pointer {loc_str} points to struct base {hex(target_val)} (offset +{hex(struct_off)})")
                return
                
            # 이 current_val을 가리키는 포인터가 있는지 조사
            # 구조체 베이스 주소 후보 = current_val - struct_offset
            # 구조체 크기를 최대 0x1000 (4KB)로 상정하고 8바이트 정렬 기준으로 전수조사
            for struct_off in range(0, 0x1000, 8):
                candidate_base = current_val - struct_off
                if candidate_base in global_ptrs:
                    for ptr_addr in global_ptrs[candidate_base]:
                        # 순환 참조 방지
                        if any(ptr_addr == prev_ptr for prev_ptr, _, _ in path_so_far):
                            continue
                        
                        new_path = path_so_far + [(ptr_addr, candidate_base, struct_off)]
                        trace(ptr_addr, current_offset_in_struct, new_path, depth + 1)
                        
        # target_w_addr 자체에서부터 추적 시작
        trace(target_w_addr, 0, [], 1)
        
        print("\n[*] Trace finished.")
        
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
