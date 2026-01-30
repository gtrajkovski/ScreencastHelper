/**
 * PlaybackEngine - Orchestrates timeline execution with audio and animations.
 * ScreenCast Studio v4.0
 *
 * Coordinates JupyterSimulator, TypewriterEngine, and AudioController
 * to play a synchronized segment with timed events.
 */

class PlaybackEngine {
    /**
     * @param {JupyterSimulator} jupyter
     * @param {TypewriterEngine} typewriter
     * @param {AudioController} audioController
     */
    constructor(jupyter, typewriter, audioController) {
        this.jupyter = jupyter;
        this.typewriter = typewriter;
        this.audio = audioController;

        this.segmentData = null;
        this.timeline = null;
        this.audioUrl = null;
        this.audioBuffer = null;

        this.isPlaying = false;
        this.currentTime = 0;
        this._rafId = null;
        this._eventIndex = 0;
        this._startTimestamp = 0;
        this._pauseOffset = 0;
        this._scheduledTimers = [];

        // Callbacks
        this.onProgress = null;   // (timeMs, totalMs) => {}
        this.onComplete = null;   // () => {}
    }

    /**
     * Load segment data and timeline for playback.
     * @param {Object} segmentData - Segment object with cells, narration, etc.
     * @param {Object} timeline - {events: [{time_ms, type, data}], total_duration_ms}
     * @param {string|null} audioUrl - URL to audio file, or null
     */
    async loadSegment(segmentData, timeline, audioUrl = null) {
        this.stop();
        this.segmentData = segmentData;
        this.timeline = timeline;
        this.audioUrl = audioUrl;
        this.audioBuffer = null;
        this._eventIndex = 0;
        this._pauseOffset = 0;

        // Pre-load audio if available
        if (audioUrl) {
            try {
                this.audioBuffer = await this.audio.loadAudio(audioUrl);
            } catch (err) {
                console.warn('Audio load failed:', err);
                this.audioBuffer = null;
            }
        }
    }

    /**
     * Start or resume playback.
     */
    async play() {
        if (!this.timeline) return;
        this.isPlaying = true;

        // Resume audio context if needed
        if (this.audio.audioContext?.state === 'suspended') {
            await this.audio.audioContext.resume();
        }

        // Start audio
        if (this.audioBuffer) {
            this.audio.play(this.audioBuffer, this._pauseOffset / 1000).then(() => {
                // Audio ended naturally
                if (this.isPlaying) {
                    this._finish();
                }
            });
        }

        // Schedule events
        this._scheduleEvents(this._pauseOffset);

        // Start progress tick
        this._startTimestamp = performance.now() - this._pauseOffset;
        this._tick();
    }

    /**
     * Pause playback.
     */
    pause() {
        this.isPlaying = false;
        this._pauseOffset = this._getCurrentTimeMs();

        // Pause audio
        this.audio.pause();

        // Cancel scheduled events
        this._cancelTimers();

        // Stop progress tick
        if (this._rafId) {
            cancelAnimationFrame(this._rafId);
            this._rafId = null;
        }

        // Pause typewriter
        this.typewriter.stop();
    }

    /**
     * Stop and reset.
     */
    stop() {
        this.isPlaying = false;
        this._pauseOffset = 0;
        this._eventIndex = 0;

        this.audio.stop();
        this.typewriter.stop();
        this._cancelTimers();

        if (this._rafId) {
            cancelAnimationFrame(this._rafId);
            this._rafId = null;
        }
    }

    /**
     * Seek to specific time in milliseconds.
     */
    seek(timeMs) {
        const wasPlaying = this.isPlaying;
        this.stop();
        this._pauseOffset = Math.max(0, Math.min(timeMs, this._getTotalMs()));

        // Find the event index for this time
        this._eventIndex = 0;
        if (this.timeline && this.timeline.events) {
            for (let i = 0; i < this.timeline.events.length; i++) {
                if (this.timeline.events[i].time_ms <= timeMs) {
                    this._eventIndex = i + 1;
                } else {
                    break;
                }
            }
        }

        if (wasPlaying) this.play();
    }

    // ---- Private ----

    _getCurrentTimeMs() {
        if (!this.isPlaying) return this._pauseOffset;

        // Use audio time if available, otherwise wall clock
        if (this.audioBuffer && this.audio.isPlaying) {
            return this.audio.getCurrentTime() * 1000;
        }
        return performance.now() - this._startTimestamp;
    }

    _getTotalMs() {
        return this.timeline ? (this.timeline.total_duration_ms || 0) : 0;
    }

    _scheduleEvents(fromMs) {
        if (!this.timeline || !this.timeline.events) return;

        const now = performance.now();

        for (let i = this._eventIndex; i < this.timeline.events.length; i++) {
            const event = this.timeline.events[i];
            const delay = event.time_ms - fromMs;

            if (delay < 0) {
                // Event already past, fire immediately for catch-up
                this._executeEvent(event);
                this._eventIndex = i + 1;
                continue;
            }

            const timer = setTimeout(() => {
                if (!this.isPlaying) return;
                this._executeEvent(event);
                this._eventIndex = i + 1;
            }, delay);

            this._scheduledTimers.push(timer);
        }
    }

    _cancelTimers() {
        this._scheduledTimers.forEach(t => clearTimeout(t));
        this._scheduledTimers = [];
    }

    _tick() {
        if (!this.isPlaying) return;

        const timeMs = this._getCurrentTimeMs();
        const totalMs = this._getTotalMs();

        if (this.onProgress) {
            this.onProgress(timeMs, totalMs);
        }

        // Check if playback should end (no audio case)
        if (!this.audioBuffer && timeMs >= totalMs) {
            this._finish();
            return;
        }

        this._rafId = requestAnimationFrame(() => this._tick());
    }

    _finish() {
        this.isPlaying = false;
        this._cancelTimers();

        if (this._rafId) {
            cancelAnimationFrame(this._rafId);
            this._rafId = null;
        }

        // Fire remaining events
        if (this.timeline && this.timeline.events) {
            for (let i = this._eventIndex; i < this.timeline.events.length; i++) {
                this._executeEvent(this.timeline.events[i]);
            }
        }

        if (this.onProgress) {
            this.onProgress(this._getTotalMs(), this._getTotalMs());
        }

        if (this.onComplete) {
            this.onComplete();
        }
    }

    /**
     * Execute a single timeline event.
     */
    _executeEvent(event) {
        const { type, data } = event;

        switch (type) {
            case 'audio_start':
                // Handled by play()
                break;

            case 'audio_end':
            case 'segment_end':
                // Handled by _finish()
                break;

            case 'show_cell':
            case 'focusCell': {
                const cellId = data.cell_id || data.cellId;
                const cellIndex = data.cellIndex;
                if (cellId) {
                    this.jupyter.showCell(cellId);
                    this.jupyter.setActiveCell(cellId);
                } else if (cellIndex !== undefined) {
                    // Find cell by index from segment data
                    const cells = this.segmentData?.cells || [];
                    if (cells[cellIndex]) {
                        this.jupyter.showCell(cells[cellIndex].id);
                        this.jupyter.setActiveCell(cells[cellIndex].id);
                    }
                }
                break;
            }

            case 'type_code':
            case 'startTyping': {
                const cellId = data.cell_id || data.cellId;
                const text = data.text || data.code || '';
                const durationMs = data.duration_ms || (data.duration ? data.duration * 1000 : 2000);

                let targetEl = null;
                if (cellId) {
                    targetEl = this.jupyter.getCellInputElement(cellId);
                } else if (data.cellIndex !== undefined) {
                    const cells = this.segmentData?.cells || [];
                    if (cells[data.cellIndex]) {
                        targetEl = this.jupyter.getCellInputElement(cells[data.cellIndex].id);
                    }
                }

                if (targetEl && text) {
                    this.typewriter.type(targetEl, text, durationMs, { cursorChar: '|' });
                }
                break;
            }

            case 'execute_cell':
            case 'executeCell': {
                const cellId = data.cell_id || data.cellId;
                const cellIndex = data.cellIndex;
                const cells = this.segmentData?.cells || [];

                let targetCellId = cellId;
                let output = null;

                if (!targetCellId && cellIndex !== undefined && cells[cellIndex]) {
                    targetCellId = cells[cellIndex].id;
                    output = cells[cellIndex].output;
                } else if (targetCellId) {
                    const cell = cells.find(c => c.id === targetCellId);
                    if (cell) output = cell.output;
                }

                if (targetCellId) {
                    this.jupyter.executeCell(targetCellId, output);
                }
                break;
            }

            case 'showOutput': {
                // Output handled by executeCell
                break;
            }

            case 'showPrompt':
            case 'showBullet':
                // Not applicable for Jupyter-only v4.0
                break;

            default:
                console.log('Unknown event type:', type, data);
        }
    }
}
