import os
import httpx

# 🛠️ TOOL 1: NPS Alerts
async def get_park_alerts(park_code: str) -> str:
    api_key = os.getenv("NPS_API_KEY")
    if not api_key:
        return "NPS API Key missing."
    url = f"https://developer.nps.gov/api/v1/alerts?parkCode={park_code}&api_key={api_key}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            data = resp.json()
            if not data.get("data"):
                return f"No active alerts for {park_code} right now."
            alerts = [item["title"] for item in data["data"][:2]]
            return f"Active alerts for {park_code}: {', '.join(alerts)}"
    except Exception as e:
        return f"Error fetching NPS data: {str(e)}"

# 🛠️ TOOL 2: Weather
async def get_weather(location: str) -> str:
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key or api_key == "your_openweather_key_here":
        return "OpenWeather API Key is missing or using placeholder text."
    
    url = "https://api.openweathermap.org/data/2.5/weather"
    query_params = {
        "q": location,
        "units": "imperial",
        "appid": api_key
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=query_params)
            data = resp.json()
            if resp.status_code != 200:
                return f"Could not find weather for {location}. API response: {data.get('message', 'Unknown error')}"
            temp = data["main"]["temp"]
            desc = data["weather"][0]["description"]
            return f"Current weather in {location}: {temp}°F and {desc}."
    except Exception as e:
        return f"Error fetching weather data: {str(e)}"

# 🛠️ TOOL 3: Travel Recommendations (OSRM + Nominatim)
async def get_travel_recommendations(origin: str, destination: str) -> str:
    try:
        async with httpx.AsyncClient() as client:
            geocode_url = "https://nominatim.openstreetmap.org/search"
            
            # Get origin coordinates
            origin_resp = await client.get(geocode_url, params={
                "q": origin,
                "format": "json",
                "limit": 1
            })
            origin_data = origin_resp.json()
            if not origin_data:
                return f"Could not find location: {origin}"
            
            origin_lat = float(origin_data[0]["lat"])
            origin_lon = float(origin_data[0]["lon"])
            
            # Get destination coordinates
            dest_resp = await client.get(geocode_url, params={
                "q": destination,
                "format": "json",
                "limit": 1
            })
            dest_data = dest_resp.json()
            if not dest_data:
                return f"Could not find location: {destination}"
            
            dest_lat = float(dest_data[0]["lat"])
            dest_lon = float(dest_data[0]["lon"])
            
            # Get route from OSRM
            osrm_url = f"https://router.project-osrm.org/route/v1/driving/{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
            route_resp = await client.get(osrm_url)
            route_data = route_resp.json()
            
            if not route_data.get("routes"):
                return f"No route found from {origin} to {destination}."
            
            distance_km = route_data["routes"][0]["distance"] / 1000
            duration_hours = route_data["routes"][0]["duration"] / 3600
            
            if distance_km > 800:
                return f"{origin} to {destination}: {distance_km:.0f}km ({duration_hours:.1f}h). Fly from {origin} to {destination}."
            elif distance_km > 300:
                return f"{distance_km:.0f}km ({duration_hours:.1f}h). Consider flying or taking a train."
            elif distance_km > 100:
                return f"{distance_km:.0f}km ({duration_hours:.1f}h). Rent a car or take a bus."
            else:
                return f"{distance_km:.0f}km ({duration_hours:.1f}h). Car rental or rideshare recommended."
    
    except Exception as e:
        return f"Error fetching travel data: {str(e)}"
