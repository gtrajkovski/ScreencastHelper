/**
 * Simulated IDE Environments for ScreenCast Studio v4.0
 * Renders Jupyter, VS Code, and Terminal environments in the browser.
 */

/* ============================================
   Base SimEnvironment Class
   ============================================ */

class SimEnvironment {
    constructor(container) {
        this.container = container;
        this.container.innerHTML = '';
        this.container.classList.add('sim-environment');
    }

    render() {
        // Override in subclasses
    }

    clear() {
        this.container.innerHTML = '';
    }

    destroy() {
        this.container.classList.remove('sim-environment');
        this.clear();
    }

    getType() {
        return 'base';
    }
}

/* ============================================
   Jupyter Notebook Environment
   ============================================ */

class SimJupyter extends SimEnvironment {
    constructor(container) {
        super(container);
        this.cells = [];
        this.executionCount = 0;
        this.render();
    }

    getType() {
        return 'jupyter';
    }

    render() {
        this.container.classList.add('sim-jupyter');
        this.container.innerHTML = `
            <div class="jupyter-toolbar">
                <button class="toolbar-btn">+</button>
                <button class="toolbar-btn">&#9986;</button>
                <button class="toolbar-btn">&#9776;</button>
                <button class="toolbar-btn run-btn">&#9654; Run</button>
                <button class="toolbar-btn">&#9632; Stop</button>
                <button class="toolbar-btn">&#8635; Restart</button>
                <div class="kernel-status">
                    <span class="kernel-name">Python 3</span>
                    <span class="kernel-dot" id="kernel-dot"></span>
                </div>
            </div>
            <div class="cells-container" id="cells-container"></div>
        `;
        this.cellsContainer = this.container.querySelector('#cells-container');
        this.kernelDot = this.container.querySelector('#kernel-dot');
    }

    addCell(code = '', output = '') {
        const index = this.cells.length;
        const cellEl = document.createElement('div');
        cellEl.className = 'notebook-cell';
        cellEl.dataset.index = index;

        cellEl.innerHTML = `
            <div class="cell-input">
                <div class="cell-label">In [&nbsp;]:</div>
                <div class="cell-code"></div>
            </div>
            <div class="cell-output"></div>
        `;

        this.cellsContainer.appendChild(cellEl);

        const cellData = {
            element: cellEl,
            codeEl: cellEl.querySelector('.cell-code'),
            outputEl: cellEl.querySelector('.cell-output'),
            labelEl: cellEl.querySelector('.cell-label'),
            code: code,
            output: output,
            executed: false
        };

        this.cells.push(cellData);

        if (code) {
            cellData.codeEl.textContent = code;
        }

        return index;
    }

    focusCell(index) {
        // Remove focus from all cells
        this.cells.forEach(c => c.element.classList.remove('focused'));

        if (index >= 0 && index < this.cells.length) {
            this.cells[index].element.classList.add('focused');
            // Scroll cell into view
            this.cells[index].element.scrollIntoView({
                behavior: 'smooth',
                block: 'nearest'
            });
        }
    }

    getCellCodeElement(index) {
        if (index >= 0 && index < this.cells.length) {
            return this.cells[index].codeEl;
        }
        return null;
    }

    setCellOutput(index, output) {
        if (index >= 0 && index < this.cells.length) {
            const cell = this.cells[index];
            cell.output = output;
            cell.outputEl.textContent = output;
            cell.outputEl.classList.add('visible');
        }
    }

    markCellExecuted(index) {
        if (index >= 0 && index < this.cells.length) {
            this.executionCount++;
            const cell = this.cells[index];
            cell.executed = true;
            cell.labelEl.textContent = `In [${this.executionCount}]:`;
            cell.labelEl.classList.add('executed');

            // Show kernel busy briefly
            if (this.kernelDot) {
                this.kernelDot.classList.add('busy');
                setTimeout(() => {
                    this.kernelDot.classList.remove('busy');
                }, 800);
            }

            // Show output if it exists
            if (cell.output) {
                cell.outputEl.textContent = cell.output;
                cell.outputEl.classList.add('visible');
            }
        }
    }

    clear() {
        this.cells = [];
        this.executionCount = 0;
        if (this.cellsContainer) {
            this.cellsContainer.innerHTML = '';
        }
    }
}

/* ============================================
   VS Code Environment
   ============================================ */

class SimVSCode extends SimEnvironment {
    constructor(container) {
        super(container);
        this.tabs = [];
        this.activeTab = -1;
        this.render();
    }

    getType() {
        return 'vscode';
    }

    render() {
        this.container.classList.add('sim-vscode');
        this.container.innerHTML = `
            <div class="activity-bar">
                <div class="activity-icon active" title="Explorer">&#128462;</div>
                <div class="activity-icon" title="Search">&#128269;</div>
                <div class="activity-icon" title="Source Control">&#8726;</div>
                <div class="activity-icon" title="Debug">&#9654;</div>
                <div class="activity-icon" title="Extensions">&#9881;</div>
            </div>
            <div class="vscode-main">
                <div class="tab-bar" id="tab-bar"></div>
                <div class="editor-area">
                    <div class="line-numbers" id="line-numbers"></div>
                    <div class="editor-content" id="editor-content"></div>
                </div>
                <div class="vscode-terminal" style="display:none;">
                    <div class="terminal-header">
                        <span>Terminal</span>
                        <span class="terminal-tab">bash</span>
                    </div>
                    <div class="terminal-body" id="vscode-terminal-body"></div>
                </div>
            </div>
        `;

        this.tabBar = this.container.querySelector('#tab-bar');
        this.lineNumbers = this.container.querySelector('#line-numbers');
        this.editorContent = this.container.querySelector('#editor-content');
        this.terminalPanel = this.container.querySelector('.vscode-terminal');
        this.terminalBody = this.container.querySelector('#vscode-terminal-body');
    }

    openFile(name, content = '') {
        const tabIndex = this.tabs.length;
        const tabEl = document.createElement('div');
        tabEl.className = 'tab';
        tabEl.dataset.index = tabIndex;

        // File icon based on extension
        let icon = '&#128196;';
        if (name.endsWith('.py')) icon = '&#128013;';
        else if (name.endsWith('.js')) icon = 'JS';
        else if (name.endsWith('.json')) icon = '{}';

        tabEl.innerHTML = `<span class="tab-icon">${icon}</span> ${name}`;
        tabEl.addEventListener('click', () => this._activateTab(tabIndex));

        this.tabBar.appendChild(tabEl);
        this.tabs.push({ name, content, element: tabEl });

        this._activateTab(tabIndex);
        return tabIndex;
    }

    _activateTab(index) {
        this.tabs.forEach((t, i) => {
            t.element.classList.toggle('active', i === index);
        });
        this.activeTab = index;

        if (index >= 0 && index < this.tabs.length) {
            this.setEditorContent(this.tabs[index].content);
        }
    }

    setEditorContent(content) {
        if (this.activeTab >= 0 && this.activeTab < this.tabs.length) {
            this.tabs[this.activeTab].content = content;
        }

        this.editorContent.textContent = content;
        this._updateLineNumbers(content);
    }

    _updateLineNumbers(content) {
        const lines = (content || '').split('\n');
        this.lineNumbers.textContent = lines.map((_, i) => i + 1).join('\n');
    }

    getEditorElement() {
        return this.editorContent;
    }

    showTerminalOutput(text) {
        this.terminalPanel.style.display = '';
        this.terminalBody.textContent += text + '\n';
        this.terminalBody.scrollTop = this.terminalBody.scrollHeight;
    }

    clear() {
        this.tabs = [];
        this.activeTab = -1;
        if (this.tabBar) this.tabBar.innerHTML = '';
        if (this.editorContent) this.editorContent.textContent = '';
        if (this.lineNumbers) this.lineNumbers.textContent = '';
        if (this.terminalBody) this.terminalBody.textContent = '';
        if (this.terminalPanel) this.terminalPanel.style.display = 'none';
    }
}

/* ============================================
   Terminal Environment
   ============================================ */

class SimTerminal extends SimEnvironment {
    constructor(container, title = 'Terminal') {
        super(container);
        this.title = title;
        this.commands = [];
        this.prompt = '$ ';
        this.render();
    }

    getType() {
        return 'terminal';
    }

    render() {
        this.container.classList.add('sim-terminal');
        this.container.innerHTML = `
            <div class="terminal-titlebar">
                <div class="window-dots">
                    <span class="dot dot-red"></span>
                    <span class="dot dot-yellow"></span>
                    <span class="dot dot-green"></span>
                </div>
                <div class="title-text">${this.title}</div>
            </div>
            <div class="terminal-body" id="terminal-body"></div>
        `;
        this.terminalBody = this.container.querySelector('#terminal-body');
    }

    setPrompt(text) {
        this.prompt = text;
    }

    addCommand(cmd) {
        const index = this.commands.length;
        const lineEl = document.createElement('div');
        lineEl.className = 'terminal-line';
        lineEl.innerHTML = `
            <span class="terminal-prompt">${this._escapeHtml(this.prompt)}</span>
            <span class="terminal-command" data-cmd-index="${index}"></span>
        `;

        this.terminalBody.appendChild(lineEl);
        this.commands.push({
            element: lineEl,
            commandEl: lineEl.querySelector('.terminal-command'),
            cmd: cmd,
            outputEl: null
        });

        this.terminalBody.scrollTop = this.terminalBody.scrollHeight;
        return index;
    }

    getCommandElement(index) {
        if (index >= 0 && index < this.commands.length) {
            return this.commands[index].commandEl;
        }
        return null;
    }

    addOutput(text) {
        const outputEl = document.createElement('div');
        outputEl.className = 'terminal-output';
        outputEl.textContent = text;
        this.terminalBody.appendChild(outputEl);
        this.terminalBody.scrollTop = this.terminalBody.scrollHeight;

        // Link to last command
        if (this.commands.length > 0) {
            this.commands[this.commands.length - 1].outputEl = outputEl;
        }
    }

    clear() {
        this.commands = [];
        if (this.terminalBody) {
            this.terminalBody.innerHTML = '';
        }
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

/* ============================================
   Factory Function
   ============================================ */

function createSimEnvironment(container, type) {
    switch (type) {
        case 'jupyter':
        case 'notebook':
            return new SimJupyter(container);
        case 'vscode':
            return new SimVSCode(container);
        case 'terminal':
            return new SimTerminal(container);
        default:
            return new SimJupyter(container);
    }
}
