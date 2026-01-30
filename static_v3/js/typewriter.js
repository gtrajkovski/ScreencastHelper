/**
 * Typewriter - Character-by-character code typing animation.
 * ScreenCast Studio v4.0
 */

class Typewriter {
    /**
     * @param {HTMLElement} element - Target element to type into
     * @param {Object} options
     * @param {number} options.baseSpeed - Base ms per character (default 40)
     * @param {number} options.variance - Speed variance factor 0-1 (default 0.3)
     * @param {number} options.newlinePause - Extra ms pause on newlines (default 200)
     * @param {number} options.punctuationPause - Extra ms on punctuation (default 100)
     */
    constructor(element, options = {}) {
        this.element = element;
        this.baseSpeed = options.baseSpeed || 40;
        this.variance = options.variance || 0.3;
        this.newlinePause = options.newlinePause || 200;
        this.punctuationPause = options.punctuationPause || 100;

        this._text = '';
        this._position = 0;
        this._paused = false;
        this._cancelled = false;
        this._resolve = null;
        this._cursorEl = null;
    }

    /**
     * Type text character-by-character into the element.
     * @param {string} text - Text to type
     * @returns {Promise} Resolves when typing is complete or cancelled
     */
    async type(text) {
        this._text = text;
        this._position = 0;
        this._paused = false;
        this._cancelled = false;

        // Add cursor
        this._addCursor();

        return new Promise((resolve) => {
            this._resolve = resolve;
            this._typeNext();
        });
    }

    /**
     * Type text with a fixed total duration, adjusting speed to fit.
     * @param {string} text - Text to type
     * @param {number} durationMs - Total duration in milliseconds
     * @returns {Promise}
     */
    async typeWithDuration(text, durationMs) {
        // Calculate base speed to fit duration
        const charCount = text.length;
        if (charCount > 0) {
            this.baseSpeed = Math.max(5, durationMs / charCount);
        }
        return this.type(text);
    }

    _typeNext() {
        if (this._cancelled) {
            this._finish();
            return;
        }

        if (this._paused) {
            setTimeout(() => this._typeNext(), 50);
            return;
        }

        if (this._position >= this._text.length) {
            this._finish();
            return;
        }

        const char = this._text[this._position];
        this._position++;

        // Update element content
        this.element.textContent = this._text.substring(0, this._position);
        this._addCursor();

        // Calculate delay for next character
        let delay = this._getDelay(char);
        setTimeout(() => this._typeNext(), delay);
    }

    _getDelay(char) {
        // Base delay with variance
        const varianceFactor = 1 + (Math.random() * 2 - 1) * this.variance;
        let delay = this.baseSpeed * varianceFactor;

        // Extra pause for newlines
        if (char === '\n') {
            delay += this.newlinePause;
        }

        // Extra pause for punctuation
        if ('.,:;!?'.includes(char)) {
            delay += this.punctuationPause;
        }

        return Math.max(5, delay);
    }

    _addCursor() {
        // Remove existing cursor
        this._removeCursor();

        this._cursorEl = document.createElement('span');
        this._cursorEl.className = 'typing-cursor';
        this.element.appendChild(this._cursorEl);
    }

    _removeCursor() {
        if (this._cursorEl && this._cursorEl.parentNode) {
            this._cursorEl.parentNode.removeChild(this._cursorEl);
            this._cursorEl = null;
        }
    }

    _finish() {
        this._removeCursor();
        if (this._resolve) {
            this._resolve();
            this._resolve = null;
        }
    }

    /** Pause typing */
    pause() {
        this._paused = true;
    }

    /** Resume typing */
    resume() {
        this._paused = false;
    }

    /** Complete typing instantly */
    complete() {
        this._position = this._text.length;
        this.element.textContent = this._text;
        this._finish();
    }

    /** Cancel typing */
    cancel() {
        this._cancelled = true;
    }

    /** Get progress as fraction 0-1 */
    getProgress() {
        if (!this._text || this._text.length === 0) return 1;
        return this._position / this._text.length;
    }

    /** Seek to a fraction of the text (0-1) */
    seekTo(fraction) {
        const pos = Math.floor(fraction * this._text.length);
        this._position = Math.max(0, Math.min(pos, this._text.length));
        this.element.textContent = this._text.substring(0, this._position);
        if (this._position < this._text.length) {
            this._addCursor();
        } else {
            this._removeCursor();
        }
    }
}
