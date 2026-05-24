import sys
import time
import pymem
import pymem.process
import ctypes
import struct

sys.stdout.reconfigure(encoding='utf-8')

# Windows API Constants
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
    """현재 프로세스의 읽기/쓰기 가능한 커밋된 메모리 영역 목록 조회"""
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

def scan_heap_for_value(pm, regions, target_val):
    """전체 힙 메모리 영역에서 4바이트 정수 값이 target_val과 일치하는 모든 절대 메모리 주소 수집 (초고속 벌크 및 4바이트 정렬 필터 적용)"""
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
                # 주소가 반드시 4바이트 정렬(0, 4, 8, C로 끝남)되어 있는지 강력 검사!
                addr = reg_start + idx
                if addr % 4 == 0:
                    matched_addresses.append(addr)
                offset = idx + 4
        except Exception:
            pass
    return matched_addresses

def solve_direct_static_pointer(pm, base, limit, target_address):
    """
    정적 데이터 스캐너 (초고속 C-level linear scan):
    최종 힙 주소(target_address) 주변이 구조체의 일부분이라고 가정하고,
    정적 모듈(LC.exe 이미지 영역 전역)에 이 구조체 시작 지점을 가리키는 '진짜 다이렉트 포인터'가 존재하는지 스캔합니다.
    """
    print("[*] 정적 모듈 전반에 대해 readable 페이지 분석 중...")
    kernel32 = ctypes.windll.kernel32
    process_handle = pm.process_handle
    mbi = MEMORY_BASIC_INFORMATION()
    
    static_pages = []
    address = base
    while address < limit:
        if kernel32.VirtualQueryEx(process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)) > 0:
            reg_start = address
            reg_size = mbi.RegionSize
            reg_end = reg_start + reg_size
            
            if reg_start >= base and reg_start < limit:
                if mbi.State == MEM_COMMIT and mbi.Protect in (0x02, 0x04, 0x20, 0x40):
                    read_size = min(reg_size, limit - reg_start)
                    try:
                        page_bytes = pm.read_bytes(reg_start, read_size)
                        static_pages.append((reg_start, page_bytes))
                    except Exception:
                        pass
            address = reg_end
        else:
            break
            
    print(f"    [+] 총 {len(static_pages)}개의 정적 세그먼트 블록(Readable) 로드 완료.")
    print("[*] 힙 객체 시작점 오프셋 연계 역추적 스캔 개시 (초고속 선형 스캔)...")
    
    solutions = []
    min_addr = target_address - 0x3000
    max_addr = target_address
    
    # 정적 데이터에서 포인터가 4바이트 혹은 8바이트 경계에 맞춰 저장되어 있을 것이므로,
    # 8바이트 정렬된 패턴과 4바이트 오프셋 정렬 패턴을 struct.iter_unpack으로 초고속 대조합니다.
    for reg_start, page_bytes in static_pages:
        # 1) 8바이트 경계 (일반적인 64비트 포인터 정렬)
        extra = len(page_bytes) % 8
        bytes_to_unpack = page_bytes[:-extra] if extra else page_bytes
        
        for i, (val,) in enumerate(struct.iter_unpack("<Q", bytes_to_unpack)):
            if min_addr <= val <= max_addr:
                struct_off = target_address - val
                if struct_off % 4 == 0:
                    static_ptr_addr = reg_start + (i * 8)
                    solutions.append({
                        "static_addr": static_ptr_addr,
                        "static_offset": static_ptr_addr - base,
                        "struct_base": val,
                        "wt_offset": struct_off
                    })
                    
        # 2) 4바이트 오프셋 경계 (혹시 모를 4바이트 정렬 포인터)
        if len(page_bytes) >= 12:
            bytes_to_unpack_4 = page_bytes[4:len(page_bytes) - ((len(page_bytes) - 4) % 8)]
            for i, (val,) in enumerate(struct.iter_unpack("<Q", bytes_to_unpack_4)):
                if min_addr <= val <= max_addr:
                    struct_off = target_address - val
                    if struct_off % 4 == 0:
                        static_ptr_addr = reg_start + 4 + (i * 8)
                        solutions.append({
                            "static_addr": static_ptr_addr,
                            "static_offset": static_ptr_addr - base,
                            "struct_base": val,
                            "wt_offset": struct_off
                        })
                        
    return solutions

def main():
    print("=" * 70)
    print("  리니지 클래식 초정밀 정적 포인터 다이렉트 솔버 (창고 및 재할당 완벽 회피)")
    print("=" * 70)
    
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        char_base = base + 0x149b350
        limit = base + module.SizeOfImage
        
        print(f"[+] 게임 연결 성공: LC.exe (Base Address: {hex(base)})")
        print(f"[+] 캐릭터 기준 주소: {hex(char_base)}")
        print("[*] 현재 가상 메모리 영역 매핑 중...")
        regions = get_readable_regions(pm)
        print(f"[+] 총 {len(regions)}개의 읽기/쓰기 가능한 메모리 블록을 탐지했습니다.")
        print("-" * 70)
        
        # 1. 1차 무게 스캔
        print("[!] 1단계: 현재 게임 화면의 캐릭터 무게(WT)를 입력해 주세요.")
        try:
            target_w = int(input("    현재 캐릭터 무게 (%)를 입력하세요 (예: 28) -> ").strip())
        except ValueError:
            print("[-] 올바른 숫자를 입력해 주셔야 합니다. 프로그램을 종료합니다.")
            return
            
        print(f"\n[*] 1차 스캔 검색 조건 설정 완료: WEIGHT={target_w}%")
        print("[*] 전체 힙 영역에서 해당 값을 가진 절대 주소 전수조사 가동...")
        addresses_1 = scan_heap_for_value(pm, regions, target_w)
        
        if not addresses_1:
            print(f"\n[-] 메모리 전체 영역에서 값 {target_w}을 가진 주소를 찾지 못했습니다.")
            return
            
        print(f"[+] 1차 스캔 완료: 총 {len(addresses_1)}개의 절대 주소를 검출했습니다.")
        print("-" * 70)
        
        # 2. 2차 동적 무게 스캔
        print("[!] 2단계: 무게 변화 추적을 개시합니다.")
        print("    1. 게임 화면으로 돌아가서 창고나 가방을 열어 무게 수치를 변경해 주세요.")
        print("    2. 수치가 확실히 변경된 것을 확인한 후, 이 콘솔창으로 돌아오세요.")
        input("    [무게 변경을 마쳤다면 엔터키를 눌러주세요...] ")
        
        try:
            new_w = int(input("\n    [새로운 수치] 변경된 캐릭터 무게 (%)를 입력하세요 -> ").strip())
        except ValueError:
            print("[-] 올바른 숫자를 입력해 주셔야 합니다. 프로그램을 종료합니다.")
            return
            
        print(f"\n[*] 2차 검증 조건 설정 완료: WEIGHT={new_w}%")
        
        golden_addresses = []
        for addr in addresses_1:
            try:
                val = pm.read_int(addr)
                if val == new_w:
                    golden_addresses.append(addr)
            except Exception:
                pass
                
        print(f"[+] 2차 교차 필터링 완료: 후보 주소가 {len(addresses_1)}개 -> {len(golden_addresses)}개로 압축되었습니다.")
        
        # 힙 재할당 셔플링 방어
        if not golden_addresses:
            print("\n[-] 2차 변화 검증 실패. 구조체 상대 간격 매칭 필터링 실행...")
            addresses_2 = scan_heap_for_value(pm, regions, new_w)
            approx_food = float(input("    현재 게임 화면의 포만도(%) 수치를 입력해 주세요 (예: 84) -> ").strip())
            approx_food_val = int(approx_food * 10)
            
            # 보다 안전하게 넓은 버퍼(±2048바이트)를 읽어 상대 포만도 위치가 4바이트 정렬된 상태로 주변에 존재하는지 정밀 대조
            for addr2 in addresses_2:
                try:
                    # 4바이트 정렬이 깨졌거나 이상 주소는 패스
                    if addr2 % 4 != 0:
                        continue
                    # 무게 변수 주변 ±1024바이트 영역 벌크 리딩
                    struct_data = pm.read_bytes(addr2 - 1024, 2048)
                    for off in range(0, 2048 - 4, 4):
                        val = int.from_bytes(struct_data[off:off+4], byteorder='little', signed=True)
                        # 포만도가 100% (1000 또는 100) 근처인지 정밀 확인
                        if abs(val - approx_food_val) <= 15 or abs(val - int(approx_food)) <= 1:
                            # 실제 오프셋 거리 계산
                            real_dist = off - 1024
                            # 너무 터무니없는 거리는 배제 (일반적으로 무게와 포만감은 동일 구조체 내부 512바이트 안에 모여있음)
                            if abs(real_dist) <= 512:
                                golden_addresses.append(addr2)
                                break
                except Exception:
                    pass
            print(f"    [+] 상대 구조체 매칭 완료: 최종 후보 주소 {len(golden_addresses)}개 색출.")
            
        if not golden_addresses:
            print("[-] 최종 주소 복구 실패: 일치하는 주소를 검출해내지 못했습니다.")
            return
            
        # 3. 진짜 무게 주소 도출
        target_addr = golden_addresses[0]
        print(f"\n[*] 3단계: 진짜 무게 주소({hex(target_addr)})를 가리키는 정적 다이렉트 포인터 솔빙 개시...")
        
        solutions = solve_direct_static_pointer(pm, base, limit, target_addr)
        
        print("\n" + "=" * 70)
        if not solutions:
            print("[-] 다이렉트 역추적 실패: 해당 힙 주소를 직접 가리키는 정적 포인터를 찾지 못했습니다.")
            print("    무게 장부가 다단계 포인터 체인(2레벨 이상) 깊은 힙 구조 내부에 존재하는 경우입니다.")
            print(f"    (진짜 무게 절대 주소 번지: {hex(target_addr)})")
            
            # [역공학 기습 솔버 가동]
            # 캐릭터 베이스(0x149b350 ~ 0x149b650) 내부의 8바이트 포인터들이 가리키는 모든 힙(lvl1)들을
            # 수집하여 최종 target_address와 간접 연결선(3단계)이 발생하는지 교차 검사!
            print("\n[*] [대체 솔버] 캐릭터 정적 기본 주소 내부 다단계(1~3레벨) 포인터 체인 스캔 개시...")
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
            
            # 레벨별 탐색 루프 (C-level 벌크 팩토리 스캔)
            for off1, lvl1 in static_ptrs:
                # --- 1단계 체인 검증 ---
                dist1 = target_addr - lvl1
                if 0 <= dist1 < 0x3000 and dist1 % 4 == 0:
                    print(f"\n[SUCCESS] [대체 솔버] 1단계 캐릭터 포인터 직접 체인 검출 성공!")
                    print(f"    골든 체인 오프셋 정보 (1단계):")
                    print(f"        lvl1_off (direct): {hex(off1)}")
                    print(f"        wt_offset: {hex(dist1)}")
                    found_chain = True
                    break
                
                # --- 2단계 체인 검증 ---
                try:
                    lvl1_bytes = pm.read_bytes(lvl1, 0x2000)
                    extra1 = len(lvl1_bytes) % 8
                    bytes_to_unpack1 = lvl1_bytes[:-extra1] if extra1 else lvl1_bytes
                    for i2, (lvl2,) in enumerate(struct.iter_unpack("<Q", bytes_to_unpack1)):
                        if lvl2 != 0 and (lvl2 & 0x7fffffffffff) == lvl2 and lvl2 > 0x10000000:
                            off2 = i2 * 8
                            dist2 = target_addr - lvl2
                            if 0 <= dist2 < 0x3000 and dist2 % 4 == 0:
                                print(f"\n[SUCCESS] [대체 솔버] 2단계 캐릭터 포인터 간접 체인 검출 성공!")
                                print(f"    골든 체인 오프셋 정보 (2단계):")
                                print(f"        lvl1_entry: {hex(off1)}")
                                print(f"        lvl1_off: {hex(off2)}")
                                print(f"        lvl2_wt_off: {hex(dist2)}")
                                found_chain = True
                                break
                except Exception:
                    pass
                if found_chain:
                    break
                    
                # --- 3단계 체인 검증 (실제 mem_state_reader의 무게 장부 구조) ---
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
                                            print(f"\n[SUCCESS] [대체 솔버] 3단계 캐릭터 포인터 골든 간접 체인 검출 성공!")
                                            print(f"    골든 체인 매핑 관계:")
                                            print(f"        [Base + 0x149b350] + {hex(off1)} -> lvl1")
                                            print(f"        [lvl1 + {hex(off2)}] -> lvl2")
                                            print(f"        [lvl2 + {hex(off3)}] -> lvl3")
                                            print(f"        [lvl3 + {hex(dist3)}] -> WEIGHT ({pm.read_int(target_addr)}%)")
                                            
                                            # 포만감 오프셋 역탐색
                                            approx_food = float(input("\n    현재 게임 화면의 포만도(%) 수치를 입력해 주세요 (예: 84) -> ").strip())
                                            approx_food_val = int(approx_food * 10)
                                            
                                            struct_data = pm.read_bytes(lvl3, 0x3000)
                                            candidates_fd = []
                                            for near_off in range(max(0, dist3 - 512), min(0x3000 - 4, dist3 + 512), 4):
                                                if near_off == dist3:
                                                    continue
                                                val = int.from_bytes(struct_data[near_off:near_off+4], byteorder='little', signed=True)
                                                if abs(val - approx_food_val) <= 30 or abs(val - int(approx_food)) <= 3:
                                                    candidates_fd.append((near_off, val))
                                                    
                                            if candidates_fd:
                                                candidates_fd.sort(key=lambda x: abs(x[0] - dist3))
                                                best_fd_off, fd_val = candidates_fd[0]
                                                print(f"    [+] 포만도 오프셋 자동 역탐색 성공!")
                                                print(f"        무게 오프셋({hex(dist3)}) 기준 {best_fd_off - dist3} 바이트 거리에서 포만감 오프셋({hex(best_fd_off)}) 검출 (메모리 값: {fd_val})")
                                                
                                                print(f"\n    [★ 최종 최적화 복구 정보 도출 완료 ★]")
                                                if off1 == 0xb0:
                                                    print(f"        [!] 매칭 성공! 캐릭터 기본 오프셋이 정확히 0xb0와 완벽 일치합니다.")
                                                else:
                                                    print(f"        [⚠️ 경고] 매칭 성공했으나, 캐릭터 기본 오프셋이 0xb0가 아닌 {hex(off1)}입니다. (mem_state_reader 코드 확인 필요)")
                                                print(f"        lvl1_off: {hex(off2)}")
                                                print(f"        lvl2_off: {hex(off3)}")
                                                print(f"        lvl3_wt_off: {hex(dist3)}")
                                                print(f"        lvl3_fd_off: {hex(best_fd_off)}")
                                                print("\n    이 오프셋 세트를 복사하셔서 대화창에 알려주시면 즉각 복구됩니다.")
                                            else:
                                                print(f"    [-] 포만도 매칭값 근처에서 {approx_food_val} 또는 {int(approx_food)}을 검출해내지 못했습니다.")
                                                print(f"\n    [★ 무게 단독 복구 정보 도출 완료 ★]")
                                                print(f"        lvl1_off: {hex(off2)}")
                                                print(f"        lvl2_off: {hex(off3)}")
                                                print(f"        lvl3_wt_off: {hex(dist3)}")
                                                
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
                print("[-] 대체 솔버마저 포인터 관계 식별에 실패했습니다. (안티치트 실시간 완전 은닉 상태)")
        else:
            best = solutions[0]
            print("[SUCCESS] 축하합니다! 1단계 다이렉트 정적 포인터 검출에 완벽히 성공했습니다!")
            print(f"\n    [확정된 다이렉트 무게 공식]")
            print(f"        공식: [LC.exe + {hex(best['static_offset'])}] + {hex(best['wt_offset'])}")
            print(f"        정적 포인터 주소: LC.exe + {hex(best['static_offset'])}")
            print(f"        무게 오프셋: {hex(best['wt_offset'])}")
            
        print("=" * 70)
        
    except Exception as e:
        print(f"[-] 에러가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
