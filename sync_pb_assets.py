import requests
import os
import json

pb_url = 'http://127.0.0.1:8090'
target_dir = 'resources/targets'
os.makedirs(target_dir, exist_ok=True)

def sync_monsters():
    print("Authenticating with PocketBase...")
    try:
        # Auth as superuser
        auth_res = requests.post(
            f'{pb_url}/api/collections/_superusers/auth-with-password', 
            json={'identity': 'admin@example.com', 'password': 'Admin1234!!'}
        )
        auth_data = auth_res.json()
        token = auth_data.get('token')
        
        if not token:
            print("Authentication failed.")
            return False
            
        headers = {'Authorization': token}
        
        # 2. Get all monsters
        print("Fetching monster records...")
        res = requests.get(f'{pb_url}/api/collections/monsters/records?perPage=500', headers=headers)
        data = res.json()
        
        items = data.get('items', [])
        print(f"Found {len(items)} records in PocketBase.")
        
        mapping = {}
        
        for item in items:
            name = item.get('name')
            rec_id = item.get('id')
            collection_id = item.get('collectionId')
            img_file = item.get('thumbnail') or item.get('image')
            
            if not img_file:
                continue
                
            file_url = f"{pb_url}/api/files/{collection_id}/{rec_id}/{img_file}"
            local_path = os.path.join(target_dir, f"{name}.png")
            
            # Download if not exists
            if not os.path.exists(local_path):
                print(f"Downloading {name}...")
                img_res = requests.get(file_url, headers=headers)
                with open(local_path, 'wb') as f:
                    f.write(img_res.content)
            
            mapping[name] = local_path
            
        # Save mapping
        with open('resources/monster_mapping.json', 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
            
        print(f"Successfully synced {len(mapping)} assets.")
        return True
    except Exception as e:
        print(f"Sync error: {e}")
        return False

if __name__ == "__main__":
    sync_monsters()
