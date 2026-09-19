/**
 * MediaPipe(브라우저 로컬) 기반 비언어 지표. 서버·클라우드 전송 없이 이 브라우저에서 랜드마크만 계산한다.
 * 감정 분류 모델이 아니라 좌표/블렌드셰이프로 얼굴 위치·정면·카메라 응시·움직임·표정·자세를 추정한다.
 * WASM/모델은 CDN 에서 받는다(운영 시 self-host 가능). 미지원·로드 실패 시 이 지표만 스킵한다.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  FaceLandmarker,
  NormalizedLandmark,
  PoseLandmarker,
} from '@mediapipe/tasks-vision';
import type { ClipEvent, ClipEventKind, MetricRow, Tone } from './delivery';

const WASM_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm';
const FACE_MODEL =
  'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';
const POSE_MODEL =
  'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task';

const DETECT_INTERVAL_MS = 100; // ~10fps 로 throttle (얼굴+자세 동시 실행 부하 완화)
const MIN_EVENT_MS = 1000; // 타임라인 마커로 남길 최소 이탈 지속(깜박임 수준 노이즈 제거)

// FaceMesh(478) 랜드마크 인덱스
const NOSE = 1;
const CHEEK_L = 234;
const CHEEK_R = 454;
const EYE_L_INNER = 133;
const EYE_L_OUTER = 33;
const EYE_R_INNER = 362;
const EYE_R_OUTER = 263;
const IRIS_L = 468;
const IRIS_R = 473;
// Pose(33) 어깨
const SHOULDER_L = 11;
const SHOULDER_R = 12;

/** 문항별 비언어 지표(요약값). 값은 0~1 비율 또는 근사 각도. */
export interface NonverbalMetrics {
  faceRatio: number;
  inFrameRatio: number;
  frontalRatio: number;
  gazeRatio: number;
  headMovement: number; // 0 안정 ~ 1 산만
  postureStable: number; // 0~1
  postureTiltDeg: number;
  /** 고개를 숙이고 있던 시간 비율 (0 좋음 ~ 1 내내 숙임). 답변 첫 2초 자세를 기준선으로 본다 */
  headDownRatio: number;
  /** 어깨와 얼굴 간격이 좁아진(구부정한) 시간 비율 (0 좋음 ~ 1 내내 구부정) */
  slouchRatio: number;
  hasFace: boolean;
  hasPose: boolean;
}

interface FaceFrame {
  centerX: number;
  centerY: number;
  height: number;
  yawAsym: number; // 0 정면
  gazeOffset: number; // |평균 홍채 오프셋 - 0.5|
  /** 눈높이에서 코까지 거리 / 얼굴 높이. 고개를 숙일수록 작아진다 */
  pitch: number;
}
interface PoseFrame {
  midX: number;
  midY: number;
  tiltDeg: number;
}

function extractFace(lm: NormalizedLandmark[]): FaceFrame {
  let minX = 1;
  let maxX = 0;
  let minY = 1;
  let maxY = 0;
  for (const p of lm) {
    if (p.x < minX) minX = p.x;
    if (p.x > maxX) maxX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.y > maxY) maxY = p.y;
  }
  const nose = lm[NOSE];
  const dl = nose.x - lm[CHEEK_L].x;
  const dr = lm[CHEEK_R].x - nose.x;
  const yawAsym = dr + dl !== 0 ? Math.abs((dr - dl) / (dr + dl)) : 0;

  const irisOffset = (iris: NormalizedLandmark, inner: NormalizedLandmark, outer: NormalizedLandmark) => {
    const span = outer.x - inner.x;
    return span !== 0 ? (iris.x - inner.x) / span : 0.5;
  };
  const gl = irisOffset(lm[IRIS_L], lm[EYE_L_INNER], lm[EYE_L_OUTER]);
  const gr = irisOffset(lm[IRIS_R], lm[EYE_R_INNER], lm[EYE_R_OUTER]);
  // 좌·우 눈은 inner/outer 방향이 반대라 (gl+gr)/2-0.5 로 합치면 수평 시선이 상쇄돼 항상 0에 가까워진다.
  // 눈별 중심(0.5) 편차의 절댓값을 먼저 낸 뒤 평균해야 시선 이탈 정도가 남는다.
  const gazeOffset = (Math.abs(gl - 0.5) + Math.abs(gr - 0.5)) / 2;
  // 고개를 숙이면 눈-코 간격이 짧아 보인다(원근 단축). 얼굴 높이로 나눠 거리에 영향받지 않게 한다.
  const eyeY = (lm[EYE_L_INNER].y + lm[EYE_L_OUTER].y + lm[EYE_R_INNER].y + lm[EYE_R_OUTER].y) / 4;
  const height = maxY - minY;
  const pitch = height > 0 ? (nose.y - eyeY) / height : 0;
  return { centerX: (minX + maxX) / 2, centerY: (minY + maxY) / 2, height, yawAsym, gazeOffset, pitch };
}

function extractPose(lm: NormalizedLandmark[]): PoseFrame | null {
  const sl = lm[SHOULDER_L];
  const sr = lm[SHOULDER_R];
  if (!sl || !sr || (sl.visibility ?? 0) < 0.5 || (sr.visibility ?? 0) < 0.5) return null;
  // 화면에서는 오른쪽 어깨가 왼쪽에 잡혀 x 차이가 음수가 되기 쉽다.
  // 그대로 atan2 를 쓰면 반듯하게 앉아도 180도 근처가 나오므로, 가로 성분은 절댓값으로 눕혀
  // "수평에서 몇 도 벗어났는지"(0~90)만 남긴다.
  const tiltDeg = Math.abs((Math.atan2(sr.y - sl.y, Math.abs(sr.x - sl.x)) * 180) / Math.PI);
  return { midX: (sl.x + sr.x) / 2, midY: (sl.y + sr.y) / 2, tiltDeg };
}

function std(values: number[], mean: number): number {
  if (values.length === 0) return 0;
  const v = values.reduce((a, x) => a + (x - mean) ** 2, 0) / values.length;
  return Math.sqrt(v);
}
function mean(values: number[]): number {
  return values.length ? values.reduce((a, x) => a + x, 0) / values.length : 0;
}
function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x));
}

// 얼굴 위치 양호 판정
function inFrame(f: FaceFrame): boolean {
  return f.centerX > 0.25 && f.centerX < 0.75 && f.centerY > 0.2 && f.centerY < 0.85 && f.height > 0.25 && f.height < 0.95;
}

interface Accumulator {
  total: number;
  startPerf: number; // start() 호출 시각(performance.now) — 프레임 상대시각 계산 기준
  face: FaceFrame[];
  faceT: number[]; // face 와 평행: 각 프레임의 녹화 시작 기준 ms
  pose: PoseFrame[];
  /** 얼굴과 어깨가 같은 프레임에서 잡혔을 때의 목 길이(어깨 중앙 y - 얼굴 중앙 y) */
  neck: number[];
  neckT: number[];
}

/** 답변 첫 2초(20프레임)의 중앙값을 그 사람의 기준 자세로 본다. 표본이 적으면 전체 중앙값. */
function baseline(values: number[]): number {
  if (values.length === 0) return 0;
  const head = values.slice(0, Math.min(20, values.length));
  const sample = head.length >= 5 ? head : values;
  const sorted = [...sample].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

/** 기준선보다 이만큼 낮아지면 "고개를 숙였다"고 본다 (얼굴 높이 대비) */
const PITCH_DROP = 0.03;
/** 기준선 대비 목 길이가 이 비율 아래로 줄면 "구부정하다"고 본다 */
const NECK_SHRINK = 0.85;

function summarize(acc: Accumulator): NonverbalMetrics {
  const total = acc.total || 1;
  const face = acc.face;
  const faceRatio = face.length / total;
  const inFrameRatio = face.length ? face.filter(inFrame).length / face.length : 0;
  const frontalRatio = face.length ? face.filter((f) => f.yawAsym < 0.2).length / face.length : 0;
  const gazeRatio = face.length ? face.filter((f) => f.yawAsym < 0.2 && f.gazeOffset < 0.15).length / face.length : 0;
  const cx = face.map((f) => f.centerX);
  const cy = face.map((f) => f.centerY);
  const headMovement = clamp01((std(cx, mean(cx)) + std(cy, mean(cy))) * 15);

  const pose = acc.pose;
  const px = pose.map((p) => p.midX);
  const py = pose.map((p) => p.midY);
  const postureStable = pose.length ? clamp01(1 - (std(px, mean(px)) + std(py, mean(py))) * 20) : 0;
  const postureTiltDeg = Math.round(mean(pose.map((p) => p.tiltDeg)) * 10) / 10;

  // 고개 떨굼·구부정: 각자의 시작 자세를 기준으로 얼마나 오래 무너졌는지
  const pitchBase = baseline(face.map((f) => f.pitch));
  const headDownRatio = face.length ? face.filter((f) => f.pitch < pitchBase - PITCH_DROP).length / face.length : 0;
  const neckBase = baseline(acc.neck);
  const slouchRatio =
    acc.neck.length && neckBase > 0 ? acc.neck.filter((n) => n < neckBase * NECK_SHRINK).length / acc.neck.length : 0;
  return {
    faceRatio: Math.round(faceRatio * 100) / 100,
    inFrameRatio: Math.round(inFrameRatio * 100) / 100,
    frontalRatio: Math.round(frontalRatio * 100) / 100,
    gazeRatio: Math.round(gazeRatio * 100) / 100,
    headMovement: Math.round(headMovement * 100) / 100,
    postureStable: Math.round(postureStable * 100) / 100,
    postureTiltDeg,
    headDownRatio: Math.round(headDownRatio * 100) / 100,
    slouchRatio: Math.round(slouchRatio * 100) / 100,
    hasFace: face.length >= 5,
    hasPose: pose.length >= 5,
  };
}

/**
 * 프레임별 얼굴 신호에서 "이탈이 이어진 구간"을 뽑아 타임라인 이벤트로 만든다.
 * 판정 기준은 summarize 의 비율 계산과 동일해, 마커와 요약 수치가 어긋나지 않는다.
 * MIN_EVENT_MS 미만의 짧은 이탈(깜박임 수준)은 버린다.
 */
/** 얼굴 중심·높이로 화면 속 얼굴 자리를 만든다 (가로는 세로의 0.78 로 근사) */
function boxOf(f: FaceFrame): { x: number; y: number; w: number; h: number } {
  const h = Math.min(1, Math.max(0.05, f.height));
  const w = h * 0.78;
  return {
    x: Math.min(1, Math.max(0, f.centerX - w / 2)),
    y: Math.min(1, Math.max(0, f.centerY - h / 2)),
    w,
    h,
  };
}

function buildFaceEvents(face: FaceFrame[], t: number[]): ClipEvent[] {
  const pitchBase = baseline(face.map((f) => f.pitch));
  const conds: Array<{ kind: ClipEventKind; bad: (f: FaceFrame) => boolean }> = [
    { kind: 'offframe', bad: (f) => !inFrame(f) },
    { kind: 'nonfrontal', bad: (f) => f.yawAsym >= 0.2 },
    { kind: 'gaze', bad: (f) => f.yawAsym < 0.2 && f.gazeOffset >= 0.15 },
    { kind: 'headdown', bad: (f) => f.pitch < pitchBase - PITCH_DROP },
  ];
  const events: ClipEvent[] = [];
  for (const c of conds) {
    let runStart = -1;
    for (let i = 0; i <= face.length; i++) {
      const bad = i < face.length && c.bad(face[i]);
      if (bad && runStart < 0) runStart = i;
      if (!bad && runStart >= 0) {
        const startMs = t[runStart];
        const endMs = t[i - 1] + DETECT_INTERVAL_MS;
        if (endMs - startMs >= MIN_EVENT_MS) events.push({ kind: c.kind, startMs, endMs, box: boxOf(face[runStart]) });
        runStart = -1;
      }
    }
  }
  return events.sort((a, b) => a.startMs - b.startMs);
}

/** 목 길이가 기준선보다 짧아진 구간을 구부정한 자세 이벤트로 만든다. */
function buildSlouchEvents(neck: number[], t: number[]): ClipEvent[] {
  const base = baseline(neck);
  if (!base) return [];
  const events: ClipEvent[] = [];
  let runStart = -1;
  for (let i = 0; i <= neck.length; i++) {
    const bad = i < neck.length && neck[i] < base * NECK_SHRINK;
    if (bad && runStart < 0) runStart = i;
    if (!bad && runStart >= 0) {
      const startMs = t[runStart];
      const endMs = t[i - 1] + DETECT_INTERVAL_MS;
      if (endMs - startMs >= MIN_EVENT_MS) events.push({ kind: 'slouch', startMs, endMs });
      runStart = -1;
    }
  }
  return events;
}

// 임계값(초안)
export const FRAMING_OK = 0.8;
export const FRONTAL_OK = 0.7;
export const GAZE_OK = 0.6;
export const MOVEMENT_WARN = 0.5;
export const POSTURE_OK = 0.7;
export const TILT_WARN = 7;
/** 고개 떨굼·구부정은 이 비율을 넘으면 알린다 (답변 시간의 20%) */
export const HEAD_DOWN_WARN = 0.2;
export const SLOUCH_WARN = 0.2;

function row(key: string, value: string, tone: Tone, hint?: string): MetricRow {
  return { key, value, tone, hint };
}
const pct = (x: number) => `${Math.round(x * 100)}%`;

/** 리포트 카드용 비언어 지표 행. 얼굴/자세 인식이 잘 안 됨하면 해당 그룹은 안내로 대체한다. */
export function describeNonverbal(m: NonverbalMetrics): MetricRow[] {
  const rows: MetricRow[] = [];
  if (m.hasFace && m.faceRatio >= 0.4) {
    rows.push(
      m.inFrameRatio >= FRAMING_OK
        ? row('얼굴 위치', pct(m.inFrameRatio), 'good')
        : row('얼굴 위치', pct(m.inFrameRatio), 'warn', '얼굴을 화면 가운데에 두세요'),
    );
    rows.push(
      m.frontalRatio >= FRONTAL_OK
        ? row('정면 유지', pct(m.frontalRatio), 'good')
        : row('정면 유지', pct(m.frontalRatio), 'warn', '고개를 정면으로 향해 보세요'),
    );
    rows.push(
      m.gazeRatio >= GAZE_OK
        ? row('카메라 응시', pct(m.gazeRatio), 'good')
        : row('카메라 응시', pct(m.gazeRatio), 'warn', '렌즈를 보며 말해 보세요'),
    );
    rows.push(
      m.headMovement <= MOVEMENT_WARN
        ? row('고개 흔들림', '안정적', 'good')
        : row('고개 흔들림', '잦음', 'warn', '고개 움직임을 줄여 보세요'),
    );
    rows.push(
      m.headDownRatio <= HEAD_DOWN_WARN
        ? row('고개 각도', '든 상태 유지', 'good')
        : row('고개 각도', `숙임 ${pct(m.headDownRatio)}`, 'warn', '말할 때 고개를 들고 정면을 보세요'),
    );
  } else {
    rows.push(row('얼굴 인식', '잘 안 됨', 'warn', '조명을 밝히고 카메라와의 거리를 맞춰 보세요'));
  }
  if (m.hasPose) {
    rows.push(
      m.slouchRatio <= SLOUCH_WARN
        ? row('상체 자세', '바르게 유지', 'good')
        : row('상체 자세', `구부정 ${pct(m.slouchRatio)}`, 'warn', '등을 펴고 어깨를 열어 앉아 보세요'),
    );
    rows.push(
      m.postureStable >= POSTURE_OK
        ? row('상체 안정', '안정적', 'good')
        : row('상체 안정', '흔들림', 'warn', '상체를 편안히 고정해 보세요'),
    );
    rows.push(
      m.postureTiltDeg <= TILT_WARN
        ? row('어깨 수평', '반듯함', 'good')
        : row('어깨 수평', `${m.postureTiltDeg}° 기울어짐`, 'warn', '한쪽으로 기울지 않게 앉아 보세요'),
    );
  }
  return rows;
}

/** 여러 문항의 비언어 지표를 평균낸 세션 요약. 빈 목록이면 null. */
export function averageNonverbal(list: NonverbalMetrics[]): NonverbalMetrics | null {
  if (list.length === 0) return null;
  const n = list.length;
  const avg = (pick: (m: NonverbalMetrics) => number) =>
    Math.round((list.reduce((a, m) => a + pick(m), 0) / n) * 100) / 100;
  return {
    faceRatio: avg((m) => m.faceRatio),
    inFrameRatio: avg((m) => m.inFrameRatio),
    frontalRatio: avg((m) => m.frontalRatio),
    gazeRatio: avg((m) => m.gazeRatio),
    // 예전 기록에는 없는 값이라 0(문제 없음)으로 본다
    headDownRatio: avg((m) => m.headDownRatio ?? 0),
    slouchRatio: avg((m) => m.slouchRatio ?? 0),
    headMovement: avg((m) => m.headMovement),
    postureStable: avg((m) => m.postureStable),
    postureTiltDeg: Math.round(avg((m) => m.postureTiltDeg) * 10) / 10,
    hasFace: list.some((m) => m.hasFace),
    hasPose: list.some((m) => m.hasPose),
  };
}

export type VisionStatus = 'idle' | 'loading' | 'ready' | 'unsupported' | 'error';

function liveWarn(f: FaceFrame | null): string | null {
  if (!f) return '얼굴이 화면에서 벗어났어요';
  if (!inFrame(f)) return '화면 중앙으로 이동해 주세요';
  if (f.yawAsym >= 0.2) return '정면을 바라봐 주세요';
  return null;
}

/**
 * MediaPipe Face/Pose Landmarker 로 녹화 구간의 비언어 신호를 모은다.
 * 마운트 시 모델을 미리 로드(prewarm)하고, start()~stop() 사이에만 프레임을 분석한다.
 */
export function useVision(videoRef: React.RefObject<HTMLVideoElement | null>) {
  const faceRef = useRef<FaceLandmarker | null>(null);
  const poseRef = useRef<PoseLandmarker | null>(null);
  const accRef = useRef<Accumulator>({ total: 0, startPerf: 0, face: [], faceT: [], pose: [], neck: [], neckT: [] });
  const activeRef = useRef(false);
  const rafRef = useRef<number | null>(null);
  const lastRef = useRef(0);
  const [status, setStatus] = useState<VisionStatus>(() =>
    typeof WebAssembly === 'undefined' ? 'unsupported' : 'loading',
  );
  const [warn, setWarn] = useState<string | null>(null);

  // 모델 prewarm
  useEffect(() => {
    if (typeof WebAssembly === 'undefined') return;
    let cancelled = false;
    (async () => {
      try {
        const v = await import('@mediapipe/tasks-vision');
        const fileset = await v.FilesetResolver.forVisionTasks(WASM_URL);
        const makeFace = (delegate: 'GPU' | 'CPU') =>
          v.FaceLandmarker.createFromOptions(fileset, {
            baseOptions: { modelAssetPath: FACE_MODEL, delegate },
            runningMode: 'VIDEO',
            numFaces: 1,
          });
        const makePose = (delegate: 'GPU' | 'CPU') =>
          v.PoseLandmarker.createFromOptions(fileset, {
            baseOptions: { modelAssetPath: POSE_MODEL, delegate },
            runningMode: 'VIDEO',
            numPoses: 1,
          });
        const [face, pose] = await Promise.all([
          makeFace('GPU').catch(() => makeFace('CPU')),
          makePose('GPU').catch(() => makePose('CPU')),
        ]);
        if (cancelled) {
          face.close();
          pose.close();
          return;
        }
        faceRef.current = face;
        poseRef.current = pose;
        setStatus('ready');
      } catch {
        if (!cancelled) setStatus('error');
      }
    })();
    return () => {
      cancelled = true;
      activeRef.current = false;
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      faceRef.current?.close();
      poseRef.current?.close();
      faceRef.current = null;
      poseRef.current = null;
    };
  }, []);

  const start = useCallback(() => {
    if (status !== 'ready') return;
    accRef.current = { total: 0, startPerf: performance.now(), face: [], faceT: [], pose: [], neck: [], neckT: [] };
    lastRef.current = 0;
    activeRef.current = true;
    setWarn(null);

    // 함수 선언(호이스팅)이라 자기 자신을 참조해 재귀 rAF 를 돌릴 수 있다.
    function tick() {
      if (!activeRef.current) return;
      const video = videoRef.current;
      const face = faceRef.current;
      const pose = poseRef.current;
      const now = performance.now();
      if (video && video.readyState >= 2 && face && pose && now - lastRef.current >= DETECT_INTERVAL_MS) {
        lastRef.current = now;
        try {
          const fr = face.detectForVideo(video, now);
          const pr = pose.detectForVideo(video, now);
          accRef.current.total += 1;
          let faceFrame: FaceFrame | null = null;
          if (fr.faceLandmarks.length > 0) {
            faceFrame = extractFace(fr.faceLandmarks[0]);
            accRef.current.face.push(faceFrame);
            accRef.current.faceT.push(now - accRef.current.startPerf);
          }
          if (pr.landmarks.length > 0) {
            const pf = extractPose(pr.landmarks[0]);
            if (pf) {
              accRef.current.pose.push(pf);
              // 얼굴과 어깨가 같이 잡힌 프레임에서만 목 길이를 잰다
              if (faceFrame) {
                accRef.current.neck.push(pf.midY - faceFrame.centerY);
                accRef.current.neckT.push(now - accRef.current.startPerf);
              }
            }
          }
          const next = liveWarn(faceFrame);
          setWarn((prev) => (prev === next ? prev : next));
        } catch {
          /* 개별 프레임 분석 실패는 무시 */
        }
      }
      rafRef.current = requestAnimationFrame(tick);
    }
    rafRef.current = requestAnimationFrame(tick);
  }, [status, videoRef]);

  const stop = useCallback((): { metrics: NonverbalMetrics; events: ClipEvent[] } | null => {
    activeRef.current = false;
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    setWarn(null);
    const acc = accRef.current;
    if (acc.total === 0) return null;
    return {
      metrics: summarize(acc),
      events: [...buildFaceEvents(acc.face, acc.faceT), ...buildSlouchEvents(acc.neck, acc.neckT)].sort(
        (a, b) => a.startMs - b.startMs,
      ),
    };
  }, []);

  return { status, warn, start, stop };
}
