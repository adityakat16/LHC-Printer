# LHC-Printer
LHC IISERTVM

## Local WSL printer test

The Brother DCP-T830DW CUPS queue on the WSL machine is named `DCPT830DW`.
The print agent runs in WSL and polls Django, which runs in Docker Desktop on
Windows. WSL's `localhost` forwarding is used to reach the published backend
port.

1. Verify CUPS can see the printer:

   ```bash
   lpstat -p -d
   ```

2. Start the Docker services from the project directory in PowerShell:

   ```powershell
   docker compose up -d --build
   ```

3. Register the printer agent once. From PowerShell, visit:

   ```text
   http://localhost:8000/api/devices/register/?name=brother-wsl-agent&printer_name=DCPT830DW
   ```

   Save the returned `id` and `device_token`. The backend is configured to
   route paid orders to a device registered with printer name `DCPT830DW`.

4. In WSL, create `agent/config.json` from `agent/config.example.json` and set
   the returned device ID and token. Keep this file private; it is ignored by
   Git.

5. Run the agent in WSL:

   ```bash
   cd /mnt/d/Coursera/Print\ Kiosk/agent
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python agent.py
   ```

After a verified payment, Django creates a queued print job assigned to the
registered device. The agent downloads the PDF from Django, submits it to CUPS
with `lp -d DCPT830DW`, and reports the job status. Uploaded PDFs are kept in
the shared `uploads_data` Docker volume until the 24-hour cleanup task removes
them.
