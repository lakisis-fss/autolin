import requests
from bs4 import BeautifulSoup
import json
import csv
import time

def parse_all_pages():
    all_monsters = []
    seen_ids = set()
    page = 1
    
    while True:
        url = f'https://www.lcinfo.io/monsters?page={page}'
        headers = {'User-Agent': 'Mozilla/5.0'}
        print(f"Fetching page {page}...")
        response = requests.get(url, headers=headers)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        monster_links = soup.find_all('a', href=lambda href: href and href.startswith('/monsters/') and '?' not in href)
        
        if not monster_links:
            break
            
        added = 0
        for link in monster_links:
            href = link['href']
            npcid = href.split('/')[-1]
            if not npcid.isdigit(): continue
            
            if npcid in seen_ids:
                continue
            
            container = link.find_parent('div', class_=lambda c: c and 'rounded-xl' in c and 'bg-card/30' in c)
            if not container:
                continue
            
            # Find name specifically ignoring "Loading.." alt text
            name_links = container.find_all('a', href=href)
            name = "Unknown"
            for nl in name_links:
                t = nl.get_text(strip=True)
                if t and t != "Loading..":
                    name = t
                    break
            
            monster_data = {
                'npcid': int(npcid),
                'name': name,
                'stats': {},
                'features': [],
                'spawns': [],
                'drops': []
            }
            
            text_blocks = list(container.stripped_strings)
            for i, text in enumerate(text_blocks):
                if text in ['종족', '크기', '레벨', 'HP', 'MP', 'AC', 'MR', '경험치', '성향']:
                    if i + 1 < len(text_blocks):
                        monster_data['stats'][text] = text_blocks[i+1]
                
            boxes = container.find_all('div', class_=lambda c: c and 'min-h-[80px]' in c)
            if len(boxes) >= 3:
                # Features
                feature_spans = boxes[0].find_all('span', class_=lambda c: c and not 'text-muted-foreground' in c and not 'font-bold' in c)
                for f_span in feature_spans:
                    txt = f_span.get_text(strip=True)
                    if txt and txt != '-' and ':' in txt:
                        monster_data['features'].append(txt)
                    elif txt and txt != '-' and len(txt) > 2:
                        monster_data['features'].append(txt)
                monster_data['features'] = list(set([f for f in monster_data['features'] if f.strip() not in ['-', ',']]))

                # Spawns
                spawn_links = boxes[1].find_all('a', href=lambda h: h and '/maps' in h)
                monster_data['spawns'] = [a.get_text(strip=True) for a in spawn_links]
                
                # Drops
                drop_links = boxes[2].find_all('a', href=lambda h: h and '/items' in h)
                monster_data['drops'] = [a.get_text(strip=True) for a in drop_links]
                
            all_monsters.append(monster_data)
            seen_ids.add(npcid)
            added += 1
            
        print(f"Page {page} added {added} monsters.")
        if added == 0:
            break
            
        page += 1
        time.sleep(0.1)
        
    return all_monsters

def save_data(monsters):
    # Save as JSON
    with open('monsters.json', 'w', encoding='utf-8') as f:
        json.dump(monsters, f, ensure_ascii=False, indent=2)
        
    # Save as CSV
    with open('monsters.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        headers = ['NPC_ID', '이름', '종족', '크기', '레벨', 'HP', 'MP', 'AC', 'MR', '경험치', '성향', '특징', '출현장소', '드랍아이템']
        writer.writerow(headers)
        
        for m in monsters:
            s = m['stats']
            writer.writerow([
                m['npcid'],
                m['name'],
                s.get('종족', ''),
                s.get('크기', ''),
                s.get('레벨', ''),
                s.get('HP', ''),
                s.get('MP', ''),
                s.get('AC', ''),
                s.get('MR', ''),
                s.get('경험치', ''),
                s.get('성향', ''),
                ', '.join(m['features']),
                ', '.join(m['spawns']),
                ', '.join(m['drops'])
            ])
            
    print(f"\nSuccessfully saved {len(monsters)} monsters to monsters.json and monsters.csv")

if __name__ == '__main__':
    monsters = parse_all_pages()
    save_data(monsters)
