# ATC6 V2 upgrade

## New in this version
- Radar aircraft history trails (up to 90 samples and 15 minutes), toggleable.
- Fit all currently reported aircraft to radar view.
- AeroNav chart launcher and FlightEye / 24Scope comparison links.
- Clearance generation blocks controller-configured closed or departure-disabled runways.
- Browser storage synchronization between tabs on the same browser profile.

## Deployment
Replace the existing repository files with the files inside this ZIP, keeping the same file structure (files at repository root). Commit changes and let the existing Render service redeploy. No new environment variables are needed. `render.yaml` retains one WebSocket worker.

## What this does NOT do
- This is a **PTFS world-coordinate radar**, not a georeferenced airport diagram. Never place aircraft on a conventional map by pretending PTFS coordinates are latitude/longitude.
- AeroNav is opened externally; chart embedding/API access is not established.
- FlightEye and 24Scope are external comparison links, **not synchronized write integrations**. ATC6 cannot change aircraft positions or external flight plans.
- Airport runways are entered and confirmed by the controller; no authoritative closure status is fetched. Published ATIS does not prove runway openness.
- Runway settings remain browser-local. Cross-device/server persistence requires authentication and a durable database; avoid an unauthenticated public edit endpoint.
- The live feed has not been verified against Render in this build environment.

# ATC24 Live Scope

Render-hosted FastAPI backend + browser controller dashboard.

## Deploy on Render

1. Upload all four project files to the root of your GitHub repository (not the containing `atc6-main` folder).
2. Create or update a Render **Web Service** connected to the repository, runtime **Python**.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn -k uvicorn.workers.UvicornWorker main:app`
5. Deploy and open your Render service URL. Check `/api/status` to see WebSocket connection status.

## Features

- Backend connects to the 24data WebSocket; browser polls the backend every 3 seconds.
- Live PTFS coordinate radar, pan/zoom, callsign search and aircraft selection.
- Controller-entered airport runways, headings, open/closed, departure/arrival assignments.
- Runway heading schematic (NOT geographically accurate), plus wind component suggestion.
- Auto-generated draft ATIS letter changes when entered airport weather/runway data changes.
- IFR/VFR clearance drafting, copy buttons, saved browser-local airport briefings.

## Limitations

Runway closure and airport-specific METAR/ATIS data are **not** fetched from an authoritative live source. Wind from 24data is not necessarily airport-specific. Do not treat the schematic as a geographic airport map. The app does not send clearances into Roblox. Browser-local runway configuration is not shared between users. Verify all operational information independently.

Do not commit API keys or secrets to GitHub. The backend uses one WebSocket connection per running worker; keep a single Render worker to avoid connection limits.


## 24data integration
Backend connects to `wss://24data.ptfs.app/wss` with no Origin header, caches live aircraft, ATIS, controller and flight-plan events. It loads published ATIS once on startup from `/atis` (503 is tolerated). Browser fetches only same-origin backend endpoints. No API key is specified by the supplied 24data documentation.

Endpoints: `/api/aircraft`, `/api/atis`, `/api/controllers`, `/api/flight-plans`, `/api/event-aircraft`. Published ATIS is displayed separately from local draft ATIS. Published departure runway can populate the runway selector but is not proof of open/closed status. Flight plans populate empty fields only.

**Render:** one web worker recommended so only one upstream WebSocket is opened. Start command: `gunicorn -w 1 -k uvicorn.workers.UvicornWorker main:app`. No credentials are embedded. Live integration requires testing on Render.

## Minimal deployment

This package includes `render.yaml`, `Procfile`, and `.python-version` so no commands or environment variables need to be typed for a fresh Render Blueprint deployment. Connect this GitHub repository to Render as a Blueprint, or use the existing Render service and its settings. A GitHub upload/commit and Render deployment are still required: a ZIP cannot configure external accounts on its own.

The upstream 24data feed does not require an API key in the documentation provided. Runway closures remain manually managed, and the map is not a georeferenced airport chart. An upstream outage or Render free-service sleep may temporarily interrupt the feed.
