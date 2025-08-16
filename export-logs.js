// Improved Automa LevelDB Log Extractor
// Handles binary LevelDB data more intelligently
// Run with: node improved-leveldb-extractor.js

const fs = require('fs-extra');
const path = require('path');

class ImprovedLevelDBExtractor {
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
                    if (item.startsWith('chrome-extension_') && item.endsWith('.indexeddb.leveldb')) {
                        const extensionDir = path.join(idbDir, item);
                        automaDirs.push(extensionDir);
                        this.log(`🎯 Found extension database: ${item}`);
                    }
                }
            } catch (error) {
                this.log(`❌ Error reading ${idbDir}: ${error.message}`);
            }
        }
        
        return automaDirs;
    }

    // Enhanced string extraction from binary data
    extractCleanStrings(buffer) {
        const strings = [];
        let currentString = '';
        const minStringLength = 3; // Minimum meaningful string length
        
        for (let i = 0; i < buffer.length; i++) {
            const byte = buffer[i];
            
            // Check for printable ASCII characters (including extended)
            if ((byte >= 32 && byte <= 126) || byte === 9 || byte === 10 || byte === 13) {
                currentString += String.fromCharCode(byte);
            } else {
                // End of string - process it if it's long enough
                if (currentString.length >= minStringLength) {
                    const cleaned = this.cleanExtractedString(currentString);
                    if (cleaned && this.isValidLogData(cleaned)) {
                        strings.push(cleaned);
                    }
                }
                currentString = '';
            }
        }
        
        // Don't forget the last string
        if (currentString.length >= minStringLength) {
            const cleaned = this.cleanExtractedString(currentString);
            if (cleaned && this.isValidLogData(cleaned)) {
                strings.push(cleaned);
            }
        }
        
        return strings;
    }

    cleanExtractedString(str) {
        if (!str) return null;
        
        // Remove common LevelDB artifacts
        let cleaned = str
            .replace(/\x00+/g, ' ') // Replace null characters with spaces
            .replace(/[\x01-\x08\x0B\x0C\x0E-\x1F\x7F-\xFF]/g, '') // Remove non-printable chars
            .replace(/\s+/g, ' ') // Normalize whitespace
            .trim();
        
        // Remove obvious binary artifacts
        cleaned = cleaned
            .replace(/^[^a-zA-Z0-9]*/, '') // Remove leading junk
            .replace(/[^a-zA-Z0-9]*$/, '') // Remove trailing junk
            .trim();
        
        return cleaned.length > 2 ? cleaned : null;
    }

    isValidLogData(str) {
        if (!str || str.length < 3) return false;
        
        // Check for Automa-specific terms
        const automaTerms = [
            'trigger', 'click', 'type', 'typing', 'navigate', 'wait', 'scroll',
            'workflow', 'tab', 'element', 'success', 'failed', 'error',
            'started', 'completed', 'new tab', 'close', 'reload',
            'typing_five', 'logId', 'workflowId', 'status', 'message'
        ];
        
        const lowerStr = str.toLowerCase();
        const hasAutomaTerms = automaTerms.some(term => lowerStr.includes(term));
        
        // Check for time patterns
        const hasTimePattern = /\d{1,2}:\d{2}:\d{2}/.test(str);
        
        // Check for general log patterns
        const hasLogPattern = /\b(success|failed|error|warning|info|debug)\b/i.test(str);
        
        // Check for JSON-like structures
        const hasJSONLike = str.includes('{') || str.includes('"') || str.includes(':');
        
        // Must have at least some alphabetic content
        const hasAlphabetic = /[a-zA-Z]{3,}/.test(str);
        
        return hasAlphabetic && (hasAutomaTerms || hasTimePattern || hasLogPattern || hasJSONLike);
    }

    // Try to extract structured data from strings
    extractStructuredData(strings) {
        const structuredData = [];
        
        for (const str of strings) {
            // Try to parse as JSON first
            if (str.includes('{') && str.includes('}')) {
                try {
                    // Find JSON-like substrings
                    const jsonMatches = str.match(/\{[^{}]*\}/g);
                    if (jsonMatches) {
                        for (const match of jsonMatches) {
                            try {
                                const parsed = JSON.parse(match);
                                if (this.containsWorkflowData(parsed)) {
                                    structuredData.push({
                                        type: 'json',
                                        data: parsed,
                                        raw: match
                                    });
                                }
                            } catch (e) {
                                // Not valid JSON, continue
                            }
                        }
                    }
                } catch (e) {
                    // Not JSON, treat as text
                }
            }
            
            // Extract workflow names and actions
            const workflowMatch = str.match(/typing[_\w]*|workflow[_\w]*/i);
            const actionMatch = str.match(/trigger|click|type|navigate|wait|scroll|tab|element/i);
            const statusMatch = str.match(/success|failed|error|completed|started/i);
            const timeMatch = str.match(/\d{1,2}:\d{2}:\d{2}/);
            
            if (workflowMatch || actionMatch || statusMatch || timeMatch) {
                structuredData.push({
                    type: 'log_entry',
                    workflow: workflowMatch ? workflowMatch[0] : 'Unknown',
                    action: actionMatch ? actionMatch[0] : '',
                    status: statusMatch ? statusMatch[0] : '',
                    time: timeMatch ? timeMatch[0] : '',
                    raw: str
                });
            }
        }
        
        return structuredData;
    }

    containsWorkflowData(data) {
        const dataStr = JSON.stringify(data).toLowerCase();
        return dataStr.includes('workflow') || 
               dataStr.includes('trigger') || 
               dataStr.includes('typing') ||
               dataStr.includes('logid') ||
               dataStr.includes('workflowid');
    }

    // Convert structured data to human-readable format
    convertToHumanReadable(structuredData) {
        const readableEntries = [];
        
        for (const entry of structuredData) {
            let readable = '';
            let workflow = 'Unknown';
            
            if (entry.type === 'json' && entry.data) {
                // Handle JSON data
                if (entry.data.name) workflow = entry.data.name;
                if (entry.data.workflowId) workflow = entry.data.workflowId;
                if (entry.data.message) readable = entry.data.message;
                if (entry.data.status) readable += ` (${entry.data.status})`;
            } else if (entry.type === 'log_entry') {
                // Handle log entries
                workflow = entry.workflow || 'Unknown';
                
                const parts = [];
                if (entry.time) parts.push(`at ${entry.time}`);
                if (entry.action) parts.push(this.humanizeAction(entry.action));
                if (entry.status) parts.push(`- ${entry.status}`);
                
                readable = parts.join(' ') || entry.raw;
            }
            
            if (readable && readable.length > 0) {
                readableEntries.push({
                    workflow: this.cleanWorkflowName(workflow),
                    log: this.cleanLogEntry(readable)
                });
            }
        }
        
        return readableEntries;
    }

    humanizeAction(action) {
        const actionMap = {
            'trigger': 'Started workflow',
            'click': 'Clicked element',
            'type': 'Typed text',
            'typing': 'Typed text',
            'navigate': 'Navigated to page',
            'wait': 'Waited',
            'scroll': 'Scrolled page',
            'tab': 'Opened tab',
            'element': 'Interacted with element'
        };
        
        return actionMap[action.toLowerCase()] || action;
    }

    cleanWorkflowName(name) {
        if (!name || name === 'Unknown') return 'Unknown Workflow';
        
        // Clean up workflow names
        return name
            .replace(/[_-]/g, ' ')
            .replace(/\b\w/g, l => l.toUpperCase())
            .trim();
    }

    cleanLogEntry(entry) {
        if (!entry) return '';
        
        // Remove technical artifacts and clean up
        return entry
            .replace(/^\d+\s*/, '') // Remove leading numbers
            .replace(/\s+/g, ' ') // Normalize whitespace
            .trim()
            .replace(/^./, c => c.toUpperCase()); // Capitalize first letter
    }

    async extractWorkflowData(automaDirs) {
        const allStructuredData = [];
        
        for (const automaDir of automaDirs) {
            try {
                this.log(`🔍 Analyzing: ${path.basename(automaDir)}`);
                
                if (await fs.pathExists(automaDir)) {
                    const files = await fs.readdir(automaDir);
                    this.log(`📁 Files in extension: ${files.join(', ')}`);
                    
                    for (const file of files) {
                        const filePath = path.join(automaDir, file);
                        const stats = await fs.stat(filePath);
                        
                        // Focus on log files and database files
                        if (stats.isFile() && (
                            file.endsWith('.log') || 
                            file.endsWith('.ldb') ||
                            file === 'CURRENT' ||
                            file === 'MANIFEST-000001'
                        )) {
                            
                            try {
                                this.log(`📄 Processing: ${file} (${stats.size} bytes)`);
                                
                                // Read binary data
                                const buffer = await fs.readFile(filePath);
                                
                                // Extract clean strings
                                const strings = this.extractCleanStrings(buffer);
                                this.log(`   🔤 Extracted ${strings.length} clean strings`);
                                
                                if (strings.length > 0) {
                                    // Convert to structured data
                                    const structured = this.extractStructuredData(strings);
                                    allStructuredData.push(...structured);
                                    this.log(`   ✅ Found ${structured.length} structured entries`);
                                    
                                    // Debug: show sample strings
                                    if (strings.length > 0) {
                                        this.log(`   📝 Sample: "${strings[0].substring(0, 50)}..."`);
                                    }
                                }
                            } catch (error) {
                                this.log(`   ⚠️ Could not process ${file}: ${error.message}`);
                            }
                        }
                    }
                }
            } catch (error) {
                this.log(`❌ Error processing ${automaDir}: ${error.message}`);
            }
        }
        
        return allStructuredData;
    }

    async saveToCSV(workflowData) {
        if (workflowData.length === 0) {
            this.log('⚠️ No workflow data found to save');
            return null;
        }

        await fs.ensureDir(this.outputDir);
        
        // Convert to human-readable format
        const readableData = this.convertToHumanReadable(workflowData);
        
        if (readableData.length === 0) {
            this.log('⚠️ No readable data could be extracted');
            return null;
        }

        // Group by workflow name
        const workflows = {};
        readableData.forEach(item => {
            const workflowName = item.workflow || 'Unknown Workflow';
            if (!workflows[workflowName]) {
                workflows[workflowName] = [];
            }
            workflows[workflowName].push(item.log);
        });

        const savedFiles = [];
        const timestamp = new Date().toISOString().split('T')[0];

        // Save individual workflow files
        for (const [workflowName, logs] of Object.entries(workflows)) {
            const cleanName = workflowName.replace(/[^a-zA-Z0-9_\s-]/g, '_').substring(0, 30);
            const filename = `${cleanName}_${timestamp}.csv`;
            const filepath = path.join(this.outputDir, filename);
            
            // Create CSV content with better formatting
            let csvContent = 'timestamp,workflow_name,action,status\n';
            
            logs.forEach((log, index) => {
                const escapedLog = log.replace(/"/g, '""');
                const needsQuotes = log.includes(',') || log.includes('\n') || log.includes('"');
                const logValue = needsQuotes ? `"${escapedLog}"` : escapedLog;
                
                // Try to extract action and status from log
                const statusMatch = log.match(/\b(success|failed|error|completed|started)\b/i);
                const status = statusMatch ? statusMatch[0] : 'info';
                
                const actionMatch = log.match(/\b(clicked|typed|navigated|waited|scrolled|started|opened)\b/i);
                const action = actionMatch ? actionMatch[0] : 'action';
                
                const timestamp = new Date().toISOString();
                
                csvContent += `"${timestamp}","${workflowName}","${action}","${status}"\n`;
            });
            
            await fs.writeFile(filepath, csvContent, 'utf8');
            savedFiles.push(filepath);
            
            this.log(`✅ Saved ${logs.length} entries to: ${filename}`);
        }

        // Also create a combined file
        const combinedFilename = `all_workflows_${timestamp}.csv`;
        const combinedFilepath = path.join(this.outputDir, combinedFilename);
        
        let combinedContent = 'timestamp,workflow_name,log_entry,action,status\n';
        
        readableData.forEach(item => {
            const escapedLog = item.log.replace(/"/g, '""');
            const needsQuotes = item.log.includes(',') || item.log.includes('\n') || item.log.includes('"');
            const logValue = needsQuotes ? `"${escapedLog}"` : escapedLog;
            
            const statusMatch = item.log.match(/\b(success|failed|error|completed|started)\b/i);
            const status = statusMatch ? statusMatch[0] : 'info';
            
            const actionMatch = item.log.match(/\b(clicked|typed|navigated|waited|scrolled|started|opened)\b/i);
            const action = actionMatch ? actionMatch[0] : 'action';
            
            const timestamp = new Date().toISOString();
            
            combinedContent += `"${timestamp}","${item.workflow}",${logValue},"${action}","${status}"\n`;
        });
        
        await fs.writeFile(combinedFilepath, combinedContent, 'utf8');
        savedFiles.push(combinedFilepath);
        
        this.log(`✅ Saved combined file: ${combinedFilename}`);

        return savedFiles;
    }

    async run() {
        this.log('🚀 Starting Improved LevelDB Automa Extraction...');
        
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
            const structuredData = await this.extractWorkflowData(automaDirs);
            
            if (structuredData.length === 0) {
                this.log('❌ No structured workflow data found');
                return;
            }

            // Save to CSV
            const savedFiles = await this.saveToCSV(structuredData);
            
            this.log('\n✅ Extraction completed!');
            this.log(`📊 Found ${structuredData.length} structured entries`);
            if (savedFiles) {
                this.log(`💾 Saved to ${savedFiles.length} CSV file(s):`);
                savedFiles.forEach(file => this.log(`   - ${path.basename(file)}`));
                this.log('\n📄 Clean CSV format with columns:');
                this.log('   timestamp,workflow_name,action,status');
                this.log('   "2025-08-16T15:30:00Z","Typing Five 5","Started","success"');
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
    const extractor = new ImprovedLevelDBExtractor();
    return await extractor.run();
}

// Execute if run directly
if (require.main === module) {
    extractAutomaLogs().catch(error => {
        console.error('Error:', error.message);
        process.exit(1);
    });
}

module.exports = { ImprovedLevelDBExtractor, extractAutomaLogs };