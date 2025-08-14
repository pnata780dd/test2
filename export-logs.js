// Simple Automa CSV Log Extractor
// Extracts workflow name and logs into a simple CSV file
// Run with: node simple-automa-extractor.js

const fs = require('fs-extra');
const path = require('path');

class SimpleAutomaExtractor {
    constructor() {
        this.outputDir = '/workspace/automa-exports';
    }

    log(message) {
        console.log(`[${new Date().toLocaleTimeString()}] ${message}`);
    }

    async findChromeProfiles() {
        const possiblePaths = [
            '/workspaces/test2/chrome_profile',
            '/workspace/chrome_profile',
            process.cwd() + '/chrome_profile',
            './chrome_profile'
        ];

        for (const profilePath of possiblePaths) {
            if (await fs.pathExists(profilePath)) {
                this.log(`✅ Found Chrome profile: ${profilePath}`);
                return [profilePath];
            }
        }
        return [];
    }

    async findIndexedDBDirs(profilePaths) {
        const indexedDBDirs = [];
        
        for (const profilePath of profilePaths) {
            const idbPath = path.join(profilePath, 'Default', 'IndexedDB');
            if (await fs.pathExists(idbPath)) {
                indexedDBDirs.push(idbPath);
                this.log(`✅ Found IndexedDB: ${idbPath}`);
            }
        }
        
        return indexedDBDirs;
    }

    async findAutomaExtensions(indexedDBDirs) {
        const automaDirs = [];
        
        for (const idbDir of indexedDBDirs) {
            try {
                const contents = await fs.readdir(idbDir);
                this.log(`📂 IndexedDB contents: ${contents.join(', ')}`);
                
                for (const item of contents) {
                    // Look for Automa extension or any extension that might contain workflow data
                    if (item.startsWith('chrome-extension_') && 
                        (item.includes('infppggnoaenmfagbfknfkancpbljcca') || // Automa ID
                         item.toLowerCase().includes('automa') ||
                         contents.length <= 5)) { // If few extensions, check all
                        
                        const extensionDir = path.join(idbDir, item);
                        automaDirs.push(extensionDir);
                        this.log(`🎯 Found potential Automa extension: ${item}`);
                    }
                }
                
                // If no specific match, include all extensions for analysis
                if (automaDirs.length === 0) {
                    for (const item of contents) {
                        if (item.startsWith('chrome-extension_')) {
                            const extensionDir = path.join(idbDir, item);
                            automaDirs.push(extensionDir);
                            this.log(`📊 Including extension for analysis: ${item}`);
                        }
                    }
                }
            } catch (error) {
                this.log(`❌ Error reading ${idbDir}: ${error.message}`);
            }
        }
        
        return automaDirs;
    }

    async extractWorkflowData(automaDirs) {
        const workflowData = [];
        
        for (const automaDir of automaDirs) {
            try {
                this.log(`🔍 Analyzing: ${path.basename(automaDir)}`);
                
                if (await fs.pathExists(automaDir)) {
                    const files = await fs.readdir(automaDir);
                    this.log(`📁 Files in extension: ${files.join(', ')}`);
                    
                    for (const file of files) {
                        const filePath = path.join(automaDir, file);
                        const stats = await fs.stat(filePath);
                        
                        // Look for database files or log files
                        if (stats.isFile() && (
                            file.includes('log') || 
                            file.includes('workflow') ||
                            file.includes('.db') ||
                            file.includes('.json') ||
                            stats.size > 1024 // Larger files might contain data
                        )) {
                            
                            try {
                                // Try to read as text first
                                if (stats.size < 1024 * 1024) { // Less than 1MB
                                    let content = '';
                                    
                                    if (file.endsWith('.json')) {
                                        content = await fs.readFile(filePath, 'utf8');
                                        const jsonData = JSON.parse(content);
                                        
                                        // Look for workflow-like data
                                        if (this.containsWorkflowData(jsonData)) {
                                            const extracted = this.extractFromJSON(jsonData);
                                            workflowData.push(...extracted);
                                            this.log(`✅ Extracted workflow data from ${file}`);
                                        }
                                    } else {
                                        // Try reading as text
                                        try {
                                            content = await fs.readFile(filePath, 'utf8');
                                            if (content.includes('workflow') || content.includes('trigger') || content.includes('typing')) {
                                                // Parse as potential log data
                                                const extracted = this.extractFromText(content, file);
                                                workflowData.push(...extracted);
                                                this.log(`✅ Extracted log data from ${file}`);
                                            }
                                        } catch (textError) {
                                            // If text reading fails, might be binary database
                                            this.log(`📄 Binary file detected: ${file} (${stats.size} bytes)`);
                                            
                                            // For binary files, try to extract readable strings
                                            const buffer = await fs.readFile(filePath);
                                            const strings = this.extractStringsFromBuffer(buffer);
                                            
                                            if (strings.length > 0) {
                                                const extracted = this.extractFromStrings(strings, file);
                                                workflowData.push(...extracted);
                                                this.log(`✅ Extracted strings from binary file ${file}`);
                                            }
                                        }
                                    }
                                }
                            } catch (error) {
                                this.log(`⚠️ Could not process ${file}: ${error.message}`);
                            }
                        }
                    }
                }
            } catch (error) {
                this.log(`❌ Error processing ${automaDir}: ${error.message}`);
            }
        }
        
        return workflowData;
    }

    containsWorkflowData(data) {
        const dataStr = JSON.stringify(data).toLowerCase();
        return dataStr.includes('workflow') || 
               dataStr.includes('trigger') || 
               dataStr.includes('typing') ||
               dataStr.includes('click') ||
               dataStr.includes('automa');
    }

    extractFromJSON(data) {
        const results = [];
        
        // Recursive function to find workflow data
        const findWorkflows = (obj, parentKey = '') => {
            if (typeof obj === 'object' && obj !== null) {
                if (Array.isArray(obj)) {
                    obj.forEach((item, index) => findWorkflows(item, `${parentKey}[${index}]`));
                } else {
                    Object.keys(obj).forEach(key => {
                        if (key.toLowerCase().includes('workflow') || 
                            key.toLowerCase().includes('log') ||
                            key.toLowerCase().includes('name')) {
                            
                            if (typeof obj[key] === 'string' && obj[key].length > 0) {
                                results.push({
                                    workflow: key.includes('name') ? obj[key] : parentKey || 'Unknown',
                                    log: typeof obj[key] === 'string' ? obj[key] : JSON.stringify(obj[key])
                                });
                            }
                        }
                        findWorkflows(obj[key], key);
                    });
                }
            }
        };
        
        findWorkflows(data);
        return results;
    }

    extractFromText(content, filename) {
        const results = [];
        const lines = content.split('\n');
        
        let currentWorkflow = filename.replace(/\.[^/.]+$/, ""); // Remove extension
        
        for (const line of lines) {
            const trimmedLine = line.trim();
            if (trimmedLine.length === 0) continue;
            
            // Look for workflow name patterns
            if (trimmedLine.toLowerCase().includes('workflow') && trimmedLine.includes(':')) {
                const parts = trimmedLine.split(':');
                if (parts.length > 1) {
                    currentWorkflow = parts[1].trim();
                }
            }
            
            // Look for log entries
            if (trimmedLine.includes('Trigger') || 
                trimmedLine.includes('Click') || 
                trimmedLine.includes('New tab') ||
                trimmedLine.includes('typing')) {
                
                results.push({
                    workflow: currentWorkflow,
                    log: trimmedLine
                });
            }
        }
        
        return results;
    }

    extractStringsFromBuffer(buffer) {
        const strings = [];
        let currentString = '';
        
        for (let i = 0; i < buffer.length; i++) {
            const byte = buffer[i];
            
            // Printable ASCII characters
            if (byte >= 32 && byte <= 126) {
                currentString += String.fromCharCode(byte);
            } else {
                if (currentString.length > 3) { // Only keep strings longer than 3 chars
                    strings.push(currentString);
                }
                currentString = '';
            }
        }
        
        // Add the last string if it exists
        if (currentString.length > 3) {
            strings.push(currentString);
        }
        
        return strings.filter(s => 
            s.includes('workflow') || 
            s.includes('typing') || 
            s.includes('trigger') ||
            s.includes('click')
        );
    }

    extractFromStrings(strings, filename) {
        const results = [];
        let currentWorkflow = filename.replace(/\.[^/.]+$/, "");
        
        for (const str of strings) {
            if (str.toLowerCase().includes('workflow') && str.includes('_')) {
                // Might be a workflow name
                currentWorkflow = str;
            }
            
            if (str.includes('Trigger') || 
                str.includes('Click') || 
                str.includes('typing') ||
                str.includes('New tab')) {
                
                results.push({
                    workflow: currentWorkflow,
                    log: str
                });
            }
        }
        
        return results;
    }

    async saveToCSV(workflowData) {
        if (workflowData.length === 0) {
            this.log('⚠️ No workflow data found to save');
            return null;
        }

        await fs.ensureDir(this.outputDir);
        
        // Group by workflow name
        const workflows = {};
        workflowData.forEach(item => {
            const workflowName = item.workflow || 'Unknown';
            if (!workflows[workflowName]) {
                workflows[workflowName] = [];
            }
            workflows[workflowName].push(item.log);
        });

        const savedFiles = [];

        for (const [workflowName, logs] of Object.entries(workflows)) {
            // Clean workflow name for filename
            const cleanName = workflowName.replace(/[^a-zA-Z0-9_-]/g, '_').substring(0, 50);
            const filename = `${cleanName}.csv`;
            const filepath = path.join(this.outputDir, filename);
            
            // Create CSV content
            let csvContent = 'workflow_name,log_entry\n';
            
            logs.forEach(log => {
                // Escape quotes and wrap in quotes if needed
                const escapedLog = log.replace(/"/g, '""');
                const needsQuotes = log.includes(',') || log.includes('\n') || log.includes('"');
                const logValue = needsQuotes ? `"${escapedLog}"` : escapedLog;
                
                csvContent += `"${workflowName}",${logValue}\n`;
            });
            
            await fs.writeFile(filepath, csvContent, 'utf8');
            savedFiles.push(filepath);
            
            this.log(`✅ Saved ${logs.length} log entries to: ${filename}`);
        }

        return savedFiles;
    }

    async run() {
        this.log('🚀 Starting Simple Automa CSV Extraction...');
        
        try {
            // Find Chrome profiles
            const profilePaths = await this.findChromeProfiles();
            if (profilePaths.length === 0) {
                this.log('❌ No Chrome profiles found');
                return;
            }

            // Find IndexedDB directories
            const indexedDBDirs = await this.findIndexedDBDirs(profilePaths);
            if (indexedDBDirs.length === 0) {
                this.log('❌ No IndexedDB directories found');
                return;
            }

            // Find Automa extensions
            const automaDirs = await this.findAutomaExtensions(indexedDBDirs);
            if (automaDirs.length === 0) {
                this.log('❌ No extension databases found');
                return;
            }

            // Extract workflow data
            const workflowData = await this.extractWorkflowData(automaDirs);
            
            if (workflowData.length === 0) {
                this.log('❌ No workflow data found in any extension databases');
                return;
            }

            // Save to CSV
            const savedFiles = await this.saveToCSV(workflowData);
            
            this.log('\n✅ Extraction completed!');
            this.log(`📊 Found ${workflowData.length} log entries`);
            if (savedFiles) {
                this.log(`💾 Saved to ${savedFiles.length} CSV file(s):`);
                savedFiles.forEach(file => this.log(`   - ${path.basename(file)}`));
            }
            
            return savedFiles;

        } catch (error) {
            this.log(`❌ Extraction failed: ${error.message}`);
            throw error;
        }
    }
}

// Run the extraction
async function extractAutomaLogs() {
    const extractor = new SimpleAutomaExtractor();
    return await extractor.run();
}

// Execute if run directly
if (require.main === module) {
    extractAutomaLogs().catch(error => {
        console.error('Error:', error.message);
        process.exit(1);
    });
}

module.exports = { SimpleAutomaExtractor, extractAutomaLogs };