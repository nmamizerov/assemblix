// Microphone capture worklet: converts the graph's float samples to signed
// 16-bit PCM and posts them in ~200 ms frames, which is the chunk size the
// realtime provider buffers around. Runs off the main thread so a busy React
// render cannot introduce gaps in the captured audio.
const FRAME_MS = 200;

class PcmRecorder extends AudioWorkletProcessor {
  constructor() {
    super();
    this.frameSize = Math.round((sampleRate * FRAME_MS) / 1000);
    this.buffer = new Int16Array(this.frameSize);
    this.offset = 0;
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;

    for (let i = 0; i < channel.length; i++) {
      const clamped = Math.max(-1, Math.min(1, channel[i]));
      this.buffer[this.offset++] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;

      if (this.offset === this.frameSize) {
        // Copy: the buffer is reused for the next frame.
        this.port.postMessage(this.buffer.slice().buffer);
        this.offset = 0;
      }
    }
    return true;
  }
}

registerProcessor("pcm-recorder", PcmRecorder);
