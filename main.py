import asyncio, json
from contextlib import asynccontextmanager
import websockets
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pathlib import Path

WS_URL='wss://24data.ptfs.app/wss'
state={'connection':'disconnected','aircraft':{},'updated':None,'wind':None}
async def listener():
    while True:
        try:
            state['connection']='connecting'
            async with websockets.connect(WS_URL,origin=None,ping_interval=20) as ws:
                state['connection']='connected'
                async for raw in ws:
                    try: msg=json.loads(raw)
                    except (ValueError,TypeError): continue
                    if isinstance(msg,dict) and msg.get('t')=='ACFT_DATA' and isinstance(msg.get('d'),dict):
                        state['aircraft']=msg['d'];state['updated']=msg.get('s')
                        state['wind']=next((v.get('wind') for v in msg['d'].values() if isinstance(v,dict) and v.get('wind')),None)
        except asyncio.CancelledError: raise
        except Exception as exc:
            state['connection']='reconnecting ('+type(exc).__name__+')'
            await asyncio.sleep(8)
@asynccontextmanager
async def lifespan(app):
    task=asyncio.create_task(listener())
    yield
    task.cancel()
    try: await task
    except asyncio.CancelledError: pass
app=FastAPI(lifespan=lifespan)
@app.get('/')
def index(): return FileResponse(Path(__file__).with_name('index.html'))
@app.get('/api/status')
def status(): return {'connection':state['connection'],'messages_received':bool(state['updated'])}
@app.get('/api/aircraft')
def aircraft(): return {'connection':state['connection'],'data':{'t':'ACFT_DATA','d':state['aircraft'],'s':state['updated']},'wind':state['wind']}
