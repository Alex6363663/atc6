import asyncio
import json
from contextlib import asynccontextmanager

import websockets
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

WS_URL = 'wss://24data.ptfs.app/wss'
latest_aircraft = {}
last_update = None
connection_status = 'disconnected'

async def listen_to_24data():
    global connection_status, latest_aircraft, last_update
    while True:
        try:
            connection_status = 'connecting'
            async with websockets.connect(WS_URL, origin=None, ping_interval=20) as ws:
                connection_status = 'connected'
                async for message in ws:
                    try:
                        data = json.loads(message)
                    except (ValueError, TypeError):
                        continue
                    if isinstance(data, dict) and data.get('t') == 'ACFT_DATA' and isinstance(data.get('d'), dict):
                        latest_aircraft = data['d']
                        last_update = data.get('s')
        except asyncio.CancelledError:
            raise
        except Exception:
            connection_status = 'reconnecting'
            await asyncio.sleep(10)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(listen_to_24data())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

app = FastAPI(title='ATC24 Clearance Generator', lifespan=lifespan)

@app.get('/api/status')
async def status():
    return {'connection': connection_status, 'messages_received': last_update is not None, 'aircraft_count': len(latest_aircraft)}

@app.get('/api/aircraft')
async def aircraft():
    return {'connection': connection_status, 'data': {'t': 'ACFT_DATA', 'd': latest_aircraft, 's': last_update}}

@app.get('/')
async def home():
    return HTMLResponse(PAGE)

PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ATC24 | Clearance Desk</title>
<style>
:root{color-scheme:dark;--bg:#0b1220;--card:#182438;--line:#30435c;--text:#f1f5fb;--muted:#a9bad0;--accent:#48b9ff}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px system-ui,Arial,sans-serif}.wrap{max-width:1200px;margin:auto;padding:28px 18px}header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:22px}h1{font-size:28px;margin:0}h2{font-size:19px;margin:0 0 16px}.sub,.hint{color:var(--muted)}.status{padding:9px 13px;border:1px solid var(--line);border-radius:30px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px;margin-bottom:18px}.fields{display:grid;grid-template-columns:1fr 1fr;gap:14px}label{display:block;font-size:13px;color:var(--muted);margin-bottom:5px}input,select,textarea{width:100%;padding:11px 12px;border:1px solid #425671;border-radius:8px;background:#0e192b;color:white;font:inherit}textarea{min-height:125px;resize:vertical}button{border:0;border-radius:8px;background:var(--accent);color:#061320;padding:11px 16px;font-weight:700;cursor:pointer}button.secondary{background:#30435c;color:white}button:hover{filter:brightness(1.1)}.actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:15px}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.metric{background:#101c2e;padding:12px;border-radius:8px}.metric b{display:block;font-size:18px;margin-top:5px}.notice{border-left:3px solid var(--accent);padding:10px 12px;background:#10263c;margin-top:14px}.wide{grid-column:1/-1}@media(max-width:760px){.grid,.fields{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}}
</style></head><body><div class="wrap">
<header><div><h1>ATC24 Clearance Desk</h1><div class="sub">Live 24data aircraft feed · IFR &amp; VFR drafting</div></div><div class="status" id="status">Connecting…</div></header>
<div class="grid"><section><div class="card"><h2>Live aircraft</h2><label for="search">Search callsign or player</label><input id="search" placeholder="Search aircraft…"><div style="height:12px"></div><label for="aircraft">Select aircraft</label><select id="aircraft"><option value="">Waiting for aircraft…</option></select><p class="hint" id="count">No aircraft loaded</p><div class="metrics"><div class="metric">Aircraft type<b id="type">—</b></div><div class="metric">Altitude<b id="alt">—</b></div><div class="metric">Heading<b id="hdg">—</b></div><div class="metric">Speed<b id="spd">—</b></div><div class="metric">Wind (feed)<b id="wind">—</b></div><div class="metric">Status<b id="ground">—</b></div></div><p class="hint" id="player"></p></div>
<div class="card"><h2>Flight details</h2><div class="fields"><div><label for="mode">Clearance type</label><select id="mode"><option>IFR</option><option>VFR</option></select></div><div><label for="runway">Runway</label><input id="runway" placeholder="e.g. 27"></div><div><label for="departure">Departure airport</label><input id="departure" placeholder="e.g. IRFD"></div><div><label for="destination">Destination airport</label><input id="destination" placeholder="e.g. ITKO"></div><div><label for="altitude">Initial altitude</label><input id="altitude" placeholder="e.g. 3000 ft"></div><div><label for="frequency">Departure frequency</label><input id="frequency" placeholder="e.g. 124.85"></div><div><label for="squawk">Squawk</label><input id="squawk" placeholder="e.g. 4321"></div><div><label for="atis">ATIS information</label><input id="atis" placeholder="e.g. Bravo"></div><div class="wide"><label for="route">Route / departure instructions</label><input id="route" placeholder="e.g. radar vectors / filed route"></div></div><div class="notice">Departure, destination, runway, route, ATIS and frequencies are manual. The aircraft feed does not verify them.</div></div></section>
<section><div class="card"><h2>Clearance preview</h2><p class="hint">Select an aircraft, complete the fields, then generate a draft to read in-game.</p><textarea id="output" readonly placeholder="Your clearance will appear here…"></textarea><div class="actions"><button id="generate">Generate clearance</button><button id="copy" class="secondary">Copy clearance</button></div><p class="hint" id="feedback"></p></div><div class="card"><h2>Feed information</h2><p>Updated: <b id="updated">Waiting…</b></p><p class="hint">Aircraft details refresh every 5 seconds. The selected aircraft stays selected while available.</p><p class="hint">This tool drafts clearances only. It does not transmit instructions to pilots or control aircraft.</p></div></section></div></div>
<script>
let planes={}, selected='';
const el=id=>document.getElementById(id);
function display(){
 const term=el('search').value.trim().toLowerCase(), names=Object.keys(planes).filter(n=>n.toLowerCase().includes(term)||(planes[n].playerName||'').toLowerCase().includes(term)).sort();
 const dropdown=el('aircraft'); dropdown.replaceChildren();
 const placeholder=document.createElement('option');placeholder.value='';placeholder.textContent='Select an aircraft';dropdown.append(placeholder);
 for(const n of names){const option=document.createElement('option');option.value=n;option.textContent=n+' · '+(planes[n].aircraftType||'Unknown');dropdown.append(option)}
 dropdown.value=names.includes(selected)?selected:'';el('count').textContent=Object.keys(planes).length+' live aircraft · '+names.length+' matching';updateDetails();
}
function updateDetails(){const p=planes[selected];el('type').textContent=p?.aircraftType||'—';el('alt').textContent=p?.altitude!=null?p.altitude+' ft':'—';el('hdg').textContent=p?.heading!=null?String(p.heading).padStart(3,'0')+'°':'—';el('spd').textContent=p?.speed!=null?p.speed:'—';el('wind').textContent=p?.wind||'—';el('ground').textContent=p?(p.isOnGround?'Ground':'Airborne'):'—';el('player').textContent=p?'Player: '+(p.playerName||'Unknown')+(p.isEmergencyOccuring?' · EMERGENCY REPORTED':''):'';}
async function refresh(){try{const response=await fetch('/api/aircraft',{cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);const payload=await response.json();planes=payload.data?.d||{};el('status').textContent='● '+payload.connection+' · '+Object.keys(planes).length+' aircraft';el('updated').textContent=payload.data?.s?new Date(payload.data.s).toLocaleString():'No aircraft update yet';display()}catch(e){el('status').textContent='● Feed unavailable';el('feedback').textContent='Unable to refresh: '+e.message}}
el('search').addEventListener('input',display);el('aircraft').addEventListener('change',e=>{selected=e.target.value;updateDetails()});
function field(id){return el(id).value.trim()}
el('generate').addEventListener('click',()=>{
 const callsign=selected, mode=field('mode'),dep=field('departure'),dest=field('destination'),runway=field('runway'),alt=field('altitude'),freq=field('frequency'),squawk=field('squawk'),route=field('route'),atis=field('atis');
 if(!callsign){el('feedback').textContent='Select an aircraft first.';return}
 const parts=[callsign+', '+(mode==='IFR'?'cleared IFR':'VFR departure approved')];
 if(dest)parts.push('to '+dest);if(dep)parts.push('from '+dep);if(runway)parts.push('runway '+runway);if(route)parts.push('via '+route);if(alt)parts.push('initial altitude '+alt);if(freq)parts.push('departure frequency '+freq);if(squawk)parts.push('squawk '+squawk);if(atis)parts.push('information '+atis+' received');
 el('output').value=parts.join(', ')+'.';el('feedback').textContent='Draft generated. Verify all instructions before use.';
});
el('copy').addEventListener('click',async()=>{if(!el('output').value)return;try{await navigator.clipboard.writeText(el('output').value);el('feedback').textContent='Copied!'}catch{el('output').select();el('feedback').textContent='Select and copy the highlighted text.'}});
refresh();setInterval(refresh,5000);
</script></body></html>'''
