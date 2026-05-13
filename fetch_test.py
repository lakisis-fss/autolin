import urllib.request
import re

url = 'https://www.lcinfo.io/monsters/45005'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
    
    # Extract monster name
    name_match = re.search(r'<h1[^>]*>([^<]+) 정보</h1>', html)
    if not name_match:
        name_match = re.search(r'<h2[^>]*>([^<]+)</h2>', html)
    
    print("Name:", name_match.group(1) if name_match else "Unknown")
    
    # Extract drops
    # It might be under "드랍 아이템"
    drops_part = html.split('드랍 아이템')[-1]
    # The drops are likely link texts
    # Let's find <a href="/items?...">...</a>
    drops = re.findall(r'<a[^>]+href="/items\?[^"]+"[^>]*>([^<]+)</a>', drops_part)
    print("Drops:", drops)

    # Extract spawn locations
    spawn_part = html.split('출현 장소')[-1].split('드랍 아이템')[0]
    spawns = re.findall(r'<a[^>]+href="/maps\?[^"]+"[^>]*>([^<]+)</a>', spawn_part)
    print("Spawns:", spawns)

except Exception as e:
    print(f"Error: {e}")
