// ScreenCast Studio v3.0 - Workspace JavaScript

let currentEnvironment = 'jupyter';
let generated = { script: false, tts: false, demo: false, data: false };
let currentScriptView = 'preview';
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
        '/recording',
        'RecordingStudio',
        `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=no`
    );
}

// Open Presentation Mode
async function openPresentationMode() {
    addChatMessage('system', 'Parsing script for presentation...');
    try {
        const response = await fetch('/api/parse-script', {method: 'POST'});
        const data = await response.json();
        if (!data.success) {
            addChatMessage('assistant', 'Cannot open presentation: ' + data.message);
            return;
        }
        addChatMessage('system', `Presentation ready: ${data.total_segments} segments. Opening...`);
        const w = screen.width;
        const h = screen.height;
        window.open('/present', 'Presentation',
            `width=${w},height=${h},left=0,top=0,resizable=yes`);
    } catch (error) {
        addChatMessage('assistant', 'Error: ' + error.message);
    }
}

// Open Segment Recorder
async function openSegmentRecorder() {
    addChatMessage('system', 'Parsing script into recording segments...');
    try {
        const response = await fetch('/api/parse-segments', {method: 'POST'});
        const data = await response.json();
        if (!data.success) {
            addChatMessage('assistant', 'Cannot open segment recorder: ' + data.message);
            return;
        }
        addChatMessage('system', `${data.total_segments} segments ready. Opening recorder...`);
        window.open('/segment-recorder', '_blank');
    } catch (error) {
        addChatMessage('assistant', 'Error: ' + error.message);
    }
}

async function openRecordingController() {
    addChatMessage('system', 'Parsing segments for recording controller...');
    try {
        const response = await fetch('/api/parse-segments', {method: 'POST'});
        const data = await response.json();
        if (!data.success) {
            addChatMessage('assistant', 'Cannot open controller: ' + data.message);
            return;
        }
        addChatMessage('system', `${data.total_segments} segments ready. Opening popup controller...`);
        const popup = window.open(
            '/recording-controller',
            'RecordingController',
            'width=420,height=650,top=100,left=100,resizable=yes'
        );
        if (!popup) {
            addChatMessage('assistant', 'Popup blocked. Please allow popups for this site.');
        }
    } catch (error) {
        addChatMessage('assistant', 'Error: ' + error.message);
    }
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
    // Set up initial word/line counts
    updateEditorStats('script-editor');
    updateEditorStats('tts-editor');
    updateEditorStats('demo-editor');
    // Initialize script in preview mode
    setScriptView('preview');
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

    // Update word/line counts
    updateEditorStats(editorId);

    // Re-render preview if script changed while in preview mode
    if (editorId === 'script-editor' && currentScriptView === 'preview') {
        renderScriptPreview();
    }

    // Mark project unsaved if modified
    if (isModified) {
        markProjectModified();
    }
}

function updateEditorStats(editorId) {
    const editor = document.getElementById(editorId);
    if (!editor) return;
    const content = editor.value || '';

    if (editorId === 'script-editor') {
        const words = content.trim().split(/\s+/).filter(w => w).length;
        const el = document.getElementById('script-words');
        if (el) el.textContent = words ? `${words} words` : '';
    } else if (editorId === 'tts-editor') {
        const words = content.trim().split(/\s+/).filter(w => w).length;
        const el = document.getElementById('tts-words');
        if (el) el.textContent = words ? `${words} words` : '';
    } else if (editorId === 'demo-editor') {
        const lines = content.split('\n').length;
        const el = document.getElementById('demo-lines');
        if (el) el.textContent = content ? `${lines} lines` : '';
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

    // Show saving status
    const statusEl = document.getElementById(statusId);
    if (statusEl) {
        statusEl.textContent = '⏳ Saving...';
        statusEl.className = 'sync-status saving';
    }

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
            if (statusEl) {
                statusEl.textContent = '✓ Saved';
                statusEl.className = 'sync-status synced';
            }

            if (artifactType === 'narration_script.md') {
                originalContent.script = content;
            } else if (artifactType === 'narration_tts.txt') {
                originalContent.tts = content;
            }

            modificationStatus[artifactType] = false;

            // If script was saved, offer to update TTS
            if (artifactType === 'narration_script.md') {
                showUpdateToast();
            } else {
                addChatMessage('system', `✅ ${artifactType} saved`);
            }
        }
    } catch (error) {
        if (statusEl) {
            statusEl.textContent = '● Modified';
            statusEl.className = 'sync-status modified';
        }
        addChatMessage('assistant', `❌ Error saving: ${error.message}`);
    }
}

async function saveCurrentDemo() {
    const editor = document.getElementById('demo-editor');
    const content = editor?.value || '';

    const demoKey = currentEnvironment === 'jupyter' ? 'demo.ipynb' :
                    currentEnvironment === 'terminal' ? 'demo.sh' : 'demo.py';

    const statusEl = document.getElementById('demo-sync-status');
    if (statusEl) {
        statusEl.textContent = '⏳ Saving...';
        statusEl.className = 'sync-status saving';
    }

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
            if (statusEl) {
                statusEl.textContent = '✓ Saved';
                statusEl.className = 'sync-status synced';
            }
            originalContent.demo = content;
            modificationStatus.demo = false;

            document.getElementById('demo-type-badge').textContent = demoKey;
            addChatMessage('system', `✅ ${demoKey} saved`);
        }
    } catch (error) {
        if (statusEl) {
            statusEl.textContent = '● Modified';
            statusEl.className = 'sync-status modified';
        }
        addChatMessage('assistant', `❌ Error saving: ${error.message}`);
    }
}

// ============================================================
// Auto-Update Propagation (Script → TTS)
// ============================================================

function showUpdateToast() {
    const toast = document.getElementById('update-toast');
    if (toast) toast.style.display = 'flex';
}

function dismissToast() {
    const toast = document.getElementById('update-toast');
    if (toast) toast.style.display = 'none';
    addChatMessage('system', '✅ Script saved. TTS not updated.');
}

async function confirmAutoUpdate() {
    const toast = document.getElementById('update-toast');
    if (toast) toast.style.display = 'none';

    // Show syncing status on TTS
    const statusEl = document.getElementById('tts-sync-status');
    if (statusEl) {
        statusEl.textContent = '🔄 Syncing...';
        statusEl.className = 'sync-status syncing';
    }

    addChatMessage('system', '🔄 Regenerating TTS from updated script...');

    try {
        const response = await fetch('/api/propagate-changes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source: 'narration_script.md',
                targets: ['narration_tts.txt']
            })
        });

        const result = await response.json();

        if (result.success) {
            // Reload TTS content from server
            const artResponse = await fetch('/api/get-artifacts');
            const artData = await artResponse.json();

            if (artData.success && artData.artifacts) {
                const newTts = artData.artifacts['narration_tts.txt'] || '';
                document.getElementById('tts-editor').value = newTts;
                originalContent.tts = newTts;
                modificationStatus['narration_tts.txt'] = false;
                updateEditorStats('tts-editor');
            }

            if (statusEl) {
                statusEl.textContent = '✓ Saved';
                statusEl.className = 'sync-status synced';
            }
            addChatMessage('system', '✅ TTS updated from script!');
        } else {
            throw new Error(result.message);
        }
    } catch (err) {
        if (statusEl) {
            statusEl.textContent = '● Modified';
            statusEl.className = 'sync-status modified';
        }
        addChatMessage('assistant', `❌ TTS update failed: ${err.message}`);
    }
}

async function regenerateFromScript() {
    if (!confirm('Regenerate TTS from the current script? This will overwrite your TTS edits.')) return;
    await confirmAutoUpdate();
}

// ============================================================
// AI Suggestions System
// ============================================================

let currentSuggestionsTarget = 'narration_script.md';

function reviewContent(target) {
    currentSuggestionsTarget = target;
    const targetLabel = document.getElementById('suggestions-target');
    const names = {
        'narration_script.md': 'Script',
        'narration_tts.txt': 'TTS',
    };
    if (targetLabel) targetLabel.textContent = `(${names[target] || target})`;
    document.getElementById('suggestions-panel').style.display = 'block';
    fetchSuggestions();
}

function reviewDemoContent() {
    const demoKey = currentEnvironment === 'jupyter' ? 'demo.ipynb' :
                    currentEnvironment === 'terminal' ? 'demo.sh' : 'demo.py';
    currentSuggestionsTarget = demoKey;
    const targetLabel = document.getElementById('suggestions-target');
    if (targetLabel) targetLabel.textContent = '(Demo)';
    document.getElementById('suggestions-panel').style.display = 'block';
    fetchSuggestions();
}

function refreshSuggestions() {
    fetchSuggestions();
}

function closeSuggestionsPanel() {
    document.getElementById('suggestions-panel').style.display = 'none';
}

async function fetchSuggestions() {
    const listEl = document.getElementById('suggestions-list');
    const focus = document.getElementById('suggestion-focus')?.value || 'general';

    listEl.innerHTML = '<div class="suggestions-loading"><div class="spinner"></div><div>Analyzing content...</div></div>';

    try {
        const response = await fetch('/api/get-suggestions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                target: currentSuggestionsTarget,
                focus: focus
            })
        });

        const result = await response.json();

        if (result.success) {
            renderSuggestionCards(result.suggestions);
        } else {
            throw new Error(result.message);
        }
    } catch (err) {
        listEl.innerHTML = `<div class="suggestions-loading"><div>Error: ${err.message}</div><button onclick="fetchSuggestions()" class="btn btn-sm" style="margin-top:10px">Try Again</button></div>`;
    }
}

function renderSuggestionCards(suggestions) {
    const listEl = document.getElementById('suggestions-list');

    if (!suggestions || suggestions.length === 0) {
        listEl.innerHTML = '<div class="suggestions-loading"><div>No suggestions - looking good!</div></div>';
        return;
    }

    listEl.innerHTML = suggestions.map((s, i) => {
        const id = s.id || String(i);
        const escapedSuggestion = encodeURIComponent(s.suggestion || '');
        return `
        <div class="suggestion-card" data-id="${id}" data-suggestion="${escapedSuggestion}">
            <div class="suggestion-card-header">
                <span class="suggestion-type ${s.type || 'improvement'}">${s.type || 'improvement'}</span>
                <span class="suggestion-section">${s.section || 'general'}</span>
                <span class="suggestion-priority ${s.priority || 'medium'}">${s.priority || 'medium'}</span>
            </div>
            ${s.issue ? `<div class="suggestion-issue">${escapeHtml(s.issue)}</div>` : ''}
            <div class="suggestion-text">${escapeHtml(s.suggestion || '')}</div>
            <div class="suggestion-actions">
                <button class="btn-accept" onclick="acceptSuggestionCard('${id}')">✓ Accept</button>
                <button class="btn-dismiss-card" onclick="dismissSuggestionCard('${id}')">✕ Dismiss</button>
                <button class="btn-edit-card" onclick="editSuggestionCard('${id}')">✏️ Edit</button>
            </div>
        </div>`;
    }).join('');
}

async function acceptSuggestionCard(id) {
    const card = document.querySelector(`.suggestion-card[data-id="${id}"]`);
    if (!card) return;

    const suggestion = decodeURIComponent(card.dataset.suggestion);
    const actionsEl = card.querySelector('.suggestion-actions');
    const originalActions = actionsEl.innerHTML;
    actionsEl.innerHTML = '<span class="suggestion-implementing">Implementing...</span>';

    try {
        const response = await fetch('/api/implement-suggestion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                suggestion: suggestion,
                target: currentSuggestionsTarget,
                action: 'improve'
            })
        });

        const result = await response.json();

        if (result.success) {
            // Update the editor with the new content
            const editorMap = {
                'narration_script.md': 'script-editor',
                'narration_tts.txt': 'tts-editor'
            };
            let editorId = editorMap[result.target];
            if (!editorId && result.target.startsWith('demo.')) {
                editorId = 'demo-editor';
            }

            if (editorId) {
                const editor = document.getElementById(editorId);
                if (editor) {
                    editor.value = result.updated_content;
                    handleEditorChange(editorId);
                }
            }

            card.classList.add('accepted');
            actionsEl.innerHTML = '<span class="suggestion-applied">✓ Applied!</span>';

            // Fade out card
            setTimeout(() => {
                card.style.transition = 'all 0.3s';
                card.style.opacity = '0';
                card.style.maxHeight = '0';
                card.style.padding = '0';
                card.style.margin = '0';
                card.style.overflow = 'hidden';
                setTimeout(() => card.remove(), 300);
            }, 1500);

            addChatMessage('system', `💡 Suggestion applied to ${result.target}`);
        } else {
            throw new Error(result.message);
        }
    } catch (err) {
        actionsEl.innerHTML = originalActions;
        addChatMessage('assistant', `❌ Failed to apply suggestion: ${err.message}`);
    }
}

function dismissSuggestionCard(id) {
    const card = document.querySelector(`.suggestion-card[data-id="${id}"]`);
    if (card) {
        card.style.transition = 'all 0.3s';
        card.style.opacity = '0';
        card.style.maxHeight = '0';
        card.style.overflow = 'hidden';
        setTimeout(() => card.remove(), 300);
    }
}

function editSuggestionCard(id) {
    const card = document.querySelector(`.suggestion-card[data-id="${id}"]`);
    if (!card) return;

    const textEl = card.querySelector('.suggestion-text');
    const currentText = textEl.textContent;

    textEl.innerHTML = `<textarea class="suggestion-edit-area">${currentText}</textarea>`;

    const textarea = textEl.querySelector('textarea');
    textarea.focus();
    textarea.addEventListener('input', () => {
        card.dataset.suggestion = encodeURIComponent(textarea.value);
    });

    const editBtn = card.querySelector('.btn-edit-card');
    editBtn.textContent = '✓ Done';
    editBtn.onclick = () => {
        const newText = textarea.value;
        textEl.textContent = newText;
        card.dataset.suggestion = encodeURIComponent(newText);
        editBtn.textContent = '✏️ Edit';
        editBtn.onclick = () => editSuggestionCard(id);
    };
}

async function acceptAllSuggestions() {
    const cards = document.querySelectorAll('.suggestion-card:not(.accepted)');
    if (cards.length === 0) return;
    if (!confirm(`Apply all ${cards.length} suggestions sequentially?`)) return;

    for (const card of cards) {
        await acceptSuggestionCard(card.dataset.id);
        await new Promise(r => setTimeout(r, 500));
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
                // Update TTS editor
                if (target === 'narration_tts.txt') {
                    const editor = document.getElementById('tts-editor');
                    const content = artifacts.artifacts[target];

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
    if (section === 'all') {
        if (currentScriptView === 'preview') {
            const preview = document.getElementById('script-preview');
            if (preview) preview.scrollTop = 0;
        } else {
            const editor = document.getElementById('script-editor');
            if (editor) editor.scrollTop = 0;
        }
        return;
    }

    jumpToSection(section);
}

function jumpToSection(section) {
    const sectionMap = {
        'hook': '## HOOK',
        'objective': '## OBJECTIVE',
        'content': '## CONTENT',
        'summary': '## SUMMARY',
        'cta': '## CALL TO ACTION'
    };

    const marker = sectionMap[section];
    if (!marker) return;

    if (currentScriptView === 'preview') {
        const preview = document.getElementById('script-preview');
        if (!preview) return;
        const heading = preview.querySelector(`[data-section="${section}"]`);
        if (heading) {
            heading.scrollIntoView({ behavior: 'smooth', block: 'start' });
            heading.classList.add('section-highlight');
            setTimeout(() => heading.classList.remove('section-highlight'), 1500);
        }
    } else {
        const editor = document.getElementById('script-editor');
        if (!editor) return;
        const content = editor.value;
        const index = content.indexOf(marker);
        if (index !== -1) {
            editor.focus();
            editor.setSelectionRange(index, index);
            const lineHeight = 20;
            const lines = content.substring(0, index).split('\n').length;
            editor.scrollTop = lines * lineHeight - 100;
        }
    }
}

function setScriptView(view) {
    currentScriptView = view;
    const editor = document.getElementById('script-editor');
    const preview = document.getElementById('script-preview');
    const toggleBtns = document.querySelectorAll('#script-view-toggle .view-btn');

    toggleBtns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
    });

    if (view === 'preview') {
        editor.style.display = 'none';
        preview.style.display = 'block';
        renderScriptPreview();
    } else {
        preview.style.display = 'none';
        editor.style.display = 'block';
        editor.focus();
    }
}

function renderScriptPreview() {
    const editor = document.getElementById('script-editor');
    const preview = document.getElementById('script-preview');
    if (!editor || !preview) return;

    const rawText = editor.value;
    if (!rawText.trim()) {
        preview.innerHTML = '<p class="empty-state">Narration script will appear here. Click \'Generate Package\' to create content.</p>';
        return;
    }

    // Configure marked for safe rendering
    if (typeof marked !== 'undefined') {
        let html = marked.parse(rawText);

        // Style visual cues: [click here], [scroll down], etc.
        html = html.replace(/\[PAUSE\]/g, '<span class="visual-cue pause-marker">[PAUSE]</span>');
        html = html.replace(/\[([^\]]+)\]/g, '<span class="visual-cue">[$1]</span>');

        // Add data-section attributes to section headings
        html = html.replace(/<h2[^>]*>(HOOK|OBJECTIVE|CONTENT|SUMMARY|CALL TO ACTION|CTA)[^<]*<\/h2>/gi, (match, section) => {
            const sectionKey = section.toLowerCase().replace('call to action', 'cta');
            return match.replace('<h2', `<h2 data-section="${sectionKey}"`);
        });

        preview.innerHTML = html;
    } else {
        // Fallback if marked.js not loaded
        preview.innerHTML = '<pre>' + rawText.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</pre>';
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
        content = document.getElementById('script-editor')?.value || '';
    } else if (currentAIContext === 'tts') {
        content = document.getElementById('tts-editor')?.value || '';
    } else if (currentAIContext === 'demo') {
        content = document.getElementById('demo-editor')?.value || '';
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

        // Ctrl+O to open project file
        if (e.ctrlKey && e.key === 'o') {
            e.preventDefault();
            openProjectFile();
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
            // Update editors directly
            const scriptContent = data.artifacts['narration_script.md'] || '';
            const ttsContent = data.artifacts['narration_tts.txt'] || '';

            const demoKey = currentEnvironment === 'jupyter' ? 'demo.ipynb' :
                           currentEnvironment === 'terminal' ? 'demo.sh' : 'demo.py';
            const demoContent = data.artifacts[demoKey] || data.artifacts['demo.py'] || '';

            // Update script editor
            document.getElementById('script-editor').value = scriptContent;
            originalContent.script = scriptContent;

            // Update TTS editor
            document.getElementById('tts-editor').value = ttsContent;
            originalContent.tts = ttsContent;

            // Update Demo editor
            document.getElementById('demo-editor').value = demoContent;
            document.getElementById('demo-type-badge').textContent = demoKey;
            originalContent.demo = demoContent;

            // Update word/line counts
            updateEditorStats('script-editor');
            updateEditorStats('tts-editor');
            updateEditorStats('demo-editor');

            // Render script preview if in preview mode
            if (currentScriptView === 'preview') {
                renderScriptPreview();
            }

            // Reset sync statuses to saved
            ['script-sync-status', 'tts-sync-status', 'demo-sync-status'].forEach(id => {
                const el = document.getElementById(id);
                if (el) { el.textContent = '✓ Saved'; el.className = 'sync-status synced'; }
            });

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
        document.getElementById('script-editor').value = scriptContent;
        originalContent.script = scriptContent;
        generated.script = true;
    }

    if (ttsContent) {
        document.getElementById('tts-editor').value = ttsContent;
        originalContent.tts = ttsContent;
        generated.tts = true;
    }

    if (demoContent) {
        document.getElementById('demo-editor').value = demoContent;
        document.getElementById('demo-type-badge').textContent = demoKey;
        originalContent.demo = demoContent;
        generated.demo = true;
    }

    // Update stats and sync statuses
    updateEditorStats('script-editor');
    updateEditorStats('tts-editor');
    updateEditorStats('demo-editor');
    ['script-sync-status', 'tts-sync-status', 'demo-sync-status'].forEach(id => {
        const el = document.getElementById(id);
        if (el) { el.textContent = '✓ Saved'; el.className = 'sync-status synced'; }
    });

    // Render script preview if in preview mode
    if (currentScriptView === 'preview') {
        renderScriptPreview();
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

            // Reset editors
            document.getElementById('script-editor').value = '';
            document.getElementById('tts-editor').value = '';
            document.getElementById('demo-editor').value = '';
            renderScriptPreview();

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

// Export Project - with Windows Explorer save dialog
async function exportProjectDialog() {
    closeProjectMenu();
    try {
        const name = document.getElementById('project-name').textContent || 'my-project';
        const dialogRes = await fetch('/api/save-dialog', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ default_name: name, type: 'project' })
        });
        const dialog = await dialogRes.json();

        if (!dialog.success) {
            if (dialog.cancelled) return;
            throw new Error(dialog.message);
        }

        const exportRes = await fetch('/api/projects/export', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ filepath: dialog.filepath })
        });
        const result = await exportRes.json();

        if (result.success) {
            projectSaved = true;
            updateSavedIndicator();
            addChatMessage('system', `📦 Exported to ${result.filepath} (${result.size_kb} KB)`);
        } else {
            throw new Error(result.message);
        }
    } catch (err) {
        addChatMessage('assistant', `❌ Export failed: ${err.message}`);
    }
}

// Open Project - with Windows Explorer open dialog
async function openProjectFile() {
    closeProjectMenu();

    if (!projectSaved) {
        pendingAction = { type: 'open-file' };
        showUnsavedModal();
        return;
    }

    await doOpenProjectFile();
}

async function doOpenProjectFile() {
    try {
        const dialogRes = await fetch('/api/open-dialog', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ type: 'project' })
        });
        const dialog = await dialogRes.json();

        if (!dialog.success) {
            if (dialog.cancelled) return;
            throw new Error(dialog.message);
        }

        const importRes = await fetch('/api/projects/import-file', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ filepath: dialog.filepath })
        });
        const result = await importRes.json();

        if (result.success) {
            currentProjectId = result.project.id;
            projectSaved = false;
            updateSavedIndicator();
            loadCurrentProject();
            addChatMessage('system', `📂 Opened: ${result.project.name || 'Untitled'}`);
        } else {
            throw new Error(result.message);
        }
    } catch (err) {
        addChatMessage('assistant', `❌ Open failed: ${err.message}`);
    }
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
                document.getElementById('script-editor').value = '';
                document.getElementById('tts-editor').value = '';
                document.getElementById('demo-editor').value = '';
                renderScriptPreview();
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
    } else if (action.type === 'open-file') {
        doOpenProjectFile();
    }
}

function closeProjectMenu() {
    const dropdown = document.querySelector('.project-dropdown');
    const menu = document.getElementById('project-menu');
    if (dropdown) dropdown.classList.remove('open');
    if (menu) menu.classList.add('hidden');
}
