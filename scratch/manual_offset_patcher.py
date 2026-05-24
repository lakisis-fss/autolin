import os
import sys
import time
import pymem
import pymem.process
import struct
import re

def scan_heap_for_value(pm, regions, target_val):
    matched_addresses = []
    target_pattern = int(target_val).to_bytes(4, byteorder='little', signed=True)
    
    for reg_start, reg_size in regions:
        try:
            region_bytes = pm.read_bytes(reg_start, reg_size)
            offset = 0
            while True:
                idx = region_bytes.find(target_pattern, offset)
                if idx == -1:
                    break
                addr = reg_start + idx
                if addr % 4 == 0:
                    matched_addresses.append(addr)
                offset = idx + 4
        except Exception:
            pass
    return matched_addresses

def get_readable_regions(pm):
    import ctypes
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
    kernel32 = ctypes.windll.kernel32
    process_handle = pm.process_handle
    mbi = MEMORY_BASIC_INFORMATION()
    address = 0
    regions = []
    
    while kernel32.VirtualQueryEx(process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)) > 0:
        if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40):
            regions.append((address, mbi.RegionSize))
        address += mbi.RegionSize
    return regions

def patch_reader_file(off1, off2, off3, wt_off, fd_off):
    file_path = "mem_state_reader.py"
    if not os.path.exists(file_path):
        print(f"[-] {file_path} 파일이 존재하지 않습니다.")
        return False
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # 1. weight_chain 블록 치환
        chain_pattern = r"self\.weight_chain\s*=\s*\{[^}]*\}"
        new_chain = f"""self.weight_chain = {{
            "lvl1_off": {hex(off2)},
            "lvl2_off": {hex(off3)},
            "lvl3_wt_off": {hex(wt_off)},
            "lvl3_fd_off": {hex(fd_off)}
        }}"""
        content = re.sub(chain_pattern, new_chain, content)
        
        # 2. char_base + 0xXX 진입 오프셋 교정
        content = content.replace("char_base + 0xb0", f"char_base + {hex(off1)}")
        content = content.replace("char_base + 0xc0", f"char_base + {hex(off1)}")
        
        # 3. 추가로 Level과 EXP Offset 교정 (Level: 0x2b8로 변경)
        # 기존: level: 0x149b36c -> 149b350 + 28 -> offsets["level"] = 0x149b36c
        # level offset이 구조체상 0x2b8로 바뀜!
        # exp_abs offset도 새로 분석해서 대입해야 함 (일단 Level이 0x2b8이면 exp_abs는 무엇인지 아래에서 분석함)
        # offsets 딕셔너리 안의 level과 exp_abs를 직접 치환해줌
        # level: 0x149b350 + 0x2b8 = 0x149b608
        # exp_abs: 0x149b350 + 0x2c4 = 0x149b614 (0x2b8 + 12 = 0x2c4)
        level_pattern = r"\"level\":\s*0x149b36c"
        content = re.sub(level_pattern, '"level": 0x149b608', content)
        
        exp_pattern = r"\"exp_abs\":\s*0x149b378"
        content = re.sub(exp_pattern, '"exp_abs": 0x149b614', content)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        print(f"\n[+] {file_path} 파일 자동 패치 성공!")
        print("    이제 대시보드를 재시작하시면 실시간 수치가 즉각 완벽 동기화됩니다.")
        return True
    except Exception as e:
        print(f"[-] 파일 패치 중 오류 발생: {e}")
        return False

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 60)
    print("      리니지 클래식 수동 입력 메모리 오프셋 복구 엔진")
    print("=" * 60)
    
    # OCR 비교값에서 나온 고정값 대입
    target_w = 25
    target_f = 10 # 10%
    approx_food_val = 100 # 포만감 10% -> 100
    
    print(f"[*] 스캔 대상 타겟 설정: WEIGHT={target_w}%, FOOD={target_f}% (메모리 포만감 타겟: {approx_food_val})")
    
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        char_base = base + 0x149b350
    except Exception as e:
        print(f"[-] 게임 연결 실패: {e}")
        return
        
    print("[*] 현재 가상 메모리 영역 분석 중...")
    regions = get_readable_regions(pm)
    print(f"    [+] 총 {len(regions)}개의 메모리 세그먼트 로드 완료.")
    
    print("[*] 힙 메모리에서 실시간 무게 주소 전수 조사 중...")
    addr_list = scan_heap_for_value(pm, regions, target_w)
    print(f"    [+] 1차 스캔 검출 주소: {len(addr_list)}개")
    
    # 구조체 매칭으로 압축
    golden_addresses = []
    for addr in addr_list:
        try:
            struct_data = pm.read_bytes(addr - 1024, 2048)
            for off in range(0, 2048 - 4, 4):
                val = int.from_bytes(struct_data[off:off+4], byteorder='little', signed=True)
                if abs(val - approx_food_val) <= 15:
                    real_dist = off - 1024
                    if abs(real_dist) <= 512:
                        golden_addresses.append((addr, real_dist, val))
                        break
        except Exception:
            pass
            
    print(f"    [+] 구조체 매칭 후 압축 주소: {len(golden_addresses)}개")
    if not golden_addresses:
        print("[-] 일치하는 진짜 캐릭터 정보 주소를 검출하지 못했습니다.")
        return
        
    target_addr, food_offset_dist, detected_food = golden_addresses[0]
    print(f"    [+] 최종 확정된 캐릭터 무게 절대 주소: {hex(target_addr)}")
    
    print("[*] 다단계 포인터 체인(1~3레벨) 추적 엔진 가동...")
    
    static_ptrs = []
    for off in range(0, 0x300, 8):
        ptr_addr = char_base + off
        try:
            val = pm.read_longlong(ptr_addr)
            if val != 0 and (val & 0x7fffffffffff) == val and val > 0x10000000:
                static_ptrs.append((off, val))
        except Exception:
            pass
            
    print(f"    [+] 캐릭터 베이스 내부에서 {len(static_ptrs)}개의 유효한 1차 진입 포인터(lvl1) 검출.")
    
    found_chain = False
    
    for off1, lvl1 in static_ptrs:
        # --- 3단계 체인 검증 ---
        try:
            lvl1_bytes = pm.read_bytes(lvl1, 0x2000)
            extra1 = len(lvl1_bytes) % 8
            bytes_to_unpack1 = lvl1_bytes[:-extra1] if extra1 else lvl1_bytes
            
            for i2, (lvl2,) in enumerate(struct.iter_unpack("<Q", bytes_to_unpack1)):
                if lvl2 != 0 and (lvl2 & 0x7fffffffffff) == lvl2 and lvl2 > 0x10000000:
                    off2 = i2 * 8
                    
                    try:
                        lvl2_bytes = pm.read_bytes(lvl2, 0x2000)
                        extra2 = len(lvl2_bytes) % 8
                        bytes_to_unpack2 = lvl2_bytes[:-extra2] if extra2 else lvl2_bytes
                        
                        for i3, (lvl3,) in enumerate(struct.iter_unpack("<Q", bytes_to_unpack2)):
                            if lvl3 != 0 and (lvl3 & 0x7fffffffffff) == lvl3 and lvl3 > 0x10000000:
                                off3 = i3 * 8
                                dist3 = target_addr - lvl3
                                
                                if 0 <= dist3 < 0x3000 and dist3 % 4 == 0:
                                    fd_off = dist3 + food_offset_dist
                                    print(f"\n[SUCCESS] 다단계 골든 포인터 체인 검출에 성공했습니다!")
                                    print(f"    골든 체인 오프셋 정보:")
                                    print(f"        lvl1_entry: {hex(off1)}")
                                    print(f"        lvl1_off: {hex(off2)}")
                                    print(f"        lvl2_off: {hex(off3)}")
                                    print(f"        lvl3_wt_off: {hex(dist3)}")
                                    print(f"        lvl3_fd_off: {hex(fd_off)}")
                                    
                                    # mem_state_reader.py 파일 자동 패치
                                    patch_reader_file(off1, off2, off3, dist3, fd_off)
                                    found_chain = True
                                    break
                    except Exception:
                        pass
                if found_chain:
                    break
        except Exception:
            pass
        if found_chain:
            break
            
    if not found_chain:
        print("[-] 포인터 연결선 검출 실패: 안티치트가 메모리 통신을 차단했거나 캐릭터 구조체가 갱신되지 않았습니다.")

if __name__ == "__main__":
    main()
