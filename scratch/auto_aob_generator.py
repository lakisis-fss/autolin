import sys
import time
import pymem
import pymem.process
import ctypes
import binascii

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

def scan_heap_for_value(pm, regions, target_val, is_food=False):
    matched_addresses = []
    
    # 포만도의 경우 메모리 상에 10배수로 저장될 수 있으므로 둘 다 찾음 (예: UI 17% -> 메모리 170)
    targets = [target_val]
    if is_food:
        targets.append(target_val * 10)
        
    for t_val in targets:
        target_pattern = int(t_val).to_bytes(4, byteorder='little', signed=True)
        
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
                        matched_addresses.append((addr, t_val))
                    offset = idx + 4
            except Exception:
                pass
    return matched_addresses

def main():
    print("=" * 70)
    print("  완전자동 AOB 지문 생성기 (무게 / 포만도 겸용)")
    print("=" * 70)
    
    print("어떤 수치의 AOB 지문을 추출하시겠습니까?")
    print("1. 무게 (Weight)")
    print("2. 포만도 (Food)")
    choice = input("선택 (1 또는 2) -> ").strip()
    
    is_food = (choice == "2")
    stat_name = "포만도" if is_food else "무게"
    
    try:
        pm = pymem.Pymem("LC.exe")
        print("[+] 게임(LC.exe) 연결 성공!")
    except Exception as e:
        print(f"[-] 게임을 찾을 수 없습니다. 게임이 켜져 있는지 확인해 주세요: {e}")
        return
        
    print("[*] 메모리 지도를 그리는 중...")
    regions = get_readable_regions(pm)
    print(f"[+] 총 {len(regions)}개의 메모리 블록 탐지 완료.\n")
    
    # 1. 1차 스캔
    print(f"[!] 1단계: 현재 게임 화면에 표시된 캐릭터의 '{stat_name}(%)'를 입력해 주세요.")
    if is_food:
        print("    (게임 화면에 17% 라고 적혀있다면 17 을 입력하시면 됩니다)")
    try:
        target_w = int(input(f"    현재 {stat_name} (%) -> ").strip())
    except ValueError:
        print("[-] 올바른 숫자를 입력해 주세요.")
        return
        
    print(f"\n[*] 전체 메모리에서 숫자 전수조사 중...")
    matches_1 = scan_heap_for_value(pm, regions, target_w, is_food)
    
    if not matches_1:
        print(f"\n[-] 메모리에서 값을 찾지 못했습니다.")
        return
        
    print(f"[+] 1차 스캔 완료: 후보 주소 {len(matches_1)}개 발견.\n")
    
    # 2. 반복 검증 (변화 감지)
    step = 2
    golden_addresses = matches_1
    
    while len(golden_addresses) > 1:
        print("=" * 70)
        print(f"[!] {step}단계: 게임 화면으로 가셔서 {stat_name} 수치를 한 번 더 변경해 주세요!")
        if is_food:
            print("    (고기를 먹거나 시간이 지나길 기다리세요)")
        else:
            print("    (가방의 아이템을 버리거나 주워서 수치를 변경하세요)")
        print("    (반드시 이전 값과 다른 숫자로 만들어야 합니다)")
        print(f"    (현재 {len(golden_addresses)}개의 후보 주소가 남았습니다. 딱 1개가 남을 때까지 걸러냅니다)")
        print("=" * 70)
        input("    [수치를 변경하셨다면 엔터키를 눌러주세요...] ")
        
        try:
            new_w = int(input(f"\n    변경된 현재 {stat_name} (%) -> ").strip())
        except ValueError:
            print("[-] 올바른 숫자를 입력해 주세요.")
            continue
            
        print(f"\n[*] {step}차 검증 시작...")
        next_golden = []
        
        # is_food일 때 메모리 상 값이 10배수일 수 있음
        possible_new_vals = [new_w]
        if is_food:
            possible_new_vals.append(new_w * 10)
            
        for addr, old_val in golden_addresses:
            try:
                val = pm.read_int(addr)
                if val in possible_new_vals:
                    next_golden.append((addr, new_w))
            except Exception:
                pass
                
        if not next_golden:
            print("[-] 스캔 실패: 일치하는 주소를 검출해내지 못했습니다. 게임 화면 수치와 입력한 수치가 정확한지 확인 후 처음부터 다시 시도해주세요.")
            return
            
        golden_addresses = next_golden
        print(f"[+] {step}차 압축 완료: 후보 주소를 {len(golden_addresses)}개로 좁혔습니다!\n")
        step += 1
    
    target_addr = golden_addresses[0][0]
    print(f"[*] 최종 {stat_name} 주소 확정: {hex(target_addr)}")
    
    # 3. AOB 지문 추출
    print("\n[*] 해당 주소 주변의 고유 바이트를 분석하여 AOB 지문을 추출합니다...")
    try:
        data = pm.read_bytes(target_addr, 16)
        aob_string = 'b"' + ''.join([f'\\x{b:02x}' for b in data]) + '"'
        
        print("\n" + "=" * 70)
        print("[SUCCESS] 완벽한 AOB 지문 생성이 완료되었습니다!")
        
        if is_food:
            print("\n아래의 코드를 복사하여 mem_state_reader.py 파일의 52번째 줄에 있는")
            print("self.struct_fd_aob_pattern 변수 안에 쏙 집어넣으세요!\n")
            print(f"    self.struct_fd_aob_pattern = {aob_string}\n")
        else:
            print("\n아래의 코드를 복사하여 mem_state_reader.py 파일의 48번째 줄에 있는")
            print("self.struct_aob_pattern 변수 안에 쏙 집어넣으세요!\n")
            print(f"    self.struct_aob_pattern = {aob_string}\n")
            
        print("=" * 70)
    except Exception as e:
        print(f"[-] AOB 추출 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
