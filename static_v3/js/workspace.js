// ScreenCast Studio v3.0 - Workspace JavaScript

let currentEnvironment = 'jupyter';
let generated = { script: false, tts: false, demo: false, data: false };
let editMode = false;
let currentAIContext = 'script';
let currentSuggestion = '';
let modificationStatus = {
    'narration_script.md': false,
    'narration_tts.txt': false,
    'demo': false
};

// Store original content for tracking changes
let originalContent = {
    script: '',
    tts: '',
    demo: ''
};

// Project management state
let currentProjectId = null;
let projectSaved = true;
let pendingAction = null;  // Stores action to perform after save/discard
let projectToDelete = null;

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    setupTabs();
    setupEnvironmentButtons();
    setupChatInput();
    setupActionButtons();
    setupQuickActions();
    setupEditMode();
    setupSectionTabs();
    setupAIAssistant();
    setupKeyboardShortcuts();
    setupProjectManagement();
    loadCurrentProject();
});

// Warn before leaving with unsaved changes
window.addEventListener('beforeunload', (e) => {
    if (!projectSaved) {
        e.preventDefault();
        e.returnValue = '';
    }
});

// Tab switching
function setupTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
        });
    });
}

// Environment selection
function setupEnvironmentButtons() {
    document.querySelectorAll('.env-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.env-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentEnvironment = btn.dataset.env;
            updateStatus();
        });
    });

    // Recommend button
    document.getElementById('recommend-env-btn').addEventListener('click', recommendEnvironment);
}

// Chat input
function setupChatInput() {
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');

    sendBtn.addEventListener('click', sendChat);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendChat();
    });
}

// Action buttons
function setupActionButtons() {
    document.getElementById('generate-btn').addEventListener('click', generatePackage);
    document.getElementById('align-btn').addEventListener('click', checkAlignment);
    document.getElementById('quality-btn').addEventListener('click', checkQuality);
    document.getElementById('export-btn').addEventListener('click', () => {
        window.location.href = '/export';
    });
    document.getElementById('record-btn').addEventListener('click', openRecordingStudio);
    document.getElementById('record-studio-btn').addEventListener('click', openRecordingStudio);
}

// Open Recording Studio in new window
function openRecordingStudio() {
    const width = 1400;
    const height = 900;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;

    window.open(
        '/recording-studio',
        'RecordingStudio',
        `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=no`
    );
}

// Quick action buttons
function setupQuickActions() {
    document.querySelectorAll('.quick-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.getElementById('chat-input').value = btn.dataset.action;
        });
    });
}

// ============================================================
// Edit Mode
// ============================================================

function setupEditMode() {
    const toggle = document.getElementById('edit-mode-toggle');
    if (toggle) {
        toggle.addEventListener('change', (e) => {
            editMode = e.target.checked;
            toggleEditMode(editMode);
        });
    }
}

function toggleEditMode(enabled) {
    const previewElements = ['script-preview', 'tts-preview', 'demo-preview'];
    const editorElements = ['script-editor', 'tts-editor', 'demo-editor'];

    previewElements.forEach((id, i) => {
        const preview = document.getElementById(id);
        const editor = document.getElementById(editorElements[i]);

        if (preview && editor) {
            if (enabled) {
                preview.classList.add('hidden');
                editor.classList.remove('hidden');

                // Populate editor with current content
                const content = preview.querySelector('pre')?.textContent || '';
                editor.value = content;

                // Store original for change tracking
                if (i === 0) originalContent.script = content;
                if (i === 1) originalContent.tts = content;
                if (i === 2) originalContent.demo = content;
            } else {
                preview.classList.remove('hidden');
                editor.classList.add('hidden');
            }
        }
    });

    // Track changes in editors
    ['script-editor', 'tts-editor', 'demo-editor'].forEach(id => {
        const editor = document.getElementById(id);
        if (editor) {
            editor.addEventListener('input', () => handleEditorChange(id));
        }
    });
}

function handleEditorChange(editorId) {
    const editor = document.getElementById(editorId);
    let artifactKey, statusId, original;

    if (editorId === 'script-editor') {
        artifactKey = 'narration_script.md';
        statusId = 'script-sync-status';
        original = originalContent.script;
    } else if (editorId === 'tts-editor') {
        artifactKey = 'narration_tts.txt';
        statusId = 'tts-sync-status';
        original = originalContent.tts;
    } else if (editorId === 'demo-editor') {
        artifactKey = 'demo';
        statusId = 'demo-sync-status';
        original = originalContent.demo;
    }

    const isModified = editor.value !== original;
    modificationStatus[artifactKey] = isModified;

    // Update sync status indicator
    const statusEl = document.getElementById(statusId);
    if (statusEl) {
        if (isModified) {
            statusEl.textContent = '● Modified';
            statusEl.classList.add('modified');
            statusEl.classList.remove('synced');
        } else {
            statusEl.textContent = '✓ Saved';
            statusEl.classList.remove('modified');
            statusEl.classList.add('synced');
        }
    }

    // Show propagation warning if script changed
    if (editorId === 'script-editor' && isModified) {
        showPropagationWarning();
    }
}

// ============================================================
// Save Artifacts
// ============================================================

async function saveArtifact(artifactType) {
    let editorId, statusId;

    if (artifactType === 'narration_script.md') {
        editorId = 'script-editor';
        statusId = 'script-sync-status';
    } else if (artifactType === 'narration_tts.txt') {
        editorId = 'tts-editor';
        statusId = 'tts-sync-status';
    }

    const editor = document.getElementById(editorId);
    const content = editor?.value || '';

    try {
        const response = await fetch('/api/update-artifact', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: artifactType,
                content: content
            })
        });

        const data = await response.json();

        if (data.success) {
            // Update status
            const statusEl = document.getElementById(statusId);
            if (statusEl) {
                statusEl.textContent = '✓ Saved';
                statusEl.classList.remove('modified');
                statusEl.classList.add('synced');
            }

            // Update original content
            if (artifactType === 'narration_script.md') {
                originalContent.script = content;
            } else if (artifactType === 'narration_tts.txt') {
                originalContent.tts = content;
            }

            modificationStatus[artifactType] = false;

            // Update preview
            const previewId = artifactType === 'narration_script.md' ? 'script-preview' : 'tts-preview';
            const preview = document.getElementById(previewId);
            if (preview) {
                preview.innerHTML = `<pre>${escapeHtml(content)}</pre>`;
            }

            addChatMessage('system', `✅ ${artifactType} saved`);

            // Check if propagation needed
            if (data.needs_update && data.needs_update.length > 0) {
                showPropagationWarning();
            }
        }
    } catch (error) {
        addChatMessage('assistant', `❌ Error saving: ${error.message}`);
    }
}

async function saveCurrentDemo() {
    const editor = document.getElementById('demo-editor');
    const content = editor?.value || '';

    // Determine demo filename based on environment
    const demoKey = currentEnvironment === 'jupyter' ? 'demo.ipynb' :
                    currentEnvironment === 'terminal' ? 'demo.sh' : 'demo.py';

    try {
        const response = await fetch('/api/update-artifact', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: demoKey,
                content: content
            })
        });

        const data = await response.json();

        if (data.success) {
            const statusEl = document.getElementById('demo-sync-status');
            if (statusEl) {
                statusEl.textContent = '✓ Saved';
                statusEl.classList.remove('modified');
                statusEl.classList.add('synced');
            }
            originalContent.demo = content;
            modificationStatus.demo = false;

            // Update preview
            const preview = document.getElementById('demo-preview');
            if (preview) {
                preview.innerHTML = `<div class="demo-badge">${demoKey}</div><pre>${escapeHtml(content)}</pre>`;
            }

            addChatMessage('system', `✅ ${demoKey} saved`);
        }
    } catch (error) {
        addChatMessage('assistant', `❌ Error saving: ${error.message}`);
    }
}

// ============================================================
// Propagation Warning
// ============================================================

function showPropagationWarning() {
    const warning = document.getElementById('propagation-warning');
    if (warning) {
        warning.classList.remove('hidden');
    }
}

function dismissWarning() {
    const warning = document.getElementById('propagation-warning');
    if (warning) {
        warning.classList.add('hidden');
    }
}

async function propagateChanges(target) {
    addChatMessage('system', `🔄 Regenerating ${target}...`);

    try {
        const response = await fetch('/api/propagate-changes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source: 'narration_script.md',
                targets: [target]
            })
        });

        const data = await response.json();

        if (data.success && data.updated.length > 0) {
            addChatMessage('assistant', `✅ Updated: ${data.updated.join(', ')}`);

            // Refresh artifacts
            const artifactsResponse = await fetch('/api/get-artifacts');
            const artifacts = await artifactsResponse.json();

            if (artifacts.success && artifacts.artifacts[target]) {
                // Update TTS preview/editor
                if (target === 'narration_tts.txt') {
                    const preview = document.getElementById('tts-preview');
                    const editor = document.getElementById('tts-editor');
                    const content = artifacts.artifacts[target];

                    if (preview) {
                        preview.innerHTML = `<div class="tts-notice">✓ TTS Optimized</div><pre>${escapeHtml(content)}</pre>`;
                    }
                    if (editor) {
                        editor.value = content;
                    }
                    originalContent.tts = content;
                }
            }

            dismissWarning();
        } else if (data.errors && data.errors.length > 0) {
            addChatMessage('assistant', `⚠️ Errors: ${data.errors.join(', ')}`);
        }
    } catch (error) {
        addChatMessage('assistant', `❌ Error: ${error.message}`);
    }
}

// ============================================================
// Section Tabs
// ============================================================

function setupSectionTabs() {
    const tabs = document.getElementById('script-section-tabs');
    if (tabs) {
        tabs.addEventListener('click', (e) => {
            if (e.target.classList.contains('section-tab')) {
                // Update active state
                tabs.querySelectorAll('.section-tab').forEach(t => t.classList.remove('active'));
                e.target.classList.add('active');

                // Filter content based on section
                filterScriptSection(e.target.dataset.section);
            }
        });
    }
}

function filterScriptSection(section) {
    const editor = document.getElementById('script-editor');
    const preview = document.getElementById('script-preview');

    if (section === 'all') {
        // Show all content
        return;
    }

    // Scroll to section in editor/preview
    const sectionMap = {
        'hook': '## HOOK',
        'objective': '## OBJECTIVE',
        'content': '## CONTENT',
        'summary': '## SUMMARY',
        'cta': '## CALL TO ACTION'
    };

    const marker = sectionMap[section];
    if (marker && editor && editMode) {
        const content = editor.value;
        const index = content.indexOf(marker);
        if (index !== -1) {
            editor.focus();
            editor.setSelectionRange(index, index);
            // Scroll to position
            const lineHeight = 20;
            const lines = content.substring(0, index).split('\n').length;
            editor.scrollTop = lines * lineHeight - 100;
        }
    }
}

// ============================================================
// AI Assistant
// ============================================================

function setupAIAssistant() {
    // Quick action buttons
    document.querySelectorAll('.ai-action-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const action = btn.dataset.action;
            executeAIAction(action);
        });
    });

    // Custom input
    const aiInput = document.getElementById('ai-custom-input');
    if (aiInput) {
        aiInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendAIRequest();
            }
        });
    }

    // Make panel draggable
    makeDraggable(document.getElementById('ai-assistant-panel'));
}

function openAIAssistant(context) {
    currentAIContext = context;
    const panel = document.getElementById('ai-assistant-panel');
    const contextLabel = document.getElementById('ai-panel-context');

    if (panel) {
        panel.classList.remove('hidden');
        panel.classList.remove('minimized');
    }

    if (contextLabel) {
        contextLabel.textContent = `- ${context.charAt(0).toUpperCase() + context.slice(1)}`;
    }

    // Clear previous messages (keep welcome message)
    const messages = document.getElementById('ai-messages');
    if (messages) {
        messages.innerHTML = `
            <div class="ai-message assistant">
                How can I help improve this ${context}? Click a quick action or describe what you need.
            </div>
        `;
    }

    // Hide suggestion box
    const suggestionBox = document.getElementById('ai-suggestion-box');
    if (suggestionBox) {
        suggestionBox.classList.add('hidden');
    }
}

function closeAIPanel() {
    const panel = document.getElementById('ai-assistant-panel');
    if (panel) {
        panel.classList.add('hidden');
    }
}

function minimizeAIPanel() {
    const panel = document.getElementById('ai-assistant-panel');
    if (panel) {
        panel.classList.toggle('minimized');
    }
}

async function executeAIAction(action) {
    // Get current content based on context
    let content = '';
    if (currentAIContext === 'script') {
        content = document.getElementById('script-editor')?.value ||
                  document.getElementById('script-preview')?.textContent || '';
    } else if (currentAIContext === 'tts') {
        content = document.getElementById('tts-editor')?.value ||
                  document.getElementById('tts-preview')?.textContent || '';
    } else if (currentAIContext === 'demo') {
        content = document.getElementById('demo-editor')?.value ||
                  document.getElementById('demo-preview')?.textContent || '';
    }

    // Add user message
    addAIMessage('user', `Applying: ${action.replace('_', ' ')}`);
    addAIMessage('loading', 'Thinking...');

    try {
        const response = await fetch('/api/ai-improve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: currentAIContext,
                content: content,
                action: action
            })
        });

        const data = await response.json();

        // Remove loading message
        removeLoadingMessage();

        if (data.success) {
            currentSuggestion = data.suggestion;

            // Show suggestion box
            const suggestionBox = document.getElementById('ai-suggestion-box');
            const suggestionContent = document.getElementById('ai-suggestion-content');

            if (suggestionBox && suggestionContent) {
                suggestionContent.textContent = data.suggestion.substring(0, 500) +
                    (data.suggestion.length > 500 ? '...' : '');
                suggestionBox.classList.remove('hidden');
            }

            addAIMessage('assistant', `✅ Suggestion ready! Click "Apply" to use it.`);
        } else {
            addAIMessage('assistant', `❌ ${data.message || 'Failed to generate suggestion'}`);
        }
    } catch (error) {
        removeLoadingMessage();
        addAIMessage('assistant', `❌ Error: ${error.message}`);
    }
}

async function sendAIRequest() {
    const input = document.getElementById('ai-custom-input');
    const message = input?.value?.trim();
    if (!message) return;

    input.value = '';

    // Get current content
    let content = '';
    if (currentAIContext === 'script') {
        content = document.getElementById('script-editor')?.value || '';
    } else if (currentAIContext === 'tts') {
        content = document.getElementById('tts-editor')?.value || '';
    } else if (currentAIContext === 'demo') {
        content = document.getElementById('demo-editor')?.value || '';
    }

    addAIMessage('user', message);
    addAIMessage('loading', 'Thinking...');

    try {
        const response = await fetch('/api/ai-improve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: currentAIContext,
                content: content,
                action: 'custom',
                custom_request: message
            })
        });

        const data = await response.json();
        removeLoadingMessage();

        if (data.success) {
            currentSuggestion = data.suggestion;

            const suggestionBox = document.getElementById('ai-suggestion-box');
            const suggestionContent = document.getElementById('ai-suggestion-content');

            if (suggestionBox && suggestionContent) {
                suggestionContent.textContent = data.suggestion.substring(0, 500) +
                    (data.suggestion.length > 500 ? '...' : '');
                suggestionBox.classList.remove('hidden');
            }

            addAIMessage('assistant', `✅ Done! Click "Apply" to use the suggestion.`);
        } else {
            addAIMessage('assistant', `❌ ${data.message || 'Failed'}`);
        }
    } catch (error) {
        removeLoadingMessage();
        addAIMessage('assistant', `❌ Error: ${error.message}`);
    }
}

function applySuggestion() {
    if (!currentSuggestion) return;

    let editorId;
    if (currentAIContext === 'script') {
        editorId = 'script-editor';
    } else if (currentAIContext === 'tts') {
        editorId = 'tts-editor';
    } else if (currentAIContext === 'demo') {
        editorId = 'demo-editor';
    }

    const editor = document.getElementById(editorId);
    if (editor) {
        // Enable edit mode if not already
        if (!editMode) {
            const toggle = document.getElementById('edit-mode-toggle');
            if (toggle) {
                toggle.checked = true;
                toggleEditMode(true);
            }
        }

        editor.value = currentSuggestion;
        handleEditorChange(editorId);

        // Hide suggestion box
        const suggestionBox = document.getElementById('ai-suggestion-box');
        if (suggestionBox) {
            suggestionBox.classList.add('hidden');
        }

        addAIMessage('assistant', '✅ Applied! Don\'t forget to save.');
    }
}

function addAIMessage(role, content) {
    const messages = document.getElementById('ai-messages');
    if (!messages) return;

    const msg = document.createElement('div');
    msg.className = `ai-message ${role}`;
    msg.textContent = content;
    messages.appendChild(msg);
    messages.scrollTop = messages.scrollHeight;
}

function removeLoadingMessage() {
    const messages = document.getElementById('ai-messages');
    if (!messages) return;

    const loading = messages.querySelector('.ai-message.loading');
    if (loading) {
        loading.remove();
    }
}

// Make element draggable
function makeDraggable(element) {
    if (!element) return;

    const header = element.querySelector('.ai-panel-header');
    if (!header) return;

    let isDragging = false;
    let offsetX, offsetY;

    header.addEventListener('mousedown', (e) => {
        isDragging = true;
        offsetX = e.clientX - element.offsetLeft;
        offsetY = e.clientY - element.offsetTop;
        header.style.cursor = 'grabbing';
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;

        element.style.left = (e.clientX - offsetX) + 'px';
        element.style.top = (e.clientY - offsetY) + 'px';
        element.style.right = 'auto';
    });

    document.addEventListener('mouseup', () => {
        isDragging = false;
        header.style.cursor = 'move';
    });
}

// ============================================================
// Keyboard Shortcuts
// ============================================================

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl+Shift+S to save project
        if (e.ctrlKey && e.shiftKey && e.key === 'S') {
            e.preventDefault();
            saveProject();
            return;
        }

        // Ctrl+S to save current artifact
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();

            // Find active tab and save
            const activeTab = document.querySelector('.tab.active');
            if (activeTab) {
                const tab = activeTab.dataset.tab;
                if (tab === 'script') {
                    saveArtifact('narration_script.md');
                } else if (tab === 'tts') {
                    saveArtifact('narration_tts.txt');
                } else if (tab === 'demo') {
                    saveCurrentDemo();
                }
            }
        }

        // Ctrl+I to open AI assistant
        if (e.ctrlKey && e.key === 'i') {
            e.preventDefault();
            const activeTab = document.querySelector('.tab.active');
            if (activeTab) {
                openAIAssistant(activeTab.dataset.tab);
            }
        }

        // Ctrl+N for new project
        if (e.ctrlKey && e.key === 'n') {
            e.preventDefault();
            newProject();
        }

        // Escape to close modals and AI panel
        if (e.key === 'Escape') {
            closeAIPanel();
            closeNewProjectModal();
            closeSaveAsModal();
            closeDeleteModal();
            closeUnsavedModal();
        }
    });
}

// ============================================================
// Generate Package (updated)
// ============================================================

async function generatePackage() {
    const btn = document.getElementById('generate-btn');
    const overlay = document.getElementById('loading-overlay');

    btn.disabled = true;
    overlay.classList.remove('hidden');

    addChatMessage('system', '🎬 Generating package...');

    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                topic: document.getElementById('topic').value,
                bullets: document.getElementById('bullets').value,
                duration: parseInt(document.getElementById('duration').value) || 7,
                demo_requirements: document.getElementById('demo-req').value,
                environment: currentEnvironment,
                audience: document.getElementById('audience').value
            })
        });

        const data = await response.json();

        if (data.success) {
            // Update previews and editors
            const scriptContent = data.artifacts['narration_script.md'] || '';
            const ttsContent = data.artifacts['narration_tts.txt'] || '';

            const demoKey = currentEnvironment === 'jupyter' ? 'demo.ipynb' :
                           currentEnvironment === 'terminal' ? 'demo.sh' : 'demo.py';
            const demoContent = data.artifacts[demoKey] || data.artifacts['demo.py'] || '';

            // Update script
            document.getElementById('script-preview').innerHTML = `<pre>${escapeHtml(scriptContent)}</pre>`;
            document.getElementById('script-editor').value = scriptContent;
            originalContent.script = scriptContent;

            // Update TTS
            document.getElementById('tts-preview').innerHTML =
                `<div class="tts-notice">✓ TTS Optimized: Removed visual cues, expanded acronyms</div>
                 <pre>${escapeHtml(ttsContent)}</pre>`;
            document.getElementById('tts-editor').value = ttsContent;
            originalContent.tts = ttsContent;

            // Update Demo
            document.getElementById('demo-preview').innerHTML =
                `<div class="demo-badge">${demoKey}</div>
                 <pre>${escapeHtml(demoContent)}</pre>`;
            document.getElementById('demo-editor').value = demoContent;
            document.getElementById('demo-type-badge').textContent = demoKey;
            originalContent.demo = demoContent;

            // Update datasets
            if (data.datasets && data.datasets.length > 0) {
                updateDatasets(data.datasets);
                document.getElementById('data-preview').innerHTML = formatDataPreview(data.datasets);
            }

            // Update project name
            document.getElementById('project-name').textContent =
                document.getElementById('topic').value || 'New Project';

            generated = { script: true, tts: true, demo: true, data: true };
            updateStatus();

            // Reset modification status
            modificationStatus = {
                'narration_script.md': false,
                'narration_tts.txt': false,
                'demo': false
            };

            // Mark project as modified (new content generated)
            markProjectModified();

            addChatMessage('assistant', `✅ Package generated!\n\n${data.message}\n\nReady to review or modify.`);
        } else {
            addChatMessage('assistant', `❌ ${data.message}`);
        }
    } catch (error) {
        addChatMessage('assistant', `❌ Error: ${error.message}`);
    }

    btn.disabled = false;
    overlay.classList.add('hidden');
}

// ============================================================
// Chat functionality
// ============================================================

async function sendChat() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

    input.value = '';
    addChatMessage('user', message);

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        });

        const data = await response.json();
        addChatMessage('assistant', data.response);
    } catch (error) {
        addChatMessage('assistant', `❌ Error: ${error.message}`);
    }
}

function addChatMessage(role, content) {
    const container = document.getElementById('chat-container');
    const msg = document.createElement('div');
    msg.className = `chat-message ${role}`;
    msg.textContent = content;
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
}

// ============================================================
// Check alignment & quality
// ============================================================

async function checkAlignment() {
    addChatMessage('system', '🔍 Checking alignment...');

    try {
        const response = await fetch('/api/check-alignment', { method: 'POST' });
        const data = await response.json();

        document.getElementById('report-preview').innerHTML =
            `<pre>${escapeHtml(data.report)}</pre>`;

        document.querySelector('[data-tab="report"]').click();

        addChatMessage('assistant', data.success ?
            '✅ Alignment check complete. See Report tab.' :
            '❌ No artifacts to check. Generate a package first.');
    } catch (error) {
        addChatMessage('assistant', `❌ Error: ${error.message}`);
    }
}

async function checkQuality() {
    addChatMessage('system', '📊 Running quality checks...');

    try {
        const response = await fetch('/api/check-quality', { method: 'POST' });
        const data = await response.json();

        document.getElementById('report-preview').innerHTML =
            `<pre>${escapeHtml(data.report)}</pre>`;

        document.querySelector('[data-tab="report"]').click();

        addChatMessage('assistant', data.success ?
            '✅ Quality report ready. See Report tab.' :
            '❌ No artifacts to check. Generate a package first.');
    } catch (error) {
        addChatMessage('assistant', `❌ Error: ${error.message}`);
    }
}

// Environment recommendation
async function recommendEnvironment() {
    addChatMessage('system', '🤖 Analyzing best environment...');

    try {
        const response = await fetch('/api/recommend-env', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                topic: document.getElementById('topic').value,
                demo_requirements: document.getElementById('demo-req').value,
                audience: document.getElementById('audience').value
            })
        });

        const data = await response.json();

        if (data.success) {
            document.querySelectorAll('.env-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.env === data.environment);
            });
            currentEnvironment = data.environment;
            updateStatus();

            addChatMessage('assistant',
                `🎬 Recommendation: **${data.environment.toUpperCase()}**\n\n${data.reason}\n\nAlternatives: ${data.alternatives.join(', ')}`);
        }
    } catch (error) {
        addChatMessage('assistant', `❌ Error: ${error.message}`);
    }
}

// ============================================================
// Helpers
// ============================================================

function updateStatus() {
    document.getElementById('status-script').textContent =
        `${generated.script ? '✓' : '○'} Script`;
    document.getElementById('status-script').classList.toggle('active', generated.script);

    document.getElementById('status-tts').textContent =
        `${generated.tts ? '✓' : '○'} TTS`;
    document.getElementById('status-tts').classList.toggle('active', generated.tts);

    document.getElementById('status-demo').textContent =
        `${generated.demo ? '✓' : '○'} Demo`;
    document.getElementById('status-demo').classList.toggle('active', generated.demo);

    document.getElementById('status-data').textContent =
        `${generated.data ? '✓' : '○'} Data`;
    document.getElementById('status-data').classList.toggle('active', generated.data);
}

function updateDatasets(datasets) {
    const list = document.getElementById('datasets-list');
    list.innerHTML = datasets.map(ds => `
        <div class="dataset-item">
            <div class="name">${ds.filename}</div>
            <div class="info">${ds.rows.toLocaleString()} rows • ${ds.columns}</div>
        </div>
    `).join('');
}

function formatDataPreview(datasets) {
    return datasets.map(ds => `
        <div class="data-section">
            <h4>${ds.filename}</h4>
            <p>${ds.rows.toLocaleString()} rows</p>
            <p>Columns: ${ds.columns}</p>
            <table class="data-table">
                <thead>
                    <tr>${ds.columns.split(', ').map(c => `<th>${c}</th>`).join('')}</tr>
                </thead>
                <tbody>
                    <tr>${ds.columns.split(', ').map(() => `<td>...</td>`).join('')}</tr>
                </tbody>
            </table>
        </div>
    `).join('');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================
// Project Management
// ============================================================

function setupProjectManagement() {
    // Project selector dropdown toggle
    const selector = document.getElementById('project-selector');
    const menu = document.getElementById('project-menu');
    const dropdown = document.querySelector('.project-dropdown');

    if (selector && menu) {
        selector.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdown.classList.toggle('open');
            menu.classList.toggle('hidden');

            if (!menu.classList.contains('hidden')) {
                loadProjectList();
            }
        });

        // Close menu when clicking outside
        document.addEventListener('click', (e) => {
            if (!dropdown.contains(e.target)) {
                dropdown.classList.remove('open');
                menu.classList.add('hidden');
            }
        });
    }

    // Save project button in header
    const saveBtn = document.getElementById('save-project-btn');
    if (saveBtn) {
        saveBtn.addEventListener('click', saveProject);
    }

    // Track form changes to mark project as modified
    const formInputs = ['topic', 'duration', 'audience', 'bullets', 'demo-req'];
    formInputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', markProjectModified);
            el.addEventListener('change', markProjectModified);
        }
    });
}

async function loadCurrentProject() {
    try {
        const response = await fetch('/api/projects/current');
        const data = await response.json();

        if (data.success && data.project) {
            const project = data.project;
            currentProjectId = project.id;
            projectSaved = project.saved !== false;

            // Update UI with project data
            document.getElementById('project-name').textContent = project.name || 'Untitled Project';

            if (project.topic) {
                document.getElementById('topic').value = project.topic;
            }
            if (project.duration) {
                document.getElementById('duration').value = project.duration + ' min';
            }
            if (project.audience) {
                document.getElementById('audience').value = project.audience;
            }
            if (project.bullets) {
                document.getElementById('bullets').value = project.bullets;
            }
            if (project.demo_requirements) {
                document.getElementById('demo-req').value = project.demo_requirements;
            }
            if (project.environment) {
                currentEnvironment = project.environment;
                document.querySelectorAll('.env-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.env === project.environment);
                });
            }

            // Load artifacts if present
            if (project.artifacts && Object.keys(project.artifacts).length > 0) {
                loadArtifactsToUI(project.artifacts);
            }

            updateSavedIndicator();
        }
    } catch (error) {
        console.error('Error loading current project:', error);
    }
}

function loadArtifactsToUI(artifacts) {
    const scriptContent = artifacts['narration_script.md'] || '';
    const ttsContent = artifacts['narration_tts.txt'] || '';

    const demoKey = currentEnvironment === 'jupyter' ? 'demo.ipynb' :
                    currentEnvironment === 'terminal' ? 'demo.sh' : 'demo.py';
    const demoContent = artifacts[demoKey] || artifacts['demo.py'] || '';

    if (scriptContent) {
        document.getElementById('script-preview').innerHTML = `<pre>${escapeHtml(scriptContent)}</pre>`;
        document.getElementById('script-editor').value = scriptContent;
        originalContent.script = scriptContent;
        generated.script = true;
    }

    if (ttsContent) {
        document.getElementById('tts-preview').innerHTML =
            `<div class="tts-notice">✓ TTS Optimized</div><pre>${escapeHtml(ttsContent)}</pre>`;
        document.getElementById('tts-editor').value = ttsContent;
        originalContent.tts = ttsContent;
        generated.tts = true;
    }

    if (demoContent) {
        document.getElementById('demo-preview').innerHTML =
            `<div class="demo-badge">${demoKey}</div><pre>${escapeHtml(demoContent)}</pre>`;
        document.getElementById('demo-editor').value = demoContent;
        document.getElementById('demo-type-badge').textContent = demoKey;
        originalContent.demo = demoContent;
        generated.demo = true;
    }

    updateStatus();
}

async function loadProjectList() {
    const list = document.getElementById('project-list');
    if (!list) return;

    try {
        const response = await fetch('/api/projects');
        const data = await response.json();

        if (data.success && data.projects.length > 0) {
            list.innerHTML = data.projects.map(project => `
                <div class="project-list-item ${project.id === currentProjectId ? 'active' : ''}"
                     data-id="${project.id}">
                    <span class="project-icon">🎬</span>
                    <div class="project-details">
                        <div class="project-title">${escapeHtml(project.name || 'Untitled')}</div>
                        <div class="project-meta">${formatDate(project.modified_at)} • ${project.environment}</div>
                    </div>
                    <button class="project-delete" onclick="event.stopPropagation(); deleteProject('${project.id}', '${escapeHtml(project.name)}')" title="Delete">🗑️</button>
                </div>
            `).join('');

            // Add click handlers
            list.querySelectorAll('.project-list-item').forEach(item => {
                item.addEventListener('click', () => {
                    const id = item.dataset.id;
                    if (id !== currentProjectId) {
                        switchProject(id);
                    }
                });
            });
        } else {
            list.innerHTML = '<div class="project-list-empty">No saved projects yet</div>';
        }
    } catch (error) {
        console.error('Error loading project list:', error);
        list.innerHTML = '<div class="project-list-empty">Error loading projects</div>';
    }
}

function formatDate(isoString) {
    if (!isoString) return 'Unknown';
    const date = new Date(isoString);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago';
    if (diff < 86400000) return Math.floor(diff / 3600000) + 'h ago';
    if (diff < 604800000) return Math.floor(diff / 86400000) + 'd ago';

    return date.toLocaleDateString();
}

function markProjectModified() {
    if (projectSaved) {
        projectSaved = false;
        updateSavedIndicator();
        fetch('/api/projects/mark-modified', { method: 'POST' });
    }
}

function updateSavedIndicator() {
    const indicator = document.getElementById('unsaved-indicator');
    const saveBtn = document.getElementById('save-project-btn');

    if (indicator) {
        indicator.classList.toggle('hidden', projectSaved);
    }

    if (saveBtn) {
        saveBtn.classList.toggle('unsaved', !projectSaved);
    }
}

// New Project
function newProject() {
    closeProjectMenu();

    if (!projectSaved) {
        pendingAction = { type: 'new' };
        showUnsavedModal();
        return;
    }

    showNewProjectModal();
}

function showNewProjectModal() {
    const modal = document.getElementById('new-project-modal');
    if (modal) {
        modal.classList.remove('hidden');
        document.getElementById('new-project-name').value = '';
        document.getElementById('new-project-topic').value = '';
        document.getElementById('new-project-name').focus();
    }
}

function closeNewProjectModal() {
    const modal = document.getElementById('new-project-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

async function createNewProject() {
    const name = document.getElementById('new-project-name').value.trim() || 'Untitled Project';
    const topic = document.getElementById('new-project-topic').value.trim();

    try {
        const response = await fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, topic })
        });

        const data = await response.json();

        if (data.success) {
            currentProjectId = data.project.id;
            projectSaved = false;

            // Reset form
            document.getElementById('project-name').textContent = name;
            document.getElementById('topic').value = topic;
            document.getElementById('duration').value = '7 min';
            document.getElementById('audience').value = 'intermediate';
            document.getElementById('bullets').value = '';
            document.getElementById('demo-req').value = '';

            // Reset previews
            document.getElementById('script-preview').innerHTML = `
                <div class="empty-preview">
                    <span class="icon">🎬</span>
                    <p>Click "Generate Package" to create content</p>
                </div>`;
            document.getElementById('tts-preview').innerHTML = '';
            document.getElementById('demo-preview').innerHTML = '';

            // Reset editors
            document.getElementById('script-editor').value = '';
            document.getElementById('tts-editor').value = '';
            document.getElementById('demo-editor').value = '';

            originalContent = { script: '', tts: '', demo: '' };
            generated = { script: false, tts: false, demo: false, data: false };
            updateStatus();
            updateSavedIndicator();

            closeNewProjectModal();
            addChatMessage('system', `📄 Created new project: ${name}`);
        }
    } catch (error) {
        addChatMessage('assistant', `❌ Error creating project: ${error.message}`);
    }
}

// Save Project
async function saveProject() {
    const name = document.getElementById('project-name').textContent || 'Untitled Project';

    try {
        const response = await fetch('/api/projects/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                topic: document.getElementById('topic').value,
                bullets: document.getElementById('bullets').value,
                demo_requirements: document.getElementById('demo-req').value,
                duration: parseInt(document.getElementById('duration').value) || 7,
                audience: document.getElementById('audience').value,
                environment: currentEnvironment
            })
        });

        const data = await response.json();

        if (data.success) {
            currentProjectId = data.project_id;
            projectSaved = true;
            updateSavedIndicator();
            addChatMessage('system', `💾 Project saved: ${name}`);
        } else {
            addChatMessage('assistant', `❌ ${data.message}`);
        }
    } catch (error) {
        addChatMessage('assistant', `❌ Error saving: ${error.message}`);
    }
}

// Save As
function saveProjectAs() {
    closeProjectMenu();
    showSaveAsModal();
}

function showSaveAsModal() {
    const modal = document.getElementById('save-as-modal');
    const nameInput = document.getElementById('save-as-name');
    const currentName = document.getElementById('project-name').textContent;

    if (modal && nameInput) {
        nameInput.value = currentName;
        modal.classList.remove('hidden');
        nameInput.focus();
        nameInput.select();
    }
}

function closeSaveAsModal() {
    const modal = document.getElementById('save-as-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

async function doSaveAs() {
    const name = document.getElementById('save-as-name').value.trim();
    if (!name) return;

    // Clear current ID to create new copy
    currentProjectId = null;
    document.getElementById('project-name').textContent = name;

    closeSaveAsModal();
    await saveProject();
}

// Switch Project
async function switchProject(projectId) {
    closeProjectMenu();

    if (!projectSaved) {
        pendingAction = { type: 'switch', projectId };
        showUnsavedModal();
        return;
    }

    await loadProject(projectId);
}

async function loadProject(projectId, force = false) {
    try {
        const url = `/api/projects/${projectId}${force ? '?force=true' : ''}`;
        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            const project = data.project;
            currentProjectId = project.id;
            projectSaved = true;

            // Update form
            document.getElementById('project-name').textContent = project.name || 'Untitled';
            document.getElementById('topic').value = project.topic || '';
            document.getElementById('duration').value = (project.duration || 7) + ' min';
            document.getElementById('audience').value = project.audience || 'intermediate';
            document.getElementById('bullets').value = project.bullets || '';
            document.getElementById('demo-req').value = project.demo_requirements || '';

            // Update environment
            currentEnvironment = project.environment || 'jupyter';
            document.querySelectorAll('.env-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.env === currentEnvironment);
            });

            // Load artifacts
            if (project.artifacts && Object.keys(project.artifacts).length > 0) {
                loadArtifactsToUI(project.artifacts);
            } else {
                // Reset previews
                document.getElementById('script-preview').innerHTML = `
                    <div class="empty-preview">
                        <span class="icon">🎬</span>
                        <p>Click "Generate Package" to create content</p>
                    </div>`;
                document.getElementById('tts-preview').innerHTML = '';
                document.getElementById('demo-preview').innerHTML = '';
                document.getElementById('script-editor').value = '';
                document.getElementById('tts-editor').value = '';
                document.getElementById('demo-editor').value = '';
                originalContent = { script: '', tts: '', demo: '' };
                generated = { script: false, tts: false, demo: false, data: false };
            }

            updateSavedIndicator();
            updateStatus();
            addChatMessage('system', `📂 Loaded project: ${project.name}`);
        } else if (data.unsaved) {
            pendingAction = { type: 'switch', projectId };
            showUnsavedModal();
        }
    } catch (error) {
        addChatMessage('assistant', `❌ Error loading project: ${error.message}`);
    }
}

// Delete Project
function deleteProject(projectId, projectName) {
    projectToDelete = projectId;
    document.getElementById('delete-project-name').textContent = projectName;
    document.getElementById('delete-modal').classList.remove('hidden');
}

function closeDeleteModal() {
    document.getElementById('delete-modal').classList.add('hidden');
    projectToDelete = null;
}

async function confirmDelete() {
    if (!projectToDelete) return;

    try {
        const response = await fetch(`/api/projects/${projectToDelete}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            // Reload list
            loadProjectList();

            // If deleted current project, reset
            if (projectToDelete === currentProjectId) {
                currentProjectId = null;
                document.getElementById('project-name').textContent = 'Untitled Project';
                projectSaved = true;
                updateSavedIndicator();
            }

            addChatMessage('system', '🗑️ Project deleted');
        }
    } catch (error) {
        addChatMessage('assistant', `❌ Error deleting: ${error.message}`);
    }

    closeDeleteModal();
}

// Unsaved Changes Modal
function showUnsavedModal() {
    const modal = document.getElementById('unsaved-modal');
    const nameEl = document.getElementById('unsaved-project-name');

    if (modal && nameEl) {
        nameEl.textContent = document.getElementById('project-name').textContent || 'current project';
        modal.classList.remove('hidden');
    }
}

function closeUnsavedModal() {
    const modal = document.getElementById('unsaved-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
    pendingAction = null;
}

async function saveAndContinue() {
    await saveProject();
    closeUnsavedModal();
    executePendingAction();
}

function discardAndContinue() {
    projectSaved = true;  // Mark as saved to allow switch
    closeUnsavedModal();
    executePendingAction();
}

function executePendingAction() {
    if (!pendingAction) return;

    const action = pendingAction;
    pendingAction = null;

    if (action.type === 'new') {
        showNewProjectModal();
    } else if (action.type === 'switch') {
        loadProject(action.projectId, true);
    }
}

function closeProjectMenu() {
    const dropdown = document.querySelector('.project-dropdown');
    const menu = document.getElementById('project-menu');
    if (dropdown) dropdown.classList.remove('open');
    if (menu) menu.classList.add('hidden');
}
