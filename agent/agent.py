import time
import requests
import json
import subprocess
import os
import tempfile

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
            temp_path = None
            try:
                download_url = job.get('download_url')
                if download_url:
                    with requests.get(download_url, stream=True, timeout=60) as download:
                        download.raise_for_status()
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp:
                            temp_path = temp.name
                            for chunk in download.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    temp.write(chunk)
                elif os.path.isfile(file_key):
                    temp_path = file_key
                else:
                    raise RuntimeError('No downloadable file was provided for this job')

                requests.post(f"{BASE}/devices/{DEVICE_ID}/jobs/{job_id}/status/", json={'status':'printing'}, headers=headers)
                # PrintTo targets the configured Windows printer instead of the default printer.
                command = f"Start-Process -FilePath '{temp_path}' -Verb PrintTo -ArgumentList '{PRINTER}' -PassThru"
                subprocess.run(["powershell", "-NoProfile", "-Command", command], check=True)
                requests.post(f"{BASE}/devices/{DEVICE_ID}/jobs/{job_id}/status/", json={'status':'done','attempts': job.get('attempts',0)+1}, headers=headers)
            except Exception as exc:
                print('Print failed', exc)
                requests.post(f"{BASE}/devices/{DEVICE_ID}/jobs/{job_id}/status/", json={'status':'error','last_error':str(exc),'attempts': job.get('attempts',0)+1}, headers=headers)
            finally:
                if temp_path and temp_path != file_key:
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
        time.sleep(POLL)
    except Exception as exc:
        print('Agent error', exc)
        time.sleep(POLL)
