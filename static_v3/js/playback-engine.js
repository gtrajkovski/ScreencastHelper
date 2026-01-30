/**
 * PlaybackEngine - Coordinates audio playback with timed visual events.
 * ScreenCast Studio v4.0
 */

class PlaybackEngine {
    constructor() {
        this.segments = [];        // Array of segment data
        this.currentSegment = -1;
        this.playing = false;
        this.audio = new Audio();
        this._eventIndex = 0;      // Next event to fire in current segment
        this._rafId = null;
        this._typewriters = [];    // Active Typewriter instances

        // Callbacks
        this.onEvent = null;           // (event) => {}
        this.onProgress = null;        // ({segIndex, time, fraction}) => {}
        this.onSegmentChange = null;   // (segIndex) => {}
        this.onPlaybackEnd = null;     // () => {}

        // Audio event handlers
        this.audio.addEventListener('ended', () => this._onAudioEnded());
    }

    /**
     * Load segment data for playback.
     * @param {Array} segmentData - Array of {id, audioUrl, timeline, ...}
     *   timeline: {events: [{time, action, params}], total_duration}
     */
    loadSegments(segmentData) {
        this.stop();
        this.segments = segmentData.map(seg => ({
            ...seg,
            timeline: seg.timeline || { events: [], total_duration: 0 }
        }));
        this.currentSegment = -1;
    }

    /**
     * Start or resume playback from current position.
     */
    play() {
        if (this.segments.length === 0) return;

        if (this.currentSegment < 0) {
            this._goToSegment(0);
        }

        this.playing = true;

        const seg = this.segments[this.currentSegment];
        if (seg.audioUrl) {
            this.audio.play().catch(() => {});
        }

        this._startTick();
    }

    /**
     * Pause playback.
     */
    pause() {
        this.playing = false;
        this.audio.pause();
        this._stopTick();

        // Pause active typewriters
        this._typewriters.forEach(tw => tw.pause());
    }

    /**
     * Stop playback and reset to beginning.
     */
    stop() {
        this.playing = false;
        this.audio.pause();
        this.audio.currentTime = 0;
        this._stopTick();
        this._cancelTypewriters();
        this.currentSegment = -1;
        this._eventIndex = 0;
    }

    /**
     * Seek to a specific segment and time.
     * @param {number} segIndex - Segment index
     * @param {number} time - Time in seconds within segment
     */
    seekTo(segIndex, time = 0) {
        if (segIndex < 0 || segIndex >= this.segments.length) return;

        const wasPlaying = this.playing;
        this.pause();
        this._cancelTypewriters();

        this._goToSegment(segIndex);

        // Seek audio
        if (this.audio.src) {
            this.audio.currentTime = Math.min(time, this.audio.duration || 0);
        }

        // Fire all events up to the seek time
        const timeline = this.segments[segIndex].timeline;
        this._eventIndex = 0;
        for (let i = 0; i < timeline.events.length; i++) {
            if (timeline.events[i].time <= time) {
                this._fireEvent(timeline.events[i]);
                this._eventIndex = i + 1;
            } else {
                break;
            }
        }

        if (wasPlaying) {
            this.play();
        }
    }

    /**
     * Go to next segment.
     */
    nextSegment() {
        if (this.currentSegment < this.segments.length - 1) {
            const wasPlaying = this.playing;
            this.pause();
            this._cancelTypewriters();
            this._goToSegment(this.currentSegment + 1);
            if (wasPlaying) this.play();
        }
    }

    /**
     * Go to previous segment.
     */
    prevSegment() {
        if (this.currentSegment > 0) {
            const wasPlaying = this.playing;
            this.pause();
            this._cancelTypewriters();
            this._goToSegment(this.currentSegment - 1);
            if (wasPlaying) this.play();
        }
    }

    /**
     * Get current playback state.
     */
    getState() {
        const seg = this.currentSegment >= 0 ? this.segments[this.currentSegment] : null;
        return {
            playing: this.playing,
            currentSegment: this.currentSegment,
            totalSegments: this.segments.length,
            currentTime: this.audio.currentTime || 0,
            duration: seg ? (seg.timeline.total_duration || this.audio.duration || 0) : 0
        };
    }

    /**
     * Register a Typewriter instance for lifecycle management.
     */
    registerTypewriter(tw) {
        this._typewriters.push(tw);
    }

    // --- Private methods ---

    _goToSegment(index) {
        this._cancelTypewriters();
        this.currentSegment = index;
        this._eventIndex = 0;

        const seg = this.segments[index];

        // Load audio
        if (seg.audioUrl) {
            this.audio.src = seg.audioUrl;
            this.audio.load();
        } else {
            this.audio.src = '';
        }

        if (this.onSegmentChange) {
            this.onSegmentChange(index);
        }
    }

    _startTick() {
        this._stopTick();
        const tick = () => {
            if (!this.playing) return;
            this._tick();
            this._rafId = requestAnimationFrame(tick);
        };
        this._rafId = requestAnimationFrame(tick);
    }

    _stopTick() {
        if (this._rafId) {
            cancelAnimationFrame(this._rafId);
            this._rafId = null;
        }
    }

    _tick() {
        if (this.currentSegment < 0 || this.currentSegment >= this.segments.length) return;

        const seg = this.segments[this.currentSegment];
        const timeline = seg.timeline;
        const currentTime = this.audio.currentTime || 0;

        // Fire pending events
        while (this._eventIndex < timeline.events.length) {
            const event = timeline.events[this._eventIndex];
            if (event.time <= currentTime) {
                this._fireEvent(event);
                this._eventIndex++;
            } else {
                break;
            }
        }

        // Report progress
        if (this.onProgress) {
            const duration = timeline.total_duration || this.audio.duration || 1;
            this.onProgress({
                segIndex: this.currentSegment,
                time: currentTime,
                fraction: Math.min(1, currentTime / duration)
            });
        }
    }

    _fireEvent(event) {
        if (this.onEvent) {
            this.onEvent(event);
        }
    }

    _onAudioEnded() {
        if (!this.playing) return;

        // Fire any remaining events
        const seg = this.segments[this.currentSegment];
        if (seg) {
            const timeline = seg.timeline;
            while (this._eventIndex < timeline.events.length) {
                this._fireEvent(timeline.events[this._eventIndex]);
                this._eventIndex++;
            }
        }

        // Advance to next segment or end
        if (this.currentSegment < this.segments.length - 1) {
            this._goToSegment(this.currentSegment + 1);
            this.play();
        } else {
            this.playing = false;
            this._stopTick();
            if (this.onPlaybackEnd) {
                this.onPlaybackEnd();
            }
        }
    }

    _cancelTypewriters() {
        this._typewriters.forEach(tw => tw.cancel());
        this._typewriters = [];
    }
}
