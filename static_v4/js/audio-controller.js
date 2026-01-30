/**
 * AudioController - Manages TTS audio playback via Web Audio API.
 * ScreenCast Studio v4.0
 */

class AudioController {
    constructor() {
        this.audioContext = null;
        this.currentSource = null;
        this.destination = null;
        this.gainNode = null;
        this._startTime = 0;
        this._pauseOffset = 0;
        this._currentBuffer = null;
        this.isPlaying = false;
        this._onEndedCallback = null;
    }

    /**
     * Initialize Web Audio context.
     */
    async init() {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        this.destination = this.audioContext.createMediaStreamDestination();
        this.gainNode = this.audioContext.createGain();
        this.gainNode.connect(this.audioContext.destination);
        this.gainNode.connect(this.destination);
    }

    /**
     * Load audio file from URL.
     * @param {string} url - Audio file URL
     * @returns {AudioBuffer}
     */
    async loadAudio(url) {
        // Resume context if suspended (browser autoplay policy)
        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }

        const response = await fetch(url);
        const arrayBuffer = await response.arrayBuffer();
        return await this.audioContext.decodeAudioData(arrayBuffer);
    }

    /**
     * Play audio buffer.
     * @param {AudioBuffer} audioBuffer
     * @param {number} startOffset - Start position in seconds
     * @returns {Promise} Resolves when audio ends
     */
    async play(audioBuffer, startOffset = 0) {
        this.stop();

        this._currentBuffer = audioBuffer;

        return new Promise((resolve) => {
            this.currentSource = this.audioContext.createBufferSource();
            this.currentSource.buffer = audioBuffer;
            this.currentSource.connect(this.gainNode);

            this._onEndedCallback = () => {
                this.isPlaying = false;
                resolve();
            };
            this.currentSource.onended = this._onEndedCallback;

            this._startTime = this.audioContext.currentTime - startOffset;
            this._pauseOffset = startOffset;
            this.currentSource.start(0, startOffset);
            this.isPlaying = true;
        });
    }

    /**
     * Pause playback.
     */
    pause() {
        if (!this.isPlaying || !this.currentSource) return;

        this._pauseOffset = this.getCurrentTime();
        this.currentSource.onended = null;
        this.currentSource.stop();
        this.currentSource = null;
        this.isPlaying = false;
    }

    /**
     * Resume from paused position.
     * @returns {Promise}
     */
    async resume() {
        if (!this._currentBuffer) return;
        return this.play(this._currentBuffer, this._pauseOffset);
    }

    /**
     * Stop playback completely.
     */
    stop() {
        if (this.currentSource) {
            this.currentSource.onended = null;
            try { this.currentSource.stop(); } catch {}
            this.currentSource = null;
        }
        this._pauseOffset = 0;
        this._startTime = 0;
        this.isPlaying = false;
    }

    /**
     * Get current playback time in seconds.
     */
    getCurrentTime() {
        if (!this.isPlaying) return this._pauseOffset;
        return this.audioContext.currentTime - this._startTime;
    }

    /**
     * Get audio output stream for recording.
     * @returns {MediaStream}
     */
    getOutputStream() {
        return this.destination ? this.destination.stream : null;
    }

    /**
     * Set volume (0-1).
     */
    setVolume(level) {
        if (this.gainNode) {
            this.gainNode.gain.value = Math.max(0, Math.min(1, level));
        }
    }
}
