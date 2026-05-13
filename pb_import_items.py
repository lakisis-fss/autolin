import requests
import json
import time

pb_url = 'http://127.0.0.1:8090'

# 1. Auth as superuser
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
col_res = requests.get(f'{pb_url}/api/collections/items', headers=headers)
if col_res.status_code == 404:
    print("Creating collection 'items'...")
    col_def = {
        "name": "items",
        "type": "base",
        "fields": [
            {"name": "item_id", "type": "number"},
            {"name": "name", "type": "text"},
            {"name": "category", "type": "text"},
            {"name": "item_type", "type": "text"},
            {"name": "material", "type": "text"},
            {"name": "weight", "type": "number"},
            {"name": "trade", "type": "bool"},
            {"name": "cant_delete", "type": "bool"},
            {"name": "dmg_small", "type": "number"},
            {"name": "dmg_large", "type": "number"},
            {"name": "ac", "type": "number"},
            {"name": "min_lvl", "type": "number"},
            {"name": "max_lvl", "type": "number"},
            {"name": "description", "type": "text"},
            {"name": "image", "type": "file", "maxSelect": 1, "maxSize": 5242880}
        ]
    }
    create_res = requests.post(f'{pb_url}/api/collections', headers=headers, json=col_def)
    if create_res.status_code not in [200, 201]:
        print("Failed to create collection:", create_res.text)
        exit(1)
    print("Collection created successfully!")
else:
    print("Collection 'items' already exists.")

# 3. Import data
try:
    with open('items_db.json', 'r', encoding='utf-8') as f:
        items = json.load(f)
except Exception as e:
    print("Could not read items_db.json:", e)
    exit(1)

def parse_num(val):
    if val is None or val == '': return 0
    try: return float(val)
    except: return 0

print(f"Starting import of {len(items)} items...")
for i, itm in enumerate(items):
    iname = itm.get('name', 'Unknown')
    print(f"[{i+1}/{len(items)}] Uploading {iname}...")
    
    # Download image
    # Trying common extensions
    img_res = None
    best_img_name = f"{iname}.png"
    for ext in ['.png', '.gif']:
        img_url = f"https://www.lcinfo.io/images/items/{iname}{ext}"
        r = requests.get(img_url, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            img_res = r
            best_img_name = f"{iname}{ext}"
            break
            
    file_tuple = None
    if img_res:
        file_tuple = ('image', (best_img_name, img_res.content, f"image/{best_img_name.split('.')[-1]}"))
        
    data = {
        'item_id': parse_num(itm.get('item_id', 0)),
        'name': iname,
        'category': itm.get('category', 'etc'),
        'item_type': itm.get('item_type', ''),
        'material': itm.get('material', ''),
        'weight': parse_num(itm.get('weight', 0)) / 1000.0, # Normalizing based on common site scaling
        'trade': bool(itm.get('trade', 1)),
        'cant_delete': bool(itm.get('cant_delete', 0)),
        'dmg_small': parse_num(itm.get('dmg_small', 0)),
        'dmg_large': parse_num(itm.get('dmg_large', 0)),
        'ac': parse_num(itm.get('ac', 0)),
        'min_lvl': parse_num(itm.get('min_lvl', 0)),
        'max_lvl': parse_num(itm.get('max_lvl', 0)),
        'description': itm.get('itemdesc_id', '') # Fallback to desc id if text missing
    }
    
    files = [file_tuple] if file_tuple else []
    
    rec_res = requests.post(f'{pb_url}/api/collections/items/records', headers=headers, data=data, files=files)
    if rec_res.status_code not in [200, 201]:
        print(f"  -> Failed to upload {iname}: {rec_res.status_code} {rec_res.text}")
        
    time.sleep(0.05)

print("\nItem data import completed!")
