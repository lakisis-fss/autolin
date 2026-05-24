import sys
import time
import pymem
import ctypes
import struct

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

def snapshot_memory(pm, regions):
    snapshot = {}
    total_items = 0
    for start, size in regions:
        try:
            data = pm.read_bytes(start, size)
            region_dict = {}
            for i in range(0, size - 3, 4):
                val = struct.unpack('<i', data[i:i+4])[0]
                if val > 0: # 0 이하인 쓰레기값 제외 (포만도는 보통 양수)
                    region_dict[i] = val
                    total_items += 1
            if region_dict:
                snapshot[start] = (size, region_dict)
        except Exception:
            pass
    return snapshot, total_items

def main():
    print("=" * 70)
    print("  궁극의 메모리 스캐너 (알 수 없는 초기값 추적기) - 초고속 버전")
    print("=" * 70)
    print("이 도구는 화면에 보이는 수치(예: 23%)와 실제 메모리 저장 방식(예: 2300, 255 등)이")
    print("완전히 다를 때 사용하는 '증감 기반' 추적기입니다.\n")
    
    try:
        pm = pymem.Pymem("LC.exe")
        print("[+] 게임(LC.exe) 연결 성공!")
    except Exception as e:
        print(f"[-] 게임을 찾을 수 없습니다: {e}")
        return
        
    print("[*] 메모리 지도를 그리는 중...")
    regions = get_readable_regions(pm)
    print(f"[+] 총 {len(regions)}개의 메모리 블록 탐지 완료.\n")
    
    print("[!] 1단계: 현재 포만도 상태에서 전체 메모리 스냅샷을 찍습니다.")
    input("    [준비되셨으면 엔터키를 눌러주세요...] ")
    
    print("\n[*] 메모리 스냅샷 촬영 중 (수 초 소요)...")
    snapshot, total_items = snapshot_memory(pm, regions)
    print(f"[+] 1차 스냅샷 완료: {total_items}개의 데이터 확보.\n")
    
    step = 2
    while total_items > 15:
        print("=" * 70)
        print(f"[!] {step}단계: 게임에서 포만도를 변화시켜 주세요!")
        print("    (사탕이나 고기를 먹어서 포만도를 '증가'시키거나,")
        print("     가만히 서서 시간이 지나 포만도가 '감소'하게 만드세요)")
        print(f"    (현재 {total_items}개의 후보가 남았습니다)")
        print("=" * 70)
        print("포만도가 어떻게 변했나요?")
        print("1. 증가했다 (Increased)")
        print("2. 감소했다 (Decreased)")
        print("3. 변하지 않았다 (Unchanged)")
        print("4. 정확한 숫자로 검색 (Exact Value)")
        
        choice = input("\n선택 (1/2/3/4) -> ").strip()
        
        exact_val = None
        if choice == "4":
            try:
                exact_val = int(input("화면에 보이는 정확한 수치를 입력하세요 -> ").strip())
            except:
                print("잘못된 입력입니다.")
                continue
        elif choice not in ["1", "2", "3"]:
            print("1, 2, 3, 4 중에서 선택해주세요.")
            continue
            
        print(f"\n[*] {step}차 필터링 중...")
        new_snapshot = {}
        total_items = 0
        
        for start, (size, region_dict) in snapshot.items():
            try:
                # 단 한 번의 커널 API 호출로 블록 전체를 가져옴
                new_data = pm.read_bytes(start, size)
                new_region_dict = {}
                
                # C레벨 구조체 탐색 속도와 맞먹도록 로컬 사전 순회
                for offset, old_val in region_dict.items():
                    if offset + 4 > size:
                        continue
                    new_val = struct.unpack('<i', new_data[offset:offset+4])[0]
                    
                    if choice == "1" and new_val > old_val:
                        new_region_dict[offset] = new_val
                    elif choice == "2" and new_val < old_val:
                        new_region_dict[offset] = new_val
                    elif choice == "3" and new_val == old_val:
                        new_region_dict[offset] = new_val
                    elif choice == "4":
                        if new_val == exact_val or new_val == exact_val * 10 or new_val == exact_val * 100:
                            new_region_dict[offset] = new_val
                            
                if new_region_dict:
                    new_snapshot[start] = (size, new_region_dict)
                    total_items += len(new_region_dict)
            except Exception:
                pass
                
        snapshot = new_snapshot
        print(f"[+] 필터링 완료: {total_items}개 남음.\n")
        step += 1
        
        if total_items == 0:
            print("[-] 후보가 0개가 되었습니다! 실수로 잘못된 조건을 선택하셨을 수 있습니다. 도구를 재시작해주세요.")
            return
            
    print("=" * 70)
    print("[SUCCESS] 후보를 완벽하게 좁혔습니다!")
    print("발견된 메모리 주소와 현재 값:")
    target_addr = 0
    for start, (size, region_dict) in snapshot.items():
        for offset, val in region_dict.items():
            addr = start + offset
            print(f"  - 주소: {hex(addr)} | 현재 값: {val}")
            target_addr = addr
        
    if target_addr > 0:
        print(f"\n[*] {hex(target_addr)} 주소를 기준으로 AOB 지문을 추출합니다...")
        try:
            data = pm.read_bytes(target_addr, 16)
            aob_string = 'b"' + ''.join([f'\\x{b:02x}' for b in data]) + '"'
            print("\n아래 코드를 mem_state_reader.py 의 self.struct_fd_aob_pattern 에 붙여넣으세요:\n")
            print(f"    self.struct_fd_aob_pattern = {aob_string}\n")
        except:
            print("[-] AOB 추출 실패")

if __name__ == "__main__":
    main()
