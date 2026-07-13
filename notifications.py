import asyncio
import httpx
import random
from datetime import datetime
import os

ALL_PARKS = [
    "acad", "arch", "badl", "bibe", "bisc", "blca", "brca", "cany", "capk", "card",
    "cave", "chis", "choa", "cong", "crla", "cuva", "dena", "deso", "deva", "drto",
    "ever", "gate", "gett", "glac", "glba", "grca", "grte", "grvi", "grsm", "guco",
    "hale", "havo", "heho", "hosp", "isle", "jotree", "kena", "ketl", "king", "lavo",
    "lehe", "maca", "mami", "mavo", "mepo", "meve", "mint", "mora", "moun", "nace",
    "noca", "nope", "nori", "olym", "pais", "peco", "pefo", "pinn", "pisc", "pore",
    "reau", "redw", "romo", "sagu", "sasi", "seki", "shen", "tede", "teto", "thro",
    "voya", "waca", "whsa", "wica", "wotr", "yell", "yose", "zion"
]

ALL_CITIES = [
    "Denver", "Los Angeles", "San Francisco", "Seattle", "Portland",
    "Chicago", "New York", "Boston", "Miami", "Houston",
    "Phoenix", "Las Vegas", "Salt Lake City", "Albuquerque", "Santa Fe",
    "Austin", "Nashville", "Atlanta", "Washington DC", "Philadelphia",
    "San Diego", "Sacramento", "Eugene", "Bend", "Reno",
    "Boise", "Missoula", "Billings", "Rapid City", "Cheyenne",
    "Providence", "Hartford", "Burlington", "Montpelier", "Concord",
    "Manchester", "Albany", "Buffalo", "Rochester", "Pittsburgh",
    "Cleveland", "Detroit", "Milwaukee", "Minneapolis", "St Louis",
    "Kansas City", "Tulsa", "Oklahoma City", "Memphis", "New Orleans"
]

async def get_latest_nps_alerts() -> list:
    """Fetch latest NPS alerts from all parks"""
    api_key = os.getenv("NPS_API_KEY")
    if not api_key:
        print("⚠️ NPS_API_KEY not set")
        return []
    
    all_alerts = []
    url = "https://developer.nps.gov/api/v1/alerts"
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            tasks = [client.get(url, params={"parkCode": park_code, "api_key": api_key}) for park_code in ALL_PARKS]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, response in enumerate(responses):
                if isinstance(response, Exception):
                    continue
                try:
                    data = response.json()
                    if data.get("data"):
                        for alert in data["data"]:
                            all_alerts.append({
                                "type": "park_alert",
                                "park": ALL_PARKS[i].upper(),
                                "title": alert.get("title", "")[:70],
                                "description": alert.get("description", "")[:100],
                                "timestamp": datetime.now().isoformat(),
                                "icon": "🏞️"
                            })
                except Exception as e:
                    pass
    except Exception as e:
        print(f"❌ Error fetching NPS alerts: {e}")
    
    print(f"📍 Fetched {len(all_alerts)} park alerts")
    return sorted(all_alerts, key=lambda x: x["timestamp"], reverse=True)[:10]

async def get_top_weather_updates() -> list:
    """Fetch weather for shuffled random cities"""
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        print("⚠️ OPENWEATHER_API_KEY not set")
        return []
    
    if api_key == "your_openweather_key_here":
        print("⚠️ OPENWEATHER_API_KEY is set to placeholder")
        print("   Get a free key at: https://openweathermap.org/api")
        return []
    
    # Shuffle cities to get random ones each time
    shuffled_cities = ALL_CITIES.copy()
    random.shuffle(shuffled_cities)
    selected_cities = shuffled_cities[:20]  # Pick 20 random cities
    
    all_weather = []
    url = "https://api.openweathermap.org/data/2.5/weather"
    
    print(f"🌤️ Fetching weather for {len(selected_cities)} random cities...")
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            for location in selected_cities:
                try:
                    resp = await client.get(url, params={"q": location, "units": "imperial", "appid": api_key})
                    data = resp.json()
                    
                    if resp.status_code == 200:
                        temp = data["main"]["temp"]
                        condition = data["weather"][0].get("main", "")
                        desc = data["weather"][0].get("description", "").capitalize()
                        humidity = data["main"].get("humidity", 0)
                        wind = data["wind"].get("speed", 0)
                        
                        icon_map = {
                            "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️", 
                            "Snow": "❄️", "Thunderstorm": "⛈️", "Drizzle": "🌦️",
                            "Mist": "🌫️", "Fog": "🌫️"
                        }
                        icon = icon_map.get(condition, "🌡️")
                        
                        all_weather.append({
                            "type": "weather_alert",
                            "location": location,
                            "temp": f"{int(temp)}°F",
                            "description": desc,
                            "condition": condition,
                            "humidity": f"{humidity}%",
                            "wind": f"{int(wind)} mph",
                            "icon": icon,
                            "timestamp": datetime.now().isoformat()
                        })
                    else:
                        if resp.status_code == 401:
                            print(f"❌ API KEY ERROR: Invalid OPENWEATHER_API_KEY")
                            break
                except Exception as e:
                    pass
    except Exception as e:
        print(f"❌ Error fetching weather: {e}")
    
    print(f"🌡️ Fetched {len(all_weather)} weather updates")
    return sorted(all_weather, key=lambda x: x["timestamp"], reverse=True)[:10]

async def fetch_global_notifications():
    """Fetch global latest alerts and random weather"""
    alerts, weather = await asyncio.gather(
        get_latest_nps_alerts(),
        get_top_weather_updates()
    )
    
    return {
        "alerts": alerts,
        "weather": weather,
        "timestamp": datetime.now().isoformat()
    }
