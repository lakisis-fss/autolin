import requests
from bs4 import BeautifulSoup

url = 'https://www.lcinfo.io/items?type=etc&page=1'
headers = {'User-Agent': 'Mozilla/5.0'}
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

# Find 등잔
item_name = "등잔"
item_row = None
for row in soup.find_all('div', class_=lambda c: c and 'grid' in c):
    if item_name in row.get_text():
        item_row = row
        break

if item_row:
    img = item_row.find('img')
    if img:
        print(f"등잔 Icon Src: {img.get('src')}")
    else:
        print("Icon not found for 등잔")
else:
    print("Row not found for 등잔")

# Find 빨간 물약
item_name = "빨간 물약"
item_row = None
for row in soup.find_all('div', class_=lambda c: c and 'grid' in c):
    if item_name in row.get_text():
        item_row = row
        break
if item_row:
    img = item_row.find('img')
    if img:
        print(f"빨간 물약 Icon Src: {img.get('src')}")
