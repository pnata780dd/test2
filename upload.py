#!/usr/bin/env python3
"""
Script to upload a single Automa workflow file to Chrome extension storage via DevTools Protocol (9222)
Enhanced with comprehensive logging and status messages.
"""

import os
import json
import time
import logging
import requests
import websocket
import urllib.parse
from datetime import datetime

# Configuration
CHROME_DEBUG_URL = "http://localhost:9222/json"
WORKFLOW_FILE = "/workspace/workflows/test.automa.json"
LOG_LEVEL = logging.INFO

# Setup logging
def setup_logging():
    """Configure logging with both file and console output"""
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Create logs directory if it doesn't exist
    log_dir = "/workspace/logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"automa_upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    # Configure logging
    logging.basicConfig(
        level=LOG_LEVEL,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"📝 Logging initialized. Log file: {log_file}")
    return logger

# Initialize logger
logger = setup_logging()

def print_banner():
    """Print startup banner"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                 Automa Workflow Uploader v2.0               ║
║          Enhanced with comprehensive logging support         ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)
    logger.info("Starting Automa Workflow Uploader v2.0")

def get_chrome_tabs():
    """Get all Chrome tabs and pages"""
    logger.info("🔍 Attempting to connect to Chrome DevTools...")
    print("🔍 Connecting to Chrome DevTools Protocol...")
    
    try:
        logger.debug(f"Making request to: {CHROME_DEBUG_URL}")
        response = requests.get(CHROME_DEBUG_URL, timeout=10)
        
        if response.status_code == 200:
            tabs = response.json()
            logger.info(f"✅ Successfully connected to Chrome. Found {len(tabs)} contexts.")
            print(f"✅ Connected to Chrome - Found {len(tabs)} browser contexts")
            return tabs
        else:
            logger.error(f"❌ Chrome DevTools returned status code: {response.status_code}")
            print(f"❌ Chrome DevTools error - Status code: {response.status_code}")
            return []
            
    except requests.exceptions.ConnectError as e:
        logger.error(f"❌ Connection refused to Chrome DevTools: {e}")
        print("❌ Cannot connect to Chrome DevTools - Is Chrome running with --remote-debugging-port=9222?")
        return []
    except requests.exceptions.Timeout as e:
        logger.error(f"❌ Timeout connecting to Chrome DevTools: {e}")
        print("❌ Timeout connecting to Chrome DevTools")
        return []
    except Exception as e:
        logger.error(f"❌ Unexpected error getting Chrome tabs: {e}")
        print(f"❌ Failed to get Chrome contexts: {e}")
        return []

def find_automa_context():
    """Find Automa extension context (background page or any page with Automa)"""
    logger.info("🔍 Searching for Automa extension context...")
    print("🔍 Searching for Automa extension context...")
    
    tabs = get_chrome_tabs()
    if not tabs:
        return None
    
    print("\n📋 Available Chrome contexts:")
    logger.info("Available Chrome contexts:")
    
    for i, tab in enumerate(tabs):
        title = tab.get('title', 'Unknown')
        url = tab.get('url', 'Unknown')
        tab_type = tab.get('type', 'Unknown')
        context_info = f"  {i+1}. [{tab_type}] {title} - {url[:60]}..."
        print(context_info)
        logger.debug(f"Context {i+1}: Type={tab_type}, Title={title}, URL={url}")
    
    # Priority 1: Background pages with Automa
    logger.info("🎯 Searching for Automa background pages...")
    for tab in tabs:
        if (tab.get('type') == 'background_page' and 
            ('automa' in tab.get('title', '').lower() or 
             'automa' in tab.get('url', '').lower())):
            context_info = f"✅ Found Automa background page: {tab.get('title')}"
            print(context_info)
            logger.info(f"Found Automa background page: {tab.get('title')} - {tab.get('url')}")
            return tab.get('webSocketDebuggerUrl')
    
    # Priority 2: Extension pages with Automa
    logger.info("🎯 Searching for Automa extension pages...")
    for tab in tabs:
        url = tab.get('url', '').lower()
        if 'chrome-extension' in url and 'automa' in url:
            context_info = f"✅ Found Automa extension page: {tab.get('title')}"
            print(context_info)
            logger.info(f"Found Automa extension page: {tab.get('title')} - {tab.get('url')}")
            return tab.get('webSocketDebuggerUrl')
    
    # Priority 3: Any page with Automa in title
    logger.info("🎯 Searching for pages with 'Automa' in title...")
    for tab in tabs:
        if 'automa' in tab.get('title', '').lower():
            context_info = f"✅ Found Automa-related page: {tab.get('title')}"
            print(context_info)
            logger.info(f"Found Automa-related page: {tab.get('title')} - {tab.get('url')}")
            return tab.get('webSocketDebuggerUrl')
    
    logger.warning("⚠️ No Automa context found in available tabs")
    print("⚠️ No Automa extension context found")
    return None

def load_workflows():
    """Load the single workflow JSON file"""
    logger.info(f"📁 Loading workflow file: {WORKFLOW_FILE}")
    print(f"📁 Loading workflow from: {WORKFLOW_FILE}")
    
    workflows = []
    
    # Check if file exists
    if not os.path.exists(WORKFLOW_FILE):
        error_msg = f"❌ Workflow file not found: {WORKFLOW_FILE}"
        logger.error(error_msg)
        print(error_msg)
        return workflows
    
    # Check file size
    file_size = os.path.getsize(WORKFLOW_FILE)
    logger.info(f"📊 File size: {file_size} bytes")
    print(f"📊 File size: {file_size:,} bytes")
    
    try:
        logger.debug("🔄 Reading and parsing JSON file...")
        with open(WORKFLOW_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Process workflow data
        filename = os.path.splitext(os.path.basename(WORKFLOW_FILE))[0]
        original_id = data.get("id", "unknown")
        original_name = data.get("name", "unknown")
        
        # Set default values
        data.setdefault("id", filename)
        data.setdefault("name", filename.title())
        data.setdefault("createdAt", int(time.time() * 1000))
        data.setdefault("updatedAt", int(time.time() * 1000))
        data.setdefault("isDisabled", False)
        data.setdefault("description", f"Imported workflow: {filename}")
        
        workflows.append(data)
        
        success_msg = f"✅ Successfully loaded workflow: '{data['name']}' (ID: {data['id']})"
        logger.info(success_msg)
        print(success_msg)
        
        # Log workflow details
        workflow_details = f"📋 Workflow details - Original ID: {original_id}, Original Name: {original_name}"
        logger.info(workflow_details)
        print(workflow_details)
        
        if "drawflow" in data:
            node_count = len(data["drawflow"].get("Home", {}).get("data", {}))
            logger.info(f"📊 Workflow contains {node_count} nodes")
            print(f"📊 Workflow contains {node_count} nodes")
        
    except json.JSONDecodeError as e:
        error_msg = f"❌ Invalid JSON in {WORKFLOW_FILE}: {e}"
        logger.error(error_msg)
        print(error_msg)
    except Exception as e:
        error_msg = f"❌ Failed to parse {WORKFLOW_FILE}: {e}"
        logger.error(error_msg)
        print(error_msg)
    
    return workflows

def inject_workflows_via_websocket(ws_url, workflows):
    """Inject workflows using WebSocket connection into chrome.storage.local only"""
    logger.info(f"🔗 Attempting WebSocket connection to: {ws_url[:50]}...")
    print(f"🔗 Connecting via WebSocket...")
    
    try:
        # Establish WebSocket connection
        logger.debug("Creating WebSocket connection...")
        ws = websocket.create_connection(ws_url)
        logger.info("✅ WebSocket connection established")
        print("✅ WebSocket connected")
        
        # Prepare workflows data
        workflows_data = {w["id"]: w for w in workflows}
        logger.info(f"📦 Preparing to upload {len(workflows)} workflow(s)")
        print(f"📦 Preparing {len(workflows)} workflow(s) for upload...")
        
        # Create storage injection script
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
        
        logger.debug("📤 Sending storage injection command...")
        print("📤 Injecting workflows into Chrome storage...")
        
        try:
            message = {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": storage_method}
            }
            ws.send(json.dumps(message))
            logger.debug("✅ Storage command sent, waiting for response...")
            
            result = json.loads(ws.recv())
            logger.debug(f"📥 Received response: {result}")
            
            if "result" in result and "result" in result["result"]:
                result_value = result["result"]["result"].get("value", "")
                if "chrome_storage_done" in result_value:
                    success_msg = "✅ Workflows successfully saved to chrome.storage.local"
                    logger.info(success_msg)
                    print(success_msg)
                elif "chrome_storage_unavailable" in result_value:
                    error_msg = "❌ Chrome storage API not available in this context"
                    logger.error(error_msg)
                    print(error_msg)
                else:
                    warning_msg = f"⚠️ Storage method executed but returned unexpected result: {result_value}"
                    logger.warning(warning_msg)
                    print(warning_msg)
            else:
                error_result = f"⚠️ Storage method had issues: {result}"
                logger.warning(error_result)
                print(error_result)
                
        except Exception as e:
            error_msg = f"❌ Storage injection failed: {e}"
            logger.error(error_msg)
            print(error_msg)
        
        # Attempt to refresh the page
        logger.info("🔄 Attempting to refresh the extension page...")
        print("🔄 Refreshing extension page...")
        
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
        refresh_result = ws.recv()
        logger.debug(f"📥 Refresh command result: {refresh_result}")
        
        # Close WebSocket connection
        ws.close()
        logger.info("🔌 WebSocket connection closed")
        
        final_msg = f"✅ Upload process completed for {len(workflows)} workflow(s)"
        logger.info(final_msg)
        print(final_msg)
        
    except websocket.WebSocketException as e:
        error_msg = f"❌ WebSocket error: {e}"
        logger.error(error_msg)
        print(error_msg)
    except Exception as e:
        error_msg = f"❌ Failed to inject workflows: {e}"
        logger.error(error_msg)
        print(error_msg)

def open_automa_extension():
    """Try to open Automa extension in a new tab"""
    logger.info("🚀 Attempting to open Automa extension...")
    print("🚀 Trying to open Automa extension...")
    
    try:
        tabs = get_chrome_tabs()
        extension_id = None
        
        # Try to find extension ID from existing tabs
        logger.debug("🔍 Searching for extension ID in existing tabs...")
        for tab in tabs:
            url = tab.get('url', '')
            if 'chrome-extension' in url and len(url.split('/')[2]) > 20:
                extension_id = url.split('/')[2]
                logger.info(f"📋 Found extension ID: {extension_id}")
                break
        
        if not extension_id:
            logger.warning("⚠️ Could not determine extension ID, using generic approach")
            print("⚠️ Extension ID not found, trying generic Chrome extensions page")
            extension_url = "chrome://extensions/"
        else:
            extension_url = f"chrome-extension://{extension_id}/src/newtab/index.html"
            logger.info(f"🎯 Target extension URL: {extension_url}")
        
        # Open new tab
        logger.debug(f"📤 Creating new tab with URL: {extension_url}")
        response = requests.get(f"{CHROME_DEBUG_URL}/new?{urllib.parse.quote(extension_url)}")
        new_tab = response.json()
        
        success_msg = f"✅ Opened Automa extension in new tab"
        logger.info(success_msg)
        print(success_msg)
        
        debugger_url = new_tab.get('webSocketDebuggerUrl')
        logger.info(f"🔗 New tab debugger URL: {debugger_url}")
        
        return debugger_url
        
    except Exception as e:
        error_msg = f"❌ Failed to open Automa extension: {e}"
        logger.error(error_msg)
        print(error_msg)
        return None

def print_completion_summary():
    """Print final completion summary"""
    summary = """
╔══════════════════════════════════════════════════════════════╗
║                     UPLOAD COMPLETED                        ║
╠══════════════════════════════════════════════════════════════╣
║  Next Steps:                                                 ║
║  1. Open Chrome GUI at http://localhost:6080/vnc.html       ║
║  2. Navigate to the Automa extension                         ║
║  3. Check if your workflow appears in the dashboard          ║
║  4. If not visible, try refreshing the page                  ║
║                                                              ║
║  Troubleshooting:                                            ║
║  • Check the log file for detailed error information         ║
║  • Ensure Chrome is running with debugging enabled          ║
║  • Verify the workflow file is valid JSON                   ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(summary)

def main():
    """Main execution function"""
    start_time = time.time()
    
    print_banner()
    logger.info("="*60)
    logger.info("STARTING AUTOMA WORKFLOW UPLOAD PROCESS")
    logger.info("="*60)
    
    print("🔄 Initializing workflow upload process...")
    logger.info(f"📁 Target workflow file: {WORKFLOW_FILE}")
    logger.info(f"🔗 Chrome DevTools URL: {CHROME_DEBUG_URL}")
    
    # Step 1: Load workflows
    logger.info("STEP 1: Loading workflow file")
    workflows = load_workflows()
    if not workflows:
        logger.error("❌ No workflows loaded, aborting process")
        print("❌ No workflows to upload, process aborted")
        return

    # Step 2: Find or create Automa context
    logger.info("STEP 2: Finding Automa extension context")
    debugger_url = find_automa_context()
    
    if not debugger_url:
        logger.info("STEP 2b: No context found, attempting to create one")
        print("⚠️ No Automa context found, trying to create one...")
        debugger_url = open_automa_extension()
        
        if not debugger_url:
            logger.info("STEP 2c: Still no context, using fallback method")
            print("⚠️ Still no context, trying with any available tab...")
            tabs = get_chrome_tabs()
            if tabs:
                debugger_url = tabs[0].get('webSocketDebuggerUrl')
                logger.info(f"Using fallback tab: {tabs[0].get('title')}")
            
    if not debugger_url:
        error_msg = "❌ Could not establish connection to Chrome - process aborted"
        logger.error(error_msg)
        print(error_msg)
        return

    # Step 3: Upload workflows
    logger.info("STEP 3: Uploading workflows via WebSocket")
    print(f"🔗 Using connection: {debugger_url[:50]}...")
    inject_workflows_via_websocket(debugger_url, workflows)
    
    # Calculate execution time
    execution_time = time.time() - start_time
    
    # Final summary
    logger.info("="*60)
    logger.info("UPLOAD PROCESS COMPLETED")
    logger.info(f"⏱️ Total execution time: {execution_time:.2f} seconds")
    logger.info(f"📊 Workflows processed: {len(workflows)}")
    logger.info("="*60)
    
    print_completion_summary()
    print(f"⏱️ Process completed in {execution_time:.2f} seconds")

if __name__ == "__main__":
    main()