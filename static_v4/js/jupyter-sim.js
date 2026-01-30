/**
 * JupyterSimulator - Renders a fake Jupyter notebook in HTML/CSS.
 * ScreenCast Studio v4.0
 */

class JupyterSimulator {
    constructor(containerElement) {
        this.container = containerElement;
        this.cells = new Map();
        this.executionCount = 0;
        this.kernelDot = null;
    }

    /**
     * Initialize notebook with header, menu, and toolbar.
     */
    init(notebookTitle = 'Untitled.ipynb') {
        this.container.innerHTML = '';
        this.container.className = 'jupyter-notebook';

        // Header
        const header = document.createElement('div');
        header.className = 'jupyter-header';
        header.innerHTML = `
            <span class="jupyter-logo">Jupyter</span>
            <span class="notebook-name">${this._escape(notebookTitle)}</span>
            <div class="kernel-badge">
                Python 3 (ipykernel)
                <span class="kernel-dot" id="jp-kernel-dot"></span>
            </div>
        `;
        this.container.appendChild(header);

        // Menu bar
        const menubar = document.createElement('div');
        menubar.className = 'jupyter-menubar';
        menubar.innerHTML = `
            <span class="menu-item">File</span>
            <span class="menu-item">Edit</span>
            <span class="menu-item">View</span>
            <span class="menu-item">Insert</span>
            <span class="menu-item">Cell</span>
            <span class="menu-item">Kernel</span>
            <span class="menu-item">Help</span>
        `;
        this.container.appendChild(menubar);

        // Toolbar
        const toolbar = document.createElement('div');
        toolbar.className = 'jupyter-toolbar';
        toolbar.innerHTML = `
            <button class="tb-btn">+</button>
            <button class="tb-btn">&#9986;</button>
            <button class="tb-btn">&#9776;</button>
            <span class="tb-separator"></span>
            <button class="tb-btn run">&#9654; Run</button>
            <button class="tb-btn">&#9632;</button>
            <button class="tb-btn">&#8635;</button>
            <span class="tb-separator"></span>
            <span class="cell-type-select">Code</span>
        `;
        this.container.appendChild(toolbar);

        // Cells container
        this.cellsContainer = document.createElement('div');
        this.cellsContainer.className = 'jupyter-cells';
        this.container.appendChild(this.cellsContainer);

        this.kernelDot = this.container.querySelector('#jp-kernel-dot');
        this.cells.clear();
        this.executionCount = 0;
    }

    /**
     * Add a cell to the notebook.
     */
    addCell(cellId, type = 'code', content = '', executionCount = null) {
        const cellEl = document.createElement('div');
        cellEl.className = 'jupyter-cell';
        cellEl.dataset.cellId = cellId;

        const label = executionCount !== null ? `In [${executionCount}]:` : 'In [ ]:';

        if (type === 'code') {
            cellEl.innerHTML = `
                <div class="cell-sidebar">
                    <span class="cell-label">${label}</span>
                </div>
                <div class="cell-content">
                    <div class="cell-input" data-cell-id="${cellId}"></div>
                    <div class="cell-output" data-cell-id="${cellId}"></div>
                </div>
            `;
        } else {
            cellEl.innerHTML = `
                <div class="cell-sidebar"></div>
                <div class="cell-content">
                    <div class="cell-markdown">${this._escape(content)}</div>
                </div>
            `;
        }

        this.cellsContainer.appendChild(cellEl);

        const cellData = {
            id: cellId,
            type,
            element: cellEl,
            inputEl: cellEl.querySelector('.cell-input'),
            outputEl: cellEl.querySelector('.cell-output'),
            labelEl: cellEl.querySelector('.cell-label'),
            content: content,
            executed: executionCount !== null
        };

        this.cells.set(cellId, cellData);

        // Set initial content if provided
        if (content && type === 'code') {
            cellData.inputEl.textContent = content;
        }

        // Start hidden for animation
        cellEl.style.opacity = '0';
        cellEl.style.transform = 'translateY(8px)';

        return cellData;
    }

    /**
     * Show cell with fade-in animation.
     */
    showCell(cellId) {
        const cell = this.cells.get(cellId);
        if (!cell) return;

        cell.element.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        cell.element.style.opacity = '1';
        cell.element.style.transform = 'translateY(0)';

        // Scroll into view
        cell.element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    /**
     * Update cell content (used during typing animation).
     */
    updateCellContent(cellId, content) {
        const cell = this.cells.get(cellId);
        if (!cell || !cell.inputEl) return;
        cell.content = content;
        cell.inputEl.textContent = content;
    }

    /**
     * Get the input element for a cell (for Typewriter targeting).
     */
    getCellInputElement(cellId) {
        const cell = this.cells.get(cellId);
        return cell ? cell.inputEl : null;
    }

    /**
     * Execute cell: show spinner briefly, update label, show output.
     */
    executeCell(cellId, output = null) {
        const cell = this.cells.get(cellId);
        if (!cell) return;

        this.executionCount++;
        const count = this.executionCount;

        // Mark executing
        cell.element.classList.add('executing');
        if (cell.labelEl) {
            cell.labelEl.textContent = 'In [*]:';
        }

        // Kernel busy
        if (this.kernelDot) {
            this.kernelDot.classList.add('busy');
        }

        // After a brief delay, show completed state
        setTimeout(() => {
            cell.element.classList.remove('executing');
            cell.element.classList.add('executed');
            cell.executed = true;

            if (cell.labelEl) {
                cell.labelEl.textContent = `In [${count}]:`;
                cell.labelEl.classList.add('executed');
            }

            if (this.kernelDot) {
                this.kernelDot.classList.remove('busy');
            }

            // Show output if provided
            if (output && cell.outputEl) {
                cell.outputEl.textContent = output;
                cell.outputEl.classList.add('visible');
            }
        }, 600);
    }

    /**
     * Set cell as active (blue border).
     */
    setActiveCell(cellId) {
        // Remove active from all
        this.cells.forEach(c => c.element.classList.remove('active'));

        const cell = this.cells.get(cellId);
        if (cell) {
            cell.element.classList.add('active');
            cell.element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    /**
     * Clear all cells.
     */
    clear() {
        this.cells.clear();
        this.executionCount = 0;
        if (this.cellsContainer) {
            this.cellsContainer.innerHTML = '';
        }
    }

    /**
     * Get the cells container element (for canvas capture).
     */
    getContainer() {
        return this.container;
    }

    _escape(text) {
        const d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }
}
