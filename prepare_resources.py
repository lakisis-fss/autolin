import requests
import os
import json

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

# 2. Get monster list to find file paths
print("Fetching monsters from PocketBase...")
res = requests.get(f'{pb_url}/api/collections/monsters/records?perPage=200', headers=headers)
data = res.json()
monsters = data.get('items', [])

target_dir = os.path.join(os.getcwd(), 'resources', 'targets')
if not os.path.exists(target_dir):
    os.makedirs(target_dir)

mapping = {}

for m in monsters:
    name = m.get('name')
    img_file = m.get('image')
    rec_id = m.get('id')
    col_id = m.get('collectionId')
    
    if img_file:
        # File path in pb_data/storage
        # Format: pb_data/storage/[col_id]/[rec_id]/[filename]
        local_path = os.path.join(os.getcwd(), 'pb_data', 'storage', col_id, rec_id, img_file)
        if os.path.exists(local_path):
            mapping[name] = local_path
            print(f"Found image for {name}: {local_path}")
        else:
            print(f"Warning: File not found for {name} at {local_path}")

with open('resources/monster_mapping.json', 'w', encoding='utf-8') as f:
    json.dump(mapping, f, ensure_ascii=False, indent=2)

print(f"Successfully mapped {len(mapping)} monsters.")
