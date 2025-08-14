#!/usr/bin/env python3
"""
Automa CSV Exporter Module
- Export workflows to CSV format
- Export detailed workflow configurations as JSON
- Support for workflow analysis and reporting
"""

import os
import json
import csv
import websocket
from datetime import datetime
from typing import Dict, List, Any, Optional

def export_workflows_to_csv(ws_url: str, output_path: str) -> bool:
    """Export workflows to CSV format"""
    print(f"📋 Exporting workflows to CSV: {output_path}")
    
    try:
        ws = websocket.create_connection(ws_url)
        
        # Get workflows from storage
        get_workflows_script = """
        new Promise((resolve) => {
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                chrome.storage.local.get(['workflows'], (result) => {
                    const workflows = result.workflows || {};
                    const workflowList = Object.keys(workflows).map(id => {
                        const workflow = workflows[id];
                        return {
                            id: id,
                            name: workflow.name || 'Unnamed',
                            description: workflow.description || '',
                            isDisabled: workflow.isDisabled || false,
                            createdAt: workflow.createdAt || 0,
                            updatedAt: workflow.updatedAt || 0,
                            version: workflow.version || '1.0',
                            category: workflow.category || 'General',
                            trigger: workflow.trigger || 'manual',
                            nodeCount: workflow.drawflow ? Object.keys(workflow.drawflow.drawflow.Home.data).length : 0,
                            lastExecution: workflow.lastExecution ? JSON.stringify(workflow.lastExecution) : '',
                            tags: workflow.tags ? workflow.tags.join(', ') : '',
                            author: workflow.author || '',
                            isPublic: workflow.isPublic || false,
                            dataColumns: workflow.dataColumns ? Object.keys(workflow.dataColumns).join(', ') : '',
                            globalData: workflow.globalData ? JSON.stringify(workflow.globalData) : '',
                            settings: workflow.settings ? JSON.stringify(workflow.settings) : ''
                        };
                    });
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
            "id": 10,
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
                
                if workflows:
                    # Convert timestamps
                    for workflow in workflows:
                        for time_field in ['createdAt', 'updatedAt']:
                            if workflow[time_field] and str(workflow[time_field]).isdigit():
                                ts = int(workflow[time_field]) / 1000
                                workflow[time_field] = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Write CSV
                    fieldnames = [
                        'id', 'name', 'description', 'isDisabled', 'createdAt', 'updatedAt',
                        'version', 'category', 'trigger', 'nodeCount', 'tags', 'author',
                        'isPublic', 'dataColumns', 'lastExecution', 'globalData', 'settings'
                    ]
                    
                    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(workflows)
                    
                    print(f"✅ Exported {len(workflows)} workflows to CSV")
                    return True
                else:
                    print("❌ No workflows found to export")
                    return False
            else:
                print(f"❌ Failed to get workflows: {result_data.get('error')}")
                return False
        else:
            print("❌ Invalid response from workflows export")
            return False
            
    except Exception as e:
        print(f"❌ Error exporting workflows to CSV: {e}")
        return False

def export_detailed_workflows_json(ws_url: str, output_path: str) -> bool:
    """Export detailed workflow configurations as JSON"""
    print(f"💾 Exporting detailed workflows to JSON: {output_path}")
    
    try:
        ws = websocket.create_connection(ws_url)
        
        # Get complete workflow data including nodes and connections
        get_detailed_workflows_script = """
        new Promise((resolve) => {
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                chrome.storage.local.get(['workflows'], (result) => {
                    const workflows = result.workflows || {};
                    
                    resolve({
                        success: true,
                        workflows: workflows,
                        workflowCount: Object.keys(workflows).length,
                        exportTimestamp: Date.now(),
                        exportVersion: '1.0'
                    });
                });
            } else {
                resolve({success: false, error: 'Storage not available'});
            }
        })
        """
        
        message = {
            "id": 11,
            "method": "Runtime.evaluate",
            "params": {
                "expression": get_detailed_workflows_script,
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
                export_data = {
                    'export_timestamp': datetime.now().isoformat(),
                    'export_version': result_data.get('exportVersion', '1.0'),
                    'workflow_count': result_data.get('workflowCount', 0),
                    'workflows': result_data.get('workflows', {})
                }
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                
                print(f"✅ Exported {export_data['workflow_count']} detailed workflows to JSON")
                return True
            else:
                print(f"❌ Failed to get detailed workflows: {result_data.get('error')}")
                return False
        else:
            print("❌ Invalid response from detailed workflows export")
            return False
            
    except Exception as e:
        print(f"❌ Error exporting detailed workflows to JSON: {e}")
        return False

def analyze_workflow_structure(ws_url: str) -> Dict[str, Any]:
    """Analyze workflow structure and generate statistics"""
    print("📊 Analyzing workflow structure...")
    
    try:
        ws = websocket.create_connection(ws_url)
        
        analysis_script = """
        new Promise((resolve) => {
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                chrome.storage.local.get(['workflows'], (result) => {
                    const workflows = result.workflows || {};
                    const analysis = {
                        totalWorkflows: 0,
                        enabledWorkflows: 0,
                        disabledWorkflows: 0,
                        nodeTypes: {},
                        triggerTypes: {},
                        categories: {},
                        totalNodes: 0,
                        averageNodesPerWorkflow: 0,
                        workflowsWithData: 0,
                        workflowsWithSettings: 0,
                        oldestWorkflow: null,
                        newestWorkflow: null
                    };
                    
                    let oldestTime = Infinity;
                    let newestTime = 0;
                    
                    Object.keys(workflows).forEach(workflowId => {
                        const workflow = workflows[workflowId];
                        analysis.totalWorkflows++;
                        
                        // Status
                        if (workflow.isDisabled) {
                            analysis.disabledWorkflows++;
                        } else {
                            analysis.enabledWorkflows++;
                        }
                        
                        // Trigger types
                        const trigger = workflow.trigger || 'manual';
                        analysis.triggerTypes[trigger] = (analysis.triggerTypes[trigger] || 0) + 1;
                        
                        // Categories
                        const category = workflow.category || 'General';
                        analysis.categories[category] = (analysis.categories[category] || 0) + 1;
                        
                        // Node analysis
                        if (workflow.drawflow && workflow.drawflow.drawflow && workflow.drawflow.drawflow.Home) {
                            const nodes = workflow.drawflow.drawflow.Home.data || {};
                            const nodeCount = Object.keys(nodes).length;
                            analysis.totalNodes += nodeCount;
                            
                            Object.values(nodes).forEach(node => {
                                const nodeType = node.name || 'unknown';
                                analysis.nodeTypes[nodeType] = (analysis.nodeTypes[nodeType] || 0) + 1;
                            });
                        }
                        
                        // Data and settings
                        if (workflow.globalData && Object.keys(workflow.globalData).length > 0) {
                            analysis.workflowsWithData++;
                        }
                        if (workflow.settings && Object.keys(workflow.settings).length > 0) {
                            analysis.workflowsWithSettings++;
                        }
                        
                        // Time analysis
                        const createdAt = workflow.createdAt || 0;
                        if (createdAt && createdAt < oldestTime) {
                            oldestTime = createdAt;
                            analysis.oldestWorkflow = {
                                id: workflowId,
                                name: workflow.name,
                                createdAt: createdAt
                            };
                        }
                        if (createdAt && createdAt > newestTime) {
                            newestTime = createdAt;
                            analysis.newestWorkflow = {
                                id: workflowId,
                                name: workflow.name,
                                createdAt: createdAt
                            };
                        }
                    });
                    
                    // Calculate averages
                    if (analysis.totalWorkflows > 0) {
                        analysis.averageNodesPerWorkflow = Math.round(analysis.totalNodes / analysis.totalWorkflows * 100) / 100;
                    }
                    
                    resolve({
                        success: true,
                        analysis: analysis
                    });
                });
            } else {
                resolve({success: false, error: 'Storage not available'});
            }
        })
        """
        
        message = {
            "id": 12,
            "method": "Runtime.evaluate",
            "params": {
                "expression": analysis_script,
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
                analysis = result_data.get("analysis", {})
                
                # Print analysis summary
                print(f"✅ Workflow Analysis Complete:")
                print(f"  📊 Total Workflows: {analysis.get('totalWorkflows', 0)}")
                print(f"  🟢 Enabled: {analysis.get('enabledWorkflows', 0)}")
                print(f"  🔴 Disabled: {analysis.get('disabledWorkflows', 0)}")
                print(f"  🔧 Total Nodes: {analysis.get('totalNodes', 0)}")
                print(f"  📈 Avg Nodes/Workflow: {analysis.get('averageNodesPerWorkflow', 0)}")
                
                # Most common node types
                node_types = analysis.get('nodeTypes', {})
                if node_types:
                    top_nodes = sorted(node_types.items(), key=lambda x: x[1], reverse=True)[:5]
                    print(f"  🏆 Top Node Types: {', '.join([f'{k}({v})' for k, v in top_nodes])}")
                
                return analysis
            else:
                print(f"❌ Analysis failed: {result_data.get('error')}")
                return {}
        else:
            print("❌ Invalid response from workflow analysis")
            return {}
            
    except Exception as e:
        print(f"❌ Error analyzing workflows: {e}")
        return {}

def export_workflow_analysis(analysis_data: Dict[str, Any], output_path: str) -> bool:
    """Export workflow analysis results to JSON"""
    try:
        export_data = {
            'analysis_timestamp': datetime.now().isoformat(),
            'analysis_version': '1.0',
            **analysis_data
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Analysis exported to: {output_path}")
        return True
    except Exception as e:
        print(f"❌ Error exporting analysis: {e}")
        return False