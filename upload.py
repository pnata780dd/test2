#!/usr/bin/env python3
"""
Script to upload a single Automa workflow file to Chrome extension storage via DevTools Protocol (9222)
"""

import os
import json
import time
import requests
import websocket
import urllib.parse

CHROME_DEBUG_URL = "http://localhost:9222/json"
WORKFLOW_FILE = "/workspace/workflows/test.automa.json"


def get_chrome_tabs():
    """Get all Chrome tabs and pages"""
    try:
        response = requests.get(CHROME_DEBUG_URL, timeout=10)
        return response.json()
    except Exception as e:
        print(f"❌ Failed to get Chrome targets: {e}")
        return []


def find_automa_context():
    """Find Automa extension context (background page or any page with Automa)"""
    tabs = get_chrome_tabs()
    
    print("🔍 Available Chrome contexts:")
    for i, tab in enumerate(tabs):
        title = tab.get('title', 'Unknown')
        url = tab.get('url', 'Unknown')
        tab_type = tab.get('type', 'Unknown')
        print(f"  {i+1}. {title} ({tab_type}) - {url[:60]}...")
    
    for tab in tabs:
        if (tab.get('type') == 'background_page' and 
            ('automa' in tab.get('title', '').lower() or 
             'chrome-extension' in tab.get('url', ''))):
            print(f"✅ Found background page: {tab.get('title')}")
            return tab.get('webSocketDebuggerUrl')
    
    for tab in tabs:
        url = tab.get('url', '').lower()
        if 'chrome-extension' in url and 'automa' in url:
            print(f"✅ Found extension page: {tab.get('title')}")
            return tab.get('webSocketDebuggerUrl')
    
    for tab in tabs:
        if 'automa' in tab.get('title', '').lower():
            print(f"✅ Found Automa-related page: {tab.get('title')}")
            return tab.get('webSocketDebuggerUrl')
    
    return None


def load_workflows():
    """Load the single workflow JSON file"""
    workflows = []
    
    if not os.path.exists(WORKFLOW_FILE):
        print(f"❌ Workflow file not found: {WORKFLOW_FILE}")
        return workflows
        
    try:
        with open(WORKFLOW_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        filename = os.path.splitext(os.path.basename(WORKFLOW_FILE))[0]
        data.setdefault("id", filename)
        data.setdefault("name", filename.title())
        data.setdefault("createdAt", int(time.time() * 1000))
        data.setdefault("updatedAt", int(time.time() * 1000))
        data.setdefault("isDisabled", False)
        data.setdefault("description", f"Imported workflow: {filename}")
        
        workflows.append(data)
        print(f"✅ Loaded workflow: {data['name']}")
        
    except Exception as e:
        print(f"❌ Failed to parse {WORKFLOW_FILE}: {e}")
    
    return workflows


def inject_workflows_via_websocket(ws_url, workflows):
    """Inject workflows using WebSocket connection into chrome.storage.local only"""
    try:
        ws = websocket.create_connection(ws_url)
        workflows_data = {w["id"]: w for w in workflows}
        
        storage_method = f"""
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {{
            chrome.storage.local.set({{workflows: {json.dumps(workflows_data)}}}, () => {{
                console.log('Workflows saved to chrome.storage.local');
            }});
            'chrome_storage_done';
        }} else {{
            'chrome_storage_unavailable';
        }}
        """
        
        try:
            message = {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": storage_method}
            }
            ws.send(json.dumps(message))
            result = json.loads(ws.recv())
            
            if "result" in result and "result" in result["result"]:
                result_value = result["result"]["result"].get("value", "")
                if "chrome_storage_done" in result_value:
                    print(f"✅ Storage method 'chrome.storage.local' executed successfully: {result_value}")
                else:
                    print(f"⚠️ Storage method executed but returned: {result_value}")
            else:
                print(f"⚠️ Storage method had issues: {result}")
                
        except Exception as e:
            print(f"❌ Storage method failed: {e}")
        
        refresh_script = """
        if (typeof window.location !== 'undefined' && window.location.reload) {
            setTimeout(() => window.location.reload(), 1000);
        }
        'refresh_attempted';
        """
        
        refresh_msg = {
            "id": 99,
            "method": "Runtime.evaluate", 
            "params": {"expression": refresh_script}
        }
        ws.send(json.dumps(refresh_msg))
        ws.recv()
        
        ws.close()
        print(f"✅ Successfully attempted to upload {len(workflows)} workflow(s) to chrome.storage.local")
        
    except Exception as e:
        print(f"❌ Failed to inject workflows: {e}")
        print("\n📋 Successfully used storage methods: None (WebSocket connection failed)")


def open_automa_extension():
    """Try to open Automa extension in a new tab"""
    try:
        tabs = get_chrome_tabs()
        extension_id = None
        
        for tab in tabs:
            url = tab.get('url', '')
            if 'chrome-extension' in url and len(url.split('/')[2]) > 20:
                extension_id = url.split('/')[2]
                break
        
        if not extension_id:
            print("⚠️ Could not determine extension ID, trying generic approach")
            extension_url = "chrome://extensions/"
        else:
            extension_url = f"chrome-extension://{extension_id}/src/newtab/index.html"
        
        response = requests.get(f"{CHROME_DEBUG_URL}/new?{urllib.parse.quote(extension_url)}")
        new_tab = response.json()
        
        print(f"✅ Opened Automa extension at: {extension_url}")
        return new_tab.get('webSocketDebuggerUrl')
        
    except Exception as e:
        print(f"❌ Failed to open Automa extension: {e}")
        return None


def main():
    """Main execution function"""
    print("🔄 Starting workflow upload process...")
    print(f"📁 Checking file: {WORKFLOW_FILE}")
    
    workflows = load_workflows()
    if not workflows:
        return

    debugger_url = find_automa_context()
    
    if not debugger_url:
        print("⚠️ No Automa context found, trying to create one...")
        debugger_url = open_automa_extension()
        
        if not debugger_url:
            print("⚠️ Still no context, trying with any available tab...")
            tabs = get_chrome_tabs()
            if tabs:
                debugger_url = tabs[0].get('webSocketDebuggerUrl')
            
    if not debugger_url:
        print("❌ Could not establish connection to Chrome")
        return

    print(f"🔗 Using debugger URL: {debugger_url[:50]}...")
    inject_workflows_via_websocket(debugger_url, workflows)
    
    print("\n" + "="*50)
    print("✅ Upload process completed!")
    print("📝 Next steps:")
    print("   1. Open Chrome GUI at http://localhost:6080/vnc.html")
    print("   2. Navigate to the Automa extension")
    print("   3. Check if your workflow appears in the dashboard")
    print("   4. If not visible, try refreshing the page")
    print("="*50)


if __name__ == "__main__":
    main()
