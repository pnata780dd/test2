#!/usr/bin/env python3
"""
Automa Workflow CSV Exporter
Extracts workflows from Chrome storage and exports them to CSV format
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
OUTPUT_DIR = "/workspace/exports"

def print_banner():
    """Print startup banner"""
    print("=" * 60)
    print("🔄 AUTOMA WORKFLOW CSV EXPORTER")
    print("📊 Extracting workflows to CSV format")
    print("=" * 60)

def get_chrome_tabs() -> List[Dict]:
    """Get all Chrome tabs"""
    try:
        print("🔍 Connecting to Chrome DevTools...")
        response = requests.get(CHROME_DEBUG_URL, timeout=10)
        if response.status_code == 200:
            tabs = response.json()
            print(f"✅ Found {len(tabs)} Chrome contexts")
            return tabs
        else:
            print(f"❌ Chrome DevTools error: {response.status_code}")
            return []
    except requests.exceptions.ConnectError:
        print("❌ Cannot connect to Chrome - Is it running with --remote-debugging-port=9222?")
        return []
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return []

def find_automa_context() -> Optional[str]:
    """Find Automa extension context"""
    print("🎯 Looking for Automa extension...")
    tabs = get_chrome_tabs()
    
    if not tabs:
        return None
    
    # Show available contexts
    print("\n📋 Available contexts:")
    for i, tab in enumerate(tabs[:10]):  # Show first 10
        title = tab.get('title', 'Unknown')[:40]
        tab_type = tab.get('type', 'Unknown')
        print(f"  {i+1}. [{tab_type}] {title}")
    
    # Find Automa contexts
    for tab in tabs:
        # Background page
        if (tab.get('type') == 'background_page' and 
            'automa' in tab.get('title', '').lower()):
            print("✅ Found Automa background page")
            return tab.get('webSocketDebuggerUrl')
    
    # Extension pages
    for tab in tabs:
        url = tab.get('url', '').lower()
        if 'chrome-extension' in url and 'automa' in url:
            print("✅ Found Automa extension page")
            return tab.get('webSocketDebuggerUrl')
    
    # Any page with Automa
    for tab in tabs:
        if 'automa' in tab.get('title', '').lower():
            print("✅ Found Automa page")
            return tab.get('webSocketDebuggerUrl')
    
    print("⚠️ No Automa context found")
    return None

def extract_workflows_from_storage(ws_url: str) -> Dict[str, Any]:
    """Extract workflows from Chrome storage"""
    print("📤 Extracting workflows from chrome.storage.local...")
    
    try:
        ws = websocket.create_connection(ws_url)
        print("✅ WebSocket connected")
        
        # JavaScript to extract workflows
        extraction_script = """
        new Promise((resolve) => {
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                chrome.storage.local.get(['workflows'], (result) => {
                    const workflows = result.workflows || {};
                    resolve({
                        success: true,
                        count: Object.keys(workflows).length,
                        workflows: workflows,
                        timestamp: Date.now()
                    });
                });
            } else {
                resolve({
                    success: false,
                    error: 'Chrome storage not available',
                    workflows: {}
                });
            }
        })
        """
        
        # Send extraction command
        message = {
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": extraction_script,
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
                count = result_data.get("count", 0)
                print(f"✅ Successfully extracted {count} workflows")
                return result_data.get("workflows", {})
            else:
                print(f"❌ Extraction failed: {result_data.get('error', 'Unknown error')}")
                return {}
        else:
            print("❌ Invalid response from Chrome")
            return {}
            
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        return {}

def analyze_workflow_structure(workflows: Dict[str, Any]) -> Dict[str, set]:
    """Analyze workflow structure to determine CSV columns"""
    print("📊 Analyzing workflow structure...")
    
    all_fields = set()
    node_fields = set()
    
    for workflow_id, workflow in workflows.items():
        # Basic workflow fields
        for key in workflow.keys():
            if key != 'drawflow':
                all_fields.add(key)
        
        # Analyze nodes in drawflow
        if 'drawflow' in workflow and 'Home' in workflow['drawflow']:
            data = workflow['drawflow']['Home'].get('data', {})
            for node_id, node in data.items():
                if isinstance(node, dict):
                    for node_key in node.keys():
                        node_fields.add(f"node_{node_key}")
    
    print(f"📋 Found {len(all_fields)} workflow fields and {len(node_fields)} node fields")
    return {"workflow": all_fields, "nodes": node_fields}

def export_workflows_to_csv(workflows: Dict[str, Any], output_path: str) -> bool:
    """Export workflows to CSV file"""
    print(f"💾 Exporting workflows to CSV: {output_path}")
    
    if not workflows:
        print("❌ No workflows to export")
        return False
    
    try:
        # Prepare CSV data
        csv_rows = []
        
        for workflow_id, workflow in workflows.items():
            row = {
                'workflow_id': workflow_id,
                'name': workflow.get('name', 'Unnamed'),
                'description': workflow.get('description', ''),
                'created_at': workflow.get('createdAt', ''),
                'updated_at': workflow.get('updatedAt', ''),
                'is_disabled': workflow.get('isDisabled', False),
                'version': workflow.get('version', ''),
                'category': workflow.get('category', ''),
                'author': workflow.get('author', ''),
                'website': workflow.get('website', ''),
            }
            
            # Convert timestamps to readable format
            for time_field in ['created_at', 'updated_at']:
                if row[time_field] and str(row[time_field]).isdigit():
                    timestamp = int(row[time_field]) / 1000
                    row[time_field] = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            
            # Count nodes and connections
            node_count = 0
            connection_count = 0
            node_types = []
            
            if 'drawflow' in workflow and 'Home' in workflow['drawflow']:
                data = workflow['drawflow']['Home'].get('data', {})
                node_count = len(data)
                
                for node_id, node in data.items():
                    if isinstance(node, dict):
                        node_name = node.get('name', 'unknown')
                        if node_name not in node_types:
                            node_types.append(node_name)
                        
                        # Count outputs (connections)
                        outputs = node.get('outputs', {})
                        for output_key, output_data in outputs.items():
                            if isinstance(output_data, dict):
                                connections = output_data.get('connections', [])
                                connection_count += len(connections)
            
            row.update({
                'node_count': node_count,
                'connection_count': connection_count,
                'node_types': ', '.join(node_types[:5]),  # First 5 node types
                'complexity_score': node_count + connection_count,
            })
            
            # Add raw JSON for advanced users
            row['raw_json_size'] = len(json.dumps(workflow))
            row['has_settings'] = 'settings' in workflow
            row['has_trigger'] = any('trigger' in str(node).lower() for node in workflow.get('drawflow', {}).get('Home', {}).get('data', {}).values())
            
            csv_rows.append(row)
        
        # Write CSV
        if csv_rows:
            fieldnames = csv_rows[0].keys()
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_rows)
            
            print(f"✅ Successfully exported {len(csv_rows)} workflows to CSV")
            return True
        else:
            print("❌ No data to write to CSV")
            return False
            
    except Exception as e:
        print(f"❌ CSV export failed: {e}")
        return False

def export_detailed_workflows_json(workflows: Dict[str, Any], output_path: str) -> bool:
    """Export complete workflows as JSON for backup"""
    print(f"💾 Exporting detailed JSON backup: {output_path}")
    
    try:
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'export_version': '1.0',
            'workflow_count': len(workflows),
            'workflows': workflows
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ JSON backup exported successfully")
        return True
    except Exception as e:
        print(f"❌ JSON export failed: {e}")
        return False

def main():
    """Main export process"""
    start_time = time.time()
    print_banner()
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Find Automa context
    ws_url = find_automa_context()
    if not ws_url:
        print("❌ Cannot find Automa extension context")
        print("💡 Make sure Automa extension is installed and active")
        return
    
    # Extract workflows
    workflows = extract_workflows_from_storage(ws_url)
    if not workflows:
        print("❌ No workflows found or extraction failed")
        return
    
    print(f"📊 Processing {len(workflows)} workflows...")
    
    # Export to CSV
    csv_path = os.path.join(OUTPUT_DIR, f"automa_workflows_{timestamp}.csv")
    csv_success = export_workflows_to_csv(workflows, csv_path)
    
    # Export detailed JSON backup
    json_path = os.path.join(OUTPUT_DIR, f"automa_workflows_backup_{timestamp}.json")
    json_success = export_detailed_workflows_json(workflows, json_path)
    
    # Summary
    execution_time = time.time() - start_time
    print("\n" + "=" * 60)
    print("🎉 EXPORT COMPLETED")
    print("=" * 60)
    
    if csv_success:
        print(f"📊 CSV Export: {csv_path}")
    if json_success:
        print(f"💾 JSON Backup: {json_path}")
    
    print(f"⏱️ Export completed in {execution_time:.2f} seconds")
    print(f"📈 Total workflows: {len(workflows)}")
    
    # File size info
    if csv_success and os.path.exists(csv_path):
        csv_size = os.path.getsize(csv_path)
        print(f"📋 CSV file size: {csv_size:,} bytes")
    
    print("\n💡 You can now:")
    print("   • Open the CSV in Excel/Google Sheets for analysis")
    print("   • Use the JSON backup for importing workflows")
    print("   • Share the CSV for workflow documentation")

if __name__ == "__main__":
    main()