import requests
import random

# 랜덤 포켓몬 가져오기
pokemon_id = random.randint(1, 151)
url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}"
response = requests.get(url)
data = response.json()

print(f"👾 포켓몬: {data['name']}")
print(f"🖼️ 이미지: {data['sprites']['front_default']}")
