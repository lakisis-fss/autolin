import sys
import os
import struct
import pymem
import pymem.process

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 70)
    print("  Precise Character Structure Offset Finder")
    print("=" * 70)
    
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        
        # 기준 주소
        char_base = base + 0x149b350
        print(f"[+] connected to LC.exe (Base: {hex(base)})")
        print(f"[+] Character Base Address: {hex(char_base)}")
        
        # 우리가 찾는 실제 인게임 타겟 값들 (OCR 기준으로 직접 스캔)
        # HP: 114, Max HP: 114
        # MP: 67, Max MP: 67
        # Level: 11
        target_hp = 114
        target_max_hp = 114
        target_mp = 67
        target_max_mp = 67
        target_level = 11
        
        print(f"\n[*] Scanning memory around char_base (-0x1000 to +0x2000)...")
        start_addr = char_base - 0x1000
        size = 0x3000
        
        try:
            mem_bytes = pm.read_bytes(start_addr, size)
        except Exception as e:
            print(f"[-] Failed to read memory: {e}")
            return
            
        print("[+] Memory read successful. Analyzing 4-byte integers...")
        print("-" * 70)
        print(f"{'Offset':<10} | {'Absolute Addr':<16} | {'Value (Int32)':<12} | {'Matches / Notes':<30}")
        print("-" * 70)
        
        found_matches = []
        for i in range(0, size - 4, 4):
            val = struct.unpack("<i", mem_bytes[i:i+4])[0]
            addr = start_addr + i
            rel_offset = addr - char_base
            
            notes = []
            if val == target_hp:
                notes.append("HP Match (114)")
            if val == target_max_hp:
                notes.append("MaxHP Match (114)")
            if val == target_mp:
                notes.append("MP Match (67)")
            if val == target_max_mp:
                notes.append("MaxMP Match (67)")
            if val == target_level:
                notes.append("Level Match (11)")
                
            if notes:
                found_matches.append((rel_offset, addr, val, ", ".join(notes)))
                print(f"{hex(rel_offset):<10} | {hex(addr):<16} | {val:<12} | {', '.join(notes)}")
                
        # 구조체 연쇄 분석 (HP -> MaxHP -> MP -> MaxMP -> Level)가 연속해서 등장하는 블록 찾기
        print("\n[*] Analyzing consecutive structure candidates...")
        # 기존 오프셋: HP (0x0c), MaxHP (0x10), MP (0x14), MaxMP (0x18), Level (0x1c)
        # 만약 이 구조 자체가 통째로 평행이동했다면, 각 변수간의 상대 오프셋 거리는 일정할 것입니다:
        # MaxHP - HP = 4
        # MP - MaxHP = 4
        # MaxMP - MP = 4
        # Level - MaxMP = 4
        
        for i in range(0, size - 32, 4):
            val_hp = struct.unpack("<i", mem_bytes[i:i+4])[0]
            val_max_hp = struct.unpack("<i", mem_bytes[i+4:i+8])[0]
            val_mp = struct.unpack("<i", mem_bytes[i+8:i+12])[0]
            val_max_mp = struct.unpack("<i", mem_bytes[i+12:i+16])[0]
            val_level = struct.unpack("<i", mem_bytes[i+16:i+20])[0]
            
            addr_hp = start_addr + i
            offset_hp = addr_hp - char_base
            
            if (val_hp == target_hp and 
                val_max_hp == target_max_hp and 
                val_mp == target_mp and 
                val_max_mp == target_max_mp and 
                val_level == target_level):
                print(f"\n[🏆 GOLDEN CANDIDATE FOUND!]")
                print(f"    Structure starts at: char_base + {hex(offset_hp - 12)}")
                print(f"    HP Offset:      {hex(offset_hp)} (Value: {val_hp})")
                print(f"    MaxHP Offset:   {hex(offset_hp + 4)} (Value: {val_max_hp})")
                print(f"    MP Offset:      {hex(offset_hp + 8)} (Value: {val_mp})")
                print(f"    MaxMP Offset:   {hex(offset_hp + 12)} (Value: {val_max_mp})")
                print(f"    Level Offset:   {hex(offset_hp + 16)} (Value: {val_level})")
                
                # 경험치 절대량 스캔 (Level 뒤에 존재할 가능성이 높음. 기존 오프셋은 Level + 12)
                exp_abs_val = struct.unpack("<i", mem_bytes[i+28:i+32])[0]
                print(f"    EXP Offset (Candidate): {hex(offset_hp + 28)} (Value: {exp_abs_val})")
                
        print("=" * 70)
        
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
