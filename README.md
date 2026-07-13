# 🏔️ Backcountry Route Coordinator: Agentic Voice AI

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED)
![LangGraph](https://img.shields.io/badge/LangGraph-Agentic-green)

A stateful, multi-turn AI voice agent designed for outdoor enthusiasts and road-trippers. The Backcountry Route Coordinator handles complex logistical planning by integrating real-time speech processing with tool-calling capabilities to fetch national park alerts, weather forecasts, and dynamic driving routes.

## ✨ Features

* **Real-Time Voice Interface:** Low-latency conversational interactions using modern Speech-to-Text (STT) and Text-to-Speech (TTS) pipelines.
* **Agentic Routing:** Utilizes LangGraph to intelligently route user queries to specialized sub-agents and tool chains.
* **National Park Service (NPS) API Integration:** Fetches real-time trail closures, park conditions, and alerts.
* **Dynamic Route Calculation:** Calculates driving distances and times between distinct geographic coordinates or landmarks.
* **Containerized Deployment:** Fully packaged with Docker and Docker Compose for seamless local execution and dependency management.

## 🏗️ Architecture

The system relies on a three-stage asynchronous pipeline:
1. **The Ears (STT):** Captures microphone input and transcribes audio to text in real-time.
2. **The Brain (Orchestrator):** A LangGraph state machine maintains conversational memory and executes API tool calls based on user intent.
3. **The Voice (TTS):** Streams the LLM's text output back into high-fidelity synthesized audio.

## 📂 Repository Structure

```text
backcountry-voice-agent/
│
├── agent/                  # LangGraph state definition and routing
├── audio/                  # STT and TTS handlers
├── tools/                  # API wrappers (NPS, Weather, Routing)
├── .env.example            # Template for required API keys
├── docker-compose.yml      # Orchestration for local environment
├── Dockerfile              # Container definition
├── requirements.txt        # Python dependencies
└── main.py                 # Application entry point
