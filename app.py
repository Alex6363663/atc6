"""Hosted ATC24 dashboard: one upstream WebSocket per server process."""
import json
import os
import threading
import time
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, render_template
from websocket import WebSocketApp

app = Flask(__name__)
lock = threading.Lock()
state = {'aircraft': {}, 'controllers': [], 'atis': [], 'plans': {},
         'connected': False, 'updated': {}, 'error': None}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def apply_event(event, data):
    with lock:
        if event == 'FLIGHT_PLAN' and isinstance(data, dict):
            callsign = data.get('callsign')
            if callsign:
                state['plans'][str(callsign).upper()] = data
                # Avoid indefinite growth of historical submissions.
                if len(state['plans']) > 300:
                    state['plans'].pop(next(iter(state['plans'])))
                state['updated']['plans'] = timestamp()
        elif event == 'ACFT_DATA' and isinstance(data, dict):
            state['aircraft'] = data
            state['updated']['aircraft'] = timestamp()
        elif event == 'CONTROLLERS' and isinstance(data, list):
            state['controllers'] = data
            state['updated']['controllers'] = timestamp()
        elif event == 'ATIS':
            updates = data if isinstance(data, list) else [data]
            current = {x['airport']: x for x in state['atis'] if isinstance(x, dict) and x.get('airport')}
            for item in updates:
                if isinstance(item, dict) and item.get('airport'):
                    current[item['airport']] = item
            state['atis'] = list(current.values())
            state['updated']['atis'] = timestamp()


def bootstrap_snapshot():
    """Fetch one initial REST snapshot; live updates thereafter arrive via WebSocket."""
    for key, route in [('aircraft', 'acft-data'), ('controllers', 'controllers'), ('atis', 'atis')]:
        try:
            response = requests.get('https://24data.ptfs.app/' + route, timeout=10)
            response.raise_for_status()
            payload = response.json()
            if key == 'atis' and isinstance(payload, dict):
                payload = list(payload.values())
            with lock:
                # Initial REST data must not overwrite fresher WS updates.
                if key not in state['updated']:
                    state[key] = payload
                    state['updated'][key] = timestamp()
        except Exception as exc:
            with lock:
                state['error'] = f'Initial {key} snapshot: {exc}'


def websocket_worker():
    retry = 3
    while True:
        def on_open(ws):
            nonlocal retry
            retry = 3
            with lock:
                state['connected'] = True
                state['error'] = None
            threading.Thread(target=bootstrap_snapshot, daemon=True).start()

        def on_message(ws, message):
            try:
                event = json.loads(message)
                if isinstance(event, dict):
                    apply_event(event.get('t'), event.get('d'))
            except (ValueError, TypeError):
                pass

        def on_error(ws, error):
            with lock:
                state['error'] = str(error)

        def on_close(ws, code, reason):
            with lock:
                state['connected'] = False

        try:
            # websocket-client on the server, not in the browser.
            # Explicitly send an empty Origin header, as required by 24data.
            ws = WebSocketApp('wss://24data.ptfs.app/wss',
                              on_open=on_open, on_message=on_message,
                              on_error=on_error, on_close=on_close)
            ws.run_forever(origin='', ping_interval=30, ping_timeout=10)
        except Exception as exc:
            with lock:
                state['error'] = str(exc)
                state['connected'] = False
        time.sleep(retry)
        retry = min(retry * 2, 60)


@app.get('/api/state')
def get_state():
    with lock:
        return jsonify(state)


@app.get('/')
def home():
    return render_template('index.html')


# Exactly one Gunicorn worker in render.yaml, hence one upstream WS connection.
threading.Thread(target=websocket_worker, daemon=True, name='24data-websocket').start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '5055')), debug=False)
