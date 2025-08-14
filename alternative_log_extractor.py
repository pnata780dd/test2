#!/usr/bin/env python3
"""
Alternative Automa Log Extractor
Tries different methods to access Automa's database
"""

import os
import json
import requests
import websocket
from datetime import datetime

def try_extension_storage_api(ws_url):
    """Try using Chrome extension storage API"""
    try:
        ws = websocket.create_connection(ws_url)
        
        script = """
        new Promise((resolve) => {
            try {
                // Try multiple ways to access the database
                const attempts = [
                    // Method 1: Direct chrome.storage access
                    () => new Promise(res => {
                        if (typeof chrome !== 'undefined' && chrome.storage) {
                            chrome.storage.local.get(['logs', 'workflows', 'workflowLogs'], (result) => {
                                res({method: 'chrome.storage', data: result, success: true});
                            });
                        } else {
                            res({method: 'chrome.storage', success: false, error: 'Chrome storage not available'});
                        }
                    }),
                    
                    // Method 2: Check for global Dexie instances
                    () => new Promise(res => {
                        try {
                            const dexieInstances = [];
                            if (typeof window !== 'undefined') {
                                for (let prop in window) {
                                    if (prop.includes('db') || prop.includes('Database') || prop.includes('logs')) {
                                        try {
                                            const obj = window[prop];
                                            if (obj && typeof obj === 'object' && obj.constructor && obj.constructor.name) {
                                                dexieInstances.push({
                                                    name: prop,
                                                    type: obj.constructor.name,
                                                    hasOpen: typeof obj.open === 'function',
                                                    hasTables: obj.tables ? Object.keys(obj.tables) : []
                                                });
                                            }
                                        } catch (e) {}
                                    }
                                }
                            }
                            res({method: 'global-search', data: dexieInstances, success: true});
                        } catch (error) {
                            res({method: 'global-search', success: false, error: error.message});
                        }
                    }),
                    
                    // Method 3: Try accessing IndexedDB directly
                    () => new Promise(res => {
                        if (typeof indexedDB !== 'undefined') {
                            const request = indexedDB.open('logs');
                            request.onsuccess = (event) => {
                                try {
                                    const db = event.target.result;
                                    const storeNames = Array.from(db.objectStoreNames);
                                    db.close();
                                    res({method: 'indexeddb', data: {databases: ['logs'], stores: storeNames}, success: true});
                                } catch (error) {
                                    res({method: 'indexeddb', success: false, error: error.message});
                                }
                            };
                            request.onerror = () => {
                                res({method: 'indexeddb', success: false, error: 'Database not found'});
                            };
                        } else {
                            res({method: 'indexeddb', success: false, error: 'IndexedDB not available'});
                        }
                    })
                ];
                
                Promise.all(attempts.map(fn => fn())).then(results => {
                    resolve({
                        context: window.location ? window.location.href : 'unknown',
                        timestamp: Date.now(),
                        attempts: results,
                        availableGlobals: Object.keys(window || {}).filter(k => 
                            k.toLowerCase().includes('db') || 
                            k.toLowerCase().includes('log') || 
                            k.toLowerCase().includes('automa')
                        )
                    });
                });
                
            } catch (error) {
                resolve({
                    error: error.message,
                    stack: error.stack,
                    context: 'script-execution-failed'
                });
            }
        })
        """
        
        message = {
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": script,
                "awaitPromise": True,
                "returnByValue": True
            }
        }
        
        ws.send(json.dumps(message))
        response = json.loads(ws.recv())
        ws.close()
        
        return response
        
    except Exception as e:
        return {"error": str(e)}

def scan_chrome_extension_directory():
    """Look for Automa extension data in Chrome profile"""
    possible_paths = [
        "~/.config/google-chrome/Default/Local Extension Settings/",
        "~/.config/chromium/Default/Local Extension Settings/",
        "/tmp/chrome-debug/Default/Local Extension Settings/",
        "~/Library/Application Support/Google/Chrome/Default/Local Extension Settings/",  # macOS
        "%LOCALAPPDATA%/Google/Chrome/User Data/Default/Local Extension Settings/"  # Windows
    ]
    
    print("🔍 Scanning for Chrome extension data...")
    
    for path in possible_paths:
        expanded_path = os.path.expanduser(path)
        if os.path.exists(expanded_path):
            print(f"✅ Found extension directory: {expanded_path}")
            
            # List extensions
            try:
                extensions = os.listdir(expanded_path)
                print(f"   Found {len(extensions)} extensions")
                
                for ext_id in extensions:
                    ext_path = os.path.join(expanded_path, ext_id)
                    if os.path.isdir(ext_path):
                        # Try to identify Automa by checking manifest or files
                        manifest_files = ['manifest.json', 'MANIFEST-000001']
                        for manifest in manifest_files:
                            manifest_path = os.path.join(ext_path, manifest)
                            if os.path.exists(manifest_path):
                                print(f"   Extension {ext_id}: Has {manifest}")
                                break
                
            except Exception as e:
                print(f"   ❌ Error reading directory: {e}")
        else:
            print(f"❌ Path not found: {expanded_path}")

def main():
    print("🔧 Alternative Automa Log Extractor")
    print("=" * 50)
    
    # 1. Check Chrome debugging
    try:
        response = requests.get("http://localhost:9222/json", timeout=5)
        if response.status_code != 200:
            print("❌ Chrome debugging not accessible")
            return
        
        tabs = response.json()
        print(f"✅ Found {len(tabs)} Chrome contexts")
        
    except Exception as e:
        print(f"❌ Chrome debugging error: {e}")
        print("💡 Start Chrome with: google-chrome --remote-debugging-port=9222")
        return
    
    # 2. Try each context
    automa_found = False
    for i, tab in enumerate(tabs):
        title = tab.get('title', 'No title')
        url = tab.get('url', '')
        ws_url = tab.get('webSocketDebuggerUrl')
        
        print(f"\n🔍 Testing context {i+1}: {title[:50]}...")
        
        if ws_url:
            result = try_extension_storage_api(ws_url)
            
            if "result" in result and "result" in result["result"]:
                data = result["result"]["result"]["value"]
                print(f"   ✅ Successfully executed in context")
                print(f"   🔧 Available globals: {data.get('availableGlobals', [])}")
                
                for attempt in data.get('attempts', []):
                    method = attempt.get('method')
                    success = attempt.get('success')
                    if success:
                        print(f"   ✅ {method}: Success")
                        if attempt.get('data'):
                            print(f"      Data: {str(attempt['data'])[:100]}...")
                        automa_found = True
                    else:
                        print(f"   ❌ {method}: {attempt.get('error', 'Failed')}")
            else:
                print(f"   ❌ Failed to execute in context")
                if "error" in result:
                    print(f"      Error: {result['error']}")
        else:
            print(f"   ⚠️ No WebSocket URL available")
    
    if not automa_found:
        print("\n🔍 Trying filesystem scan...")
        scan_chrome_extension_directory()
    
    # 3. Provide troubleshooting steps
    print("\n💡 Troubleshooting Steps:")
    print("1. Make sure Automa extension is installed and enabled")
    print("2. Open Automa dashboard at least once to initialize database")
    print("3. Try running a workflow to generate some logs")
    print("4. Restart Chrome with debugging:")
    print("   google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug")
    print("5. Load the Automa extension page directly:")
    print("   chrome-extension://<automa-id>/dashboard.html")

if __name__ == "__main__":
    main()