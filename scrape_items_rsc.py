import urllib.request
import json
import time
import os

def get_page_rsc(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'rsc': '1'})
    try:
        response = urllib.request.urlopen(req)
        return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

def extract_item_objects(data):
    items = []
    idx = 0
    search_str = '{"item":'
    
    while True:
        idx = data.find(search_str, idx)
        if idx == -1:
            break
        
        # We found '{"item":'. The object starts at '{"item_id"' or similar.
        # Let's find the inner JSON object
        start = data.find('{', idx + 7) # Look for the '{' after 'item":'
        if start == -1:
            break
            
        end = start
        brace_count = 0
        for i in range(start, len(data)):
            if data[i] == '{':
                brace_count += 1
            elif data[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break
        
        obj_str = data[start:end]
        try:
            item = json.loads(obj_str)
            items.append(item)
        except:
            pass
        
        idx = end
    return items

def main():
    categories = ['weapon', 'armor', 'etc']
    all_items = []
    seen_ids = set()
    
    for cat in categories:
        page = 1
        print(f"Scraping category: {cat}...")
        while True:
            url = f'https://www.lcinfo.io/items?type={cat}&page={page}'
            data = get_page_rsc(url)
            if not data:
                break
                
            page_items = extract_item_objects(data)
            if not page_items:
                break
                
            added = 0
            for itm in page_items:
                # Add category info
                itm['category'] = cat
                if itm['item_id'] not in seen_ids:
                    all_items.append(itm)
                    seen_ids.add(itm['item_id'])
                    added += 1
            
            print(f"  Page {page}: found {len(page_items)} items, {added} new.")
            if added == 0:
                # Assuming if no new items on a page, we've hit the end or duplicate
                break
                
            page += 1
            time.sleep(0.1)

    print(f"\nTotal unique items found: {len(all_items)}")
    
    with open('items_db.json', 'w', encoding='utf-8') as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    print("Saved all items to items_db.json")

if __name__ == '__main__':
    main()
