import os
import json
import asyncio
import httpx
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
from groq import AsyncGroq
from notifications import fetch_global_notifications
from text_processing import normalize_user_input, humanize_response, verbalize_entities
from tools import get_park_alerts, get_weather, get_travel_recommendations

load_dotenv()

# ✅ Define lifespan FIRST
@asynccontextmanager
async def lifespan(app: FastAPI):
    global notifications_cache
    notifications_cache = await fetch_global_notifications()
    print("✅ Notifications loaded")
    yield
    print("🛑 Shutting down...")

# ✅ Create app ONCE with lifespan
app = FastAPI(title="Backcountry Route Coordinator", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

deepgram = DeepgramClient(os.getenv("DEEPGRAM_API_KEY"))
llm = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

chat_histories = {}
active_utterances = {}
notifications_cache = {"alerts": [], "weather": [], "timestamp": None}

# Tool Schema
agent_tools = [
    {"type": "function", "function": {"name": "get_park_alerts", "description": "Get real-time alerts for a US National Park.", "parameters": {"type": "object", "properties": {"park_code": {"type": "string", "description": "4-letter park code (zion, grca, yose, etc)."}}, "required": ["park_code"]}}},
    {"type": "function", "function": {"name": "get_weather", "description": "Get current weather for a location.", "parameters": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]}}},
    {"type": "function", "function": {"name": "get_travel_recommendations", "description": "Get realistic travel recommendations and distance between two cities.", "parameters": {"type": "object", "properties": {"origin": {"type": "string"}, "destination": {"type": "string"}}, "required": ["origin", "destination"]}}},
    {"type": "function", "function": {"name": "get_park_pricing", "description": "Get park entrance fees.", "parameters": {"type": "object", "properties": {"park_name": {"type": "string"}}, "required": ["park_name"]}}},
    {"type": "function", "function": {"name": "get_parking_info", "description": "Get parking info.", "parameters": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]}}},
    {"type": "function", "function": {"name": "get_travel_itinerary", "description": "Create itineraries.", "parameters": {"type": "object", "properties": {"trip_description": {"type": "string"}}, "required": ["trip_description"]}}}
]

async def get_park_pricing(park_name: str) -> str:
    return f"For {park_name}, typical entrance fees range from $25-$35 per vehicle."

async def get_parking_info(location: str) -> str:
    return f"Parking at {location} is typically available at visitor centers and trailheads."

async def get_travel_itinerary(trip_description: str) -> str:
    return f"For your trip: {trip_description}. Suggested plan: Day 1 - Travel. Day 2-3 - Explore. Day 4 - Return."

def get_system_prompt():
    return """You are a friendly backcountry guide. Be casual and helpful. Keep responses short (1-2 sentences).

TOOL USAGE RULES (CRITICAL):
- Tools execute silently in the background. NEVER write or display function calls, JSON, code, or tool syntax in your response.
- Only use tools when the user explicitly asks about: weather, park alerts, pricing, parking, routes, or itineraries.
- After tools run, integrate results naturally into conversation—never mention how you got the data.

RESPONSE RULES:
- Never fabricate or guess information. If you don't know, say so.
- Respond conversationally, like talking to a friend.
- Keep it short: 1-2 sentences max.
- Never output: <function=...>, JSON, code blocks, function names, or technical details.

CLOSING LOGIC:
- If user says "no", "nope", "I'm good", "that's all", "thanks", or indicates they're done, respond with a warm closing like: "Safe travels out there! Enjoy the trails. 🏕️" or "Awesome! Have an amazing adventure!"
- Keep closing statements short and genuine."""

async def process_llm_response(chat_history):
    try:
        response = await llm.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=chat_history,
            tools=agent_tools,
            tool_choice="auto",
            temperature=0.7
        )

        message = response.choices[0].message

        if message.tool_calls:
            chat_history.append({"role": "assistant", "content": message.content or "", "tool_calls": message.tool_calls})

            for tool_call in message.tool_calls:
                args = json.loads(tool_call.function.arguments)
                tool_name = tool_call.function.name

                if tool_name == "get_park_alerts":
                    data = await get_park_alerts(args.get("park_code", "zion"))
                elif tool_name == "get_weather":
                    data = await get_weather(args.get("location"))
                elif tool_name == "get_travel_recommendations":
                    data = await get_travel_recommendations(args.get("origin", ""), args.get("destination", ""))
                elif tool_name == "get_park_pricing":
                    data = await get_park_pricing(args.get("park_name"))
                elif tool_name == "get_parking_info":
                    data = await get_parking_info(args.get("location"))
                elif tool_name == "get_travel_itinerary":
                    data = await get_travel_itinerary(args.get("trip_description", ""))
                else:
                    data = "Tool not recognized."

                chat_history.append({"role": "tool", "tool_call_id": tool_call.id, "name": tool_name, "content": data})

            final_response = await llm.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=chat_history,
                temperature=0.7
            )
            reply = final_response.choices[0].message.content
        else:
            reply = message.content or "What can I help you with?"

        reply = humanize_response(reply)
        reply = verbalize_entities(reply)

        chat_history.append({"role": "assistant", "content": reply})

        if len(chat_history) > 20:
            chat_history = [chat_history[0]] + chat_history[-19:]

        return reply, chat_history

    except Exception as e:
        return f"Error: {str(e)}", chat_history

@app.get("/")
async def get_interface(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/notifications")
async def get_notifications():
    return JSONResponse(notifications_cache)

@app.post("/refresh-notifications")
async def refresh_notifications():
    global notifications_cache
    notifications_cache = await fetch_global_notifications()
    return JSONResponse(notifications_cache)

@app.post("/search-weather")
async def search_weather(request: Request):
    data = await request.json()
    city = data.get("city", "").strip()
    
    if not city:
        return JSONResponse({"error": "City name required"})
    
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return JSONResponse({"error": "Weather API key not configured"})
    
    url = "https://api.openweathermap.org/data/2.5/weather"
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params={"q": city, "units": "imperial", "appid": api_key})
            data = resp.json()
            
            if resp.status_code == 200:
                temp = data["main"]["temp"]
                condition = data["weather"][0].get("main", "")
                desc = data["weather"][0].get("description", "").capitalize()
                humidity = data["main"].get("humidity", 0)
                wind = data["wind"].get("speed", 0)
                feels_like = data["main"].get("feels_like", temp)
                
                icon_map = {
                    "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️", 
                    "Snow": "❄️", "Thunderstorm": "⛈️", "Drizzle": "🌦️",
                    "Mist": "🌫️", "Fog": "🌫️"
                }
                icon = icon_map.get(condition, "🌡️")
                
                return JSONResponse({
                    "success": True,
                    "location": data.get("name", city),
                    "country": data.get("sys", {}).get("country", ""),
                    "temp": f"{int(temp)}°F",
                    "feels_like": f"{int(feels_like)}°F",
                    "description": desc,
                    "condition": condition,
                    "humidity": f"{humidity}%",
                    "wind": f"{int(wind)} mph",
                    "icon": icon
                })
            else:
                error = data.get("message", "City not found")
                return JSONResponse({"error": error}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/chat")
async def text_chat(request: Request):
    data = await request.json()
    user_message = data.get("message", "").strip()
    if not user_message:
        return JSONResponse({"response": "Hey, say something!"})

    user_message = normalize_user_input(user_message)

    chat_history = chat_histories.get("global", [{"role": "system", "content": get_system_prompt()}])
    chat_history.append({"role": "user", "content": user_message})

    reply, chat_history = await process_llm_response(chat_history)
    chat_histories["global"] = chat_history

    return JSONResponse({"response": reply})

@app.websocket("/ws/audio")
async def audio_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🎙️ WebSocket connection established. Booting Agent...")
    session_id = id(websocket)
    
    greeting = "Hey there! Ready to explore some backcountry? Just ask me about weather, routes, or trail conditions."
    await websocket.send_text(greeting)
    
    chat_history = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "assistant", "content": greeting}
    ]

    dg_connection = None
    keepalive_task = None

    try:
        dg_connection = deepgram.listen.asyncwebsocket.v("1")

        async def on_message(self, result, **kwargs):
            nonlocal chat_history
            try:
                transcript = result.channel.alternatives[0].transcript
                if transcript and result.is_final:
                    print(f"🗣️ User (raw): {transcript}")
            
                    normalized_transcript = normalize_user_input(transcript)
                    print(f"🗣️ User (normalized): {normalized_transcript}")
            
                    chat_history.append({"role": "user", "content": normalized_transcript})
                    reply, chat_history = await process_llm_response(chat_history)
                    print(f"🏕️ Guide: {reply}")
            
                    # ✅ SEND USER MESSAGE FIRST
                    await websocket.send_text(json.dumps({"type": "user", "text": normalized_transcript}))
            
                    # ✅ THEN SEND AGENT RESPONSE
                    await websocket.send_text(json.dumps({"type": "agent", "text": reply}))
            except Exception as e:
                print(f"Error: {e}")

        async def on_error(self, error, **kwargs):
            print(f"Deepgram Error: {error}")

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)

        options = LiveOptions(
            model="nova-2",
            language="en-US",
            smart_format=True,
            interim_results=True,
            endpointing=300,
            vad_events=True
        )

        if await dg_connection.start(options) is False:
            print("❌ Failed to connect to Deepgram")
            return

        print("🟢 Agent Online. Ready for audio.")

        async def keepalive():
            while True:
                try:
                    await asyncio.sleep(5)
                    if dg_connection:
                        await dg_connection.keep_alive()
                except Exception as e:
                    print(f"Keepalive error: {e}")
                    break

        keepalive_task = asyncio.create_task(keepalive())

        while True:
            audio_bytes = await websocket.receive_bytes()
            if audio_bytes:
                await dg_connection.send(audio_bytes)

    except WebSocketDisconnect:
        print("🔌 Client disconnected.")
    except Exception as e:
        print(f"❌ Server Error: {e}")
    finally:
        if keepalive_task:
            keepalive_task.cancel()
        if dg_connection:
            await dg_connection.finish()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
