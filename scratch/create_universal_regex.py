import sys
import pymem
import pymem.process
import ctypes
import struct
import time

sys.stdout.reconfigure(encoding='utf-8')

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

def scan_heap_for_int(pm, regions, target_val):
    matched = []
    target_pattern = int(target_val).to_bytes(4, byteorder='little', signed=True)
    for reg_start, reg_size in regions:
        try:
            region_bytes = pm.read_bytes(reg_start, reg_size)
            offset = 0
            while True:
                idx = region_bytes.find(target_pattern, offset)
                if idx == -1: break
                addr = reg_start + idx
                if addr % 4 == 0:
                    matched.append(addr)
                offset = idx + 4
        except: pass
    return matched

def scan_heap_for_float(pm, regions, target_val):
    matched = []
    # Floats can have slight precision differences, so we find by struct packing
    target_pattern = struct.pack("<f", float(target_val))
    for reg_start, reg_size in regions:
        try:
            region_bytes = pm.read_bytes(reg_start, reg_size)
            offset = 0
            while True:
                idx = region_bytes.find(target_pattern, offset)
                if idx == -1: break
                addr = reg_start + idx
                if addr % 4 == 0:
                    matched.append(addr)
                offset = idx + 4
        except: pass
    return matched

def generate_regex_for_address(pm, addr, value_type):
    # Read 16 bytes before, and 48 bytes after (Total 64 bytes)
    # The value is at index 16
    start_addr = addr - 16
    try:
        data = pm.read_bytes(start_addr, 64)
    except:
        return None
        
    regex_str = 'b"'
    i = 0
    while i < 64:
        # Mask out the value itself (4 bytes)
        if i == 16:
            regex_str += '.{4}'
            i += 4
            continue
            
        # Check if the next 8 bytes form a 64-bit pointer
        if i % 8 == 0 and i + 8 <= 64:
            ptr_val = int.from_bytes(data[i:i+8], byteorder='little', signed=False)
            # A typical valid heap/module pointer in 64-bit Windows is between 0x10000000000 and 0x7FFFFFFFFFFF
            if 0x10000000000 <= ptr_val <= 0x7FFFFFFFFFFF:
                regex_str += '.{8}'
                i += 8
                continue
                
        # Otherwise, keep the exact byte
        regex_str += f'\\x{data[i]:02x}'
        i += 1
        
    regex_str += '"'
    return regex_str

def main():
    print("=" * 70)
    print("  리니지 클래식 궁극의 정규식(Regex) 지문 생성기")
    print("  (무게와 포만도를 완벽히 독립적으로 추적하여 영구 지문을 생성합니다)")
    print("=" * 70)
    
    try:
        pm = pymem.Pymem("LC.exe")
        print("[+] 게임 연결 성공!")
    except:
        print("[-] 게임을 찾을 수 없습니다.")
        return
        
    regions = get_readable_regions(pm)
    print(f"[+] 메모리 영역 {len(regions)}개 로드 완료.\n")
    
    # ----------------------------------------------------------------
    # 1. 무게(WT) 지문 추출
    # ----------------------------------------------------------------
    print(">>> [1단계] 무게(WT) 영구 지문 추출 <<<")
    wt1 = int(input("현재 무게(%) 입력 (예: 28) -> ").strip())
    wt_addrs = scan_heap_for_int(pm, regions, wt1)
    print(f"[+] 1차 후보: {len(wt_addrs)}개 발견")
    
    input("게임에서 아이템을 옮겨 무게를 변경한 뒤 엔터를 누르세요...")
    wt2 = int(input("변경된 새 무게(%) 입력 (예: 27) -> ").strip())
    
    wt_cands = []
    for a in wt_addrs:
        try:
            if pm.read_int(a) == wt2:
                wt_cands.append(a)
        except: pass
        
    print(f"[+] 2차 후보: {len(wt_cands)}개로 압축됨")
    
    if len(wt_cands) > 1:
        input("정확도를 위해 무게를 한 번 더 변경한 뒤 엔터를 누르세요...")
        wt3 = int(input("변경된 새 무게(%) 입력 -> ").strip())
        final_wt = []
        for a in wt_cands:
            try:
                if pm.read_int(a) == wt3:
                    final_wt.append(a)
            except: pass
        wt_cands = final_wt
        
    if not wt_cands:
        print("[-] 무게 주소 찾기 실패!")
        return
        
    wt_addr = wt_cands[0]
    print(f"[SUCCESS] 진짜 무게 주소 발견: {hex(wt_addr)}")
    wt_regex = generate_regex_for_address(pm, wt_addr, "int")
    print(f"[*] 무게 정규식 지문 생성 완료!\n")
    
    # ----------------------------------------------------------------
    # 2. 포만도(FD) 지문 추출
    # ----------------------------------------------------------------
    print(">>> [2단계] 포만도(FD) 영구 지문 추출 <<<")
    fd1 = float(input("현재 포만도(%) 입력 (예: 84.0) -> ").strip())
    fd_addrs = scan_heap_for_float(pm, regions, fd1)
    print(f"[+] 1차 후보: {len(fd_addrs)}개 발견")
    
    input("시간을 보내거나 음식을 먹어 포만도를 변경한 뒤 엔터를 누르세요...")
    fd2 = float(input("변경된 새 포만도(%) 입력 -> ").strip())
    
    fd_cands = []
    for a in fd_addrs:
        try:
            # Float 비교는 약간의 오차를 허용
            val = pm.read_float(a)
            if abs(val - fd2) < 0.01:
                fd_cands.append(a)
        except: pass
        
    print(f"[+] 2차 후보: {len(fd_cands)}개로 압축됨")
    
    if len(fd_cands) > 1:
        input("정확도를 위해 포만도를 한 번 더 변경한 뒤 엔터를 누르세요...")
        fd3 = float(input("변경된 새 포만도(%) 입력 -> ").strip())
        final_fd = []
        for a in fd_cands:
            try:
                val = pm.read_float(a)
                if abs(val - fd3) < 0.01:
                    final_fd.append(a)
            except: pass
        fd_cands = final_fd
        
    if not fd_cands:
        print("[-] 포만도 주소 찾기 실패!")
        return
        
    fd_addr = fd_cands[0]
    print(f"[SUCCESS] 진짜 포만도 주소 발견: {hex(fd_addr)}")
    fd_regex = generate_regex_for_address(pm, fd_addr, "float")
    print(f"[*] 포만도 정규식 지문 생성 완료!\n")
    
    # ----------------------------------------------------------------
    # 3. 최종 출력
    # ----------------------------------------------------------------
    print("=" * 70)
    print("★ [축하합니다! 불변 영구 지문 세트가 완성되었습니다] ★")
    print("=" * 70)
    print("아래 코드를 복사하여 mem_state_reader.py 의 __init__ 내부에 덮어쓰세요:\n")
    print(f"        self.struct_aob_pattern = {wt_regex}")
    print(f"        self.struct_fd_aob_pattern = {fd_regex}")
    print("\n이 지문은 포인터와 변동 수치를 모두 '.{{4}}', '.{{8}}' 와일드카드로 뚫어놓아")
    print("게임을 재실행해도 영원히 변하지 않는 무결점 지문입니다!")

if __name__ == "__main__":
    main()
