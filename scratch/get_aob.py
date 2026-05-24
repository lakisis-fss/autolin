import pymem
import binascii

try:
    pm = pymem.Pymem('LC.exe')
    addr = 0x277abb9c404
    data = pm.read_bytes(addr, 16)
    fixed_data = data[4:]
    aob_str = 'b"' + ''.join([f'\\x{b:02x}' for b in data]) + '"'
    print(f"Golden AOB: {aob_str}")
except Exception as e:
    print('Failed:', e)
