#!/usr/bin/env python3
"""
Improved Automa Workflow Log Extractor
- Multiple approaches to access Automa's database
- Better context detection
- Fallback methods for data extraction
"""

import os
import json
import csv
import time
import requests
import websocket
from datetime import datetime
from typing import Dict, List, Any, Optional

# Configuration
CHROME_DEBUG_URL = "http://localhost:9222/json"
OUTPUT_DIR = "/workspace/exports/logs"

def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║            Improved Automa Workflow Log Extractor           ║
║     📊 Multiple Access Methods  🔍 Better Detection        ║
╚══════════════════════════════════════════════════════════════╝
    """)

def get_chrome_tabs() -> List[Dict]:
    """Get all Chrome tabs with better filtering"""
    try:
        print("🔍 Connecting to Chrome DevTools...")
        response = requests.get(CHROME_DEBUG_URL, timeout=10)
        if response.status_code == 200:
            tabs = response.json()
            print(f"✅ Found {len(tabs)} Chrome contexts")
            
            # Filter for relevant contexts
            relevant_tabs = []
            for tab in tabs:
                title = tab.get('title', '').lower()
                url = tab.get('url', '').lower()
                tab_type = tab.get('type', '')
                
                # Look for Automa-related contexts
                if ('automa' in title or 'automa' in url or 
                    ('chrome-extension' in url and tab_type != 'service_worker')):
                    relevant_tabs.append(tab)
                    print(f"  🎯 Found relevant context: {tab.get('title')} ({tab_type})")
            
            return relevant_tabs
        else:
            print(f"❌ Chrome DevTools error: {response.status_code}")
            return []
    except requests.exceptions.ConnectError:
        print("❌ Cannot connect to Chrome - Is it running with --remote-debugging-port=9222?")
        return []
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return []

def try_manual_database_access(ws_url: str) -> Dict[str, Any]:
    """Try to access the database using multiple methods"""
    print("🔧 Attempting manual database access...")
    
    try:
        ws = websocket.create_connection(ws_url)
        
        # Enhanced script that tries multiple database access methods
        script = """
        new Promise(async (resolve) => {
            const results = {
                method: 'unknown',
                success: false,
                data: {},
                databases: [],
                context: window.location ? window.location.href : 'unknown',
                availableGlobals: []
            };
            
            try {
                // Method 1: Try to find existing database instances
                console.log('🔍 Method 1: Searching for existing database instances...');
                
                const globals = Object.keys(window || {});
                results.availableGlobals = globals.filter(k => 
                    k.toLowerCase().includes('db') || 
                    k.toLowerCase().includes('log') || 
                    k.toLowerCase().includes('automa') ||
                    k.toLowerCase().includes('dexie')
                );
                
                // Check for common Automa database names
                const dbNames = ['logs', 'automa', 'AutomaDB', 'workflow-logs', 'automa-logs'];
                
                // Method 2: Try IndexedDB.databases() if available
                if (typeof indexedDB !== 'undefined' && indexedDB.databases) {
                    try {
                        const databases = await indexedDB.databases();
                        results.databases = databases.map(db => db.name);
                        console.log('📋 Available databases:', results.databases);
                    } catch (e) {
                        console.warn('Could not list databases:', e);
                    }
                }
                
                // Method 3: Try to access chrome.storage (if in extension context)
                if (typeof chrome !== 'undefined' && chrome.storage) {
                    console.log('🔧 Method 3: Trying chrome.storage...');
                    
                    return new Promise(storageResolve => {
                        chrome.storage.local.get(null, (allData) => {
                            if (chrome.runtime.lastError) {
                                console.warn('Chrome storage error:', chrome.runtime.lastError);
                            } else {
                                results.method = 'chrome.storage';
                                results.success = true;
                                results.data = allData;
                                console.log('✅ Chrome storage access successful');
                                console.log('Keys found:', Object.keys(allData));
                            }
                            storageResolve(results);
                        });
                    });
                }
                
                // Method 4: Try direct IndexedDB access
                console.log('🔧 Method 4: Trying direct IndexedDB access...');
                
                for (const dbName of [...dbNames, ...results.databases]) {
                    try {
                        const request = indexedDB.open(dbName);
                        
                        await new Promise((dbResolve, dbReject) => {
                            request.onsuccess = async (event) => {
                                try {
                                    const db = event.target.result;
                                    const storeNames = Array.from(db.objectStoreNames);
                                    
                                    console.log(`✅ Opened database: ${dbName}, stores:`, storeNames);
                                    
                                    // Try to read from stores
                                    const transaction = db.transaction(storeNames, 'readonly');
                                    const storeData = {};
                                    
                                    for (const storeName of storeNames) {
                                        try {
                                            const store = transaction.objectStore(storeName);
                                            const getAllRequest = store.getAll();
                                            
                                            getAllRequest.onsuccess = () => {
                                                storeData[storeName] = getAllRequest.result;
                                                console.log(`📊 ${storeName}: ${getAllRequest.result.length} records`);
                                            };
                                        } catch (storeError) {
                                            console.warn(`Store ${storeName} error:`, storeError);
                                        }
                                    }
                                    
                                    transaction.oncomplete = () => {
                                        results.method = 'indexeddb';
                                        results.success = true;
                                        results.data = storeData;
                                        results.database = dbName;
                                        db.close();
                                        dbResolve();
                                    };
                                } catch (error) {
                                    console.warn(`Database ${dbName} access error:`, error);
                                    dbReject(error);
                                }
                            };
                            
                            request.onerror = () => {
                                console.log(`❌ Could not open database: ${dbName}`);
                                dbReject(request.error);
                            };
                        });
                        
                        if (results.success) break;
                        
                    } catch (error) {
                        console.warn(`Database ${dbName} error:`, error);
                    }
                }
                
                resolve(results);
                
            } catch (error) {
                results.error = error.message;
                results.stack = error.stack;
                resolve(results);
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
        
        if "result" in response and "result" in response["result"]:
            return response["result"]["result"]["value"]
        else:
            return {"success": False, "error": "Invalid response"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_manual_instructions() -> str:
    """Create manual extraction instructions"""
    instructions = """
# Manual Automa Database Extraction Instructions

## Method 1: Direct Console Access (Recommended)

1. **Open Chrome** and navigate to your Automa extension
2. **Click the Automa extension icon** to open the dashboard/popup
3. **Right-click on the Automa page** and select "Inspect"
4. **Go to the Console tab** in DevTools
5. **Paste and run this code:**

```javascript
// Load Dexie export utility
let script = document.createElement('script');
script.src = 'https://unpkg.com/dexie-export-import@latest';
document.body.appendChild(script);

setTimeout(async () => {
    // Try to find the logs database
    const databases = await indexedDB.databases();
    console.log('Available databases:', databases.map(db => db.name));
    
    // Try each database
    for (const dbInfo of databases) {
        try {
            const request = indexedDB.open(dbInfo.name);
            request.onsuccess = (event) => {
                const db = event.target.result;
                console.log(`Database: ${dbInfo.name}`);
                console.log('Object stores:', Array.from(db.objectStoreNames));
                
                // Export specific stores
                const transaction = db.transaction(db.objectStoreNames, 'readonly');
                const allData = {};
                
                for (const storeName of db.objectStoreNames) {
                    const store = transaction.objectStore(storeName);
                    const getAllRequest = store.getAll();
                    getAllRequest.onsuccess = () => {
                        allData[storeName] = getAllRequest.result;
                        console.log(`${storeName}: ${getAllRequest.result.length} records`);
                    };
                }
                
                transaction.oncomplete = () => {
                    // Create download link
                    const dataStr = JSON.stringify(allData, null, 2);
                    const dataBlob = new Blob([dataStr], {type: 'application/json'});
                    const link = document.createElement('a');
                    link.href = URL.createObjectURL(dataBlob);
                    link.download = `automa-data-${new Date().toISOString().slice(0,10)}.json`;
                    link.textContent = 'Download Automa Data';
                    link.style.cssText = 'display:block; padding:10px; background:#4CAF50; color:white; text-decoration:none; margin:10px 0;';
                    document.body.appendChild(link);
                };
                
                db.close();
            };
        } catch (e) {
            console.log(`Could not access ${dbInfo.name}:`, e);
        }
    }
}, 2000);
```

## Method 2: Application Tab (Alternative)

1. **Open Chrome DevTools** on the Automa extension page
2. **Go to Application tab**
3. **Expand IndexedDB** in the sidebar
4. **Look for databases** like 'logs', 'automa', or similar
5. **Browse the object stores** to view data
6. **Right-click on data** and copy or export manually

## Method 3: Extension Storage

1. **In DevTools Console**, try:

```javascript
// If in extension context
chrome.storage.local.get(null, (data) => {
    console.log('Extension storage:', data);
    // Download as JSON
    const dataStr = JSON.stringify(data, null, 2);
    const blob = new Blob([dataStr], {type: 'application/json'});
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'automa-storage.json';
    link.click();
});
```

## Troubleshooting

- **"No databases found"**: Make sure you're inspecting the Automa extension page, not a regular webpage
- **"Permission denied"**: Try opening the Automa dashboard first, then inspect
- **"Context not found"**: Restart Chrome with debugging enabled: `google-chrome --remote-debugging-port=9222`
"""
    return instructions

def main():
    """Main execution function"""
    print_banner()
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Get Chrome tabs
    tabs = get_chrome_tabs()
    
    if not tabs:
        print("❌ No relevant Chrome contexts found")
        print("\n💡 Manual extraction recommended:")
        print("1. Open Automa extension dashboard")
        print("2. Right-click and select 'Inspect'")
        print("3. Use the manual extraction method")
        
        # Save manual instructions
        instructions_path = os.path.join(OUTPUT_DIR, "manual_extraction_instructions.md")
        with open(instructions_path, 'w') as f:
            f.write(create_manual_instructions())
        print(f"\n📄 Manual instructions saved to: {instructions_path}")
        return
    
    # Try each relevant context
    success = False
    for i, tab in enumerate(tabs, 1):
        title = tab.get('title', 'Unknown')
        ws_url = tab.get('webSocketDebuggerUrl')
        
        if not ws_url:
            print(f"⚠️ Context {i} ({title}): No WebSocket URL")
            continue
        
        print(f"\n🔧 Trying context {i}: {title}")
        result = try_manual_database_access(ws_url)
        
        if result.get('success'):
            print(f"✅ Success with method: {result.get('method')}")
            
            # Save the extracted data
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(OUTPUT_DIR, f"automa_data_{timestamp}.json")
            
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            
            print(f"💾 Data saved to: {output_path}")
            success = True
            break
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")
            if result.get('availableGlobals'):
                print(f"   Available globals: {result['availableGlobals']}")
    
    if not success:
        print("\n❌ Automatic extraction failed for all contexts")
        print("\n💡 Try the manual extraction method:")
        
        # Save manual instructions
        instructions_path = os.path.join(OUTPUT_DIR, "manual_extraction_instructions.md")
        with open(instructions_path, 'w') as f:
            f.write(create_manual_instructions())
        print(f"📄 Instructions saved to: {instructions_path}")
        
        print("\n🔧 Quick manual steps:")
        print("1. Open Automa extension dashboard")
        print("2. Right-click → Inspect → Console tab")
        print("3. Run the JavaScript code from the instructions file")

if __name__ == "__main__":
    main()