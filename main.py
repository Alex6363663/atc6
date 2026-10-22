
import asyncio
import json
import os
from contextlib import asynccontextmanager

import websockets
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

WS_URL = "wss://24data.ptfs.app/wss"
aircraft = {}
connection_status = "disconnected"


async def listen_to_24data():
    global connection_status

    while True:
        try:
            connection_status = "connecting"
            async with websockets.connect(
                WS_URL,
                origin=None,
                ping_interval=20
            ) as websocket:
                connection_status = "connected"

                async for message in websocket:
                    try:
                        data = json.loads(message)
                        # Save raw feed information until the
                        # 24data message schema is verified.
                        aircraft["latest_message"] = data
                    except json.JSONDecodeError:
                        pass

        except Exception as exc:
            connection_status = f"reconnecting: {type(exc).__name__}"
            await asyncio.sleep(10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(listen_to_24data())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="ATC24 Clearance Generator", lifespan=lifespan)


@app.get("/")
async def home():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>ATC24 Clearance Generator</title>
        <style>
            body {
                background: #101827;
                color: white;
                font-family: Arial, sans-serif;
                padding: 30px;
            }
            .panel {
                background: #1e293b;
                padding: 25px;
                border-radius: 12px;
                max-width: 700px;
            }
            button {
                padding: 12px;
                cursor: pointer;
            }
        </style>
    </head>
    <body>
        <div class="panel">
            <h1>ATC24 Clearance Generator</h1>
            <p>Live 24data connection status:</p>
            <h2 id="status">Checking...</h2>
            <p>Aircraft feed connection test</p>
            <button onclick="check()">Refresh</button>
        </div>
        <script>
            async function check() {
                try {
                    const response = await fetch('/api/status');
                    const data = await response.json();
                    document.getElementById('status').textContent =
                        data.connection;
                } catch {
                    document.getElementById('status').textContent =
                        'Server unavailable';
                }
            }
            check();
            setInterval(check, 5000);
        </script>
    </body>
    </html>
    """)


@app.get("/api/status")
async def status():
    return {
        "connection": connection_status,
        "messages_received": "latest_message" in aircraft
    }
@app.get("/api/aircraft")
async def get_aircraft():
    return {
        "connection": connection_status,
        "data": aircraft.get("latest_message", {}),
    }

