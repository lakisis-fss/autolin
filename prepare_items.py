import json
import os
import requests

def download_item_icons():
    os.makedirs('resources/item_icons', exist_ok=True)
    
    # Load items from DB
    try:
        with open('items_db.json', 'r', encoding='utf-8') as f:
            items = json.load(f)
    except:
        print("items_db.json not found.")
        return

    # Target items to track (Items that drop on ground)
    targets = ["아데나", "빨간 물약", "주홍 물약", "맑은 물약", "초록 물약", "용기의 물약", "갑옷 마법 주문서", "무기 마법 주문서"]
    
    mapping = {}
    for item in items:
        name = item.get('item_name')
        if name in targets:
            icon_id = item.get('item_icon_id')
            if icon_id:
                url = f"https://www.lcinfo.io/images/item_icons/{icon_id}.png"
                path = f"resources/item_icons/{name}.png"
                
                if not os.path.exists(path):
                    print(f"Downloading {name} icon...")
                    try:
                        resp = requests.get(url)
                        if resp.status_code == 200:
                            with open(path, 'wb') as f_img:
                                f_img.write(resp.content)
                            mapping[name] = path
                    except:
                        pass
                else:
                    mapping[name] = path

    with open('resources/item_mapping.json', 'w', encoding='utf-8') as f_map:
        json.dump(mapping, f_map, ensure_ascii=False, indent=2)
    print("Item mapping saved to resources/item_mapping.json")

if __name__ == "__main__":
    download_item_icons()
