import ctypes
import ctypes.wintypes as wintypes
import psutil
import struct
import sys

# --- Windows API Constants ---
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_ALL_ACCESS = 0x001FFFFF

MEM_COMMIT = 0x1000
PAGE_READWRITE = 0x04
PAGE_READONLY = 0x02
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40

kernel32 = ctypes.windll.kernel32

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]

def find_game_process():
    """리니지 클래식 게임 프로세스 (LC) 찾기"""
    for proc in psutil.process_iter(['name', 'pid']):
        if proc.info['name'] and proc.info['name'].upper() == 'LC.EXE':
            return proc.info['pid'], proc.info['name']
    # Fallback: 'LC'로도 탐색
    for proc in psutil.process_iter(['name', 'pid']):
        if proc.info['name'] and 'LC' in proc.info['name'].upper():
            return proc.info['pid'], proc.info['name']
    return None, None

def test_open_process(pid, access_flags, desc):
    """지정된 권한으로 프로세스 핸들 열기 시도"""
    handle = kernel32.OpenProcess(access_flags, False, pid)
    if handle:
        print(f"  [+] {desc}: 성공 (Handle: {handle})")
        return handle
    else:
        err = kernel32.GetLastError()
        print(f"  [-] {desc}: 실패 (에러 코드: {err})")
        return None

def test_read_memory(handle, address, size):
    """특정 주소에서 메모리 읽기 시도"""
    buf = ctypes.create_string_buffer(size)
    bytes_read = ctypes.c_size_t(0)
    result = kernel32.ReadProcessMemory(handle, ctypes.c_void_p(address), buf, size, ctypes.byref(bytes_read))
    return result, bytes_read.value, buf.raw

def scan_memory_regions(handle, max_regions=20):
    """메모리 영역 스캔 및 요약"""
    mbi = MEMORY_BASIC_INFORMATION()
    address = 0
    regions = []
    readable_regions = 0
    total_readable_size = 0
    
    while len(regions) < 500:
        result = kernel32.VirtualQueryEx(handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi))
        if result == 0:
            break
        
        base_addr = mbi.BaseAddress if mbi.BaseAddress is not None else address
        
        if mbi.State == MEM_COMMIT:
            regions.append({
                'base': base_addr,
                'size': mbi.RegionSize,
                'protect': mbi.Protect,
                'type': mbi.Type
            })
            if mbi.Protect in (PAGE_READWRITE, PAGE_READONLY, PAGE_EXECUTE_READ, PAGE_EXECUTE_READWRITE):
                readable_regions += 1
                total_readable_size += mbi.RegionSize
        
        address = base_addr + mbi.RegionSize
        if address <= base_addr:
            break
    
    return regions, readable_regions, total_readable_size

def main():
    print("=" * 60)
    print("  리니지 클래식 (LC) 메모리 접근 테스트")
    print("=" * 60)
    
    # 1. 프로세스 탐색
    pid, name = find_game_process()
    if not pid:
        print("\n[-] LC.exe 프로세스를 찾을 수 없습니다.")
        print("    리니지 클래식 게임이 실행 중인지 확인해주세요.")
        return
    
    print(f"\n[*] 게임 프로세스 발견: {name} (PID: {pid})")
    
    # 2. 다양한 권한 레벨로 OpenProcess 시도
    print(f"\n--- 단계 1: OpenProcess 권한 테스트 ---")
    
    h_limited = test_open_process(pid, PROCESS_QUERY_LIMITED_INFORMATION, "QUERY_LIMITED_INFO")
    if h_limited: kernel32.CloseHandle(h_limited)
    
    h_query = test_open_process(pid, PROCESS_QUERY_INFORMATION, "QUERY_INFORMATION")
    if h_query: kernel32.CloseHandle(h_query)
    
    h_read = test_open_process(pid, PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, "VM_READ + QUERY_INFO")
    
    h_write = test_open_process(pid, PROCESS_VM_WRITE | PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION, "VM_WRITE + VM_OP")
    if h_write: kernel32.CloseHandle(h_write)
    
    h_all = test_open_process(pid, PROCESS_ALL_ACCESS, "ALL_ACCESS (전체 권한)")
    if h_all: kernel32.CloseHandle(h_all)
    
    # 3. 실제 메모리 읽기 테스트
    if h_read:
        print(f"\n--- 단계 2: 메모리 영역 스캔 (VirtualQueryEx) ---")
        regions, readable_count, readable_size = scan_memory_regions(h_read)
        print(f"  [*] 총 커밋된 메모리 영역: {len(regions)}개")
        print(f"  [*] 읽기 가능한 영역: {readable_count}개 ({readable_size / 1024 / 1024:.1f} MB)")
        
        print(f"\n--- 단계 3: 실제 ReadProcessMemory 테스트 ---")
        read_success = 0
        read_fail = 0
        sample_data = None
        
        for region in regions[:30]:
            if region['protect'] in (PAGE_READWRITE, PAGE_READONLY, PAGE_EXECUTE_READ):
                ok, nbytes, data = test_read_memory(h_read, region['base'], min(64, region['size']))
                if ok and nbytes > 0:
                    read_success += 1
                    if not sample_data:
                        sample_data = (region['base'], data[:32])
                else:
                    read_fail += 1
        
        print(f"  [*] 읽기 성공: {read_success}개 영역")
        print(f"  [*] 읽기 실패: {read_fail}개 영역")
        
        if sample_data:
            addr, raw = sample_data
            hex_str = ' '.join(f'{b:02X}' for b in raw)
            print(f"\n  [*] 샘플 데이터 (주소 0x{addr:X}):")
            print(f"      {hex_str}")
        
        kernel32.CloseHandle(h_read)
        
        # 4. 최종 판정
        print(f"\n{'=' * 60}")
        if read_success > 0:
            print("  [OK] 결론: 메모리 읽기가 가능합니다!")
            print("       오프셋 기반 스탯 리딩 파이프라인 구축이 가능합니다.")
        else:
            print("  [FAIL] 결론: 프로세스 핸들은 열리지만 메모리 읽기는 차단됩니다.")
            print("         안티치트가 ReadProcessMemory를 후킹하고 있을 가능성이 높습니다.")
        print("=" * 60)
    else:
        print(f"\n{'=' * 60}")
        print("  [FAIL] 결론: VM_READ 권한으로 프로세스를 열 수 없습니다.")
        print("         안티치트가 OpenProcess 핸들 권한을 필터링하고 있습니다.")
        print("=" * 60)

if __name__ == '__main__':
    main()
