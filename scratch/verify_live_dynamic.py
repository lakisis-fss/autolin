import sys
sys.stdout.reconfigure(encoding='utf-8')
import pymem
import pymem.process
import time

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        
        char_base = base + 0x149b350
        
        print("Starting Live Dynamic Verification...")
        print("Observe Satiety (Food) to see if it slowly decays in real-time.")
        print("Press Ctrl+C to stop.")
        
        for _ in range(10):
            try:
                lvl1 = pm.read_longlong(char_base + 0xb0)
                if lvl1 > 0:
                    lvl2_710 = pm.read_longlong(lvl1 + 0x710)
                    if lvl2_710 > 0:
                        lvl3 = pm.read_longlong(lvl2_710 + 0xb28)
                        if lvl3 > 0:
                            weight = pm.read_int(lvl3 + 0x1474)
                            food = pm.read_int(lvl3 + 0x14f4)
                            print(f"[LIVE] Weight: {weight}% | Food(Satiety): {food} ({food/10:.1f}%) | lvl3: {hex(lvl3)}")
                        else:
                            print("[LIVE] lvl3 is null")
                    else:
                        print("[LIVE] lvl2_710 is null")
                else:
                    print("[LIVE] lvl1 is null")
            except Exception as e:
                print(f"[LIVE] Error reading: {e}")
            time.sleep(1)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
