import requests

WEATHER_API_KEY = "YOUR_KEY"
city = "Seoul"

url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=kr"
response = requests.get(url)
data = response.json()

print(f"🌡️ 서울 기온: {data['main']['temp']}°C")
print(f"☁️ 날씨: {data['weather'][0]['description']}")
