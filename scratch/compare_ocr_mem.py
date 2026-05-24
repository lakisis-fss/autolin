import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cv_state_reader import CVStateReader
from mem_state_reader import MemStateReader
import time

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 70)
    print("  OCR vs Memory Real-time Comparison Tool")
    print("=" * 70)
    
    cv_reader = CVStateReader(debug=False)
    mem_reader = MemStateReader()
    
    if not mem_reader.attach():
        print("[-] Failed to attach to LC.exe. Is the game running?")
        return
        
    print("[+] Connected to game process.")
    print("[*] Capturing screen OCR and reading memory values...")
    print("-" * 70)
    
    for i in range(5):
        print(f"\n[Iteration {i+1}]")
        
        # 1. OCR Read
        ocr_data = cv_reader.get_state()
        if ocr_data:
            print("  [OCR Screen Values]")
            print(f"    Level:  {ocr_data.get('level')}")
            print(f"    EXP:    {ocr_data.get('exp')}")
            print(f"    HP:     {ocr_data.get('hp', {}).get('text')} ({ocr_data.get('hp', {}).get('percent'):.1f}%)")
            print(f"    MP:     {ocr_data.get('mp', {}).get('text')} ({ocr_data.get('mp', {}).get('percent'):.1f}%)")
            print(f"    Weight: {ocr_data.get('weight', {}).get('text')}")
            print(f"    Food:   {ocr_data.get('food')}")
            print(f"    AC:     {ocr_data.get('ac')}")
            print(f"    MR:     {ocr_data.get('mr')}")
        else:
            print("  [OCR Screen Values] Capture/Read Failed.")
            
        # 2. Memory Read
        ocr_w = ocr_data["weight"].get("percent") if (ocr_data and "weight" in ocr_data) else None
        mem_data = mem_reader.get_state(ocr_weight=ocr_w)
        if mem_data:
            print("  [Memory Values]")
            print(f"    Level:      {mem_data.get('level')}")
            print(f"    EXP (Abs):  {mem_data.get('exp_abs')}")
            print(f"    EXP (Pct):  {mem_data.get('exp_pct_str')}")
            print(f"    HP:         {mem_data.get('hp', {}).get('text')} ({mem_data.get('hp', {}).get('percent'):.1f}%)")
            print(f"    MP:         {mem_data.get('mp', {}).get('text')} ({mem_data.get('mp', {}).get('percent'):.1f}%)")
            print(f"    Weight:     {mem_data.get('weight', {}).get('text')}")
            print(f"    Food:       {mem_data.get('food', {}).get('text')}")
            print(f"    Coords:     {mem_data.get('coords')}")
            print(f"    Direction:  {mem_data.get('direction')}")
        else:
            print("  [Memory Values] Read Failed.")
            
        time.sleep(1.0)
        
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
