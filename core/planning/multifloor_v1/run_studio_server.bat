@echo off
echo [ArchitectOS Multi-Floor Studio] Starting Local Bridge Server on http://127.0.0.1:8095 ...
start http://127.0.0.1:8095/studio.html
python local_bridge_server.py --host 127.0.0.1 --port 8095
pause
