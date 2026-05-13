import requests
import json
import time

pb_url = 'http://127.0.0.1:8090'

# 1. Auth
print("Authenticating...")
auth_res = requests.post(f'{pb_url}/api/collections/_superusers/auth-with-password', json={
    'identity': 'admin@example.com',
    'password': 'Admin1234!!'
})
if auth_res.status_code != 200:
    print("Auth Failed:", auth_res.text)
    exit(1)
    
token = auth_res.json()['token']
headers = {'Authorization': token}

# 2. Check/Create collection
col_res = requests.get(f'{pb_url}/api/collections/monsters', headers=headers)
if col_res.status_code == 404:
    print("Creating collection 'monsters'...")
    col_def = {
        "name": "monsters",
        "type": "base",
        "fields": [
            {"name": "npcid", "type": "number"},
            {"name": "name", "type": "text"},
            {"name": "race", "type": "text"},
            {"name": "size", "type": "text"},
            {"name": "level", "type": "number"},
            {"name": "hp", "type": "number"},
            {"name": "mp", "type": "number"},
            {"name": "ac", "type": "number"},
            {"name": "mr", "type": "number"},
            {"name": "exp", "type": "number"},
            {"name": "alignment", "type": "number"},
            {"name": "features", "type": "text"},
            {"name": "spawns", "type": "text"},
            {"name": "drops", "type": "text"},
            {"name": "image", "type": "file", "maxSelect": 1, "maxSize": 5242880}
        ]
    }
    create_res = requests.post(f'{pb_url}/api/collections', headers=headers, json=col_def)
    if create_res.status_code not in [200, 201]:
        print("Failed to create collection:", create_res.text)
        exit(1)
    print("Collection created successfully!")
else:
    print("Collection 'monsters' already exists.")

# 3. Read monsters.json and import
try:
    with open('monsters.json', 'r', encoding='utf-8') as f:
        monsters = json.load(f)
except Exception as e:
    print("Could not read monsters.json:", e)
    exit(1)

def parse_num(val):
    if not val or val == '-': return 0
    v = str(val).replace(',', '')
    try: return float(v)
    except: return 0

print(f"Starting import of {len(monsters)} monsters...")
for i, m in enumerate(monsters):
    mname = m.get('name', 'Unknown')
    print(f"[{i+1}/{len(monsters)}] Uploading {mname}...")
    
    # Download image
    img_name = f"{mname}.gif"
    img_url = f"https://www.lcinfo.io/images/monsters/{img_name}"
    img_res = requests.get(img_url, headers={'User-Agent': 'Mozilla/5.0'})
    
    file_tuple = None
    if img_res.status_code == 200:
        file_tuple = ('image', (img_name, img_res.content, 'image/gif'))
    else:
        # Try .png
        img_name = f"{mname}.png"
        img_url = f"https://www.lcinfo.io/images/monsters/{img_name}"
        img_res = requests.get(img_url, headers={'User-Agent': 'Mozilla/5.0'})
        if img_res.status_code == 200:
            file_tuple = ('image', (img_name, img_res.content, 'image/png'))
            
    # Prepare data fields
    s = m.get('stats', {})
    data = {
        'npcid': int(m.get('npcid', 0)),
        'name': mname,
        'race': s.get('종족', ''),
        'size': s.get('크기', ''),
        'level': parse_num(s.get('레벨', '0')),
        'hp': parse_num(s.get('HP', '0')),
        'mp': parse_num(s.get('MP', '0')),
        'ac': parse_num(s.get('AC', '0')),
        'mr': parse_num(s.get('MR', '0')),
        'exp': parse_num(s.get('경험치', '0')),
        'alignment': parse_num(s.get('성향', '0')),
        'features': ', '.join(m.get('features', [])),
        'spawns': ', '.join(m.get('spawns', [])),
        'drops': ', '.join(m.get('drops', []))
    }
    
    files = [file_tuple] if file_tuple else []
    
    rec_res = requests.post(f'{pb_url}/api/collections/monsters/records', headers=headers, data=data, files=files)
    if rec_res.status_code not in [200, 201]:
        print(f"  -> Failed to upload {mname}: {rec_res.status_code} {rec_res.text}")
        
    time.sleep(0.05)

print("\nAll data imported successfully!")
