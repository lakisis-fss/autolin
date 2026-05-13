import requests
from bs4 import BeautifulSoup
import json
import time
import re

def scrape_items():
    categories = ['weapon', 'armor', 'etc']
    all_items = []
    
    for cat in categories:
        page = 1
        print(f"Scraping category: {cat}...")
        while True:
            url = f'https://www.lcinfo.io/items?type={cat}&page={page}'
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # The subagent identified the grid structure.
            # Let's find all divs that look like item rows.
            # They are inside the overflow-x-auto container and have 'grid' class.
            container = soup.find('div', class_=lambda c: c and 'overflow-x-auto' in c and 'bg-card' in c)
            if not container:
                print(f"Container not found for {cat} at page {page}.")
                break
                
            # Item rows are usually direct children or nested within a wrapper div.
            # In the latest Next.js patterns, they might be in a div with grid-cols.
            rows = container.find_all('div', class_=lambda c: c and 'grid' in c and 'border-b' in c)
            
            if not rows:
                print(f"No more item rows found in category {cat} at page {page}.")
                break
                
            added_on_page = 0
            for row in rows:
                item_data = {'category': cat}
                
                # 1. Icon
                img_tag = row.find('img')
                if img_tag:
                    item_data['icon_url'] = img_tag.get('src')
                
                # 2. Name & Basic Info (First few columns)
                # Usually there's an <a> tag for the name
                name_link = row.find('a', href=lambda h: h and h.startswith('/items/'))
                if name_link:
                    item_data['name'] = name_link.get_text(strip=True)
                
                # Extract all text to find stats
                all_text = list(row.stripped_strings)
                
                # Match name-related info (Type, Material, Weight)
                # These are often near the name or in the same column
                for i, txt in enumerate(all_text):
                    if '재질:' in txt:
                        item_data['재질'] = txt.split('재질:')[-1].strip()
                    if '무게:' in txt:
                        item_data['무게'] = txt.split('무게:')[-1].strip()
                    # Type is usually the first text after name if not explicitly labeled
                
                # Handle category-specific columns
                # We can use the column index or search for numeric patterns
                if cat == 'weapon':
                    # Weapons have: [Icon] [Name/Info] [Damage] [Safety] [Options]
                    # Logic: find strings with "/" for damage, and "+" for safety
                    for txt in all_text:
                        if '/' in txt and any(c.isdigit() for c in txt):
                            item_data['타격치'] = txt
                        if '+' in txt and txt.strip().startswith('+'):
                            item_data['안전 강화'] = txt
                            
                elif cat == 'armor':
                    # Armors have: [Icon] [Name/Info] [AC] [Safety] [Options]
                    for txt in all_text:
                        if (txt.startswith('-') or txt.isdigit()) and len(txt) <= 3 and cat == 'armor':
                            # Likely AC if it's a small number or negative
                            # But be careful not to pick up safety.
                            if '+' not in txt:
                                item_data['방어력 (AC)'] = txt
                        if '+' in txt and txt.strip().startswith('+'):
                            item_data['안전 강화'] = txt
                
                # Generic options check (blue text usually)
                options_span = row.find('span', class_=lambda c: c and 'text-blue-400' in c)
                if options_span:
                    item_data['options'] = options_span.get_text(strip=True)
                else:
                    # Fallback: check all_text for anything that looks like an option
                    pass

                # Classes (often identified by icons or text)
                # If they are just text strings like "군주", "기사"
                classes = []
                for txt in all_text:
                    if txt in ['군주', '기사', '요정', '마법사', '다크엘프']:
                        classes.append(txt)
                if classes:
                    item_data['사용 가능 클래스'] = ', '.join(classes)

                if 'name' in item_data:
                    all_items.append(item_data)
                    added_on_page += 1
            
            print(f"  Page {page}: scraped {added_on_page} items.")
            if added_on_page == 0:
                break
                
            page += 1
            time.sleep(0.1)
            
    return all_items

if __name__ == '__main__':
    items = scrape_items()
    with open('items.json', 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"Successfully scraped {len(items)} items to items.json")
