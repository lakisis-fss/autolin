import requests
from bs4 import BeautifulSoup
import json

def parse_page(page_num):
    url = f'https://www.lcinfo.io/monsters?page={page_num}'
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Each monster is in a div with a specific structure.
    # The parent container usually has class "space-y-4" and contains a list of monster blocks.
    # We can look for links that start with /monsters/[id]
    
    monsters = []
    
    # Find all monster blocks. Usually they are flex containers holding an image and info.
    # A reliable way is to find all monster names, which are <a> tags to /monsters/npcid
    monster_links = soup.find_all('a', href=lambda href: href and href.startswith('/monsters/') and '?' not in href)
    
    # We will iterate over unique IDs and grab their parent containers
    seen_ids = set()
    for link in monster_links:
        href = link['href']
        npcid = href.split('/')[-1]
        
        if npcid in seen_ids:
            continue
        seen_ids.add(npcid)
        
        # Traverse up to find the main container for this monster
        container = link.find_parent('div', class_=lambda c: c and 'rounded-xl' in c and 'bg-card/30' in c)
        if not container:
            continue
            
        name = link.get_text(strip=True)
        
        monster_data = {
            'npcid': int(npcid),
            'name': name,
            'stats': {},
            'features': [],
            'spawns': [],
            'drops': []
        }
        
        # Extract stats: they look like pairs of label and value
        # like "종족", "-", "레벨", "1", "HP", "20"
        stat_labels = container.find_all('span', class_=lambda c: c and 'text-muted-foreground' in c and 'font-medium' in c)
        # However, they might be structured distinctly. Let's just grab all texts in the grid
        # Actually, simpler:
        text_blocks = list(container.stripped_strings)
        
        for i, text in enumerate(text_blocks):
            if text in ['종족', '크기', '레벨', 'HP', 'MP', 'AC', 'MR', '경험치', '성향']:
                if i + 1 < len(text_blocks):
                    monster_data['stats'][text] = text_blocks[i+1]
            
            elif text == '특징':
                # Next strings until '출현 장소' are features
                pass
            
        # For features, spawns, drops, better to find the 3 boxes
        boxes = container.find_all('div', class_=lambda c: c and 'min-h-[80px]' in c)
        if len(boxes) >= 3:
            # Features
            features_box = boxes[0]
            feature_spans = features_box.find_all('span', class_=lambda c: c and not 'text-muted-foreground' in c and not 'font-bold' in c)
            for f_span in feature_spans:
                txt = f_span.get_text(strip=True)
                if txt and txt != '-' and ':' in txt: # like "약점: 불"
                    monster_data['features'].append(txt)
                elif txt and txt != '-' and len(txt) > 2: # "동족 인식", "테이밍 가능"
                    monster_data['features'].append(txt)
            
            # Remove duplicates in features caused by nested spans
            monster_data['features'] = list(set([f for f in monster_data['features'] if f.strip() != '-' and f.strip() != ',']))

            # Spawns
            spawns_box = boxes[1]
            spawn_links = spawns_box.find_all('a', href=lambda h: h and '/maps' in h)
            monster_data['spawns'] = [a.get_text(strip=True) for a in spawn_links]
            
            # Drops
            drops_box = boxes[2]
            drop_links = drops_box.find_all('a', href=lambda h: h and '/items' in h)
            monster_data['drops'] = [a.get_text(strip=True) for a in drop_links]
            
        monsters.append(monster_data)
        
    return monsters

print(json.dumps(parse_page(1)[:2], ensure_ascii=False, indent=2))
