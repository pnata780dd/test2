#!/usr/bin/env python3
"""
Automa Workflow Trigger & Log Exporter (Fixed Version)
- Trigger workflows using proper Chrome extension messaging (based on GitHub issue #1706)
- Export execution logs from Automa's internal storage
- Monitor workflow execution in real-time
- Enhanced workflow analysis and export capabilities
"""

import os
import json
import csv
import time
import requests
import websocket
from datetime import datetime
from typing import Dict, List, Any, Optional
from automa_csv_exporter import export_workflows_to_csv, export_detailed_workflows_json, analyze_workflow_structure, export_workflow_analysis

# Configuration
CHROME_DEBUG_URL = "http://localhost:9222/json"
OUTPUT_DIR = "/workspace/exports"
LOGS_DIR = "/workspace/logs"

def print_banner():
    """Print startup banner"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║           Automa Workflow Trigger & Log Exporter            ║
║     🚀 Fixed Triggering  📊 Export logs  📋 Analysis       ║
║            Based on GitHub Issue #1706 Solution             ║
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
def trigger_workflow_fixed(ws_url: str, workflow_id: str, workflow_name: str = "", variables: Dict = None) -> bool:
    """
    Trigger workflow using the fixed method from GitHub issue #1706
    This uses the proper Chrome extension messaging system
    """
    print(f"🚀 Triggering workflow (FIXED METHOD): {workflow_name or workflow_id}")
    if variables:
        print(f"📝 With variables: {variables}")
    
    try:
        ws = websocket.create_connection(ws_url)
        
        # Fixed trigger script based on GitHub issue solution
        variables_json = json.dumps(variables or {})
        trigger_script = f"""
        new Promise(async (resolve) => {{
            try {{
                // Helper functions from the GitHub issue solution
                const getWorkflow = async (id) => {{
                    const result = await chrome.storage.local.get('workflows');
                    const workflows = (result.workflows || {{}});
                    const workflowList = Object.keys(workflows)
                        .filter(workflowId => !workflows[workflowId].invisible)
                        .map(workflowId => workflows[workflowId]);
                    
                    if (id) {{
                        return workflowList.find(workflow => workflow.id === id);
                    }}
                    return workflowList;
                }};
                
                const sendMessage = (event, options, type) => {{
                    let message = {{ 
                        name: type ? type + '--' + event : event, 
                        data: options 
                    }};
                    return chrome.runtime.sendMessage(message);
                }};
                
                // Main execution function (from GitHub issue solution)
                const executeWorkflow = async (id, variables) => {{
                    try {{
                        const data = {{ 
                            workflowId: id, 
                            workflowOptions: {{ data: {{ variables: variables || {{}} }} }} 
                        }};
                        
                        const workflow = await getWorkflow(data.workflowId);
                        if (!workflow) {{
                            throw new Error(`Can't find workflow with ${{data.workflowId}} Id`);
                        }}
                        
                        const options = data.workflowOptions;
                        const result = await sendMessage('workflow:execute', {{ ...workflow, options: options }}, 'background');
                        
                        return {{
                            success: true,
                            message: 'Workflow execution triggered successfully',
                            workflowId: id,
                            workflowName: workflow.name,
                            result: result,
                            timestamp: Date.now()
                        }};
                    }} catch (error) {{
                        return {{
                            success: false,
                            error: error.message,
                            workflowId: id
                        }};
                    }}
                }};
                
                // Execute the workflow
                const variables = {variables_json};
                const result = await executeWorkflow('{workflow_id}', variables);
                resolve(result);
                
            }} catch (error) {{
                resolve({{
                    success: false,
                    error: error.message,
                    workflowId: '{workflow_id}'
                }});
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
                print(f"✅ Workflow triggered successfully!")
                print(f"   📋 Workflow: {result_data.get('workflowName', workflow_name)}")
                print(f"   🆔 ID: {result_data.get('workflowId', workflow_id)}")
                print(f"   ⏰ Timestamp: {datetime.fromtimestamp(result_data.get('timestamp', 0) / 1000).strftime('%Y-%m-%d %H:%M:%S')}")
                return True
            else:
                error_msg = result_data.get('error', 'Unknown error')
                print(f"❌ Failed to trigger workflow: {error_msg}")
                return False
        else:
            print("❌ Invalid trigger response")
            return False
            
    except Exception as e:
        print(f"❌ Error triggering workflow: {e}")
        return False

def export_workflow_logs(ws_url: str) -> Dict[str, Any]:
    """Export workflow execution logs from Automa's storage (enhanced version)"""
    print("📤 Extracting workflow execution logs...")
    
    try:
        ws = websocket.create_connection(ws_url)
        
        # Enhanced logs extraction script
        logs_extraction_script = """
        new Promise((resolve) => {
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                // Comprehensive list of potential log storage keys
                const logKeys = [
                    'workflowLogs',
                    'executionLogs', 
                    'logs',
                    'workflowHistory',
                    'execution-history',
                    'automation-logs',
                    'workflow-executions',
                    'debugLogs',
                    'errorLogs',
                    'workflow-results'
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
                    
                    // Get execution data from workflows
                    chrome.storage.local.get(['workflows'], (workflowResult) => {
                        const workflows = workflowResult.workflows || {};
                        const executionData = [];
                        
                        Object.keys(workflows).forEach(workflowId => {
                            const workflow = workflows[workflowId];
                            const executionInfo = {
                                workflowId: workflowId,
                                workflowName: workflow.name || 'Unnamed',
                                lastExecution: workflow.lastExecution || null,
                                executionHistory: workflow.executionHistory || null,
                                executionCount: workflow.executionCount || 0,
                                totalExecutionTime: workflow.totalExecutionTime || 0,
                                avgExecutionTime: workflow.avgExecutionTime || 0,
                                lastError: workflow.lastError || null,
                                successRate: workflow.successRate || null
                            };
                            
                            if (executionInfo.lastExecution || executionInfo.executionHistory) {
                                executionData.push(executionInfo);
                            }
                        });
                        
                        resolve({
                            success: true,
                            logs: logs,
                            executionData: executionData,
                            totalLogs: totalLogs,
                            timestamp: Date.now(),
                            storageKeys: Object.keys(logs),
                            workflowsWithExecutionData: executionData.length
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
                execution_workflows = result_data.get("workflowsWithExecutionData", 0)
                
                print(f"✅ Extracted {total_logs} log entries from {len(storage_keys)} storage locations")
                print(f"📊 Found execution data for {execution_workflows} workflows")
                if storage_keys:
                    print(f"🔑 Storage keys found: {', '.join(storage_keys)}")
                
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
    """Export logs to CSV format (enhanced version)"""
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
                            'node_type': entry.get('nodeType', ''),
                            'execution_context': entry.get('executionContext', ''),
                            'data_size': len(json.dumps(entry)) if entry else 0,
                            'success_count': entry.get('successCount', ''),
                            'failure_count': entry.get('failureCount', ''),
                            'trigger_type': entry.get('triggerType', '')
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
                            'node_type': entry.get('nodeType', ''),
                            'execution_context': entry.get('executionContext', ''),
                            'data_size': len(json.dumps(entry)),
                            'success_count': entry.get('successCount', ''),
                            'failure_count': entry.get('failureCount', ''),
                            'trigger_type': entry.get('triggerType', '')
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
                    'node_type': '',
                    'execution_context': 'workflow',
                    'data_size': len(json.dumps(last_exec)),
                    'success_count': exec_data.get('executionCount', ''),
                    'failure_count': '',
                    'trigger_type': last_exec.get('triggerType', 'manual')
                }
                
                # Convert timestamp if numeric
                if row['timestamp'] and str(row['timestamp']).isdigit():
                    ts = int(row['timestamp']) / 1000
                    row['timestamp'] = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                
                csv_rows.append(row)
        
        # Write CSV
        if csv_rows:
            fieldnames = [
                'log_id', 'storage_key', 'timestamp', 'workflow_id', 'workflow_name',
                'status', 'execution_time', 'error_message', 'log_level', 'message',
                'node_id', 'node_name', 'node_type', 'execution_context', 'data_size',
                'success_count', 'failure_count', 'trigger_type'
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
    """Export complete logs as JSON (enhanced version)"""
    print(f"💾 Exporting detailed logs to JSON: {output_path}")
    
    try:
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'export_version': '2.0',
            'total_logs': logs_data.get('totalLogs', 0),
            'storage_keys': logs_data.get('storageKeys', []),
            'workflows_with_execution_data': logs_data.get('workflowsWithExecutionData', 0),
            'logs': logs_data.get('logs', {}),
            'execution_data': logs_data.get('executionData', []),
            'metadata': {
                'extraction_timestamp': logs_data.get('timestamp'),
                'chrome_extension': 'Automa',
                'export_tool': 'automa_workflow_trigger_fixed.py'
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print("✅ JSON logs exported successfully")
        return True
    except Exception as e:
        print(f"❌ JSON export failed: {e}")
        return False

def monitor_workflow_execution(ws_url: str, workflow_id: str, timeout: int = 60) -> Dict[str, Any]:
    """Monitor workflow execution in real-time (enhanced version)"""
    print(f"👁️ Monitoring workflow execution for {timeout} seconds...")
    
    start_time = time.time()
    monitoring_results = {
        'started_at': datetime.now().isoformat(),
        'workflow_id': workflow_id,
        'execution_events': [],
        'final_status': 'unknown',
        'execution_timeline': [],
        'performance_metrics': {
            'total_execution_time': 0,
            'nodes_executed': 0,
            'errors_encountered': 0,
            'data_processed': 0
        }
    }
    
    try:
        ws = websocket.create_connection(ws_url)
        
        last_log_count = 0
        
        while (time.time() - start_time) < timeout:
            # Enhanced status checking script
            status_script = f"""
            new Promise((resolve) => {{
                if (typeof chrome !== 'undefined' && chrome.storage) {{
                    chrome.storage.local.get(['workflowLogs', 'workflows', 'executionLogs'], (result) => {{
                        const logs = result.workflowLogs || [];
                        const execLogs = result.executionLogs || [];
                        const workflows = result.workflows || {{}};
                        const workflow = workflows['{workflow_id}'];
                        
                        // Find recent logs for this workflow
                        const startTime = {int((start_time - 5) * 1000)};
                        const recentLogs = [...logs, ...execLogs].filter(log => 
                            log.workflowId === '{workflow_id}' && 
                            log.timestamp > startTime
                        );
                        
                        // Sort by timestamp
                        recentLogs.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
                        
                        // Calculate performance metrics
                        const nodeExecutions = recentLogs.filter(log => log.nodeId);
                        const errors = recentLogs.filter(log => log.level === 'error' || log.status === 'error');
                        
                        resolve({{
                            recentLogs: recentLogs,
                            workflowStatus: workflow ? (workflow.status || workflow.state) : 'unknown',
                            lastExecution: workflow ? workflow.lastExecution : null,
                            currentExecution: workflow ? workflow.currentExecution : null,
                            timestamp: Date.now(),
                            nodeExecutions: nodeExecutions.length,
                            errorCount: errors.length,
                            totalLogs: recentLogs.length
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
                
                # Process new logs
                new_logs = recent_logs[last_log_count:]
                for log in new_logs:
                    if log not in monitoring_results['execution_events']:
                        monitoring_results['execution_events'].append(log)
                        
                        # Create timeline entry
                        timeline_entry = {
                            'timestamp': log.get('timestamp'),
                            'event': log.get('message', 'Execution event'),
                            'status': log.get('status', 'running'),
                            'node_id': log.get('nodeId', ''),
                            'node_name': log.get('nodeName', ''),
                            'execution_time': log.get('executionTime', 0)
                        }
                        monitoring_results['execution_timeline'].append(timeline_entry)
                        
                        # Display progress
                        timestamp_str = ""
                        if log.get('timestamp') and str(log.get('timestamp')).isdigit():
                            ts = int(log.get('timestamp')) / 1000
                            timestamp_str = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
                        
                        node_info = ""
                        if log.get('nodeId'):
                            node_info = f" [{log.get('nodeName', log.get('nodeId', '')[:8])}]"
                        
                        print(f"📝 {timestamp_str} {log.get('message', 'Event')}{node_info} - {log.get('status', 'running')}")
                
                last_log_count = len(recent_logs)
                
                # Update performance metrics
                monitoring_results['performance_metrics']['nodes_executed'] = result_data.get('nodeExecutions', 0)
                monitoring_results['performance_metrics']['errors_encountered'] = result_data.get('errorCount', 0)
                
                # Check workflow status
                status = result_data.get('workflowStatus', 'unknown')
                current_exec = result_data.get('currentExecution')
                
                if status in ['completed', 'failed', 'stopped', 'finished', 'error']:
                    monitoring_results['final_status'] = status
                    print(f"🏁 Workflow {status}")
                    break
                elif current_exec and current_exec.get('status') in ['completed', 'failed', 'stopped']:
                    monitoring_results['final_status'] = current_exec.get('status')
                    print(f"🏁 Workflow {current_exec.get('status')}")
                    break
            
            time.sleep(2)  # Check every 2 seconds
        
        ws.close()
        
        # Calculate final metrics
        end_time = time.time()
        monitoring_results['ended_at'] = datetime.now().isoformat()
        monitoring_results['performance_metrics']['total_execution_time'] = end_time - start_time
        
        # Summary
        metrics = monitoring_results['performance_metrics']
        print(f"\n📊 Execution Summary:")
        print(f"   ⏱️  Total Time: {metrics['total_execution_time']:.2f}s")
        print(f"   🔧 Nodes Executed: {metrics['nodes_executed']}")
        print(f"   ❌ Errors: {metrics['errors_encountered']}")
        print(f"   📝 Total Events: {len(monitoring_results['execution_events'])}")
        
        return monitoring_results
        
    except Exception as e:
        print(f"❌ Monitoring failed: {e}")
        monitoring_results['error'] = str(e)
        return monitoring_results

def main():
    """Main execution function (enhanced)"""
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
        print("💡 Make sure Chrome is running with: --remote-debugging-port=9222")
        print("💡 And that Automa extension is installed and active")
        return
    
    # List available workflows
    workflows = list_available_workflows(ws_url)
    if not workflows:
        print("❌ No workflows found")
        print("💡 Make sure you have workflows created in Automa extension")
        return
    
    # Interactive workflow selection
    print("\n🎯 Choose an action:")
    print("1. Trigger a specific workflow (FIXED METHOD)")
    print("2. Export existing logs only")
    print("3. Trigger workflow and monitor execution")
    print("4. Export all data (workflows + logs + analysis)")
    print("5. Analyze workflow structure")
    print("6. Trigger workflow with custom variables")
    
    choice = input("Enter choice (1-6): ").strip()
    
    workflow_id = None
    workflow_name = None
    variables = None
    
    if choice in ['1', '3', '6']:
        # Select workflow to trigger
        workflow_list = list(workflows.values())
        print("\n📋 Select workflow to trigger:")
        for i, wf in enumerate(workflow_list, 1):
            status = "🔴 Disabled" if wf.get("isDisabled") else "🟢 Enabled"
            print(f"{i}. {wf['name']} ({wf['id'][:8]}...) - {status}")
        
        try:
            wf_choice = int(input("Enter workflow number: ")) - 1
            if 0 <= wf_choice < len(workflow_list):
                selected_workflow = workflow_list[wf_choice]
                workflow_id = selected_workflow['id']
                workflow_name = selected_workflow['name']
                
                # Check if workflow is disabled
                if selected_workflow.get('isDisabled'):
                    print("⚠️ Warning: Selected workflow is disabled!")
                    confirm = input("Continue anyway? (y/N): ").strip().lower()
                    if confirm != 'y':
                        print("❌ Operation cancelled")
                        return
                
                # Get custom variables if requested
                if choice == '6':
                    print("\n📝 Enter workflow variables (JSON format, or press Enter for none):")
                    variables_input = input("Variables: ").strip()
                    if variables_input:
                        try:
                            variables = json.loads(variables_input)
                            print(f"✅ Variables parsed: {variables}")
                        except json.JSONDecodeError:
                            print("❌ Invalid JSON format, proceeding without variables")
                            variables = None
                
                # Trigger workflow using FIXED method
                success = trigger_workflow_fixed(ws_url, workflow_id, workflow_name, variables)
                
                if success and choice == '3':
                    # Monitor execution
                    monitoring_data = monitor_workflow_execution(ws_url, workflow_id, 60)
                    
                    # Save monitoring data
                    monitor_path = os.path.join(LOGS_DIR, f"workflow_monitor_{timestamp}.json")
                    with open(monitor_path, 'w') as f:
                        json.dump(monitoring_data, f, indent=2)
                    print(f"📊 Monitoring data saved: {monitor_path}")
                
                if not success:
                    print("❌ Workflow triggering failed, but continuing with log export...")
            else:
                print("❌ Invalid workflow selection")
                return
        except (ValueError, IndexError):
            print("❌ Invalid input")
            return
    
    # Wait for logs to be generated
    if choice in ['1', '3', '6']:
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
    
    # Workflow analysis
    if choice in ['4', '5']:
        print("\n🔍 Analyzing workflow structure...")
        analysis_data = analyze_workflow_structure(ws_url)
        
        if analysis_data:
            analysis_path = os.path.join(OUTPUT_DIR, f"workflow_analysis_{timestamp}.json")
            export_workflow_analysis(analysis_data, analysis_path)
    
    # Export workflows if full export requested
    if choice == '4':
        print("\n📋 Exporting workflow data...")
        
        # Export workflows to CSV
        workflows_csv = os.path.join(OUTPUT_DIR, f"automa_workflows_{timestamp}.csv")
        csv_wf_success = export_workflows_to_csv(ws_url, workflows_csv)
        
        # Export detailed workflows to JSON
        workflows_json = os.path.join(OUTPUT_DIR, f"automa_workflows_detailed_{timestamp}.json")
        json_wf_success = export_detailed_workflows_json(ws_url, workflows_json)
        
        print(f"\n📋 Workflow Export Results:")
        if csv_wf_success:
            print(f"  📊 Workflows CSV: {workflows_csv}")
        if json_wf_success:
            print(f"  💾 Detailed JSON: {workflows_json}")
    
    # Summary
    execution_time = time.time() - start_time
    print(f"\n⏱️ Process completed in {execution_time:.2f} seconds")
    print("🎉 All operations completed successfully!")
    
    # Final tips
    print(f"\n💡 Tips:")
    print(f"   📁 All exports saved to: {OUTPUT_DIR}")
    print(f"   📊 Monitoring logs in: {LOGS_DIR}")
    print(f"   🔧 This version uses the FIXED triggering method from GitHub issue #1706")

if __name__ == "__main__":
    main()