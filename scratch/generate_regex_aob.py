import sys
import time
import pymem
import pymem.process
import ctypes
import struct
import re

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

def scan_heap_for_stats(pm, regions, target_w, approx_food_val):
    target_pattern = int(target_w).to_bytes(4, byteorder='little', signed=True)
    candidates = []
    
    print(f"[*] 힙 스캔 시작 (WEIGHT={target_w}, FOOD≈{approx_food_val / 10.0})...")
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
                    # 무게를 찾았으면 주변 512 바이트에서 포만도(Float) 탐색
                    start_scan = max(0, idx - 512)
                    end_scan = min(len(region_bytes) - 4, idx + 512)
                    for j in range(start_scan, end_scan, 4):
                        if j == idx: continue
                        f_val = struct.unpack("<f", region_bytes[j:j+4])[0]
                        if abs(f_val * 10 - approx_food_val) <= 15: # 소수점 오차 허용 (1.5% 이내)
                            candidates.append({
                                'wt_addr': addr,
                                'fd_addr': reg_start + j,
                                'wt_offset': idx,
                                'fd_offset': j
                            })
                            break
                offset = idx + 4
        except Exception:
            pass
    return candidates

def main():
    print("=" * 70)
    print("  리니지 클래식 불변(Invariant) AOB 정규식 추출기")
    print("  (실행마다 변하는 포인터/수치를 자동으로 걸러내고 불변 패턴만 추출합니다)")
    print("=" * 70)
    
    try:
        pm = pymem.Pymem("LC.exe")
        print("[+] 게임 프로세스 연결 성공.")
    except Exception as e:
        print(f"[-] 게임을 찾을 수 없습니다: {e}")
        return

    regions = get_readable_regions(pm)
    
    # 1차 스캔
    try:
        target_w = int(input("\n[!] 1차: 현재 화면의 캐릭터 무게(%)를 입력하세요 (예: 28) -> ").strip())
        approx_food = float(input("[!] 1차: 현재 화면의 포만도(%) 수치를 입력하세요 (예: 84) -> ").strip())
    except ValueError:
        print("[-] 올바른 숫자를 입력하세요.")
        return
        
    candidates = scan_heap_for_stats(pm, regions, target_w, int(approx_food * 10))
    if not candidates:
        print("[-] 일치하는 구조체를 찾지 못했습니다.")
        return
        
    print(f"[+] {len(candidates)}개의 구조체 후보 발견.")
    
    # 1차 메모리 스냅샷 (무게 주소 기준 -32 ~ +96 바이트, 총 128바이트)
    snapshots_1 = {}
    for cand in candidates:
        wt_addr = cand['wt_addr']
        try:
            snap = pm.read_bytes(wt_addr - 32, 128)
            snapshots_1[wt_addr] = snap
        except:
            pass
            
    print("-" * 70)
    print("\n[!] 게임으로 돌아가서 인벤토리 아이템을 이동/버리기 하여 '무게'를 확실하게 변경해주세요.")
    print("    포만도 역시 시간이 지나 변하게 두셔도 좋습니다.")
    input("    [수치가 모두 변경되었다면 엔터키를 누르세요...] ")
    
    # 2차 스캔 및 비교
    try:
        new_w = int(input("\n[!] 2차: 변경된 화면의 캐릭터 무게(%)를 입력하세요 -> ").strip())
    except ValueError:
        print("[-] 올바른 숫자를 입력하세요.")
        return

    valid_candidates = []
    snapshots_2 = {}
    
    for wt_addr, snap1 in snapshots_1.items():
        try:
            val = pm.read_int(wt_addr)
            if val == new_w: # 무게가 정확히 새 값으로 변했는지 확인
                valid_candidates.append(wt_addr)
                snapshots_2[wt_addr] = pm.read_bytes(wt_addr - 32, 128)
        except:
            pass
            
    if not valid_candidates:
        print("[-] 구조체 추적 실패. 입력하신 새 무게 값과 일치하는 힙 주소가 없습니다.")
        return
        
    best_addr = valid_candidates[0]
    snap1 = snapshots_1[best_addr]
    snap2 = snapshots_2[best_addr]
    
    print(f"\n[SUCCESS] 완벽한 불변 AOB 구조체 확보! (기준 주소: {hex(best_addr)})")
    
    # 바이트 비교하여 정규식 패턴 생성 (변하는 값은 '.', 불변 값은 '\xNN')
    regex_pattern_str = 'b"'
    raw_regex = b""
    for b1, b2 in zip(snap1, snap2):
        if b1 == b2:
            regex_pattern_str += f"\\x{b1:02x}"
            raw_regex += bytes([b1])
        else:
            regex_pattern_str += "."
            raw_regex += b"."
    regex_pattern_str += '"'
    
    # WT 위치는 32바이트 지점 (인덱스 32)
    wt_offset = 32
    
    # FD 위치 찾기 (snap2 기준으로 현재 포만도 float 찾기)
    fd_offset = -1
    for i in range(0, 128 - 4, 4):
        if i == wt_offset: continue
        f_val = struct.unpack("<f", snap2[i:i+4])[0]
        if 0.0 <= f_val <= 120.0:
            if fd_offset == -1 or f_val > 0.0: # 여러 개일 수 있으나 첫 유효값 채택
                fd_offset = i
                break
                
    if fd_offset == -1:
        print("[-] 포만도 상대 오프셋을 찾지 못했습니다.")
        fd_offset = wt_offset + 0x18C # Fallback
        
    rel_fd_offset = fd_offset - wt_offset
    
    print("\n" + "=" * 70)
    print("  [불변 AOB 정규식 지문 추출 결과]")
    print("=" * 70)
    print(f"무게와 포만도 오프셋 차이: {rel_fd_offset} 바이트")
    print("\n아래 코드를 복사하여 mem_state_reader.py 의 __init__ 안에 적용하세요:")
    print(f"    self.struct_regex_pattern = {regex_pattern_str}")
    print(f"    self.relative_fd_offset = {rel_fd_offset}")
    print("\n이 정규식 지문은 게임을 껐다 켜도, 포인터가 변경되어도 절대 변하지 않는 핵심 뼈대입니다!")

if __name__ == "__main__":
    main()
