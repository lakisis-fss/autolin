import urllib.request
import json
import time

def get_page_rsc(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'rsc': '1'})
    try:
        response = urllib.request.urlopen(req)
        return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

def extract_monster_objects(data):
    monsters = []
    idx = 0
    search_str = '{"npcid":'
    
    while True:
        idx = data.find(search_str, idx)
        if idx == -1:
            break
        
        # We found '{"npcid":'. The object starts exactly at idx!
        start = idx
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
            monster = json.loads(obj_str)
            monsters.append(monster)
        except json.JSONDecodeError:
            pass
        
        idx = end
    return monsters

def main():
    all_npcids = []
    page = 1
    
    print("Fetching monster list pages...")
    while True:
        url = f'https://www.lcinfo.io/monsters?page={page}'
        data = get_page_rsc(url)
        if not data:
            break
            
        page_monsters = extract_monster_objects(data)
        if not page_monsters:
            break
            
        added = 0
        for m in page_monsters:
            if m['npcid'] not in all_npcids:
                all_npcids.append(m['npcid'])
                added += 1
                
        print(f"Page {page}: found {len(page_monsters)} monsters, {added} new.")
        if added == 0:
            break
            
        page += 1
        time.sleep(0.1)

    print(f"\nTotal unique monsters found: {len(all_npcids)}")
    print("Fetching detailed information for each monster...")
    
    detailed_monsters = []
    
    for i, npcid in enumerate(all_npcids):
        url = f'https://www.lcinfo.io/monsters/{npcid}'
        data = get_page_rsc(url)
        m_objs = extract_monster_objects(data)
        
        if m_objs:
            # Sort by number of keys or just pick the first valid one 
            # Usually the detailed page has the full monster as the first match
            # But just in case, we pick the one with 'drops' or largest
            best_m = max(m_objs, key=lambda x: len(str(x)))
            detailed_monsters.append(best_m)
            print(f"[{i+1}/{len(all_npcids)}] NPCID: {npcid} (Drops: {len(best_m.get('drops', []))}) - {best_m.get('name', 'Unknown')}")
        else:
            print(f"[{i+1}/{len(all_npcids)}] Failed to parse detailed info for NPCID: {npcid}")
        
        time.sleep(0.05)
        
    with open('monsters_db.json', 'w', encoding='utf-8') as f:
        json.dump(detailed_monsters, f, ensure_ascii=False, indent=2)
        
    print("\nSuccessfully saved all monster data to monsters_db.json!")

if __name__ == '__main__':
    main()
