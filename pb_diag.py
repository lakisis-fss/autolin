import requests

pb_url = 'http://127.0.0.1:8090'

# 1. Auth as superuser
auth_res = requests.post(f'{pb_url}/api/collections/_superusers/auth-with-password', json={
    'identity': 'admin@example.com',
    'password': 'Admin1234!!'
})

if auth_res.status_code != 200:
    print("Auth Failed:", auth_res.text)
    exit(1)

token = auth_res.json()['token']
headers = {'Authorization': token}

# 2. Get monsters collection record count
res = requests.get(f'{pb_url}/api/collections/monsters/records?perPage=1', headers=headers)
if res.status_code == 200:
    data = res.json()
    print(f"Total Items: {data.get('totalItems')}")
    if data.get('items'):
        print("First Item Sample:", data['items'][0]['name'])
else:
    print("Error Fetching Records:", res.status_code, res.text)

# 3. List all collections to verify name
col_res = requests.get(f'{pb_url}/api/collections?perPage=50', headers=headers)
if col_res.status_code == 200:
    cols = col_res.json().get('items', [])
    print("Available Collections:", [c['name'] for c in cols])
else:
    print("Error Fetching Collections:", col_res.status_code, col_res.text)
