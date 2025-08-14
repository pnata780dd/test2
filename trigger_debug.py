#!/usr/bin/env python3
"""
Automa Extension Debug & Context Finder
Debug Chrome contexts and find Automa extension more reliably
"""

import os
import json
import requests
import websocket
from typing import Dict, List, Any, Optional

CHROME_DEBUG_URL = "http://localhost:9222/json"

def print_banner():
    """Print debug banner"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║              Automa Extension Debug Finder                   ║
║          🔍 Debug Chrome contexts & find Automa             ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def get_chrome_tabs_detailed() -> List[Dict]:
    """Get detailed Chrome tab information"""
    try:
        print("🔍 Connecting to Chrome DevTools...")
        response = requests.get(CHROME_DEBUG_URL, timeout=10)
        
        if response.status_code == 200:
            tabs = response.json()
            print(f"✅ Connected to Chrome - Found {len(tabs)} contexts")
            return tabs
        else:
            print(f"❌ Chrome DevTools error - Status: {response.status_code}")
            return []
            
    except requests.exceptions.ConnectError:
        print("❌ Connection refused to Chrome DevTools")
        print("💡 Troubleshooting steps:")
        print("   1. Make sure Chrome is running")
        print("   2. Start Chrome with: chrome --remote-debugging-port=9222")
        print("   3. Or add --remote-debugging-port=9222 to Chrome startup")
        return []
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def analyze_chrome_contexts(tabs: List[Dict]):
    """Analyze and display all Chrome contexts in detail"""
    print("\n" + "="*80)
    print("📋 DETAILED CHROME CONTEXT ANALYSIS")
    print("="*80)
    
    context_types = {}
    extension_contexts = []
    automa_candidates = []
    
    for i, tab in enumerate(tabs):
        title = tab.get('title', 'No Title')
        url = tab.get('url', 'No URL')
        tab_type = tab.get('type', 'unknown')
        tab_id = tab.get('id', 'no-id')
        ws_url = tab.get('webSocketDebuggerUrl', 'No WebSocket')
        
        # Count context types
        context_types[tab_type] = context_types.get(tab_type, 0) + 1
        
        # Find extension contexts
        if 'chrome-extension://' in url:
            extension_contexts.append({
                'index': i,
                'title': title,
                'url': url,
                'type': tab_type,
                'id': tab_id
            })
        
        # Find potential Automa contexts
        automa_keywords = ['automa', 'automation', 'workflow']
        if any(keyword in title.lower() for keyword in automa_keywords) or \
           any(keyword in url.lower() for keyword in automa_keywords):
            automa_candidates.append({
                'index': i,
                'title': title,
                'url': url,
                'type': tab_type,
                'match_reason': 'keyword match'
            })
        
        print(f"\n📄 Context {i+1}:")
        print(f"   Type: {tab_type}")
        print(f"   Title: {title}")
        print(f"   URL: {url[:80]}{'...' if len(url) > 80 else ''}")
        print(f"   ID: {tab_id}")
        print(f"   WebSocket: {'Available' if ws_url != 'No WebSocket' else 'None'}")
    
    # Summary
    print(f"\n📊 CONTEXT SUMMARY:")
    print(f"   Total Contexts: {len(tabs)}")
    for ctx_type, count in context_types.items():
        print(f"   {ctx_type}: {count}")
    
    print(f"\n🔌 EXTENSION CONTEXTS: {len(extension_contexts)}")
    for ext in extension_contexts:
        ext_id = ext['url'].split('/')[2] if 'chrome-extension://' in ext['url'] else 'unknown'
        print(f"   • {ext['title']} (ID: {ext_id[:12]}...)")
    
    print(f"\n🎯 AUTOMA CANDIDATES: {len(automa_candidates)}")
    for candidate in automa_candidates:
        print(f"   • {candidate['title']} ({candidate['match_reason']})")
    
    return extension_contexts, automa_candidates

def test_extension_context(ws_url: str, context_name: str) -> Dict[str, Any]:
    """Test if a context has Automa functionality"""
    print(f"\n🧪 Testing context: {context_name}")
    
    try:
        ws = websocket.create_connection(ws_url, timeout=5)
        
        # Test for Automa-specific APIs
        test_script = """
        (function() {
            const results = {
                hasChrome: typeof chrome !== 'undefined',
                hasChromeStorage: typeof chrome !== 'undefined' && !!chrome.storage,
                hasChromeRuntime: typeof chrome !== 'undefined' && !!chrome.runtime,
                hasAutoma: false,
                automaObjects: [],
                extensionId: '',
                manifestVersion: 'unknown'
            };
            
            // Check for Chrome extension APIs
            if (typeof chrome !== 'undefined') {
                if (chrome.runtime && chrome.runtime.id) {
                    results.extensionId = chrome.runtime.id;
                }
                if (chrome.runtime && chrome.runtime.getManifest) {
                    try {
                        const manifest = chrome.runtime.getManifest();
                        results.manifestVersion = manifest.manifest_version || 'unknown';
                        if (manifest.name && manifest.name.toLowerCase().includes('automa')) {
                            results.hasAutoma = true;
                        }
                    } catch(e) {}
                }
            }
            
            // Check for Automa-specific objects in window
            const automaKeys = Object.keys(window).filter(key => 
                key.toLowerCase().includes('automa') || 
                key.toLowerCase().includes('workflow') ||
                key.toLowerCase().includes('automation')
            );
            results.automaObjects = automaKeys;
            
            // Check for common Automa patterns
            if (automaKeys.length > 0 || 
                document.querySelector('[data-testid*="automa"]') ||
                document.querySelector('.automa') ||
                window.location.href.includes('automa')) {
                results.hasAutoma = true;
            }
            
            return results;
        })()
        """
        
        message = {
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": test_script,
                "returnByValue": True
            }
        }
        
        ws.send(json.dumps(message))
        response = json.loads(ws.recv())
        ws.close()
        
        if "result" in response and "result" in response["result"]:
            result_data = response["result"]["result"]["value"]
            
            print(f"   Chrome APIs: {'✅' if result_data.get('hasChrome') else '❌'}")
            print(f"   Chrome Storage: {'✅' if result_data.get('hasChromeStorage') else '❌'}")
            print(f"   Chrome Runtime: {'✅' if result_data.get('hasChromeRuntime') else '❌'}")
            print(f"   Automa Detected: {'✅' if result_data.get('hasAutoma') else '❌'}")
            
            if result_data.get('extensionId'):
                print(f"   Extension ID: {result_data['extensionId']}")
            if result_data.get('automaObjects'):
                print(f"   Automa Objects: {result_data['automaObjects']}")
                
            return result_data
        else:
            print("   ❌ Failed to execute test script")
            return {}
            
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return {}

def try_storage_access(ws_url: str, context_name: str) -> bool:
    """Try to access Chrome storage in this context"""
    print(f"\n💾 Testing storage access in: {context_name}")
    
    try:
        ws = websocket.create_connection(ws_url, timeout=5)
        
        storage_test_script = """
        new Promise((resolve) => {
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                chrome.storage.local.get(['workflows', 'workflowLogs'], (result) => {
                    const workflows = result.workflows || {};
                    const logs = result.workflowLogs || [];
                    
                    resolve({
                        success: true,
                        hasWorkflows: Object.keys(workflows).length > 0,
                        workflowCount: Object.keys(workflows).length,
                        hasLogs: logs.length > 0,
                        logCount: logs.length,
                        storageKeys: Object.keys(result)
                    });
                });
            } else {
                resolve({
                    success: false,
                    error: 'Chrome storage not available'
                });
            }
        })
        """
        
        message = {
            "id": 2,
            "method": "Runtime.evaluate",
            "params": {
                "expression": storage_test_script,
                "awaitPromise": True,
                "returnByValue": True
            }
        }
        
        ws.send(json.dumps(message))
        response = json.loads(ws.recv())
        ws.close()
        
        if "result" in response and "result" in response["result"]:
            result_data = response["result"]["result"]["value"]
            
            if result_data.get("success"):
                workflow_count = result_data.get("workflowCount", 0)
                log_count = result_data.get("logCount", 0)
                storage_keys = result_data.get("storageKeys", [])
                
                print(f"   ✅ Storage access successful")
                print(f"   📋 Workflows found: {workflow_count}")
                print(f"   📊 Logs found: {log_count}")
                print(f"   🔑 Storage keys: {storage_keys}")
                
                return workflow_count > 0 or log_count > 0
            else:
                print(f"   ❌ Storage access failed: {result_data.get('error')}")
                return False
        else:
            print("   ❌ Invalid storage response")
            return False
            
    except Exception as e:
        print(f"   ❌ Storage test failed: {e}")
        return False

def open_automa_extension() -> Optional[str]:
    """Try to open Automa extension in a new tab"""
    print("\n🚀 Attempting to open Automa extension...")
    
    try:
        # Try different potential Automa URLs
        automa_urls = [
            "chrome-extension://infppggnoaenmfagbfknfkancpbljcca/src/newtab/index.html",  # Common Automa extension ID
            "chrome://extensions/?id=infppggnoaenmfagbfknfkancpbljcca",
            "chrome://extensions/",
        ]
        
        for url in automa_urls:
            try:
                print(f"   Trying: {url}")
                response = requests.get(f"{CHROME_DEBUG_URL}/new?{url}")
                
                if response.status_code == 200:
                    new_tab = response.json()
                    print(f"   ✅ Opened: {url}")
                    return new_tab.get('webSocketDebuggerUrl')
                    
            except Exception as e:
                print(f"   ❌ Failed: {e}")
                continue
        
        print("   ⚠️ Could not open Automa extension directly")
        return None
        
    except Exception as e:
        print(f"❌ Failed to open extension: {e}")
        return None

def find_automa_by_manifest():
    """Try to find Automa by checking extension manifests"""
    print("\n🔍 Searching for Automa by extension manifest...")
    
    tabs = get_chrome_tabs_detailed()
    extension_tabs = [tab for tab in tabs if 'chrome-extension://' in tab.get('url', '')]
    
    for tab in extension_tabs:
        ws_url = tab.get('webSocketDebuggerUrl')
        if ws_url:
            try:
                ws = websocket.create_connection(ws_url, timeout=3)
                
                manifest_script = """
                (function() {
                    if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.getManifest) {
                        try {
                            const manifest = chrome.runtime.getManifest();
                            return {
                                name: manifest.name || 'Unknown',
                                version: manifest.version || 'Unknown',
                                description: manifest.description || '',
                                id: chrome.runtime.id || 'Unknown'
                            };
                        } catch(e) {
                            return { error: e.message };
                        }
                    }
                    return { error: 'No manifest access' };
                })()
                """
                
                message = {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": manifest_script, "returnByValue": True}
                }
                
                ws.send(json.dumps(message))
                response = json.loads(ws.recv())
                ws.close()
                
                if "result" in response and "result" in response["result"]:
                    manifest = response["result"]["result"]["value"]
                    name = manifest.get('name', '').lower()
                    
                    if 'automa' in name:
                        print(f"   ✅ Found Automa: {manifest.get('name')} v{manifest.get('version')}")
                        print(f"   📋 Description: {manifest.get('description', '')[:60]}...")
                        print(f"   🆔 Extension ID: {manifest.get('id')}")
                        return ws_url
                        
            except Exception as e:
                continue
    
    print("   ❌ Automa not found via manifest search")
    return None

def main():
    """Main debugging function"""
    print_banner()
    
    # Step 1: Get all Chrome contexts
    tabs = get_chrome_tabs_detailed()
    if not tabs:
        return
    
    # Step 2: Analyze contexts in detail
    extension_contexts, automa_candidates = analyze_chrome_contexts(tabs)
    
    # Step 3: Test each potential context
    print(f"\n🧪 TESTING CONTEXTS FOR AUTOMA FUNCTIONALITY")
    print("="*60)
    
    viable_contexts = []
    
    # Test automa candidates first
    for candidate in automa_candidates:
        ws_url = tabs[candidate['index']].get('webSocketDebuggerUrl')
        if ws_url:
            test_result = test_extension_context(ws_url, candidate['title'])
            if test_result.get('hasAutoma') or test_result.get('hasChromeStorage'):
                storage_access = try_storage_access(ws_url, candidate['title'])
                if storage_access:
                    viable_contexts.append({
                        'ws_url': ws_url,
                        'title': candidate['title'],
                        'score': 10
                    })
    
    # Test extension contexts
    for ext in extension_contexts:
        ws_url = tabs[ext['index']].get('webSocketDebuggerUrl')
        if ws_url:
            test_result = test_extension_context(ws_url, ext['title'])
            storage_access = try_storage_access(ws_url, ext['title'])
            
            score = 0
            if test_result.get('hasAutoma'): score += 5
            if test_result.get('hasChromeStorage'): score += 3
            if storage_access: score += 5
            
            if score > 0:
                viable_contexts.append({
                    'ws_url': ws_url,
                    'title': ext['title'],
                    'score': score
                })
    
    # Step 4: Try alternative methods
    if not viable_contexts:
        print(f"\n🔄 TRYING ALTERNATIVE DETECTION METHODS")
        print("="*50)
        
        # Method 1: Search by manifest
        manifest_url = find_automa_by_manifest()
        if manifest_url:
            viable_contexts.append({
                'ws_url': manifest_url,
                'title': 'Found via manifest',
                'score': 8
            })
        
        # Method 2: Try to open extension
        if not viable_contexts:
            new_tab_url = open_automa_extension()
            if new_tab_url:
                viable_contexts.append({
                    'ws_url': new_tab_url,
                    'title': 'Newly opened extension',
                    'score': 6
                })
    
    # Step 5: Results and recommendations
    print(f"\n🎯 FINAL RESULTS")
    print("="*40)
    
    if viable_contexts:
        # Sort by score
        viable_contexts.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"✅ Found {len(viable_contexts)} viable Automa context(s):")
        for i, context in enumerate(viable_contexts, 1):
            print(f"   {i}. {context['title']} (Score: {context['score']}/10)")
            print(f"      WebSocket: {context['ws_url'][:50]}...")
        
        print(f"\n💡 RECOMMENDED ACTION:")
        best_context = viable_contexts[0]
        print(f"   Use this WebSocket URL in your script:")
        print(f"   {best_context['ws_url']}")
        
        # Save the best URL to a file for easy use
        with open('/workspace/automa_ws_url.txt', 'w') as f:
            f.write(best_context['ws_url'])
        print(f"   💾 Saved to: /workspace/automa_ws_url.txt")
        
    else:
        print("❌ No viable Automa contexts found")
        print("\n💡 TROUBLESHOOTING SUGGESTIONS:")
        print("   1. Make sure Automa extension is installed and enabled")
        print("   2. Open the Automa extension in a Chrome tab")
        print("   3. Check if Chrome is running with --remote-debugging-port=9222")
        print("   4. Try visiting chrome://extensions/ and enabling Automa")
        print("   5. Restart Chrome with debugging enabled")

if __name__ == "__main__":
    main()