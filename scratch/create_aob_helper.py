import sys
import pymem
import pymem.process
import binascii

def main():
    print("=" * 70)
    print("  자동 AOB 지문 생성기 (가방 구조체 스캐닝용)")
    print("=" * 70)
    print("[!] 치트엔진 등을 통해 찾아낸 '무게(WT)' 값의 정확한 '절대 주소'를 입력해 주세요.")
    print("    (예: 0x2A1B3F4C020 또는 2893549232160)")
    
    addr_str = input("\n무게 절대 주소 입력: ").strip()
    if not addr_str:
        return
        
    try:
        if addr_str.lower().startswith("0x"):
            wt_addr = int(addr_str, 16)
        else:
            wt_addr = int(addr_str)
    except ValueError:
        print("[-] 올바른 숫자를 입력해 주세요.")
        return
        
    try:
        pm = pymem.Pymem("LC.exe")
    except Exception as e:
        print(f"[-] 게임(LC.exe)을 찾을 수 없습니다: {e}")
        return
        
    try:
        # 무게 변수를 포함하여 주변 16바이트를 읽어옵니다. (무게가 시작점)
        # 구조체: [무게(4바이트)] [포만도(4바이트)] [여유(8바이트)]
        data = pm.read_bytes(wt_addr, 16)
        
        print("\n[*] 메모리 데이터 판독 완료!")
        print(f"    Raw Bytes: {binascii.hexlify(data).decode('utf-8')}")
        
        # 파이썬 바이트열 형태로 출력
        aob_string = 'b"' + ''.join([f'\\x{b:02x}' for b in data]) + '"'
        
        print("\n" + "=" * 70)
        print("[SUCCESS] AOB 지문 생성이 완료되었습니다!")
        print("\n아래의 코드를 복사하여 mem_state_reader.py 파일의 48번째 줄에 있는")
        print("self.struct_aob_pattern 변수에 붙여넣으세요:\n")
        print(f"    self.struct_aob_pattern = {aob_string}")
        print("\n주의: 게임을 재시작하여 인벤토리 데이터가 변하더라도")
        print("이 바이트 패턴이 고유하게 유지된다면 계속해서 사용할 수 있습니다.")
        print("=" * 70)
        
    except Exception as e:
        print(f"[-] 메모리를 읽는 중 오류가 발생했습니다: {e}")
        print("    주소가 올바른지, 게임이 켜져 있는지 확인해 주세요.")

if __name__ == "__main__":
    main()
