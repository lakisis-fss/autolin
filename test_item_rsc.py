import urllib.request
import json

url = 'https://www.lcinfo.io/items?type=weapon&page=1'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'rsc': '1'})
try:
    response = urllib.request.urlopen(req)
    data = response.read().decode('utf-8')
    with open('item_rsc.txt', 'w', encoding='utf-8') as f:
        f.write(data)
    print("Saved RSC data to item_rsc.txt")
    print("Does it contain '오크족 단검'?", '오크족 단검' in data)
except Exception as e:
    print(f"Error: {e}")
