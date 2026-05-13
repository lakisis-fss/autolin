import requests
from bs4 import BeautifulSoup

url = 'https://www.lcinfo.io/monsters?page=1'
headers = {'User-Agent': 'Mozilla/5.0'}
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

monster_links = soup.find_all('a', href=lambda href: href and href.startswith('/monsters/') and '?' not in href)

for link in monster_links[:5]:
    img = link.find('img')
    if img:
        print(f"ID: {link['href'].split('/')[-1]}, Img Src: {img.get('src')}")
