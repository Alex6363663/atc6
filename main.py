import asyncio, json, os, re
from urllib.request import urlopen
from contextlib import asynccontextmanager
import websockets
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pathlib import Path

WS_URL='wss://24data.ptfs.app/wss'
state={'connection':'disconnected','aircraft':{},'updated':None,'wind':None,'atis':{},'controllers':[],'flight_plans':{},'event_aircraft':{},'event_flight_plans':{}}
def normalize_atis(payload):
    if isinstance(payload,list): return {a['airport'].upper():a for a in payload if isinstance(a,dict) and isinstance(a.get('airport'),str)}
    if isinstance(payload,dict):
        if isinstance(payload.get('airport'),str):return {payload['airport'].upper():payload}
        return {str(k).upper():v for k,v in payload.items() if isinstance(v,dict)}
    return {}

async def initial_atis():
    def request():
        with urlopen('https://24data.ptfs.app/atis',timeout=12) as r:return json.load(r)
    try:state['atis'].update(normalize_atis(await asyncio.to_thread(request)))
    except Exception:pass  # WebSocket updates still work when REST returns 503.

async def listener():
    while True:
        try:
            state['connection']='connecting'
            async with websockets.connect(WS_URL,origin=None,ping_interval=20) as ws:
                state['connection']='connected'
                async for raw in ws:
                    try: msg=json.loads(raw)
                    except (ValueError,TypeError): continue
                    if not isinstance(msg,dict):continue
                    event=msg.get('t'); payload=msg.get('d')
                    if event=='ATIS':state['atis'].update(normalize_atis(payload))
                    elif event=='CONTROLLERS' and isinstance(payload,list):state['controllers']=payload
                    elif event in ('FLIGHT_PLAN','EVENT_FLIGHT_PLAN') and isinstance(payload,dict):
                        if payload.get('callsign'):state['flight_plans' if event=='FLIGHT_PLAN' else 'event_flight_plans'][payload['callsign']]=payload
                    elif event=='EVENT_ACFT_DATA' and isinstance(payload,dict):state['event_aircraft']=payload
                    if event=='ACFT_DATA' and isinstance(payload,dict):
                        state['aircraft']=msg['d'];state['updated']=msg.get('s')
                        state['wind']=next((v.get('wind') for v in msg['d'].values() if isinstance(v,dict) and v.get('wind')),None)
        except asyncio.CancelledError: raise
        except Exception as exc:
            state['connection']='reconnecting ('+type(exc).__name__+')'
            await asyncio.sleep(8)
@asynccontextmanager
async def lifespan(app):
    task=asyncio.create_task(listener())
    atis_task=asyncio.create_task(initial_atis())
    yield
    task.cancel()
    atis_task.cancel()
    try: await task
    except asyncio.CancelledError: pass
app=FastAPI(lifespan=lifespan)
@app.get('/')
def index(): return FileResponse(Path(__file__).with_name('index.html'))
@app.get('/api/status')
def status(): return {'connection':state['connection'],'messages_received':bool(state['updated'])}
@app.get('/api/aircraft')
def aircraft(): return {'connection':state['connection'],'data':{'t':'ACFT_DATA','d':state['aircraft'],'s':state['updated']},'wind':state['wind']}

@app.get('/api/atis')
def atis(): return {'data':state['atis'],'source':'24data','live':state['connection']=='connected'}
@app.get('/api/controllers')
def controllers():return {'data':state['controllers']}
@app.get('/api/flight-plans')
def flight_plans():return {'data':state['flight_plans']}
@app.get('/api/event-aircraft')
def event_aircraft():return {'data':state['event_aircraft']}
