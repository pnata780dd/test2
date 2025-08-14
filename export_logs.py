#!/usr/bin/env python3
"""
Automa Workflow Log Exporter
- Export logs from Automa's Dexie/IndexedDB storage
- Filter logs by workflow ID
- Export in multiple formats (CSV, JSON, Excel)
- Analyze execution patterns and performance metrics
- Based on Automa's actual log storage structure
"""

import os
import json
import csv
import time
import requests
import websocket
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict, Counter

# Configuration
CHROME_DEBUG_URL = "http://localhost:9222/json"
OUTPUT_DIR = "/workspace/exports/logs"
BATCH_SIZE = 1000  # Process logs in batches to avoid memory issues

def print_banner():
    """Print startup banner"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                Automa Workflow Log Exporter                 ║
║     📊 Export Logs  🔍 Filter by Workflow  📈 Analytics    ║
║              Based on Automa's Dexie Database               ║
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

def get_available_workflows(ws_url: str) -> Dict[str, Any]:
    """Get list of available workflows with their basic info"""
    print("📋 Fetching available workflows...")
    
    try:
        ws = websocket.create_connection(ws_url)
        
        script = """
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
                        updatedAt: workflows[id].updatedAt || 0,
                        executionCount: workflows[id].executionCount || 0
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
                "expression": script,
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
                    exec_count = workflow.get("executionCount", 0)
                    print(f"  {i}. {workflow['name']} ({workflow['id'][:8]}...) - {status} - {exec_count} executions")
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

def extract_dexie_logs(ws_url: str, workflow_id: str = None, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """Extract logs from Automa's Dexie database"""
    print(f"📤 Extracting logs from Automa's Dexie database...")
    if workflow_id:
        print(f"🎯 Filtering by workflow ID: {workflow_id}")
    if start_date or end_date:
        print(f"📅 Date range: {start_date} to {end_date}")
    
    try:
        ws = websocket.create_connection(ws_url)
        
        # Build date filter conditions
        date_filter = ""
        if start_date:
            start_timestamp = int(datetime.fromisoformat(start_date.replace('Z', '+00:00')).timestamp() * 1000)
            date_filter += f" && item.startedAt >= {start_timestamp}"
        if end_date:
            end_timestamp = int(datetime.fromisoformat(end_date.replace('Z', '+00:00')).timestamp() * 1000)
            date_filter += f" && item.endedAt <= {end_timestamp}"
        
        # Workflow filter
        workflow_filter = f" && item.workflowId === '{workflow_id}'" if workflow_id else ""
        
        # Enhanced Dexie logs extraction script based on the schema you provided
        logs_script = f"""
        new Promise(async (resolve) => {{
            try {{
                // Check if we're in the right context with access to the logs database
                if (typeof Dexie === 'undefined') {{
                    // Try to access through window or global context
                    const checkGlobal = () => {{
                        return window.dbLogs || window.Dexie || globalThis.dbLogs;
                    }};
                    
                    const dbLogs = checkGlobal();
                    if (!dbLogs) {{
                        resolve({{
                            success: false,
                            error: 'Dexie database not accessible in this context'
                        }});
                        return;
                    }}
                }}
                
                // Access the logs database - based on your schema
                let dbLogs;
                try {{
                    // Try different ways to access the database
                    if (typeof window !== 'undefined' && window.dbLogs) {{
                        dbLogs = window.dbLogs;
                    }} else if (typeof globalThis !== 'undefined' && globalThis.dbLogs) {{
                        dbLogs = globalThis.dbLogs;
                    }} else {{
                        // Create database connection using the schema you provided
                        dbLogs = new Dexie('logs');
                        dbLogs.version(1).stores({{
                            ctxData: '++id, logId',
                            logsData: '++id, logId',
                            histories: '++id, logId',
                            items: '++id, name, endedAt, workflowId, status, collectionId'
                        }});
                    }}
                }} catch (error) {{
                    resolve({{
                        success: false,
                        error: 'Failed to connect to logs database: ' + error.message
                    }});
                    return;
                }}
                
                // Extract data from all tables
                const [items, ctxData, logsData, histories] = await Promise.all([
                    dbLogs.items.where(item => {{
                        return true{workflow_filter}{date_filter};
                    }}).toArray(),
                    dbLogs.ctxData.toArray(),
                    dbLogs.logsData.toArray(),
                    dbLogs.histories.toArray()
                ]);
                
                // Get log details for each item
                const enrichedItems = await Promise.all(
                    items.map(async (item) => {{
                        try {{
                            // Get associated context data
                            const itemCtxData = ctxData.filter(ctx => ctx.logId === item.id);
                            
                            // Get associated logs data
                            const itemLogsData = logsData.filter(log => log.logId === item.id);
                            
                            // Get associated histories
                            const itemHistories = histories.filter(hist => hist.logId === item.id);
                            
                            return {{
                                ...item,
                                ctxData: itemCtxData,
                                logsData: itemLogsData,
                                histories: itemHistories,
                                executionTime: item.endedAt - item.startedAt,
                                formattedStartTime: new Date(item.startedAt).toISOString(),
                                formattedEndTime: new Date(item.endedAt).toISOString()
                            }};
                        }} catch (error) {{
                            console.warn('Error enriching item:', item.id, error);
                            return {{
                                ...item,
                                ctxData: [],
                                logsData: [],
                                histories: [],
                                executionTime: item.endedAt - item.startedAt,
                                formattedStartTime: new Date(item.startedAt).toISOString(),
                                formattedEndTime: new Date(item.endedAt).toISOString(),
                                enrichmentError: error.message
                            }};
                        }}
                    }})
                );
                
                // Calculate statistics
                const stats = {{
                    totalLogs: enrichedItems.length,
                    successfulExecutions: enrichedItems.filter(item => item.status === 'success').length,
                    failedExecutions: enrichedItems.filter(item => item.status === 'error' || item.status === 'failed').length,
                    uniqueWorkflows: [...new Set(enrichedItems.map(item => item.workflowId))].length,
                    dateRange: {{
                        earliest: enrichedItems.length > 0 ? Math.min(...enrichedItems.map(item => item.startedAt)) : null,
                        latest: enrichedItems.length > 0 ? Math.max(...enrichedItems.map(item => item.endedAt)) : null
                    }},
                    totalExecutionTime: enrichedItems.reduce((sum, item) => sum + (item.executionTime || 0), 0),
                    averageExecutionTime: enrichedItems.length > 0 ? 
                        enrichedItems.reduce((sum, item) => sum + (item.executionTime || 0), 0) / enrichedItems.length : 0
                }};
                
                resolve({{
                    success: true,
                    logs: enrichedItems,
                    statistics: stats,
                    totalCtxData: ctxData.length,
                    totalLogsData: logsData.length,
                    totalHistories: histories.length,
                    extractedAt: Date.now(),
                    filters: {{
                        workflowId: '{workflow_id}' || null,
                        startDate: '{start_date}' || null,
                        endDate: '{end_date}' || null
                    }}
                }});
                
            }} catch (error) {{
                resolve({{
                    success: false,
                    error: error.message,
                    stack: error.stack
                }});
            }}
        }})
        """
        
        message = {
            "id": 2,
            "method": "Runtime.evaluate",
            "params": {
                "expression": logs_script,
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
                stats = result_data.get("statistics", {})
                total_logs = stats.get("totalLogs", 0)
                successful = stats.get("successfulExecutions", 0)
                failed = stats.get("failedExecutions", 0)
                
                print(f"✅ Extracted {total_logs} log entries")
                print(f"📊 Success rate: {successful}/{total_logs} ({(successful/total_logs*100) if total_logs > 0 else 0:.1f}%)")
                print(f"❌ Failed executions: {failed}")
                print(f"🔧 Unique workflows: {stats.get('uniqueWorkflows', 0)}")
                
                if stats.get('dateRange', {}).get('earliest'):
                    earliest = datetime.fromtimestamp(stats['dateRange']['earliest'] / 1000)
                    latest = datetime.fromtimestamp(stats['dateRange']['latest'] / 1000)
                    print(f"📅 Date range: {earliest.strftime('%Y-%m-%d %H:%M')} to {latest.strftime('%Y-%m-%d %H:%M')}")
                
                avg_time = stats.get('averageExecutionTime', 0) / 1000  # Convert to seconds
                print(f"⏱️  Average execution time: {avg_time:.2f}s")
                
                return result_data
            else:
                error_msg = result_data.get('error', 'Unknown error')
                print(f"❌ Log extraction failed: {error_msg}")
                if 'stack' in result_data:
                    print(f"🔍 Stack trace: {result_data['stack'][:200]}...")
                return {}
        else:
            print("❌ Invalid response from Dexie extraction")
            return {}
            
    except Exception as e:
        print(f"❌ Error extracting Dexie logs: {e}")
        return {}

def export_logs_to_csv(logs_data: Dict[str, Any], output_path: str, workflow_name: str = None) -> bool:
    """Export logs to CSV format with detailed information"""
    print(f"💾 Exporting logs to CSV: {output_path}")
    
    try:
        logs = logs_data.get("logs", [])
        
        if not logs:
            print("❌ No logs to export")
            return False
        
        csv_rows = []
        
        for log_item in logs:
            # Basic log information
            base_row = {
                'log_id': log_item.get('id', ''),
                'workflow_id': log_item.get('workflowId', ''),
                'workflow_name': workflow_name or log_item.get('workflowName', ''),
                'execution_name': log_item.get('name', ''),
                'status': log_item.get('status', ''),
                'started_at': log_item.get('formattedStartTime', ''),
                'ended_at': log_item.get('formattedEndTime', ''),
                'execution_time_ms': log_item.get('executionTime', 0),
                'execution_time_s': round((log_item.get('executionTime', 0) / 1000), 3),
                'parent_log': log_item.get('parentLog', ''),
                'collection_id': log_item.get('collectionId', ''),
                'message': log_item.get('message', ''),
                'ctx_data_count': len(log_item.get('ctxData', [])),
                'logs_data_count': len(log_item.get('logsData', [])),
                'histories_count': len(log_item.get('histories', [])),
                'enrichment_error': log_item.get('enrichmentError', '')
            }
            
            # If there are detailed logs, create separate rows for each
            logs_data_items = log_item.get('logsData', [])
            if logs_data_items:
                for log_detail in logs_data_items:
                    detail_row = base_row.copy()
                    detail_row.update({
                        'detail_type': 'log_data',
                        'detail_id': log_detail.get('id', ''),
                        'detail_data': json.dumps(log_detail, default=str)[:500]  # Truncate long data
                    })
                    csv_rows.append(detail_row)
            
            # Add context data details
            ctx_data_items = log_item.get('ctxData', [])
            if ctx_data_items:
                for ctx_detail in ctx_data_items:
                    detail_row = base_row.copy()
                    detail_row.update({
                        'detail_type': 'ctx_data',
                        'detail_id': ctx_detail.get('id', ''),
                        'detail_data': json.dumps(ctx_detail, default=str)[:500]
                    })
                    csv_rows.append(detail_row)
            
            # Add histories details
            history_items = log_item.get('histories', [])
            if history_items:
                for history_detail in history_items:
                    detail_row = base_row.copy()
                    detail_row.update({
                        'detail_type': 'history',
                        'detail_id': history_detail.get('id', ''),
                        'detail_data': json.dumps(history_detail, default=str)[:500]
                    })
                    csv_rows.append(detail_row)
            
            # If no detailed data, add the base row
            if not logs_data_items and not ctx_data_items and not history_items:
                base_row.update({
                    'detail_type': 'main',
                    'detail_id': '',
                    'detail_data': ''
                })
                csv_rows.append(base_row)
        
        # Write CSV
        if csv_rows:
            fieldnames = [
                'log_id', 'workflow_id', 'workflow_name', 'execution_name', 'status',
                'started_at', 'ended_at', 'execution_time_ms', 'execution_time_s',
                'parent_log', 'collection_id', 'message', 'ctx_data_count',
                'logs_data_count', 'histories_count', 'detail_type', 'detail_id',
                'detail_data', 'enrichment_error'
            ]
            
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_rows)
            
            print(f"✅ Exported {len(csv_rows)} log entries to CSV")
            return True
        else:
            print("❌ No processed log data to export")
            return False
            
    except Exception as e:
        print(f"❌ CSV export failed: {e}")
        return False

def export_logs_to_json(logs_data: Dict[str, Any], output_path: str, workflow_name: str = None) -> bool:
    """Export complete logs as structured JSON"""
    print(f"💾 Exporting logs to JSON: {output_path}")
    
    try:
        export_data = {
            'export_metadata': {
                'exported_at': datetime.now().isoformat(),
                'exporter_version': '1.0',
                'workflow_name': workflow_name,
                'total_logs': len(logs_data.get('logs', [])),
                'extraction_timestamp': logs_data.get('extractedAt'),
                'filters_applied': logs_data.get('filters', {})
            },
            'statistics': logs_data.get('statistics', {}),
            'raw_counts': {
                'total_ctx_data': logs_data.get('totalCtxData', 0),
                'total_logs_data': logs_data.get('totalLogsData', 0),
                'total_histories': logs_data.get('totalHistories', 0)
            },
            'logs': logs_data.get('logs', [])
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
        
        print("✅ JSON export completed successfully")
        return True
    except Exception as e:
        print(f"❌ JSON export failed: {e}")
        return False

def export_logs_to_excel(logs_data: Dict[str, Any], output_path: str, workflow_name: str = None) -> bool:
    """Export logs to Excel with multiple sheets"""
    print(f"💾 Exporting logs to Excel: {output_path}")
    
    try:
        logs = logs_data.get('logs', [])
        
        if not logs:
            print("❌ No logs to export")
            return False
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Main summary sheet
            summary_data = []
            for log_item in logs:
                summary_data.append({
                    'Log ID': log_item.get('id', ''),
                    'Workflow ID': log_item.get('workflowId', ''),
                    'Workflow Name': workflow_name or log_item.get('workflowName', ''),
                    'Execution Name': log_item.get('name', ''),
                    'Status': log_item.get('status', ''),
                    'Started At': log_item.get('formattedStartTime', ''),
                    'Ended At': log_item.get('formattedEndTime', ''),
                    'Execution Time (s)': round((log_item.get('executionTime', 0) / 1000), 3),
                    'Parent Log': log_item.get('parentLog', ''),
                    'Collection ID': log_item.get('collectionId', ''),
                    'Message': log_item.get('message', ''),
                    'Context Data Count': len(log_item.get('ctxData', [])),
                    'Logs Data Count': len(log_item.get('logsData', [])),
                    'Histories Count': len(log_item.get('histories', []))
                })
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Statistics sheet
            stats = logs_data.get('statistics', {})
            stats_data = [
                ['Total Logs', stats.get('totalLogs', 0)],
                ['Successful Executions', stats.get('successfulExecutions', 0)],
                ['Failed Executions', stats.get('failedExecutions', 0)],
                ['Unique Workflows', stats.get('uniqueWorkflows', 0)],
                ['Total Execution Time (ms)', stats.get('totalExecutionTime', 0)],
                ['Average Execution Time (ms)', round(stats.get('averageExecutionTime', 0), 2)],
                ['Success Rate (%)', round((stats.get('successfulExecutions', 0) / max(stats.get('totalLogs', 1), 1)) * 100, 2)]
            ]
            
            if stats.get('dateRange', {}).get('earliest'):
                earliest = datetime.fromtimestamp(stats['dateRange']['earliest'] / 1000)
                latest = datetime.fromtimestamp(stats['dateRange']['latest'] / 1000)
                stats_data.extend([
                    ['Earliest Execution', earliest.isoformat()],
                    ['Latest Execution', latest.isoformat()]
                ])
            
            stats_df = pd.DataFrame(stats_data, columns=['Metric', 'Value'])
            stats_df.to_excel(writer, sheet_name='Statistics', index=False)
            
            # Performance analysis sheet
            perf_data = []
            for log_item in logs:
                exec_time = log_item.get('executionTime', 0)
                started_at = log_item.get('startedAt', 0)
                
                perf_data.append({
                    'Log ID': log_item.get('id', ''),
                    'Execution Time (ms)': exec_time,
                    'Status': log_item.get('status', ''),
                    'Hour of Day': datetime.fromtimestamp(started_at / 1000).hour if started_at else None,
                    'Day of Week': datetime.fromtimestamp(started_at / 1000).weekday() if started_at else None,
                    'Date': datetime.fromtimestamp(started_at / 1000).date() if started_at else None
                })
            
            perf_df = pd.DataFrame(perf_data)
            perf_df.to_excel(writer, sheet_name='Performance', index=False)
        
        print("✅ Excel export completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Excel export failed: {e}")
        return False

def analyze_workflow_performance(logs_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze workflow execution patterns and performance"""
    print("📈 Analyzing workflow performance...")
    
    logs = logs_data.get('logs', [])
    if not logs:
        return {}
    
    analysis = {
        'execution_patterns': defaultdict(list),
        'status_distribution': Counter(),
        'time_patterns': {
            'by_hour': defaultdict(list),
            'by_day': defaultdict(list),
            'by_date': defaultdict(list)
        },
        'performance_metrics': {
            'fastest_execution': None,
            'slowest_execution': None,
            'execution_times': []
        },
        'error_analysis': {
            'error_messages': Counter(),
            'error_frequency': defaultdict(int)
        }
    }
    
    for log_item in logs:
        # Status distribution
        status = log_item.get('status', 'unknown')
        analysis['status_distribution'][status] += 1
        
        # Execution time analysis
        exec_time = log_item.get('executionTime', 0)
        if exec_time > 0:
            analysis['performance_metrics']['execution_times'].append(exec_time)
            
            if (analysis['performance_metrics']['fastest_execution'] is None or 
                exec_time < analysis['performance_metrics']['fastest_execution']['time']):
                analysis['performance_metrics']['fastest_execution'] = {
                    'time': exec_time,
                    'log_id': log_item.get('id'),
                    'name': log_item.get('name', '')
                }
            
            if (analysis['performance_metrics']['slowest_execution'] is None or 
                exec_time > analysis['performance_metrics']['slowest_execution']['time']):
                analysis['performance_metrics']['slowest_execution'] = {
                    'time': exec_time,
                    'log_id': log_item.get('id'),
                    'name': log_item.get('name', '')
                }
        
        # Time pattern analysis
        started_at = log_item.get('startedAt', 0)
        if started_at:
            dt = datetime.fromtimestamp(started_at / 1000)
            analysis['time_patterns']['by_hour'][dt.hour].append(exec_time)
            analysis['time_patterns']['by_day'][dt.weekday()].append(exec_time)
            analysis['time_patterns']['by_date'][dt.date().isoformat()].append(exec_time)
        
        # Error analysis
        if status in ['error', 'failed']:
            message = log_item.get('message', 'Unknown error')
            analysis['error_analysis']['error_messages'][message] += 1
            
            if started_at:
                date_key = datetime.fromtimestamp(started_at / 1000).date().isoformat()
                analysis['error_analysis']['error_frequency'][date_key] += 1
    
    # Calculate summary statistics
    exec_times = analysis['performance_metrics']['execution_times']
    if exec_times:
        analysis['performance_metrics']['statistics'] = {
            'mean': sum(exec_times) / len(exec_times),
            'median': sorted(exec_times)[len(exec_times) // 2],
            'min': min(exec_times),
            'max': max(exec_times),
            'count': len(exec_times)
        }
    
    return analysis

def save_analysis_report(analysis: Dict[str, Any], output_path: str) -> bool:
    """Save performance analysis as a readable report"""
    print(f"📊 Saving analysis report: {output_path}")
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Automa Workflow Performance Analysis Report\n\n")
            f.write(f"Generated at: {datetime.now().isoformat()}\n\n")
            
            # Status distribution
            f.write("## Execution Status Distribution\n\n")
            for status, count in analysis['status_distribution'].items():
                f.write(f"- {status.title()}: {count}\n")
            f.write("\n")
            
            # Performance metrics
            perf = analysis['performance_metrics']
            if 'statistics' in perf:
                stats = perf['statistics']
                f.write("## Performance Statistics\n\n")
                f.write(f"- Total Executions: {stats['count']}\n")
                f.write(f"- Average Execution Time: {stats['mean']:.2f}ms ({stats['mean']/1000:.2f}s)\n")
                f.write(f"- Median Execution Time: {stats['median']:.2f}ms ({stats['median']/1000:.2f}s)\n")
                f.write(f"- Fastest Execution: {stats['min']:.2f}ms ({stats['min']/1000:.2f}s)\n")
                f.write(f"- Slowest Execution: {stats['max']:.2f}ms ({stats['max']/1000:.2f}s)\n")
                f.write("\n")
            
            # Fastest and slowest executions
            if perf['fastest_execution']:
                f.write("## Fastest Execution\n\n")
                fastest = perf['fastest_execution']
                f.write(f"- Time: {fastest['time']:.2f}ms ({fastest['time']/1000:.2f}s)\n")
                f.write(f"- Log ID: {fastest['log_id']}\n")
                f.write(f"- Name: {fastest['name']}\n\n")
            
            if perf['slowest_execution']:
                f.write("## Slowest Execution\n\n")
                slowest = perf['slowest_execution']
                f.write(f"- Time: {slowest['time']:.2f}ms ({slowest['time']/1000:.2f}s)\n")
                f.write(f"- Log ID: {slowest['log_id']}\n")
                f.write(f"- Name: {slowest['name']}\n\n")
            
            # Time patterns
            f.write("## Execution Patterns by Hour\n\n")
            time_patterns = analysis['time_patterns']
            for hour in sorted(time_patterns['by_hour'].keys()):
                executions = time_patterns['by_hour'][hour]
                avg_time = sum(executions) / len(executions) if executions else 0
                f.write(f"- {hour:02d}:00 - {len(executions)} executions (avg: {avg_time:.2f}ms)\n")
            f.write("\n")
            
            f.write("## Execution Patterns by Day of Week\n\n")
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            for day_num in sorted(time_patterns['by_day'].keys()):
                executions = time_patterns['by_day'][day_num]
                avg_time = sum(executions) / len(executions) if executions else 0
                f.write(f"- {days[day_num]}: {len(executions)} executions (avg: {avg_time:.2f}ms)\n")
            f.write("\n")
            
            # Error analysis
            error_analysis = analysis['error_analysis']
            if error_analysis['error_messages']:
                f.write("## Error Analysis\n\n")
                f.write("### Most Common Error Messages:\n\n")
                for message, count in error_analysis['error_messages'].most_common(10):
                    f.write(f"- {message} ({count} times)\n")
                f.write("\n")
                
                f.write("### Error Frequency by Date:\n\n")
                for date in sorted(error_analysis['error_frequency'].keys()):
                    count = error_analysis['error_frequency'][date]
                    f.write(f"- {date}: {count} errors\n")
                f.write("\n")
        
        print("✅ Analysis report saved successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to save analysis report: {e}")
        return False

def main():
    """Main execution function"""
    start_time = time.time()
    print_banner()
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Find Automa context
    ws_url = find_automa_context()
    if not ws_url:
        print("❌ Cannot find Automa extension context")
        print("💡 Make sure Chrome is running with: --remote-debugging-port=9222")
        print("💡 And that Automa extension is installed and active")
        return
    
    # Get available workflows
    workflows = get_available_workflows(ws_url)
    if not workflows:
        print("❌ No workflows found")
        print("💡 Make sure you have workflows created in Automa extension")
        return
    
    # Interactive options
    print("\n🎯 Choose export options:")
    print("1. Export logs for specific workflow")
    print("2. Export all logs")
    print("3. Export logs with date range filter")
    print("4. Export and analyze specific workflow")
    print("5. Quick analysis of all recent logs")
    
    choice = input("Enter choice (1-5): ").strip()
    
    workflow_id = None
    workflow_name = None
    start_date = None
    end_date = None
    
    # Workflow selection
    if choice in ['1', '4']:
        workflow_list = list(workflows.values())
        print("\n📋 Select workflow:")
        for i, wf in enumerate(workflow_list, 1):
            status = "🔴 Disabled" if wf.get("isDisabled") else "🟢 Enabled"
            exec_count = wf.get("executionCount", 0)
            print(f"{i}. {wf['name']} ({wf['id'][:8]}...) - {status} - {exec_count} executions")
        
        try:
            wf_choice = int(input("Enter workflow number: ")) - 1
            if 0 <= wf_choice < len(workflow_list):
                selected_workflow = workflow_list[wf_choice]
                workflow_id = selected_workflow['id']
                workflow_name = selected_workflow['name']
                print(f"✅ Selected: {workflow_name}")
            else:
                print("❌ Invalid workflow selection")
                return
        except (ValueError, IndexError):
            print("❌ Invalid input")
            return
    
    # Date range selection
    if choice == '3':
        print("\n📅 Enter date range (YYYY-MM-DD format, or press Enter to skip):")
        start_input = input("Start date: ").strip()
        end_input = input("End date: ").strip()
        
        if start_input:
            try:
                datetime.fromisoformat(start_input)
                start_date = start_input + "T00:00:00Z"
            except ValueError:
                print("❌ Invalid start date format")
                return
        
        if end_input:
            try:
                datetime.fromisoformat(end_input)
                end_date = end_input + "T23:59:59Z"
            except ValueError:
                print("❌ Invalid end date format")
                return
    
    # Extract logs
    print("\n🔄 Extracting logs from Automa's Dexie database...")
    logs_data = extract_dexie_logs(ws_url, workflow_id, start_date, end_date)
    
    if not logs_data or not logs_data.get('success'):
        print("❌ Failed to extract logs")
        return
    
    if not logs_data.get('logs'):
        print("❌ No logs found matching the criteria")
        return
    
    # Generate file names
    file_prefix = f"automa_logs_{timestamp}"
    if workflow_name:
        safe_name = "".join(c for c in workflow_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        file_prefix = f"automa_logs_{safe_name}_{timestamp}"
    
    # Export to different formats
    export_results = {}
    
    # CSV Export
    csv_path = os.path.join(OUTPUT_DIR, f"{file_prefix}.csv")
    export_results['csv'] = export_logs_to_csv(logs_data, csv_path, workflow_name)
    
    # JSON Export
    json_path = os.path.join(OUTPUT_DIR, f"{file_prefix}.json")
    export_results['json'] = export_logs_to_json(logs_data, json_path, workflow_name)
    
    # Excel Export (if pandas is available)
    try:
        excel_path = os.path.join(OUTPUT_DIR, f"{file_prefix}.xlsx")
        export_results['excel'] = export_logs_to_excel(logs_data, excel_path, workflow_name)
    except ImportError:
        print("⚠️ pandas not available, skipping Excel export")
        export_results['excel'] = False
    except Exception as e:
        print(f"⚠️ Excel export failed: {e}")
        export_results['excel'] = False
    
    # Performance Analysis
    if choice in ['4', '5']:
        print("\n📈 Performing detailed analysis...")
        analysis = analyze_workflow_performance(logs_data)
        
        # Save analysis report
        analysis_path = os.path.join(OUTPUT_DIR, f"{file_prefix}_analysis.md")
        save_analysis_report(analysis, analysis_path)
        
        # Save analysis data as JSON
        analysis_json_path = os.path.join(OUTPUT_DIR, f"{file_prefix}_analysis.json")
        try:
            with open(analysis_json_path, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False, default=str)
            print(f"📊 Analysis data saved: {analysis_json_path}")
        except Exception as e:
            print(f"⚠️ Failed to save analysis JSON: {e}")
    
    # Summary
    execution_time = time.time() - start_time
    print(f"\n📋 Export Summary:")
    print(f"   ⏱️  Total time: {execution_time:.2f} seconds")
    print(f"   📊 Logs processed: {len(logs_data.get('logs', []))}")
    print(f"   📁 Output directory: {OUTPUT_DIR}")
    
    print(f"\n✅ Export Results:")
    if export_results.get('csv'):
        print(f"   📄 CSV: {csv_path}")
    if export_results.get('json'):
        print(f"   💾 JSON: {json_path}")
    if export_results.get('excel'):
        print(f"   📊 Excel: {excel_path}")
    
    if choice in ['4', '5']:
        print(f"   📈 Analysis: {analysis_path}")
    
    # Quick stats display
    stats = logs_data.get('statistics', {})
    if stats:
        print(f"\n📊 Quick Statistics:")
        print(f"   ✅ Successful: {stats.get('successfulExecutions', 0)}")
        print(f"   ❌ Failed: {stats.get('failedExecutions', 0)}")
        print(f"   ⏱️  Avg time: {(stats.get('averageExecutionTime', 0) / 1000):.2f}s")
        
        success_rate = (stats.get('successfulExecutions', 0) / max(stats.get('totalLogs', 1), 1)) * 100
        print(f"   📈 Success rate: {success_rate:.1f}%")
    
    print("\n🎉 Log export completed successfully!")
    
    # Usage tips
    print(f"\n💡 Tips:")
    print(f"   📊 Open the Excel file for interactive analysis")
    print(f"   🔍 Use the JSON file for programmatic processing")
    print(f"   📈 Review the analysis report for insights")
    print(f"   🔧 Filter by date ranges for specific periods")

if __name__ == "__main__":
    main()