/**
 * Recorder - Captures DOM content + audio to WebM using browser-native APIs.
 * ScreenCast Studio v4.0
 *
 * Uses html2canvas for DOM-to-canvas conversion and MediaRecorder for encoding.
 * No FFmpeg or desktop dependencies required.
 */

class Recorder {
    /**
     * @param {HTMLCanvasElement} canvas - Canvas element for capture
     * @param {MediaStream|null} audioStream - Audio stream from Web Audio API
     */
    constructor(canvas, audioStream) {
        this.canvas = canvas;
        this.audioStream = audioStream;
        this.mediaRecorder = null;
        this.chunks = [];
        this.isRecording = false;
        this._sourceElement = null;
        this._captureInterval = null;
        this._ctx = canvas.getContext('2d');
    }

    /**
     * Update source element and audio stream.
     */
    setSource(sourceElement, audioStream) {
        this._sourceElement = sourceElement;
        this.audioStream = audioStream;
    }

    /**
     * Start recording.
     */
    start() {
        if (this.isRecording) return;
        this.chunks = [];

        // Set up canvas to match source element
        if (this._sourceElement) {
            this.canvas.width = this._sourceElement.offsetWidth || 1920;
            this.canvas.height = this._sourceElement.offsetHeight || 1080;
        }

        // Create combined stream
        const videoStream = this.canvas.captureStream(30);
        const tracks = [...videoStream.getVideoTracks()];

        if (this.audioStream) {
            const audioTracks = this.audioStream.getAudioTracks();
            tracks.push(...audioTracks);
        }

        const combinedStream = new MediaStream(tracks);

        // Select best available codec
        const mimeType = this._getBestMimeType();

        this.mediaRecorder = new MediaRecorder(combinedStream, {
            mimeType: mimeType,
            videoBitsPerSecond: 5000000
        });

        this.mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) {
                this.chunks.push(e.data);
            }
        };

        this.mediaRecorder.start(1000); // Chunk every second
        this.isRecording = true;

        // Start capturing DOM to canvas
        this._startDOMCapture();
    }

    /**
     * Stop recording and return blob.
     * @returns {Promise<Blob>}
     */
    async stop() {
        if (!this.isRecording) return null;

        this._stopDOMCapture();

        return new Promise((resolve) => {
            this.mediaRecorder.onstop = () => {
                const mimeType = this.mediaRecorder.mimeType || 'video/webm';
                const blob = new Blob(this.chunks, { type: mimeType });
                this.chunks = [];
                this.isRecording = false;
                resolve(blob);
            };
            this.mediaRecorder.stop();
        });
    }

    /**
     * Download a blob as a file.
     */
    download(filename = 'recording.webm', blob = null) {
        if (!blob && this.chunks.length > 0) {
            blob = new Blob(this.chunks, { type: 'video/webm' });
        }
        if (!blob) return;

        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 5000);
    }

    /**
     * Get best available WebM mime type.
     */
    _getBestMimeType() {
        const candidates = [
            'video/webm;codecs=vp9,opus',
            'video/webm;codecs=vp8,opus',
            'video/webm;codecs=vp9',
            'video/webm;codecs=vp8',
            'video/webm'
        ];

        for (const mime of candidates) {
            if (MediaRecorder.isTypeSupported(mime)) {
                return mime;
            }
        }

        return 'video/webm';
    }

    /**
     * Start continuous DOM-to-canvas capture using drawImage from an offscreen approach.
     * Falls back to simple rendering if html2canvas is not available.
     */
    _startDOMCapture() {
        if (!this._sourceElement) return;

        // Capture at ~30fps
        this._captureInterval = setInterval(() => {
            this._captureFrame();
        }, 33);
    }

    _stopDOMCapture() {
        if (this._captureInterval) {
            clearInterval(this._captureInterval);
            this._captureInterval = null;
        }
    }

    /**
     * Capture current DOM state to canvas.
     *
     * Uses a simple approach: render the source element's computed styles
     * and content to the canvas. For more complex scenarios, html2canvas
     * can be loaded dynamically.
     */
    _captureFrame() {
        if (!this._sourceElement || !this._ctx) return;

        const el = this._sourceElement;
        const w = this.canvas.width;
        const h = this.canvas.height;

        // Use html2canvas if available (loaded externally)
        if (typeof html2canvas !== 'undefined') {
            html2canvas(el, {
                canvas: this.canvas,
                backgroundColor: '#1e1e1e',
                scale: 1,
                width: w,
                height: h,
                logging: false,
                useCORS: true
            }).catch(() => {
                // Fallback: fill with background color
                this._drawFallback(w, h);
            });
            return;
        }

        // Fallback: serialize DOM to SVG foreignObject, draw to canvas
        this._drawViaForeignObject(el, w, h);
    }

    /**
     * Render DOM element to canvas via SVG foreignObject.
     * This works for most simple DOM structures.
     */
    _drawViaForeignObject(el, w, h) {
        const data = `
            <svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}">
                <foreignObject width="100%" height="100%">
                    <div xmlns="http://www.w3.org/1999/xhtml"
                         style="font-family: sans-serif; color: #d4d4d4; background: #1e1e1e; width: ${w}px; height: ${h}px; overflow: hidden;">
                        ${el.innerHTML}
                    </div>
                </foreignObject>
            </svg>
        `;

        const img = new Image();
        const svgBlob = new Blob([data], { type: 'image/svg+xml;charset=utf-8' });
        const url = URL.createObjectURL(svgBlob);

        img.onload = () => {
            this._ctx.drawImage(img, 0, 0, w, h);
            URL.revokeObjectURL(url);
        };

        img.onerror = () => {
            this._drawFallback(w, h);
            URL.revokeObjectURL(url);
        };

        img.src = url;
    }

    /**
     * Simple fallback: just draw the background.
     */
    _drawFallback(w, h) {
        this._ctx.fillStyle = '#1e1e1e';
        this._ctx.fillRect(0, 0, w, h);
        this._ctx.fillStyle = '#808080';
        this._ctx.font = '16px sans-serif';
        this._ctx.fillText('Recording in progress...', 20, 40);
    }
}
