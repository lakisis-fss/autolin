import pymem
import struct
import ctypes

def main():
    print("=" * 70)
    print("  [긴급] 특정 주소(47% -> 29%) AOB 추출기")
    print("=" * 70)
    
    try:
        if not ctypes.windll.shell32.IsUserAnAdmin():
            print("[!] 관리자 권한으로 실행되지 않았습니다.")
            
        pm = pymem.Pymem("LC.exe")
        target_addr = 0x251a1c476d4  # 47% 였던 바로 그 주소
        
        # 16바이트 읽어오기
        data = pm.read_bytes(target_addr, 16)
        
        # 현재 소수점 값 확인
        current_val = struct.unpack('<f', data[:4])[0]
        
        # AOB 지문 생성
        full_aob_string = 'b"' + ''.join([f'\\x{b:02x}' for b in data]) + '"'
        
        print(f"[+] 목표 주소: {hex(target_addr)}")
        print(f"[+] 현재 소수점 값: {current_val:.4f}% (29% 근처인지 확인하세요!)")
        
        print("\n[성공] 아래 코드를 mem_state_reader.py 에 붙여넣으세요:\n")
        print(f"    self.struct_weight_aob_pattern = {full_aob_string}\n")
        
    except Exception as e:
        print(f"[-] 에러 발생: {e}")

if __name__ == "__main__":
    main()
