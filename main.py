import os
import json
import asyncio
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.templating import Jinja2Templates
import uvicorn
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
from groq import AsyncGroq

# Load API keys
load_dotenv()

app = FastAPI(title="Backcountry Route Coordinator")
templates = Jinja2Templates(directory="templates")

deepgram = DeepgramClient(os.getenv("DEEPGRAM_API_KEY"))
llm = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

# 🛠️ TOOL 1: NPS Alerts
async def get_park_alerts(park_code: str) -> str:
    api_key = os.getenv("NPS_API_KEY")
    if not api_key: return "NPS API Key missing."
    url = f"https://developer.nps.gov/api/v1/alerts?parkCode={park_code}&api_key={api_key}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            data = resp.json()
            if not data.get("data"): return f"No active alerts for {park_code} right now."
            alerts = [item["title"] for item in data["data"][:2]]
            return f"Active alerts for {park_code}: {', '.join(alerts)}"
    except Exception as e:
        return f"Error fetching NPS data: {str(e)}"

# 🛠️ THE FIX: Safe URL parameter encoding using params=
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

# Define the multi-tool schema
agent_tools = [
    {
        "type": "function",
        "function": {
            "name": "get_park_alerts",
            "description": "Get real-time active alerts, trail closures, and hazards for a US National Park.",
            "parameters": {
                "type": "object",
                "properties": {
                    "park_code": {
                        "type": "string",
                        "description": "The exact 4-letter NPS park code (e.g., zion, grca, yose)."
                    }
                },
                "required": ["park_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current live weather forecast for a specific location, city, or National Park.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, or National Park name (e.g., 'Zion National Park', 'Springdale, UT', 'Los Angeles')."
                    }
                },
                "required": ["location"]
            }
        }
    }
]

@app.get("/")
async def get_interface(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.websocket("/ws/audio")
async def audio_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🎙️ WebSocket connection established. Booting Agent...")

    chat_history = [
        {
            "role": "system", 
            "content": (
                "You are a friendly, casual, and highly knowledgeable travel and outdoor adventure guide. "
                "Keep your tone relaxed, smooth, and conversational. Speak like a real person helping a friend. "
                "Only check for weather or park alerts using your tools if the user explicitly asks about current conditions, alerts, closures, or the weather forecast. "
                "When a tool returns data, seamlessly and casually integrate the exact facts into your response. "
                "STRICT RULES: Never fabricate or hallucinate details. If a tool doesn't return data or if you don't know, say so honestly. "
                "Never repeat raw code, function names, JSON, or tags in your spoken response. Keep answers strictly under 2 sentences."
            )
        }
    ]

    try:
        dg_connection = deepgram.listen.asyncwebsocket.v("1")

        async def on_message(self, result, **kwargs):
            nonlocal chat_history
            sentence = result.channel.alternatives[0].transcript
            
            if sentence and result.is_final:
                print(f"\n🗣️ You: {sentence}")
                chat_history.append({"role": "user", "content": sentence})
                
                try:
                    response = await llm.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=chat_history,
                        tools=agent_tools,
                        tool_choice="auto"
                    )
                    
                    message = response.choices[0].message

                    if message.tool_calls:
                        print("🛠️ Agent is accessing live data...")
                        
                        chat_history.append(message)

                        for tool_call in message.tool_calls:
                            args = json.loads(tool_call.function.arguments)
                            
                            if tool_call.function.name == "get_park_alerts":
                                park_code = args.get("park_code", "zion")
                                data = await get_park_alerts(park_code)
                                print(f"📡 NPS Data: {data}")
                                
                            elif tool_call.function.name == "get_weather":
                                location = args.get("location", "Grand Canyon")
                                data = await get_weather(location)
                                print(f"📡 Weather Data: {data}")

                            chat_history.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_call.function.name,
                                "content": data
                            })

                        final_response = await llm.chat.completions.create(
                            model="llama-3.1-8b-instant",
                            messages=chat_history
                        )
                        reply = final_response.choices[0].message.content
                    else:
                        reply = message.content

                    print(f"🏕️ Guide: {reply}\n")
                    chat_history.append({"role": "assistant", "content": reply})
                    await websocket.send_text(reply)
                    
                    if len(chat_history) > 15:
                        chat_history = [chat_history[0]] + chat_history[-14:]

                except Exception as e:
                    print(f"❌ Groq Error: {e}")

        async def on_error(self, error, **kwargs):
            print(f"Deepgram Error: {error}")

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)

        options = LiveOptions(
            model="nova-2",
            language="en-US",
            smart_format=True,
            interim_results=False,
            endpointing=500,
            keywords=["Zion:3", "Bryce:2", "Grand Canyon:2", "Yosemite:2", "Delray Beach:2"]
        )

        if await dg_connection.start(options) is False:
            print("❌ Failed to connect to Deepgram")
            return

        print("🟢 Agent Online. Ready for your coordinates.")

        while True:
            audio_bytes = await websocket.receive_bytes()
            await dg_connection.send(audio_bytes)

    except WebSocketDisconnect:
        print("🔌 Client disconnected.")
    except Exception as e:
        print(f"❌ Server Error: {e}")
    finally:
        await dg_connection.finish()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
