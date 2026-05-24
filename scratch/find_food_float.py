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
                # 포만도는 0.0 ~ 100.0 사이의 소수점이므로 범위를 좁힘 (쓰레기값 99% 제거)
                if 0.0 <= f_val <= 100.0:
                    region_dict[i] = f_val
                    total_items += 1
            if region_dict:
                snapshot[start] = (size, region_dict)
        except:
            pass
    return snapshot, total_items

def main():
    print("=" * 70)
    print("  [포만도 전용] 소수점(Float) AOB 지문 생성기")
    print("=" * 70)
    
    try:
        pm = pymem.Pymem("LC.exe")
        print("[+] 게임 연결 성공!")
    except Exception as e:
        print(f"[-] 게임을 찾을 수 없습니다: {e}")
        return
        
    regions = get_readable_regions(pm)
    print("[!] 1단계: 현재 포만도 상태에서 소수점(Float) 스냅샷을 찍습니다.")
    input("    [준비되셨으면 엔터키를 눌러주세요...] ")
    
    snapshot, total_items = snapshot_memory_float(pm, regions)
    print(f"[+] 1차 스냅샷 완료: {total_items}개의 소수점 데이터 확보.\n")
    
    step = 2
    while total_items > 15:
        print("=" * 70)
        print(f"[!] {step}단계: 게임에서 사탕을 먹거나 시간이 지나게 두세요!")
        print(f"    (현재 {total_items}개의 후보가 남았습니다)")
        print("=" * 70)
        print("포만도가 어떻게 변했나요?")
        print("1. 증가했다 (Increased)")
        print("2. 변하지 않았다 (Unchanged)")
        print("3. 감소했다 (Decreased)")
        
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
            print("[-] 후보가 없습니다. 재시작 해주세요.")
            return

    # 1개가 남았을 때 AOB 생성
    print("=" * 70)
    print("[SUCCESS] 진짜 포만도 주소를 찾았습니다!")
    target_addr = 0
    final_float = 0.0
    for start, (size, region_dict) in snapshot.items():
        for offset, val in region_dict.items():
            target_addr = start + offset
            final_float = val
            print(f"  - 주소: {hex(target_addr)} | 현재 소수점 값: {val:.4f}%")
            
    print(f"\n[*] {hex(target_addr)} 주변의 바이트로 AOB 지문을 추출합니다...")
    try:
        data = pm.read_bytes(target_addr, 16)
        
        # 앞의 4바이트(현재 포만도 수치)는 고정 패턴에서 제외하고 가변 매칭하도록 처리
        fixed_data = data[4:]
        aob_hex = "".join([f"\\x{b:02x}" for b in fixed_data])
        
        # 완전한 16바이트 지문
        full_aob_string = 'b"' + ''.join([f'\\x{b:02x}' for b in data]) + '"'
        
        print("\n아래 코드를 mem_state_reader.py 의 self.struct_fd_aob_pattern 에 붙여넣으세요:\n")
        print(f"    self.struct_fd_aob_pattern = {full_aob_string}\n")
    except Exception as e:
        print("[-] AOB 추출 실패:", e)

if __name__ == "__main__":
    main()
