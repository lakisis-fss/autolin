import pymem
import pymem.process
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

try:
    pm = pymem.Pymem("LC.exe")
    base = pymem.process.module_from_name(pm.process_handle, "LC.exe").lpBaseOfDll
    char_base = base + 0x149b350
    lvl1 = pm.read_longlong(char_base + 0xc0)
    lvl2 = pm.read_longlong(lvl1 + 0x628)
    lvl3 = pm.read_longlong(lvl2 + 0x420)
except Exception as e:
    print(f"[-] 게임 연결 실패: {e}")
    sys.exit(1)

candidates = [0x1b7c, 0x1b84, 0x1bcc, 0x1c8c]

print("=" * 60)
print("      리니지 클래식 포만도(FD) 오프셋 실시간 감지기")
print("=" * 60)
print("[*] 현재 감지된 후보 오프셋들을 모니터링 중입니다.")
print("[*] 게임 내에서 포만감 수치가 변할 때 함께 움직이는 오프셋이 진짜입니다!")
print("[*] 종료하려면 Ctrl+C를 눌러주세요.")
print("-" * 60)

try:
    while True:
        output = []
        for off in candidates:
            try:
                val = pm.read_int(lvl3 + off)
                output.append(f"{hex(off)}: {val/10.0:.1f}% ({val})")
            except Exception:
                output.append(f"{hex(off)}: Error")
        print("\r" + " | ".join(output), end="", flush=True)
        time.sleep(0.5)
except KeyboardInterrupt:
    print("\n\n[+] 모니터링을 종료합니다.")
