/**
 * TypewriterEngine - Animates code typing character by character.
 * ScreenCast Studio v4.0
 */

class TypewriterEngine {
    constructor() {
        this.isTyping = false;
        this._cancel = false;
        this._resolve = null;
    }

    /**
     * Type text into element over a given duration.
     * @param {HTMLElement} element - Target element
     * @param {string} text - Text to type
     * @param {number} durationMs - Total duration in milliseconds
     * @param {Object} options
     * @param {boolean} options.preserveExisting - Keep existing content
     * @param {string} options.cursorChar - Cursor character
     * @returns {Promise} Resolves when typing is complete
     */
    async type(element, text, durationMs, options = {}) {
        const preserveExisting = options.preserveExisting || false;
        const cursorChar = options.cursorChar || null;

        this.stop();
        this.isTyping = true;
        this._cancel = false;

        const existing = preserveExisting ? element.textContent : '';
        const baseDelay = durationMs / Math.max(text.length, 1);

        return new Promise((resolve) => {
            this._resolve = resolve;
            let i = 0;

            const typeNext = () => {
                if (this._cancel || i >= text.length) {
                    // Final state
                    element.textContent = existing + text;
                    this.isTyping = false;
                    this._resolve = null;
                    resolve();
                    return;
                }

                i++;
                const typed = text.substring(0, i);
                element.textContent = existing + typed;

                // Add cursor
                if (cursorChar) {
                    const cursor = document.createElement('span');
                    cursor.className = 'typing-cursor';
                    element.appendChild(cursor);
                }

                const delay = this.getCharDelay(text[i - 1], baseDelay, text.length);
                setTimeout(typeNext, delay);
            };

            typeNext();
        });
    }

    /**
     * Stop current typing animation.
     */
    stop() {
        this._cancel = true;
        if (this._resolve) {
            this._resolve();
            this._resolve = null;
        }
        this.isTyping = false;
    }

    /**
     * Calculate natural delay between characters.
     */
    getCharDelay(char, baseDuration, textLength) {
        let delay = baseDuration;

        // Variance: +/- 30%
        delay *= 0.7 + Math.random() * 0.6;

        // Extra pause on newlines
        if (char === '\n') delay += 150;

        // Extra pause on punctuation
        if ('.:;,!?'.includes(char)) delay += 60;

        // Faster for spaces
        if (char === ' ') delay *= 0.5;

        return Math.max(5, delay);
    }
}
