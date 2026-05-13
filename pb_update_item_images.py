import requests
import json
import time
import io

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

# 2. Load Mapping
try:
    with open('item_image_map.json', 'r', encoding='utf-8') as f:
        image_map = json.load(f)
except Exception as e:
    print("Could not read item_image_map.json:", e)
    exit(1)

# 3. Fetch Items in PB
print("Fetching existing item records from PocketBase...")
# We might have more than 200, so let's use a large perPage or loop
all_records = []
page = 1
while True:
    res = requests.get(f'{pb_url}/api/collections/items/records?perPage=200&page={page}', headers=headers)
    data = res.json()
    items = data.get('items', [])
    if not items:
        break
    all_records.extend(items)
    if len(all_records) >= data.get('totalItems', 0):
        break
    page += 1

print(f"Total records in PB: {len(all_records)}")

# 4. Update Images
total_updated = 0
for i, rec in enumerate(all_records):
    name = rec.get('name')
    rec_id = rec.get('id')
    
    if name in image_map:
        img_url = image_map[name]
        print(f"[{i+1}/{len(all_records)}] Updating image for {name} ({img_url})...")
        
        # Download image
        try:
            img_res = requests.get(img_url, headers={'User-Agent': 'Mozilla/5.0'})
            if img_res.status_code == 200:
                # Prepare file for upload
                ext = img_url.split('.')[-1].split('?')[0]
                filename = f"{name}.{ext}"
                file_tuple = ('image', (filename, img_res.content, f"image/{ext}"))
                
                # Update record
                update_res = requests.patch(
                    f'{pb_url}/api/collections/items/records/{rec_id}',
                    headers=headers,
                    files=[file_tuple]
                )
                if update_res.status_code in [200, 201]:
                    total_updated += 1
                else:
                    print(f"  -> Failed to update {name}: {update_res.status_code} {update_res.text}")
            else:
                print(f"  -> Could not download image for {name}: {img_res.status_code}")
        except Exception as e:
            print(f"  -> Error processing {name}: {e}")
            
    # Small delay to avoid hammering
    time.sleep(0.05)

print(f"\nSuccessfully updated {total_updated} item images.")
