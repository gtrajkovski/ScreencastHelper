// ScreenCast Studio - Frontend JavaScript

// Tab Navigation
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
        // Update nav
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');

        // Update content
        const tabId = item.dataset.tab + '-tab';
        document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
        document.getElementById(tabId).classList.add('active');
    });
});

// Loading State
function showLoading() {
    document.getElementById('loading').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}

// Toast Notifications
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = 'toast ' + type + ' show';

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Copy to Clipboard
function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    const text = element.innerText || element.textContent;

    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!');
    }).catch(err => {
        showToast('Failed to copy', 'error');
    });
}

// Download Content
function downloadContent(elementId, filename) {
    const element = document.getElementById(elementId);
    const text = element.innerText || element.textContent;

    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast('Downloaded ' + filename);
}

// Generate Script
async function generateScript() {
    const bullets = document.getElementById('bullets').value;
    const duration = document.getElementById('duration').value;
    const topic = document.getElementById('topic').value;

    if (!bullets.trim()) {
        showToast('Please enter bullet points', 'error');
        return;
    }

    showLoading();

    try {
        const response = await fetch('/api/generate-script', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bullets, duration, topic })
        });

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        document.getElementById('script-output').textContent = data.script;
        document.getElementById('script-stats').textContent =
            `${data.total_words} words | ~${data.estimated_duration} min`;

        showToast('Script generated successfully!');
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Send Script to TTS
function sendToTTS() {
    const scriptOutput = document.getElementById('script-output').textContent;
    if (!scriptOutput) {
        showToast('Generate a script first', 'error');
        return;
    }

    // Switch to TTS tab
    document.querySelector('[data-tab="tts"]').click();

    // Populate TTS input
    document.getElementById('tts-input').value = scriptOutput;

    showToast('Script sent to TTS Optimizer');
}

// Optimize TTS
async function optimizeTTS() {
    const script = document.getElementById('tts-input').value;
    const format = document.getElementById('tts-format').value;

    if (!script.trim()) {
        showToast('Please enter a script to optimize', 'error');
        return;
    }

    showLoading();

    try {
        const response = await fetch('/api/optimize-tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ script, format })
        });

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        document.getElementById('tts-output').textContent = data.optimized;

        // Show changes
        const changesDiv = document.getElementById('tts-changes');
        if (data.changes && data.changes.length > 0) {
            changesDiv.innerHTML = '<h4>Replacements Made:</h4>' +
                data.changes.map(c =>
                    `<div class="change-item">
                        <span class="change-original">${c.original}</span>
                        <span class="change-arrow">→</span>
                        <span class="change-replacement">${c.replacement}</span>
                    </div>`
                ).join('');
        } else {
            changesDiv.innerHTML = '<h4>No replacements needed</h4>';
        }

        showToast('TTS optimization complete!');
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Generate Demo
async function generateDemo() {
    const script = document.getElementById('demo-script').value;
    const requirements = document.getElementById('demo-requirements').value;
    const title = document.getElementById('demo-title').value || 'Demo';
    const useAi = document.getElementById('demo-use-ai').checked;

    if (!script.trim()) {
        showToast('Please enter a script', 'error');
        return;
    }

    showLoading();

    try {
        const response = await fetch('/api/generate-demo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ script, requirements, title, use_ai: useAi })
        });

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        document.getElementById('demo-output').textContent = data.code;

        showToast('Demo generated successfully!');
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Generate Asset
async function generateAsset(type) {
    let config = {};

    if (type === 'csv') {
        const columnsRaw = document.getElementById('csv-columns').value;
        config = {
            columns: columnsRaw.split(',').map(c => c.trim()),
            rows: parseInt(document.getElementById('csv-rows').value),
            include_issues: document.getElementById('csv-issues').checked
        };
    } else if (type === 'terminal') {
        try {
            config = {
                validation_results: JSON.parse(document.getElementById('terminal-checks').value)
            };
        } catch (e) {
            showToast('Invalid JSON for validation checks', 'error');
            return;
        }
    } else if (type === 'yaml') {
        config = {
            source: document.getElementById('yaml-source').value,
            target: document.getElementById('yaml-target').value,
            transformations: [
                { name: 'filter_nulls', description: 'Remove null rows' },
                { name: 'aggregate', description: 'Group by category' }
            ]
        };
    } else if (type === 'html') {
        config = {
            title: document.getElementById('html-title').value
        };
    }

    showLoading();

    try {
        const response = await fetch('/api/generate-asset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type, config })
        });

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        // Show output
        const container = document.getElementById('asset-output-container');
        container.style.display = 'block';

        document.getElementById('asset-filename').textContent = data.filename;
        document.getElementById('asset-output').textContent = data.content;

        // Update download button
        const downloadBtn = document.getElementById('asset-download-btn');
        downloadBtn.onclick = () => downloadContent('asset-output', data.filename);

        // Show preview for HTML
        const previewBtn = document.getElementById('asset-preview-btn');
        if (type === 'html') {
            previewBtn.style.display = 'inline-flex';
            previewBtn.onclick = () => {
                const win = window.open('', '_blank');
                win.document.write(data.content);
                win.document.close();
            };
        } else {
            previewBtn.style.display = 'none';
        }

        // Scroll to output
        container.scrollIntoView({ behavior: 'smooth' });

        showToast(`${data.filename} generated!`);
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + Enter to generate
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        const activeTab = document.querySelector('.tab-content.active');
        if (activeTab.id === 'script-tab') {
            generateScript();
        } else if (activeTab.id === 'tts-tab') {
            optimizeTTS();
        } else if (activeTab.id === 'demo-tab') {
            generateDemo();
        }
    }
});
