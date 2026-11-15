// Live eye contact meter with MediaPipe's in-browser Face Landmarker, so no video
// streams to the server during the take. The careful version runs on the server afterwards.

import { FaceLandmarker, FilesetResolver } from '@mediapipe/tasks-vision'

const WASM = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.0/wasm'
const MODEL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'
const YAW_OK = 15
const PITCH_OK = 12

let landmarkerPromise

// MediaPipe's WASM prints an informational "INFO: Created TensorFlow Lite XNNPACK delegate" line
// through console.error. Drop just that line so real errors stay visible.
const consoleError = console.error
console.error = (...args) => {
  if (typeof args[0] === 'string' && args[0].startsWith('INFO: Created TensorFlow Lite')) return
  consoleError(...args)
}

function getLandmarker() {
  landmarkerPromise ??= FilesetResolver.forVisionTasks(WASM).then((fileset) =>
    FaceLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: MODEL, delegate: 'GPU' },
      runningMode: 'VIDEO',
      numFaces: 1,
      outputFacialTransformationMatrixes: true,
    }))
  return landmarkerPromise
}

// The face's forward direction from the 4x4 transform. We only compare magnitudes, so it
// works whether the matrix is row- or column-major.
function facingCamera(matrix) {
  const m = matrix.data
  const [x, y, z] = [m[8], m[9], m[10]]
  const yaw = Math.abs((Math.atan2(x, z) * 180) / Math.PI)
  const pitch = Math.abs((Math.asin(Math.max(-1, Math.min(1, y))) * 180) / Math.PI)
  return yaw <= YAW_OK && pitch <= PITCH_OK
}

// Samples the <video> ~4 times a second. onUpdate(pct of the last ~10 s, or null with no face yet).
export function startEyeContact(video, onUpdate) {
  let stopped = false
  const history = []
  let timer

  getLandmarker().then((landmarker) => {
    const tick = () => {
      if (stopped) return
      if (video.readyState >= 2) {
        const res = landmarker.detectForVideo(video, performance.now())
        const matrix = res.facialTransformationMatrixes?.[0]
        if (matrix) history.push(facingCamera(matrix))
        else history.push(false)
        if (history.length > 40) history.shift()
        onUpdate(history.length ? Math.round((100 * history.filter(Boolean).length) / history.length) : null)
      }
      timer = setTimeout(tick, 250)
    }
    tick()
  }).catch(() => onUpdate(null))

  return () => { stopped = true; clearTimeout(timer) }
}
