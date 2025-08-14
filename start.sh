#!/bin/bash
set -e

cleanup() {
  echo "Shutting down gracefully..."
  pkill -f "Xvfb|fluxbox|x11vnc|websockify|chrome" || true
  exit 0
}
trap cleanup SIGINT SIGTERM

echo "Using persistent Chrome profile at /workspace/chrome_profile"

# --- Start virtual display ---
echo "Starting Xvfb..."
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99
Xvfb :99 -screen 0 1920x1080x24 -ac +extension RANDR +extension GLX +render -noreset \
  >/tmp/xvfb.log 2>&1 &
sleep 3
export DISPLAY=:99
xdpyinfo -display :99 >/dev/null || { echo "Xvfb failed"; cat /tmp/xvfb.log; exit 1; }

export XDG_RUNTIME_DIR=/tmp/runtime-root
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
eval "$(dbus-launch --sh-syntax)"

fluxbox >/tmp/fluxbox.log 2>&1 &
sleep 2

x11vnc -display :99 -forever -shared -passwd secret -bg -o /tmp/x11vnc.log
websockify --web /usr/share/novnc 6080 localhost:5900 >/tmp/websockify.log 2>&1 &
sleep 3

# --- Locate Automa build directory ---
if [ -d "/workspace/automa/build" ]; then
  AUTOMA_DIR="/workspace/automa/build"
  echo "Found Automa at: $AUTOMA_DIR"
else
  echo "ERROR: Automa build not found"
  ls -la /workspace/automa/ 2>/dev/null || echo "Automa directory doesn't exist yet"
  exit 1
fi

# Check if required files exist
if [ ! -f "$AUTOMA_DIR/manifest.json" ]; then
  echo "ERROR: No manifest.json found in $AUTOMA_DIR"
  exit 1
fi

if [ ! -f "$AUTOMA_DIR/popup.html" ]; then
  echo "ERROR: No popup.html found in $AUTOMA_DIR"
  echo "This is required for Manifest V3 Automa"
  exit 1
fi

echo "✅ Automa extension files verified"
chmod -R a+r "$AUTOMA_DIR"

# --- Persistent Chrome profile ---
CHROME_PROFILE_DIR="/workspace/chrome_profile"
mkdir -p "$CHROME_PROFILE_DIR"
rm -f "$CHROME_PROFILE_DIR/SingletonLock" "$CHROME_PROFILE_DIR/SingletonSocket" "$CHROME_PROFILE_DIR/SingletonCookie"

# --- Start Chrome with Developer Mode and Extensions Page ---
echo "Starting Chrome with extensions page for manual loading..."
google-chrome-stable \
  --no-sandbox --disable-setuid-sandbox \
  --disable-gpu --disable-dev-shm-usage \
  --user-data-dir="$CHROME_PROFILE_DIR" \
  --remote-debugging-port=9222 --remote-debugging-address=0.0.0.0 \
  --remote-allow-origins=* \
  --disable-features=UseOzonePlatform,VizDisplayCompositor \
  --window-size=1920,1080 --start-maximized \
  --disable-web-security \
  --disable-features=VizDisplayCompositor \
  chrome://extensions/ >/tmp/chrome.log 2>&1 &

sleep 10
if ! pgrep -f "chrome" >/dev/null; then
  echo "Chrome failed to start; last logs:"; tail -20 /tmp/chrome.log
  exit 1
fi

echo "Chrome started successfully!"

# --- Auto-enable Developer Mode ---
echo "Attempting to enable Developer Mode automatically..."

# Use Chrome DevTools Protocol to enable developer mode
sleep 2

# Try to interact with the extensions page to enable developer mode
curl -s -X POST "http://localhost:9222/json/runtime/evaluate" \
  -H "Content-Type: application/json" \
  -d '{
    "expression": "document.querySelector(\"extensions-manager\").shadowRoot.querySelector(\"extensions-toolbar\").shadowRoot.querySelector(\"#devMode\").click()",
    "awaitPromise": false
  }' >/dev/null 2>&1 || echo "Auto-enable failed (expected)"

sleep 2

# --- Launch a debug terminal ---
xterm -geometry 80x24+50+50 -title "Debug Terminal" &

cat <<EOF
==============================================
🔧 Automa Setup Required - Manual Steps Needed

Chrome is now running with the extensions page open.
Access the GUI: http://localhost:6080/vnc.html (password: secret)

MANUAL SETUP STEPS (in Chrome Extensions page):
1. Enable "Developer mode" toggle (top right)
2. Click "Load unpacked" button  
3. Browse to: $AUTOMA_DIR
4. Select the automa/build folder
5. The extension should now load with an ID

After loading, the extension will be available at:
chrome-extension://[EXTENSION_ID]/popup.html

Extension Location: $AUTOMA_DIR
Chrome Profile: $CHROME_PROFILE_DIR
DevTools: http://localhost:9222

IMPORTANT NOTES:
- This is a Manifest V3 extension 
- The dashboard runs as a popup (don't close it during workflows)
- Developer mode must be manually enabled in Chrome
- Use "Load unpacked" not drag-and-drop

Logs:
  Chrome: /tmp/chrome.log
  X11VNC: /tmp/x11vnc.log  
  Xvfb: /tmp/xvfb.log

Once loaded manually, you can create a script to detect the extension ID.
==============================================
EOF

echo "Waiting for manual setup... (Press Ctrl+C to exit)"
tail -f /dev/null