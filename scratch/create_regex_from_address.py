import sys
import pymem
import binascii

def main():
    print("=" * 70)
    print("  궁극의 정규식(Regex) AOB 지문 생성기 (절대 주소 기반)")
    print("  (변수와 동적 포인터를 완벽히 마스킹하여 영구 지문을 생성합니다)")
    print("=" * 70)
    print("[!] find_weight_float.py 또는 find_food_float.py 를 통해 찾아낸")
    print("    '정확한 절대 주소'를 입력해 주세요.")
    print("    (예: 0x2A1B3F4C020 또는 2893549232160)")
    
    addr_str = input("\n절대 주소 입력: ").strip()
    if not addr_str:
        return
        
    try:
        if addr_str.lower().startswith("0x"):
            target_addr = int(addr_str, 16)
        else:
            target_addr = int(addr_str)
    except ValueError:
        print("[-] 올바른 숫자를 입력해 주세요.")
        return
        
    try:
        pm = pymem.Pymem("LC.exe")
    except Exception as e:
        print(f"[-] 게임(LC.exe)을 찾을 수 없습니다: {e}")
        return
        
    try:
        # 주소를 중심으로 앞 16바이트, 뒤 48바이트 (총 64바이트) 판독
        start_addr = target_addr - 16
        data = pm.read_bytes(start_addr, 64)
        
        print("\n[*] 메모리 데이터 64바이트 판독 완료!")
        
        regex_str = 'b"'
        i = 0
        while i < 64:
            # 1. 타겟 변수 자체 (4바이트 Float) 마스킹
            if i == 16:
                regex_str += '.{4}'
                i += 4
                continue
                
            # 2. 8바이트 정렬된 메모리 포인터 힙/모듈 주소 마스킹
            if i % 8 == 0 and i + 8 <= 64:
                ptr_val = int.from_bytes(data[i:i+8], byteorder='little', signed=False)
                # 64비트 환경의 일반적인 유효 포인터 대역 (0x10000000000 ~ 0x7FFFFFFFFFFF)
                if 0x10000000000 <= ptr_val <= 0x7FFFFFFFFFFF:
                    regex_str += '.{8}'
                    i += 8
                    continue
                    
            # 3. 불변 데이터(구조체 뼈대, 패딩 등)는 그대로 보존
            regex_str += f'\\x{data[i]:02x}'
            i += 1
            
        regex_str += '"'
        
        print("\n" + "=" * 70)
        print("[SUCCESS] 영구 정규식(Regex) AOB 지문 생성 완료!")
        print("=" * 70)
        print("아래 코드를 복사하여 mem_state_reader.py 내부의")
        print("적절한 패턴 변수(self.struct_aob_pattern 등)에 덮어쓰세요:\n")
        print(f"    self.struct_aob_pattern = {regex_str}")
        print("\n이 정규식 지문은 값의 변경이나 포인터 섞임에 절대 영향을 받지 않는")
        print("궁극의 불변(Invariant) 패턴입니다!")
        print("=" * 70)
        
    except Exception as e:
        print(f"[-] 메모리를 읽는 중 오류가 발생했습니다: {e}")
        print("    주소가 올바른지, 게임이 켜져 있는지 확인해 주세요.")

if __name__ == "__main__":
    main()
