import sys
import pymem
import ctypes
import struct
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

def snapshot_memory_float(pm, regions):
    snapshot = {}
    total_items = 0
    for start, size in regions:
        try:
            data = pm.read_bytes(start, size)
            region_dict = {}
            for i in range(0, size - 3, 4):
                # Float(소수점)으로 언팩
                f_val = struct.unpack('<f', data[i:i+4])[0]
                # 무게는 0.0% ~ 200.0% 사이일 수 있으므로 범위를 0.0 ~ 200.0으로 좁힘
                # (100% 이상인 경우도 있기 때문에 포만도보다 넉넉하게 잡습니다)
                if 0.0 <= f_val <= 200.0:
                    region_dict[i] = f_val
                    total_items += 1
            if region_dict:
                snapshot[start] = (size, region_dict)
        except:
            pass
    return snapshot, total_items

def main():
    print("=" * 70)
    print("  [무게 전용] 소수점(Float) AOB 지문 생성기")
    print("=" * 70)
    
    try:
        # 관리자 권한으로 실행되었는지 확인합니다.
        if not ctypes.windll.shell32.IsUserAnAdmin():
            print("\n[!] 경고: 현재 파이썬이 '관리자 권한'으로 실행되지 않았습니다.")
            print("    (게임 메모리에 접근하려면 관리자 권한이 필수적입니다)\n")
            
        pm = pymem.Pymem("LC.exe")
        print("[+] 게임 연결 성공!")
    except Exception as e:
        print(f"\n[-] 게임 연결 실패: {e}")
        print("\n==================================================")
        print("💡 [해결 방법 안내]")
        print("1. 리니지 클래식(LC.exe) 게임이 켜져 있는지 확인해주세요.")
        print("2. 권한 문제(Could not open process)일 확률이 높습니다.")
        print("   -> 현재 켜져 있는 VS Code(또는 터미널)를 완전히 종료하세요.")
        print("   -> VS Code 아이콘을 우클릭하여 '관리자 권한으로 실행'을 클릭하세요.")
        print("   -> 터미널을 다시 열고 명령어를 입력해 보세요.")
        print("==================================================\n")
        return
        
    regions = get_readable_regions(pm)
    print("[!] 1단계: 현재 무게 상태에서 소수점(Float) 스냅샷을 찍습니다.")
    input("    [준비되셨으면 엔터키를 눌러주세요...] ")
    
    snapshot, total_items = snapshot_memory_float(pm, regions)
    print(f"[+] 1차 스냅샷 완료: {total_items}개의 소수점 데이터 확보.\n")
    
    step = 2
    while total_items > 15:
        print("=" * 70)
        print(f"[!] {step}단계: 게임에서 아이템을 줍거나 버려서 무게를 변경하세요!")
        print(f"    (현재 {total_items}개의 후보가 남았습니다)")
        print("=" * 70)
        print("무게가 어떻게 변했나요?")
        print("1. 증가했다 (아이템 획득)")
        print("2. 변하지 않았다")
        print("3. 감소했다 (아이템 버림/소모)")
        
        choice = input("\n선택 (1/2/3) -> ").strip()
        if choice not in ["1", "2", "3"]:
            continue
            
        new_snapshot = {}
        total_items = 0
        
        for start, (size, region_dict) in snapshot.items():
            try:
                new_data = pm.read_bytes(start, size)
                new_region_dict = {}
                for offset, old_val in region_dict.items():
                    if offset + 4 > size: continue
                    new_val = struct.unpack('<f', new_data[offset:offset+4])[0]
                    
                    if choice == "1" and new_val > old_val:
                        new_region_dict[offset] = new_val
                    elif choice == "2" and new_val == old_val:
                        new_region_dict[offset] = new_val
                    elif choice == "3" and new_val < old_val:
                        new_region_dict[offset] = new_val
                        
                if new_region_dict:
                    new_snapshot[start] = (size, new_region_dict)
                    total_items += len(new_region_dict)
            except:
                pass
                
        snapshot = new_snapshot
        print(f"[+] 필터링 완료: {total_items}개 남음.\n")
        step += 1
        
        if total_items == 0:
            print("[-] 후보가 없습니다. 값을 좁히는 과정에서 실제 값이 제외되었을 수 있습니다. 재시작 해주세요.")
            return

    # 1개가 남았을 때 (또는 여러 개 중 직접 선택할 때) AOB 생성
    print("=" * 70)
    print("[SUCCESS] 후보를 좁혔습니다!")
    
    candidates = []
    for start, (size, region_dict) in snapshot.items():
        for offset, val in region_dict.items():
            candidates.append((start + offset, val))
            
    if len(candidates) > 1:
        print(f"총 {len(candidates)}개의 후보가 남았습니다. 현재 게임의 수치와 일치하는 주소를 선택해주세요.")
        for idx, (addr, val) in enumerate(candidates):
            print(f"  [{idx+1}] 주소: {hex(addr)} | 현재 값: {val:.4f}%")
        
        while True:
            sel = input(f"\n몇 번 주소가 진짜인가요? (1~{len(candidates)}) -> ")
            try:
                sel_idx = int(sel) - 1
                if 0 <= sel_idx < len(candidates):
                    target_addr, final_float = candidates[sel_idx]
                    break
            except:
                pass
    else:
        target_addr, final_float = candidates[0]
        print(f"  - 진짜 주소: {hex(target_addr)} | 현재 값: {final_float:.4f}%")
            
    print(f"\n[*] {hex(target_addr)} 주변의 바이트로 영구 정규식(Regex) AOB 지문을 추출합니다...")
    try:
        # 16바이트 앞, 48바이트 뒤 (총 64바이트)
        start_addr = target_addr - 16
        data = pm.read_bytes(start_addr, 64)
        
        regex_str = 'b"'
        i = 0
        while i < 64:
            if i == 16:
                regex_str += '.{4}'
                i += 4
                continue
            if i % 4 == 0 and i + 8 <= 64:
                ptr_val = int.from_bytes(data[i:i+8], byteorder='little', signed=False)
                if 0x10000000000 <= ptr_val <= 0x7FFFFFFFFFFF:
                    regex_str += '.{8}'
                    i += 8
                    continue
            regex_str += f'\\x{data[i]:02x}'
            i += 1
        regex_str += '"'
        
        print("\n======================================================================")
        print("[SUCCESS] 영구 정규식(Regex) AOB 지문 생성 완료!")
        print("아래 코드를 mem_state_reader.py 의 self.struct_aob_pattern 에 덮어쓰세요:\n")
        print(f"    self.struct_aob_pattern = {regex_str}")
        print("======================================================================\n")
    except Exception as e:
        print("[-] 정규식 AOB 추출 실패:", e)

if __name__ == "__main__":
    main()
