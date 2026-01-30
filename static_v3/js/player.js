/**
 * PlayerController - Wires PlaybackEngine, SimEnvironments, and Typewriter together.
 * ScreenCast Studio v4.0
 */

class PlayerController {
    constructor() {
        this.engine = new PlaybackEngine();
        this.environment = null;
        this.segments = [];
        this.recording = false;

        // DOM elements
        this.envContainer = document.getElementById('env-container');
        this.segmentNav = document.getElementById('segment-nav');
        this.teleprompter = document.getElementById('teleprompter');
        this.progressFill = document.getElementById('progress-fill');
        this.timeCurrent = document.getElementById('time-current');
        this.timeTotal = document.getElementById('time-total');
        this.btnPlay = document.getElementById('btn-play');
        this.btnPrev = document.getElementById('btn-prev');
        this.btnNext = document.getElementById('btn-next');
        this.btnRecord = document.getElementById('btn-record');
        this.btnStop = document.getElementById('btn-stop');
        this.statusText = document.getElementById('status-text');
        this.statusSegment = document.getElementById('status-segment');

        this._setupCallbacks();
        this._setupControls();
        this._setupKeyboard();
    }

    async init() {
        this.statusText.textContent = 'Loading...';
        try {
            const resp = await fetch('/api/player-data');
            const data = await resp.json();

            if (data.error) {
                this.statusText.textContent = data.error;
                return;
            }

            this.segments = data.segments || [];
            if (this.segments.length === 0) {
                this.statusText.textContent = 'No segments. Generate script and audio first.';
                return;
            }

            // Load into engine
            this.engine.loadSegments(this.segments);

            // Build segment nav
            this._buildSegmentNav();

            // Go to first segment
            this.engine.seekTo(0, 0);

            this.statusText.textContent = 'Ready';
            this.statusSegment.textContent = `${this.segments.length} segments`;

        } catch (err) {
            console.error('Failed to load player data:', err);
            this.statusText.textContent = 'Failed to load data';
        }
    }

    _setupCallbacks() {
        this.engine.onSegmentChange = (index) => {
            this._onSegmentChange(index);
        };

        this.engine.onProgress = (progress) => {
            this._updateProgress(progress);
        };

        this.engine.onEvent = (event) => {
            this._handleEvent(event);
        };

        this.engine.onPlaybackEnd = () => {
            this.btnPlay.innerHTML = '&#9654;';
            this.statusText.textContent = 'Playback complete';
            if (this.recording) {
                this._stopRecording();
            }
        };
    }

    _setupControls() {
        this.btnPlay.addEventListener('click', () => this.togglePlay());
        this.btnPrev.addEventListener('click', () => this.engine.prevSegment());
        this.btnNext.addEventListener('click', () => this.engine.nextSegment());
        this.btnRecord.addEventListener('click', () => this.toggleRecord());
        this.btnStop.addEventListener('click', () => this.stop());

        // Progress bar seeking
        const progressBar = document.getElementById('progress-bar');
        progressBar.addEventListener('click', (e) => {
            const rect = progressBar.getBoundingClientRect();
            const fraction = (e.clientX - rect.left) / rect.width;
            const state = this.engine.getState();
            if (state.duration > 0) {
                this.engine.seekTo(state.currentSegment, fraction * state.duration);
            }
        });
    }

    _setupKeyboard() {
        document.addEventListener('keydown', (e) => {
            // Don't capture if typing in an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            switch (e.key) {
                case ' ':
                    e.preventDefault();
                    this.togglePlay();
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    this.engine.prevSegment();
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    this.engine.nextSegment();
                    break;
                case 'r':
                case 'R':
                    this.toggleRecord();
                    break;
                case 's':
                case 'S':
                    this.stop();
                    break;
            }
        });
    }

    togglePlay() {
        if (this.engine.playing) {
            this.engine.pause();
            this.btnPlay.innerHTML = '&#9654;';
            this.statusText.textContent = 'Paused';
        } else {
            this.engine.play();
            this.btnPlay.innerHTML = '&#10074;&#10074;';
            this.statusText.textContent = 'Playing';
        }
    }

    stop() {
        this.engine.stop();
        this.btnPlay.innerHTML = '&#9654;';
        this.progressFill.style.width = '0%';
        this.timeCurrent.textContent = '0:00';
        this.statusText.textContent = 'Stopped';

        if (this.recording) {
            this._stopRecording();
        }
    }

    async toggleRecord() {
        if (this.recording) {
            await this._stopRecording();
        } else {
            await this._startRecording();
        }
    }

    async _startRecording() {
        const state = this.engine.getState();
        if (state.currentSegment < 0) return;

        try {
            const resp = await fetch('/api/auto-record/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    segment_id: state.currentSegment,
                    ...this._getCaptureRegion()
                })
            });
            const data = await resp.json();

            if (data.success) {
                this.recording = true;
                this.btnRecord.classList.add('recording');
                this.statusText.textContent = 'Recording...';

                // Auto-start playback
                if (!this.engine.playing) {
                    this.togglePlay();
                }
            }
        } catch (err) {
            console.error('Failed to start recording:', err);
        }
    }

    async _stopRecording() {
        try {
            await fetch('/api/auto-record/stop', { method: 'POST' });
        } catch (err) {
            console.error('Failed to stop recording:', err);
        }

        this.recording = false;
        this.btnRecord.classList.remove('recording');
        this.statusText.textContent = 'Recording saved';
    }

    _getCaptureRegion() {
        const rect = this.envContainer.getBoundingClientRect();
        return {
            offset_x: Math.round(rect.left + window.screenX),
            offset_y: Math.round(rect.top + window.screenY),
            width: Math.round(rect.width),
            height: Math.round(rect.height)
        };
    }

    _buildSegmentNav() {
        this.segmentNav.innerHTML = '';
        this.segments.forEach((seg, i) => {
            const badge = document.createElement('span');
            badge.className = 'seg-badge';
            badge.textContent = seg.section || seg.type || `Seg ${i + 1}`;
            badge.dataset.index = i;
            badge.addEventListener('click', () => {
                this.engine.seekTo(i, 0);
                if (!this.engine.playing) {
                    // Just navigate, don't auto-play
                }
            });
            this.segmentNav.appendChild(badge);
        });
    }

    _onSegmentChange(index) {
        // Update badges
        const badges = this.segmentNav.querySelectorAll('.seg-badge');
        badges.forEach((b, i) => {
            b.classList.toggle('active', i === index);
            if (i < index) b.classList.add('completed');
        });

        // Rebuild environment
        this._buildEnvironment(index);

        // Update teleprompter
        this._updateTeleprompter(index);

        // Update status
        this.statusSegment.textContent = `Segment ${index + 1} / ${this.segments.length}`;

        // Update total time
        const seg = this.segments[index];
        const duration = seg.timeline ? seg.timeline.total_duration : 0;
        this.timeTotal.textContent = this._formatTime(duration);
    }

    _buildEnvironment(index) {
        const seg = this.segments[index];
        const envType = seg.env_type || seg.type || 'jupyter';

        // Destroy previous
        if (this.environment) {
            this.environment.destroy();
        }

        // Create new environment
        this.environment = createSimEnvironment(this.envContainer, envType);

        // Pre-populate cells if notebook type
        if (envType === 'notebook' || envType === 'jupyter') {
            const cells = seg.code_cells || seg.cells || [];
            cells.forEach((cell) => {
                this.environment.addCell('', cell.output || '');
            });
        } else if (envType === 'vscode') {
            const filename = seg.filename || 'main.py';
            this.environment.openFile(filename, '');
        } else if (envType === 'terminal') {
            // Terminal starts empty
        }
    }

    _updateTeleprompter(index) {
        this.teleprompter.innerHTML = '';

        this.segments.forEach((seg, i) => {
            const block = document.createElement('div');
            block.style.marginBottom = '16px';

            const label = document.createElement('div');
            label.className = 'section-label';
            label.textContent = seg.section || seg.type || `Segment ${i + 1}`;
            block.appendChild(label);

            const text = document.createElement('div');
            text.className = 'narration-text';
            text.dataset.segIndex = i;

            let narration = seg.narration || '';
            if (typeof narration === 'object') narration = narration.text || '';
            text.textContent = narration;

            if (i === index) {
                text.classList.add('active');
            }

            block.appendChild(text);
            this.teleprompter.appendChild(block);
        });

        // Scroll active into view
        const activeEl = this.teleprompter.querySelector('.narration-text.active');
        if (activeEl) {
            activeEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    _handleEvent(event) {
        if (!this.environment) return;

        const { action, params } = event;

        switch (action) {
            case 'focusCell':
                if (this.environment.focusCell) {
                    this.environment.focusCell(params.cellIndex);
                }
                break;

            case 'startTyping': {
                const code = params.code || '';
                const duration = (params.duration || 2) * 1000;
                let targetEl = null;

                if (this.environment.getCellCodeElement) {
                    targetEl = this.environment.getCellCodeElement(params.cellIndex);
                } else if (this.environment.getEditorElement) {
                    targetEl = this.environment.getEditorElement();
                } else if (this.environment.getCommandElement) {
                    targetEl = this.environment.getCommandElement(params.commandIndex);
                }

                if (targetEl) {
                    const tw = new Typewriter(targetEl, {
                        baseSpeed: Math.max(5, duration / code.length)
                    });
                    this.engine.registerTypewriter(tw);
                    tw.type(code);
                }
                break;
            }

            case 'executeCell':
                if (this.environment.markCellExecuted) {
                    this.environment.markCellExecuted(params.cellIndex);
                }
                break;

            case 'showOutput':
                if (params.cellIndex !== undefined && this.environment.setCellOutput) {
                    this.environment.setCellOutput(params.cellIndex, params.output);
                } else if (this.environment.addOutput) {
                    this.environment.addOutput(params.output);
                } else if (this.environment.showTerminalOutput) {
                    this.environment.showTerminalOutput(params.output);
                }
                break;

            case 'showPrompt':
                if (this.environment.addCommand) {
                    const cells = this.segments[this.engine.currentSegment]?.code_cells ||
                                  this.segments[this.engine.currentSegment]?.cells || [];
                    const cmd = cells[params.commandIndex]?.code || '';
                    this.environment.addCommand(cmd);
                }
                break;

            case 'showBullet':
                // For slide segments, could append text
                break;

            case 'audio_start':
            case 'audio_end':
            case 'segment_end':
                // Internal events, no visual action
                break;
        }
    }

    _updateProgress(progress) {
        this.progressFill.style.width = `${progress.fraction * 100}%`;
        this.timeCurrent.textContent = this._formatTime(progress.time);

        // Update teleprompter active state based on progress
        const narrationEls = this.teleprompter.querySelectorAll('.narration-text');
        narrationEls.forEach((el) => {
            const idx = parseInt(el.dataset.segIndex);
            el.classList.toggle('active', idx === progress.segIndex);
        });
    }

    _formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const player = new PlayerController();
    player.init();
});
