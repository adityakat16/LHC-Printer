import time
import requests
import json
import subprocess
import os
import tempfile
import platform
import re
from printer_status import query_printer

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
CUPS_SERVER = cfg.get('cups_server', '')
CUPS_POLL_SECONDS = cfg.get('cups_poll_interval_seconds', 5)
CUPS_JOB_TIMEOUT_SECONDS = cfg.get('cups_job_timeout_seconds', 900)
CUPS_IPP_STATUS_ENABLED = cfg.get('cups_ipp_status_enabled', True)

headers = {'Authorization': f'Token {TOKEN}'} if TOKEN else {}

print(f"Starting local print agent. Polling {BASE}/devices/{DEVICE_ID}/jobs/ every {POLL}s")


def cups_command(*args):
    command = list(args)
    if CUPS_SERVER:
        command[1:1] = ['-h', CUPS_SERVER]
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f'CUPS command timed out: {command[0]}') from exc


def print_pdf(path):
    if platform.system() == 'Windows':
        command = (
            "Start-Process -FilePath "
            f"'{path}' -Verb PrintTo -ArgumentList '{PRINTER}' -PassThru"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", command], check=True)
        return None

    if not PRINTER:
        raise RuntimeError('printer_name is required for Linux/CUPS printing')

    if CUPS_IPP_STATUS_ENABLED:
        status = query_printer(PRINTER, CUPS_SERVER)
        if status.warnings:
            print('Printer warning: ' + '; '.join(status.warnings))

    result = cups_command('lp', '-d', PRINTER, path)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'CUPS rejected the print job')

    match = re.search(r'request id is\s+(\S+)', result.stdout)
    if not match:
        raise RuntimeError(f'CUPS accepted the file but returned no job ID: {result.stdout.strip()}')
    return match.group(1)


def wait_for_cups_job(cups_job_id):
    deadline = time.monotonic() + CUPS_JOB_TIMEOUT_SECONDS
    warnings = []
    while time.monotonic() < deadline:
        status = None
        try:
            if CUPS_IPP_STATUS_ENABLED:
                status = query_printer(PRINTER, CUPS_SERVER)
                warnings.extend(status.warnings)
                warnings = list(dict.fromkeys(warnings))
        except Exception as exc:
            cancel_error = cancel_cups_job(cups_job_id)
            raise RuntimeError(f'{exc}{cancel_error}') from exc

        printer = cups_command('lpstat', '-p', PRINTER, '-l')
        if printer.returncode:
            raise RuntimeError(printer.stderr.strip() or 'Unable to read CUPS printer status')

        printer_status = printer.stdout.strip()
        stopped = 'printer is stopped' in printer_status.lower() or 'printer is disabled' in printer_status.lower()
        if stopped:
            cancel_error = cancel_cups_job(cups_job_id)
            reason = status.message if CUPS_IPP_STATUS_ENABLED and status.message else printer_status
            raise RuntimeError(f'Printer stopped: {reason}{cancel_error}')

        pending = cups_command('lpstat', '-W', 'not-completed', '-o')
        if pending.returncode:
            raise RuntimeError(pending.stderr.strip() or 'Unable to read CUPS queue')
        pending_ids = {line.split()[0] for line in pending.stdout.splitlines() if line.split()}
        if cups_job_id in pending_ids:
            time.sleep(CUPS_POLL_SECONDS)
            continue

        completed = cups_command('lpstat', '-W', 'completed', '-o')
        if completed.returncode:
            raise RuntimeError(completed.stderr.strip() or 'Unable to read completed CUPS jobs')
        completed_ids = {line.split()[0] for line in completed.stdout.splitlines() if line.split()}
        if cups_job_id in completed_ids:
            return warnings

        raise RuntimeError(f'CUPS job {cups_job_id} disappeared without a completed status')

    cancel_error = cancel_cups_job(cups_job_id)
    raise RuntimeError(f'Timed out waiting for CUPS job {cups_job_id} to finish{cancel_error}')


def update_job(job_id, status, **details):
    response = requests.post(
        f"{BASE}/devices/{DEVICE_ID}/jobs/{job_id}/status/",
        json={'status': status, **details},
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()


def cancel_cups_job(cups_job_id):
    result = cups_command('cancel', cups_job_id)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or 'unknown CUPS cancellation error'
        return f'; additionally failed to cancel CUPS job {cups_job_id}: {detail}'
    return ''


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
            temp_path = None
            try:
                update_job(job_id, 'downloading')
                download_url = job.get('download_url') or f"{BASE}/devices/{DEVICE_ID}/jobs/{job_id}/file/"
                if download_url:
                    with requests.get(download_url, headers=headers, stream=True, timeout=60) as download:
                        download.raise_for_status()
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp:
                            temp_path = temp.name
                            for chunk in download.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    temp.write(chunk)
                elif file_key and os.path.isfile(file_key):
                    temp_path = file_key
                else:
                    raise RuntimeError('No downloadable file was provided for this job')

                update_job(job_id, 'printing')
                cups_job_id = print_pdf(temp_path)
                printer_warnings = []
                if cups_job_id:
                    printer_warnings = wait_for_cups_job(cups_job_id)
                update_job(
                    job_id,
                    'done',
                    attempts=job.get('attempts', 0) + 1,
                    last_error=('Printer warning: ' + '; '.join(printer_warnings)) if printer_warnings else '',
                )
            except Exception as exc:
                print('Print failed', exc)
                try:
                    update_job(
                        job_id,
                        'error',
                        last_error=str(exc),
                        attempts=job.get('attempts', 0) + 1,
                    )
                except requests.RequestException as status_error:
                    print('Unable to report print failure', status_error)
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
