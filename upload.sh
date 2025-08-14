#!/bin/bash

echo "🚀 Automa Workflow Uploader"
echo "=========================="

cd /workspace

# Enhanced Chrome status check
echo "🔍 Checking Chrome GUI status..."
if curl -s http://localhost:9222/json/version > /dev/null 2>&1; then
    echo "✅ Chrome GUI is running and accessible"
    
    # Get Chrome version info
    CHROME_INFO=$(curl -s http://localhost:9222/json/version 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "📋 Chrome Version: $(echo "$CHROME_INFO" | python3 -c "import sys, json; print(json.load(sys.stdin).get('Browser', 'Unknown'))" 2>/dev/null || echo "Unknown")"
    fi
    
    # Check available tabs/extensions
    echo "📊 Available Chrome contexts:"
    curl -s http://localhost:9222/json 2>/dev/null | python3 -c "
import sys, json
try:
    tabs = json.load(sys.stdin)
    for i, tab in enumerate(tabs[:5]):  # Show first 5 tabs
        title = tab.get('title', 'Unknown')[:40]
        tab_type = tab.get('type', 'unknown')
        url = tab.get('url', '')[:50]
        print(f'  {i+1}. {title} ({tab_type})')
        if 'chrome-extension' in url:
            print(f'      Extension URL: {url}')
    if len(tabs) > 5:
        print(f'  ... and {len(tabs)-5} more')
except:
    print('  Could not parse tab information')
" || echo "  Could not retrieve tab information"

else
    echo "❌ Chrome GUI is not running!"
    echo "💡 Make sure to run './start-gui.sh' first"
    echo "💡 Or try: docker exec -it <container> /usr/local/bin/start-gui.sh"
    exit 1
fi

# Check workflows directory
if [ ! -d "workflows" ]; then
    echo "❌ No 'workflows' directory found!"
    echo "💡 Create a 'workflows' directory and add your .json workflow files"
    exit 1
fi

# Count and list workflow files
JSON_COUNT=$(find workflows -name "*.json" | wc -l)
echo "📊 Found $JSON_COUNT JSON workflow files"

if [ "$JSON_COUNT" -eq 0 ]; then
    echo "❌ No .json files found in workflows directory"
    echo "💡 Add some .json workflow files to the workflows directory"
    exit 1
fi

echo "📋 Workflow files found:"
find workflows -name "*.json" -exec basename {} \; | sed 's/^/  - /'

# Check if Python dependencies are available
echo ""
echo "🔍 Checking Python dependencies..."
python3 -c "import requests, websocket" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ Python dependencies are available"
else
    echo "⚠️ Installing missing Python dependencies..."
    pip3 install requests websocket-client
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install Python dependencies"
        exit 1
    fi
fi

echo ""
echo "🔄 Uploading workflows to running Chrome instance..."
echo "=================================================="

# Run the Python uploader
python3 upload.py

UPLOAD_RESULT=$?

echo ""
echo "=================================================="
if [ $UPLOAD_RESULT -eq 0 ]; then
    echo "🎉 Upload process completed!"
    echo ""
    echo "📖 How to access your workflows:"
    echo "  1. Open Chrome GUI: http://localhost:6080/vnc.html"
    echo "     Password: secret"
    echo "  2. Look for Automa extension icon in Chrome toolbar"
    echo "  3. Click on Automa extension or go to chrome-extension://[extension-id]/src/newtab/index.html"
    echo "  4. Your workflows should appear in the dashboard"
    echo ""
    echo "🔧 Troubleshooting tips:"
    echo "  - If workflows don't appear, try refreshing the Automa page"
    echo "  - Check browser console (F12) for any errors" 
    echo "  - Ensure the workflow JSON files are valid"
    echo "  - Try restarting Chrome if needed"
else
    echo "❌ Upload process failed!"
    echo ""
    echo "🔧 Debugging steps:"
    echo "  1. Check if Chrome is running: curl http://localhost:9222/json"
    echo "  2. Verify Automa extension is loaded in Chrome"
    echo "  3. Check Chrome logs: tail -f /tmp/chrome.log"
    echo "  4. Restart the GUI: ./start-gui.sh"
fi

echo "=================================================="