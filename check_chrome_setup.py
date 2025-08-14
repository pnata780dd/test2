#!/usr/bin/env python3
"""
Chrome Debug Setup Checker
Verifies that Chrome is running with debugging enabled and Automa is accessible
"""

import requests
import json

def check_chrome_debug():
    """Check if Chrome debugging is accessible"""
    try:
        response = requests.get("http://localhost:9222/json", timeout=5)
        if response.status_code == 200:
            tabs = response.json()
            print(f"✅ Chrome debugging accessible - Found {len(tabs)} contexts")
            
            # List all contexts
            print("\n📋 Available Chrome contexts:")
            for i, tab in enumerate(tabs, 1):
                title = tab.get('title', 'No title')
                url = tab.get('url', 'No URL')
                tab_type = tab.get('type', 'unknown')
                print(f"  {i}. {title} ({tab_type})")
                print(f"     URL: {url[:80]}...")
                
                # Check for Automa
                if 'automa' in title.lower() or 'automa' in url.lower():
                    print(f"     🎯 AUTOMA CONTEXT FOUND!")
                print()
            
            return True
        else:
            print(f"❌ Chrome debugging not accessible - Status: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Chrome debugging not running")
        print("💡 Start Chrome with: google-chrome --remote-debugging-port=9222")
        return False
    except Exception as e:
        print(f"❌ Error checking Chrome: {e}")
        return False

def check_automa_extension():
    """Try to find and connect to Automa extension"""
    try:
        response = requests.get("http://localhost:9222/json", timeout=5)
        tabs = response.json()
        
        automa_contexts = []
        for tab in tabs:
            title = tab.get('title', '').lower()
            url = tab.get('url', '').lower()
            
            if ('automa' in title or 'automa' in url or 
                ('chrome-extension' in url and any(term in url for term in ['automa', 'automation']))):
                automa_contexts.append(tab)
        
        if automa_contexts:
            print(f"✅ Found {len(automa_contexts)} Automa-related contexts:")
            for ctx in automa_contexts:
                print(f"  - {ctx.get('title')} ({ctx.get('type')})")
                print(f"    WebSocket: {ctx.get('webSocketDebuggerUrl', 'Not available')}")
            return automa_contexts
        else:
            print("❌ No Automa contexts found")
            print("💡 Make sure Automa extension is installed and enabled")
            return []
            
    except Exception as e:
        print(f"❌ Error checking Automa: {e}")
        return []

if __name__ == "__main__":
    print("🔍 Chrome Debug Setup Checker")
    print("=" * 50)
    
    # Check Chrome debugging
    if check_chrome_debug():
        print("\n🎯 Checking for Automa extension...")
        automa_contexts = check_automa_extension()
        
        if automa_contexts:
            print("\n✅ Setup looks good!")
            print("💡 You should be able to run the log extractor now")
        else:
            print("\n❌ Automa extension not found")
            print("💡 Next steps:")
            print("   1. Install Automa extension in Chrome")
            print("   2. Make sure it's enabled")
            print("   3. Open Automa dashboard at least once")
            print("   4. Restart Chrome with debugging enabled")
    else:
        print("\n❌ Chrome debugging not available")
        print("💡 Start Chrome with debugging:")
        print("   google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug")