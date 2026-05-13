import pymem
import psutil
import time
import ctypes
import struct

# Windows Constants
MEM_COMMIT = 0x1000
PAGE_READWRITE = 0x04

class StealthScanner:
    def __init__(self, process_name="LC.exe"):
        self.process_name = process_name
        self.pm = None
        self.potential_addresses = []
        self.last_values = {} # Store last known values for unknown scans
        
    def attach(self):
        try:
            self.pm = pymem.Pymem(self.process_name)
            print(f"[*] Attached to {self.process_name} (PID: {self.pm.process_id})")
            return True
        except Exception as e:
            print(f"[-] Error attaching: {e}. '관리자 권한'으로 실행해 보세요.")
            return False

    def first_scan(self, value):
        print(f"[*] Starting First Scan for value: {value}...")
        self.potential_addresses = []
        
        pages = self.get_memory_pages()
        for i, page in enumerate(pages):
            try:
                # 에러 발생 시 건너뛰기 위해 try-except 적용
                data = self.pm.read_bytes(page['BaseAddress'], page['RegionSize'])
                for j in range(0, len(data) - 3, 4):
                    val = struct.unpack('<I', data[j:j+4])[0]
                    if val == value:
                        self.potential_addresses.append(page['BaseAddress'] + j)
                
                if i % 10 == 0:
                    print(f"[*] Progress: {i}/{len(pages)} regions scanned...", end='\r')
            except Exception:
                # 299 에러(Partial Copy) 등은 무시하고 다음 페이지로
                continue
        
        print(f"\n[*] Found {len(self.potential_addresses)} potential addresses.")

    def first_scan_unknown(self):
        print(f"[*] Starting First Scan (Unknown Initial Value)...")
        self.potential_addresses = []
        self.last_values = {}
        
        pages = self.get_memory_pages()
        for i, page in enumerate(pages):
            try:
                data = self.pm.read_bytes(page['BaseAddress'], page['RegionSize'])
                for j in range(0, len(data) - 3, 4):
                    addr = page['BaseAddress'] + j
                    val = struct.unpack('<I', data[j:j+4])[0]
                    # Filter out zero values to reduce RAM usage (optional but recommended)
                    if val != 0:
                        self.potential_addresses.append(addr)
                        self.last_values[addr] = val
                
                if i % 10 == 0:
                    print(f"[*] Progress: {i}/{len(pages)} regions recorded...", end='\r')
            except Exception:
                continue
        
        print(f"\n[*] Recorded {len(self.potential_addresses)} potential addresses.")

    def next_scan(self, value):
        if not self.potential_addresses:
            print("[!] No addresses to refine.")
            return
            
        print(f"[*] Refining: Checking {len(self.potential_addresses)} addresses for EXACT value {value}...")
        refined = []
        new_last_values = {}
        for addr in self.potential_addresses:
            try:
                val = self.pm.read_int(addr)
                if val == value:
                    refined.append(addr)
                    new_last_values[addr] = val
            except:
                continue
        
        self.potential_addresses = refined
        self.last_values = new_last_values
        print(f"[*] {len(self.potential_addresses)} addresses remaining.")
        self.show_matches()

    def next_scan_compare(self, mode="decreased"):
        """Compare current memory values with last known values."""
        if not self.potential_addresses:
            print("[!] No addresses to refine.")
            return
            
        print(f"[*] Refining: Checking {len(self.potential_addresses)} addresses for mode '{mode}'...")
        refined = []
        new_last_values = {}
        for addr in self.potential_addresses:
            try:
                current_val = self.pm.read_int(addr)
                last_val = self.last_values.get(addr, 0)
                
                keep = False
                if mode == "decreased" and current_val < last_val: keep = True
                elif mode == "increased" and current_val > last_val: keep = True
                elif mode == "changed" and current_val != last_val: keep = True
                elif mode == "unchanged" and current_val == last_val: keep = True
                
                if keep:
                    refined.append(addr)
                    new_last_values[addr] = current_val
            except:
                continue
        
        self.potential_addresses = refined
        self.last_values = new_last_values
        print(f"[*] {len(self.potential_addresses)} addresses remaining.")
        self.show_matches()

    def show_matches(self):
        if 0 < len(self.potential_addresses) <= 10:
            for addr in self.potential_addresses:
                val = self.last_values.get(addr, "Unknown")
                print(f"  [+] Match found at: {hex(addr)} (Current Value: {val})")

    def get_memory_pages(self):
        """윈도우 64비트 메모리 페이지 리스트업"""
        pages = []
        address = 0
        kernel32 = ctypes.windll.kernel32
        
        # 64-bit MBI Structure
        class MBI64(ctypes.Structure):
            _fields_ = [
                ("BaseAddress", ctypes.c_uint64),
                ("AllocationBase", ctypes.c_uint64),
                ("AllocationProtect", ctypes.c_uint32),
                ("Alignment1", ctypes.c_uint32),
                ("RegionSize", ctypes.c_uint64),
                ("State", ctypes.c_uint32),
                ("Protect", ctypes.c_uint32),
                ("Type", ctypes.c_uint32),
                ("Alignment2", ctypes.c_uint32),
            ]

        mbi = MBI64()
        size = ctypes.sizeof(mbi)
        
        while kernel32.VirtualQueryEx(self.pm.process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), size):
            # MEM_COMMIT(0x1000) 이면서 접근 권한이 읽기/쓰기 가능한 경우만 스캔
            if mbi.State == MEM_COMMIT and (mbi.Protect & (PAGE_READWRITE | 0x40)): # 0x40 is PAGE_EXECUTE_READWRITE
                pages.append({'BaseAddress': mbi.BaseAddress, 'RegionSize': mbi.RegionSize})
            address = mbi.BaseAddress + mbi.RegionSize
            
        return pages

if __name__ == "__main__":
    scanner = StealthScanner("LC.exe")
    if scanner.attach():
        print("\n" + "="*40)
        print("  Stealth Memory Scanner (Advanced)")
        print("="*40)
        
        try:
            while True:
                print("\n[MAIN MENU]")
                print(" 1. First Scan (Exact Value)")
                print(" 2. First Scan (Unknown Value)")
                print(" 3. Next Scan (Exact Value)")
                print(" 4. Next Scan (Decreased Value)")
                print(" 5. Next Scan (Increased Value)")
                print(" 6. Next Scan (Changed Value)")
                print(" 7. Next Scan (Unchanged Value)")
                print(" 0. Exit")
                
                choice = input("\nSelect Option: ")
                
                if choice == '1':
                    val = int(input("Enter Exact Value to search: "))
                    scanner.first_scan(val)
                elif choice == '2':
                    scanner.first_scan_unknown()
                elif choice == '3':
                    val = int(input("Enter Exact Value to refine: "))
                    scanner.next_scan(val)
                elif choice == '4':
                    scanner.next_scan_compare("decreased")
                elif choice == '5':
                    scanner.next_scan_compare("increased")
                elif choice == '6':
                    scanner.next_scan_compare("changed")
                elif choice == '7':
                    scanner.next_scan_compare("unchanged")
                elif choice == '0':
                    print("Exiting...")
                    break
                else:
                    print("[!] Invalid Choice.")

                if len(scanner.potential_addresses) == 1:
                    print(f"\n[!!!] TARGET IDENTIFIED: {hex(scanner.potential_addresses[0])}")
                    
        except KeyboardInterrupt:
            print("\nStopped by user.")
        except Exception as e:
            print(f"\n[!] Fatal Error: {e}")
