import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mem_state_reader import MemStateReader
import time

def main():
    print("=" * 60)
    print("  New Memory Offsets Verification Tool")
    print("=" * 60)
    
    reader = MemStateReader()
    print("[*] Attaching to LC.exe...")
    if not reader.attach():
        print("[-] Failed to attach to LC.exe. Is the game running?")
        return
        
    print("[+] Successfully attached!")
    print("[*] Reading state for 10 seconds (20 iterations)...")
    print("-" * 60)
    
    for i in range(20):
        state = reader.get_state()
        if state:
            # sys.stdout.buffer.write 를 사용하여 콘솔 인코딩 에러를 안전하게 회피하고 utf-8로 강제 출력
            log_str = (
                f"[{i+1:02d}] HP: {state['hp']['text']} ({state['hp']['percent']:.1f}%) | "
                f"MP: {state['mp']['text']} ({state['mp']['percent']:.1f}%) | "
                f"WT: {state['weight']['text']} | "
                f"FD: {state['food']['text']} | "
                f"Coords: {state['coords']} | "
                f"Dir: {state['direction']}\n"
            )
            sys.stdout.buffer.write(log_str.encode('utf-8'))
            sys.stdout.flush()
        else:
            print(f"[{i+1:02d}] Failed to read memory state.")
        time.sleep(0.5)
        
    print("=" * 60)
    print("[+] Verification finished.")

if __name__ == "__main__":
    main()
