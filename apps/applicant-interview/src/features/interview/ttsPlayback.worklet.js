/* global AudioWorkletProcessor, registerProcessor, sampleRate */

class InterviewTtsPlaybackProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.chunks = [];
    this.chunkOffset = 0;
    this.bufferedSamples = 0;
    this.started = false;
    this.ended = false;
    this.reportedEnd = false;
    this.minimumBufferSamples = Math.round(sampleRate * 0.08);
    this.port.onmessage = (event) => {
      if (event.data?.type === "chunk") {
        const pcm = new Int16Array(event.data.chunk);
        this.chunks.push(pcm);
        this.bufferedSamples += pcm.length;
      }
      if (event.data?.type === "end") this.ended = true;
    };
  }

  process(_inputs, outputs) {
    const output = outputs[0]?.[0];
    if (!output) return true;
    output.fill(0);

    if (
      !this.started &&
      this.bufferedSamples < this.minimumBufferSamples &&
      !this.ended
    ) {
      return true;
    }
    if (!this.started && this.bufferedSamples > 0) {
      this.started = true;
      this.port.postMessage({ type: "playing" });
    }

    let outputOffset = 0;
    while (outputOffset < output.length && this.chunks.length > 0) {
      const chunk = this.chunks[0];
      const available = chunk.length - this.chunkOffset;
      const length = Math.min(available, output.length - outputOffset);
      for (let index = 0; index < length; index += 1) {
        output[outputOffset + index] = chunk[this.chunkOffset + index] / 0x8000;
      }
      outputOffset += length;
      this.chunkOffset += length;
      this.bufferedSamples -= length;
      if (this.chunkOffset >= chunk.length) {
        this.chunks.shift();
        this.chunkOffset = 0;
      }
    }

    if (this.ended && this.bufferedSamples === 0 && !this.reportedEnd) {
      this.reportedEnd = true;
      this.port.postMessage({ type: "ended" });
    }
    return true;
  }
}

registerProcessor("iep-tts-playback", InterviewTtsPlaybackProcessor);
