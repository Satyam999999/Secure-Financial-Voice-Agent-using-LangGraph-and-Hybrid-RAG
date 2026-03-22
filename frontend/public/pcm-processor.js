class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer    = new Int16Array(4096);
    this._offset    = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const float32 = input[0];

    for (let i = 0; i < float32.length; i++) {
      this._buffer[this._offset++] = Math.max(
        -32768,
        Math.min(32767, float32[i] * 32768)
      );

      if (this._offset === this._buffer.length) {
        // Transfer ownership for zero-copy send
        this.port.postMessage(this._buffer.buffer, [this._buffer.buffer]);
        this._buffer = new Int16Array(4096);
        this._offset = 0;
      }
    }
    return true;
  }
}

registerProcessor("pcm-processor", PCMProcessor);