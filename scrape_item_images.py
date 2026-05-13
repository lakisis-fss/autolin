import requests
from bs4 import BeautifulSoup
import json
import time

def scrape_item_images():
    categories = ['weapon', 'armor', 'etc']
    image_map = {} # name -> icon_url
    
    for cat in categories:
        page = 1
        print(f"Scraping image map for category: {cat}...")
        while True:
            url = f'https://www.lcinfo.io/items?type={cat}&page={page}'
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Use the correct selectors found during inspection
            # Based on the subagent's result: item rows are in a <tr> or grid <div>
            # Let's find rows that have an <img> and a name <a>
            rows = []
            
            # Try <tr> first (Next.js sometimes renders tables)
            rows = soup.find_all('tr')
            if not rows:
                # Fallback to grid divs
                rows = soup.find_all('div', class_=lambda c: c and 'grid' in c and 'border-b' in c)
            
            if not rows:
                print(f"No more rows found in category {cat} at page {page}.")
                break
                
            added_on_page = 0
            for row in rows:
                img_tag = row.find('img', src=lambda s: s and ('assets/items/' in s or 'item_icons/' in s))
                name_link = row.find('a', href=lambda h: h and h.startswith('/items/'))
                
                if img_tag and name_link:
                    name = name_link.get_text(strip=True)
                    icon_url = img_tag.get('src')
                    if not icon_url.startswith('http'):
                        icon_url = f"https://www.lcinfo.io{icon_url}"
                    
                    if name not in image_map:
                        image_map[name] = icon_url
                        added_on_page += 1
            
            print(f"  Page {page}: found {added_on_page} new image mappings.")
            if added_on_page == 0 and page > 1:
                # If we've reached a page with no new mappings, we might be at the end.
                # However, some pages might have only duplicates if the site structure is weird.
                # But typically 0 new on page 2+ means end.
                # Let's check for "Next" button instead for safety.
                next_btn = soup.find('a', string=re.compile('Next|다음', re.I))
                if not next_btn:
                    # break
                    pass
            
            # Check for a total of 384 items or max pages
            if page > 50: # Safety break
                break
                
            # If we found 0 mappings on Page 1, something is wrong with selectors
            if page == 1 and added_on_page == 0:
                # Try a broader search for name links
                print("Broadening search for 1st page...")
                all_links = soup.find_all('a', href=lambda h: h and h.startswith('/items/'))
                for link in all_links:
                    name = link.get_text(strip=True)
                    if name:
                        # Find closest img
                        p_row = link.find_parent(['tr', 'div'])
                        img = p_row.find('img') if p_row else None
                        if img and name not in image_map:
                            src = img.get('src')
                            if 'item' in src:
                                image_map[name] = f"https://www.lcinfo.io{src}" if not src.startswith('http') else src
                                added_on_page += 1
            
            if added_on_page == 0:
                break

            page += 1
            time.sleep(0.1)
            
    return image_map

import re
if __name__ == '__main__':
    mapping = scrape_item_images()
    with open('item_image_map.json', 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"Successfully mapped {len(mapping)} item images to item_image_map.json")
