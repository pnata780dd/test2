#!/usr/bin/env python3
"""
Quick Automa Test - Use the detected WebSocket URL directly
"""

import json
import websocket

# Use the WebSocket URL from the debug output
WS_URL = "ws://localhost:9222/devtools/page/BAF6528DCD20672D3C962C18DCF28462"

def test_automa_connection():
    """Test connection and list workflows"""
    print("🔗 Testing Automa connection...")
    
    try:
        ws = websocket.create_connection(WS_URL)
        print("✅ Connected to Automa")
        
        # Get workflows
        get_workflows_script = """
        new Promise((resolve) => {
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                chrome.storage.local.get(['workflows'], (result) => {
                    const workflows = result.workflows || {};
                    resolve({
                        success: true,
                        workflows: workflows,
                        count: Object.keys(workflows).length
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
                workflows = result_data.get("workflows", {})
                print(f"✅ Found {len(workflows)} workflow(s)")
                
                for wf_id, workflow in workflows.items():
                    name = workflow.get('name', 'Unnamed')
                    description = workflow.get('description', 'No description')
                    is_disabled = workflow.get('isDisabled', False)
                    status = "🔴 Disabled" if is_disabled else "🟢 Enabled"
                    
                    print(f"\n📋 Workflow: {name}")
                    print(f"   ID: {wf_id}")
                    print(f"   Status: {status}")
                    print(f"   Description: {description}")
                
                return workflows
            else:
                print(f"❌ Failed: {result_data.get('error')}")
                return {}
        else:
            print("❌ Invalid response")
            return {}
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return {}

def trigger_first_workflow(workflows):
    """Trigger the first available workflow"""
    if not workflows:
        print("❌ No workflows to trigger")
        return
    
    first_workflow = list(workflows.items())[0]
    workflow_id, workflow_data = first_workflow
    workflow_name = workflow_data.get('name', 'Unnamed')
    
    print(f"\n🚀 Triggering workflow: {workflow_name}")
    
    try:
        ws = websocket.create_connection(WS_URL)
        
        # Enhanced trigger script
        trigger_script = f"""
        new Promise((resolve) => {{
            console.log('Attempting to trigger workflow: {workflow_id}');
            
            // Method 1: Try runtime message
            if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendMessage) {{
                chrome.runtime.sendMessage({{
                    type: 'workflow:execute',
                    data: {{
                        workflowId: '{workflow_id}',
                        trigger: 'manual'
                    }}
                }}, (response) => {{
                    console.log('Runtime message sent:', response);
                }});
            }}
            
            // Method 2: Try direct execution via global functions
            if (typeof window.executeWorkflow === 'function') {{
                window.executeWorkflow('{workflow_id}');
                console.log('Direct execution attempted');
            }}
            
            // Method 3: Try clicking run button
            const runButtons = document.querySelectorAll('[data-testid="run-workflow"], .workflow-run-btn, button[title*="Run"]');
            if (runButtons.length > 0) {{
                runButtons[0].click();
                console.log('UI button clicked');
            }}
            
            // Method 4: Simulate keyboard shortcut (if any)
            const event = new KeyboardEvent('keydown', {{
                key: 'Enter',
                ctrlKey: true,
                bubbles: true
            }});
            document.dispatchEvent(event);
            
            resolve({{
                success: true,
                message: 'Multiple trigger methods attempted',
                workflowId: '{workflow_id}',
                timestamp: Date.now()
            }});
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
            print(f"✅ Trigger attempted: {result_data.get('message')}")
            return True
        else:
            print("❌ Trigger failed")
            return False
            
    except Exception as e:
        print(f"❌ Trigger error: {e}")
        return False

def main():
    """Quick test main function"""
    print("🚀 Quick Automa Test")
    print("=" * 40)
    
    # Test connection and get workflows
    workflows = test_automa_connection()
    
    if workflows:
        print(f"\n🎯 Ready to trigger workflows!")
        choice = input("Do you want to trigger the first workflow? (y/n): ").lower().strip()
        
        if choice == 'y':
            trigger_first_workflow(workflows)
        else:
            print("👍 Skipping workflow trigger")
    else:
        print("❌ No workflows found or connection failed")

if __name__ == "__main__":
    main()