// MediaRecorder helpers: WebM on Chrome/Firefox, MP4 on Safari, 1 second chunks.

const TYPES = ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm', 'video/mp4']
const VIDEO_BPS = 1_000_000
const AUDIO_TYPES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']

export function pickType(audioOnly = false) {
  const list = audioOnly ? AUDIO_TYPES : TYPES
  return list.find((t) => window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || ''
}

export function extensionFor(mimeType) {
  return mimeType.includes('mp4') ? '.mp4' : '.webm'
}

export async function getMedia(withCamera) {
  return navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true },
    video: withCamera ? { width: { ideal: 1280, max: 1280 }, height: { ideal: 720, max: 720 }, facingMode: 'user' } : false,
  })
}

// Records the whole take. stop() resolves with one Blob.
export function startRecording(stream) {
  const mimeType = pickType(stream.getVideoTracks().length === 0)
  // ~1 Mbps video keeps uploads around 7 to 8 MB a minute.
  const options = { videoBitsPerSecond: VIDEO_BPS, ...(mimeType ? { mimeType } : {}) }
  const recorder = new MediaRecorder(stream, options)
  const chunks = []
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data)
  recorder.start(1000)
  return {
    mimeType: recorder.mimeType || mimeType,
    stop: () => new Promise((resolve) => {
      recorder.onstop = () => resolve(new Blob(chunks, { type: recorder.mimeType || mimeType }))
      if (recorder.state !== 'inactive') recorder.stop()
    }),
  }
}

// Records one answer's audio and hands each ~250 ms chunk to onChunk (sent over the live WebSocket).
// A fresh recorder per answer keeps the WebM header in the first chunk so the server can decode it.
export function startAnswerAudio(stream, onChunk) {
  const audio = new MediaStream(stream.getAudioTracks())
  const mimeType = pickType(true)
  const recorder = new MediaRecorder(audio, mimeType ? { mimeType } : undefined)
  recorder.ondataavailable = (e) => e.data.size && onChunk(e.data)
  recorder.start(250)
  return () => new Promise((resolve) => {
    recorder.onstop = resolve
    if (recorder.state !== 'inactive') recorder.stop()
  })
}
