import time
import requests
import json
import subprocess
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

if not os.path.exists(CONFIG_PATH):
    print('Copy config.example.json to config.json and fill device_id/device_token')
    exit(1)

with open(CONFIG_PATH) as f:
    cfg = json.load(f)

BASE = cfg.get('backend_base','http://localhost:8000/api')
DEVICE_ID = cfg.get('device_id')
POLL = cfg.get('poll_interval_seconds', 10)
TOKEN = cfg.get('device_token')
PRINTER = cfg.get('printer_name')

headers = {'Authorization': f'Token {TOKEN}'} if TOKEN else {}

print(f"Starting local print agent. Polling {BASE}/devices/{DEVICE_ID}/jobs/ every {POLL}s")

while True:
    try:
        if not DEVICE_ID:
            print('No device_id in config')
            break
        r = requests.get(f"{BASE}/devices/{DEVICE_ID}/jobs/", headers=headers, timeout=10)
        r.raise_for_status()
        jobs = r.json()
        for job in jobs:
            job_id = job['id']
            order = job['order']
            file_key = order.get('file_key')
            print(f"Found job {job_id} for file {file_key}")
            # Update status -> downloading
            requests.post(f"{BASE}/devices/{DEVICE_ID}/jobs/{job_id}/status/", json={'status':'downloading'}, headers=headers)
            # Attempt to print a local file if file_key is a path
            printed = False
            local_path = file_key if os.path.exists(file_key) else None
            if local_path:
                try:
                    # Use PowerShell Start-Process -Verb Print
                    cmd = ["powershell", "-Command", f"Start-Process -FilePath '{local_path}' -Verb Print"]
                    subprocess.run(cmd, check=True)
                    printed = True
                except Exception as e:
                    print('Print failed', e)
                    requests.post(f"{BASE}/devices/{DEVICE_ID}/jobs/{job_id}/status/", json={'status':'error','last_error':str(e),'attempts': job.get('attempts',0)+1}, headers=headers)
            else:
                print('No local file to print; marking done for demo')
                printed = True

            if printed:
                requests.post(f"{BASE}/devices/{DEVICE_ID}/jobs/{job_id}/status/", json={'status':'done','attempts': job.get('attempts',0)+1}, headers=headers)
        time.sleep(POLL)
    except Exception as exc:
        print('Agent error', exc)
        time.sleep(POLL)
