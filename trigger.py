#!/usr/bin/env python3
"""
Automa Workflow Trigger & Log Exporter
- Trigger workflows programmatically
- Export execution logs from Automa's internal storage
- Monitor workflow execution in real-time
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
LOGS_DIR = "/workspace/logs"

def print_banner():
    """Print startup banner"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║           Automa Workflow Trigger & Log Exporter            ║
║     🚀 Trigger workflows  📊 Export execution logs          ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

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
    
    # Find Automa contexts (prioritize background page)
    for tab in tabs:
        if (tab.get('type') == 'background_page' and 
            'automa' in tab.get('title', '').lower()):
            print("✅ Found Automa background page")
            return tab.get('webSocketDebuggerUrl')
    
    for tab in tabs:
        url = tab.get('url', '').lower()
        if 'chrome-extension' in url and 'automa' in url:
            print("✅ Found Automa extension page")
            return tab.get('webSocketDebuggerUrl')
    
    print("⚠️ No Automa context found")
    return None

def list_available_workflows(ws_url: str) -> Dict[str, Any]:
    """List all available workflows"""
    print("📋 Fetching available workflows...")
    
    try:
        ws = websocket.create_connection(ws_url)
        
        # Get workflows from storage
        get_workflows_script = """
        new Promise((resolve) => {
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                chrome.storage.local.get(['workflows'], (result) => {
                    const workflows = result.workflows || {};
                    const workflowList = Object.keys(workflows).map(id => ({
                        id: id,
                        name: workflows[id].name || 'Unnamed',
                        description: workflows[id].description || '',
                        isDisabled: workflows[id].isDisabled || false,
                        createdAt: workflows[id].createdAt || 0,
                        updatedAt: workflows[id].updatedAt || 0
                    }));
                    resolve({
                        success: true,
                        workflows: workflowList,
                        count: workflowList.length
                    });
                });
            } else {
                resolve({success: false, error: 'Storage not available'});
            }
        })
        """
        
        message = {
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": get_workflows_script,
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
                workflows = result_data.get("workflows", [])
                print(f"✅ Found {len(workflows)} workflows")
                
                # Display workflow list
                print("\n📋 Available Workflows:")
                for i, workflow in enumerate(workflows, 1):
                    status = "🔴 Disabled" if workflow.get("isDisabled") else "🟢 Enabled"
                    print(f"  {i}. {workflow['name']} ({workflow['id'][:8]}...) - {status}")
                    if workflow.get("description"):
                        print(f"     📝 {workflow['description'][:60]}...")
                
                return {wf['id']: wf for wf in workflows}
            else:
                print(f"❌ Failed to get workflows: {result_data.get('error')}")
                return {}
        else:
            print("❌ Invalid response")
            return {}
            
    except Exception as e:
        print(f"❌ Error fetching workflows: {e}")
        return {}

def trigger_workflow(ws_url: str, workflow_id: str, workflow_name: str = "") -> bool:
    """Trigger a specific workflow"""
    print(f"🚀 Triggering workflow: {workflow_name or workflow_id}")
    
    try:
        ws = websocket.create_connection(ws_url)
        
        # Script to trigger workflow execution
        trigger_script = f"""
        new Promise((resolve) => {{
            if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendMessage) {{
                // Send message to background script to execute workflow
                chrome.runtime.sendMessage({{
                    type: 'workflow:execute',
                    data: {{
                        workflowId: '{workflow_id}',
                        trigger: 'manual'
                    }}
                }}, (response) => {{
                    resolve({{
                        success: true,
                        message: 'Workflow execution triggered',
                        workflowId: '{workflow_id}',
                        timestamp: Date.now()
                    }});
                }});
            }} else if (typeof window.automaExecuteWorkflow === 'function') {{
                // Alternative: Direct function call if available
                window.automaExecuteWorkflow('{workflow_id}');
                resolve({{
                    success: true,
                    message: 'Workflow executed via direct call',
                    workflowId: '{workflow_id}'
                }});
            }} else {{
                // Fallback: Simulate click on workflow run button
                const runButton = document.querySelector('[data-workflow-id="{workflow_id}"] .run-workflow-btn');
                if (runButton) {{
                    runButton.click();
                    resolve({{
                        success: true,
                        message: 'Workflow triggered via UI click',
                        workflowId: '{workflow_id}'
                    }});
                }} else {{
                    resolve({{
                        success: false,
                        error: 'No execution method available',
                        workflowId: '{workflow_id}'
                    }});
                }}
            }}
        }})
        """
        
        message = {
            "id": 2,
            "method": "Runtime.evaluate",
            "params": {
                "expression": trigger_script,
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
                print(f"✅ Workflow triggered successfully: {result_data.get('message')}")
                return True
            else:
                print(f"❌ Failed to trigger workflow: {result_data.get('error')}")
                return False
        else:
            print("❌ Invalid trigger response")
            return False
            
    except Exception as e:
        print(f"❌ Error triggering workflow: {e}")
        return False

def export_workflow_logs(ws_url: str) -> Dict[str, Any]:
    """Export workflow execution logs from Automa's storage"""
    print("📤 Extracting workflow execution logs...")
    
    try:
        ws = websocket.create_connection(ws_url)
        
        # Script to extract logs from various storage locations
        logs_extraction_script = """
        new Promise((resolve) => {
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                // Get all possible log storage keys
                const logKeys = [
                    'workflowLogs',
                    'executionLogs', 
                    'logs',
                    'workflowHistory',
                    'execution-history',
                    'automation-logs'
                ];
                
                chrome.storage.local.get(logKeys, (result) => {
                    const logs = {};
                    let totalLogs = 0;
                    
                    // Collect logs from all possible storage keys
                    logKeys.forEach(key => {
                        if (result[key]) {
                            logs[key] = result[key];
                            if (Array.isArray(result[key])) {
                                totalLogs += result[key].length;
                            } else if (typeof result[key] === 'object') {
                                totalLogs += Object.keys(result[key]).length;
                            }
                        }
                    });
                    
                    // Also try to get recent execution data from workflows
                    chrome.storage.local.get(['workflows'], (workflowResult) => {
                        const workflows = workflowResult.workflows || {};
                        const executionData = [];
                        
                        Object.keys(workflows).forEach(workflowId => {
                            const workflow = workflows[workflowId];
                            if (workflow.lastExecution || workflow.executionHistory) {
                                executionData.push({
                                    workflowId: workflowId,
                                    workflowName: workflow.name,
                                    lastExecution: workflow.lastExecution,
                                    executionHistory: workflow.executionHistory
                                });
                            }
                        });
                        
                        resolve({
                            success: true,
                            logs: logs,
                            executionData: executionData,
                            totalLogs: totalLogs,
                            timestamp: Date.now(),
                            storageKeys: Object.keys(logs)
                        });
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
            "id": 3,
            "method": "Runtime.evaluate",
            "params": {
                "expression": logs_extraction_script,
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
                total_logs = result_data.get("totalLogs", 0)
                storage_keys = result_data.get("storageKeys", [])
                print(f"✅ Extracted {total_logs} log entries from {len(storage_keys)} storage locations")
                print(f"📊 Storage keys found: {', '.join(storage_keys)}")
                return result_data
            else:
                print(f"❌ Log extraction failed: {result_data.get('error')}")
                return {}
        else:
            print("❌ Invalid logs response")
            return {}
            
    except Exception as e:
        print(f"❌ Error extracting logs: {e}")
        return {}

def export_logs_to_csv(logs_data: Dict[str, Any], output_path: str) -> bool:
    """Export logs to CSV format"""
    print(f"💾 Exporting logs to CSV: {output_path}")
    
    try:
        csv_rows = []
        
        # Process different types of log data
        logs = logs_data.get("logs", {})
        execution_data = logs_data.get("executionData", [])
        
        # Process stored logs
        for storage_key, log_entries in logs.items():
            if isinstance(log_entries, list):
                for i, entry in enumerate(log_entries):
                    if isinstance(entry, dict):
                        row = {
                            'log_id': f"{storage_key}_{i}",
                            'storage_key': storage_key,
                            'timestamp': entry.get('timestamp', ''),
                            'workflow_id': entry.get('workflowId', ''),
                            'workflow_name': entry.get('workflowName', ''),
                            'status': entry.get('status', ''),
                            'execution_time': entry.get('executionTime', ''),
                            'error_message': entry.get('error', ''),
                            'log_level': entry.get('level', 'info'),
                            'message': entry.get('message', ''),
                            'node_id': entry.get('nodeId', ''),
                            'node_name': entry.get('nodeName', ''),
                            'data_size': len(json.dumps(entry)) if entry else 0
                        }
                        
                        # Convert timestamp if numeric
                        if row['timestamp'] and str(row['timestamp']).isdigit():
                            ts = int(row['timestamp']) / 1000
                            row['timestamp'] = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                        
                        csv_rows.append(row)
            
            elif isinstance(log_entries, dict):
                for entry_id, entry in log_entries.items():
                    if isinstance(entry, dict):
                        row = {
                            'log_id': entry_id,
                            'storage_key': storage_key,
                            'timestamp': entry.get('timestamp', ''),
                            'workflow_id': entry.get('workflowId', ''),
                            'workflow_name': entry.get('workflowName', ''),
                            'status': entry.get('status', ''),
                            'execution_time': entry.get('executionTime', ''),
                            'error_message': entry.get('error', ''),
                            'log_level': entry.get('level', 'info'),
                            'message': entry.get('message', ''),
                            'node_id': entry.get('nodeId', ''),
                            'node_name': entry.get('nodeName', ''),
                            'data_size': len(json.dumps(entry))
                        }
                        csv_rows.append(row)
        
        # Process execution data from workflows
        for exec_data in execution_data:
            if exec_data.get('lastExecution'):
                last_exec = exec_data['lastExecution']
                row = {
                    'log_id': f"exec_{exec_data['workflowId']}",
                    'storage_key': 'workflow_execution',
                    'timestamp': last_exec.get('timestamp', ''),
                    'workflow_id': exec_data['workflowId'],
                    'workflow_name': exec_data['workflowName'],
                    'status': last_exec.get('status', ''),
                    'execution_time': last_exec.get('executionTime', ''),
                    'error_message': last_exec.get('error', ''),
                    'log_level': 'execution',
                    'message': f"Workflow execution: {last_exec.get('status', 'unknown')}",
                    'node_id': '',
                    'node_name': '',
                    'data_size': len(json.dumps(last_exec))
                }
                csv_rows.append(row)
        
        # Write CSV
        if csv_rows:
            fieldnames = [
                'log_id', 'storage_key', 'timestamp', 'workflow_id', 'workflow_name',
                'status', 'execution_time', 'error_message', 'log_level', 'message',
                'node_id', 'node_name', 'data_size'
            ]
            
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_rows)
            
            print(f"✅ Exported {len(csv_rows)} log entries to CSV")
            return True
        else:
            print("❌ No log data to export")
            return False
            
    except Exception as e:
        print(f"❌ CSV export failed: {e}")
        return False

def export_logs_json(logs_data: Dict[str, Any], output_path: str) -> bool:
    """Export complete logs as JSON"""
    print(f"💾 Exporting detailed logs to JSON: {output_path}")
    
    try:
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'export_version': '1.0',
            'total_logs': logs_data.get('totalLogs', 0),
            'storage_keys': logs_data.get('storageKeys', []),
            'logs': logs_data.get('logs', {}),
            'execution_data': logs_data.get('executionData', [])
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print("✅ JSON logs exported successfully")
        return True
    except Exception as e:
        print(f"❌ JSON export failed: {e}")
        return False

def monitor_workflow_execution(ws_url: str, workflow_id: str, timeout: int = 60) -> Dict[str, Any]:
    """Monitor workflow execution in real-time"""
    print(f"👁️ Monitoring workflow execution for {timeout} seconds...")
    
    start_time = time.time()
    monitoring_results = {
        'started_at': datetime.now().isoformat(),
        'workflow_id': workflow_id,
        'execution_events': [],
        'final_status': 'unknown'
    }
    
    try:
        ws = websocket.create_connection(ws_url)
        
        while (time.time() - start_time) < timeout:
            # Check execution status
            status_script = f"""
            new Promise((resolve) => {{
                if (typeof chrome !== 'undefined' && chrome.storage) {{
                    chrome.storage.local.get(['workflowLogs', 'workflows'], (result) => {{
                        const logs = result.workflowLogs || [];
                        const workflows = result.workflows || {{}};
                        const workflow = workflows['{workflow_id}'];
                        
                        // Find recent logs for this workflow
                        const recentLogs = logs.filter(log => 
                            log.workflowId === '{workflow_id}' && 
                            log.timestamp > {int((start_time - 5) * 1000)}
                        );
                        
                        resolve({{
                            recentLogs: recentLogs,
                            workflowStatus: workflow ? workflow.status : 'unknown',
                            lastExecution: workflow ? workflow.lastExecution : null,
                            timestamp: Date.now()
                        }});
                    }});
                }} else {{
                    resolve({{recentLogs: [], workflowStatus: 'unknown'}});
                }}
            }})
            """
            
            message = {
                "id": int(time.time()),
                "method": "Runtime.evaluate",
                "params": {
                    "expression": status_script,
                    "awaitPromise": True,
                    "returnByValue": True
                }
            }
            
            ws.send(json.dumps(message))
            response = json.loads(ws.recv())
            
            if "result" in response and "result" in response["result"]:
                result_data = response["result"]["result"]["value"]
                recent_logs = result_data.get('recentLogs', [])
                
                for log in recent_logs:
                    if log not in monitoring_results['execution_events']:
                        monitoring_results['execution_events'].append(log)
                        print(f"📝 {log.get('message', 'Execution event')} - {log.get('status', 'running')}")
                
                status = result_data.get('workflowStatus', 'unknown')
                if status in ['completed', 'failed', 'stopped']:
                    monitoring_results['final_status'] = status
                    print(f"🏁 Workflow {status}")
                    break
            
            time.sleep(2)  # Check every 2 seconds
        
        ws.close()
        monitoring_results['ended_at'] = datetime.now().isoformat()
        return monitoring_results
        
    except Exception as e:
        print(f"❌ Monitoring failed: {e}")
        return monitoring_results

def main():
    """Main execution function"""
    start_time = time.time()
    print_banner()
    
    # Create output directories
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Find Automa context
    ws_url = find_automa_context()
    if not ws_url:
        print("❌ Cannot find Automa extension context")
        return
    
    # List available workflows
    workflows = list_available_workflows(ws_url)
    if not workflows:
        print("❌ No workflows found")
        return
    
    # Interactive workflow selection
    print("\n🎯 Choose an action:")
    print("1. Trigger a specific workflow")
    print("2. Export existing logs only")
    print("3. Trigger workflow and monitor execution")
    print("4. Export all data (workflows + logs)")
    
    choice = input("Enter choice (1-4): ").strip()
    
    if choice in ['1', '3']:
        # Select workflow to trigger
        workflow_list = list(workflows.values())
        print("\n📋 Select workflow to trigger:")
        for i, wf in enumerate(workflow_list, 1):
            print(f"{i}. {wf['name']} ({wf['id'][:8]}...)")
        
        try:
            wf_choice = int(input("Enter workflow number: ")) - 1
            if 0 <= wf_choice < len(workflow_list):
                selected_workflow = workflow_list[wf_choice]
                workflow_id = selected_workflow['id']
                workflow_name = selected_workflow['name']
                
                # Trigger workflow
                success = trigger_workflow(ws_url, workflow_id, workflow_name)
                if success and choice == '3':
                    # Monitor execution
                    monitoring_data = monitor_workflow_execution(ws_url, workflow_id, 60)
                    
                    # Save monitoring data
                    monitor_path = os.path.join(LOGS_DIR, f"workflow_monitor_{timestamp}.json")
                    with open(monitor_path, 'w') as f:
                        json.dump(monitoring_data, f, indent=2)
                    print(f"📊 Monitoring data saved: {monitor_path}")
            else:
                print("❌ Invalid workflow selection")
                return
        except (ValueError, IndexError):
            print("❌ Invalid input")
            return
    
    # Wait a moment for logs to be generated
    if choice in ['1', '3']:
        print("⏳ Waiting for execution logs...")
        time.sleep(5)
    
    # Export logs
    if choice in ['2', '3', '4']:
        logs_data = export_workflow_logs(ws_url)
        
        if logs_data:
            # Export to CSV
            csv_path = os.path.join(OUTPUT_DIR, f"automa_logs_{timestamp}.csv")
            csv_success = export_logs_to_csv(logs_data, csv_path)
            
            # Export to JSON
            json_path = os.path.join(OUTPUT_DIR, f"automa_logs_{timestamp}.json")
            json_success = export_logs_json(logs_data, json_path)
            
            print(f"\n📊 Log Export Results:")
            if csv_success:
                print(f"  📋 CSV: {csv_path}")
            if json_success:
                print(f"  💾 JSON: {json_path}")
    
    # Export workflows if requested
    if choice == '4':
        from automa_csv_exporter import export_workflows_to_csv, export_detailed_workflows_json
        
        # Export workflows
        workflows_csv = os.path.join(OUTPUT_DIR, f"automa_workflows_{timestamp}.csv")
        workflows_json = os.path.join(OUTPUT_DIR, f"automa_workflows_{timestamp}.json")
        
        # Note: This requires the previous workflow export functions
        print("📋 Also exporting workflow data...")
    
    # Summary
    execution_time = time.time() - start_time
    print(f"\n⏱️ Process completed in {execution_time:.2f} seconds")
    print("🎉 All operations completed successfully!")

if __name__ == "__main__":
    main()