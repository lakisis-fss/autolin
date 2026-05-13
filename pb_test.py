import requests
import json

base_url = 'http://127.0.0.1:8090'
auth_url = f'{base_url}/api/collections/_superusers/auth-with-password'

data = {
    'identity': 'admin@example.com',
    'password': 'Admin1234!!'
}
response = requests.post(auth_url, json=data)
if response.status_code != 200:
    print("Failed as superuser, trying admins (v0.22):")
    auth_url = f'{base_url}/api/admins/auth-with-password'
    response = requests.post(auth_url, json=data)

print("Status:", response.status_code)
print("Response:", response.text)
