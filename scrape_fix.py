import requests
from bs4 import BeautifulSoup
import json
import csv

def parse_all_pages():
    url = f'https://www.lcinfo.io/monsters?page=1'
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    monster_links = soup.find_all('a', href=lambda href: href and href.startswith('/monsters/') and '?' not in href)
    
    seen_ids = set()
    for link in monster_links:
        href = link['href']
        npcid = href.split('/')[-1]
        if not npcid.isdigit(): continue
        
        if npcid in seen_ids:
            continue
            
        container = link.find_parent('div', class_=lambda c: c and 'rounded-xl' in c and 'bg-card/30' in c)
        if not container:
            continue
            
        # Debug printing links in container
        all_child_links = container.find_all('a')
        texts = [a.get_text(strip=True) for a in all_child_links]
        print(f"ID: {npcid}")
        print("Link texts:", texts)
        
        # Proper name extraction: pick the string that doesn't equal "Loading.." and doesn't belong to a sub-category map/item link.
        # Find all <a> tags that point to /monsters/npcid
        name_links = container.find_all('a', href=href)
        name = "Unknown"
        for nl in name_links:
            t = nl.get_text(strip=True)
            if t and t != "Loading..":
                name = t
                break
                
        print("Resolved Name:", name)
        
        seen_ids.add(npcid)
        if len(seen_ids) >= 3:
            break

parse_all_pages()
