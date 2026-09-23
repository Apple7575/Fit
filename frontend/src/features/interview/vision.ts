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
import { headAnglesFromMatrix, offAxisDeg, type HeadAngles } from './headPose';

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
/** 위·아래 눈꺼풀. 눈꺼풀 사이에서 홍채가 어느 높이에 있는지로 세로 시선을 본다 */
const LID_L_UP = 159;
const LID_L_DOWN = 145;
const LID_R_UP = 386;
const LID_R_DOWN = 374;
// Pose(33) 어깨·팔
const SHOULDER_L = 11;
const SHOULDER_R = 12;
const WRIST_L = 15;
const WRIST_R = 16;
/** 이만큼은 모여야 기준으로 쓴다 (0.1초에 한 장이므로 2초치) */
const MIN_CALIB_FRAMES = 20;

/** 눈꺼풀 간격이 이보다 좁으면 감은 것으로 보고 세로 시선을 재지 않는다 */
const MIN_LID_OPEN = 0.008;

/** 이 값 아래면 그 점은 화면에서 제대로 안 잡힌 것으로 본다 */
const VISIBLE = 0.5;

/**
 * 한 프레임의 추적 결과. 리포트에서 영상 위에 겹쳐 그리고 그 순간의 수치를 같이 보여준다.
 *
 * <p>"당신은 시선이 자주 흔들렸습니다"라는 말보다, 그 순간의 영상 위에 네모와 숫자를 얹어
 * 보여주는 편이 훨씬 빨리 납득된다. 그래서 요약값과 별개로 프레임별 값을 남긴다.
 *
 * <p>0.1초마다 한 개라 1분 답변이면 600개다. 자리를 아끼려고 소수 셋째 자리에서 끊는다.
 */
export interface VisionSample {
  /** 녹화 시작 기준 ms */
  t: number;
  /** 얼굴 상자 (0~1 비율) */
  x: number;
  y: number;
  w: number;
  h: number;
  /** 고개 각도(도). 행렬을 못 받았으면 null */
  yaw: number | null;
  pitch: number | null;
  roll: number | null;
  /** 눈동자가 가운데서 벗어난 정도 */
  gaze: number;
  /** 이 순간 정면으로 봤는지 */
  frontal: boolean;
  /** 어깨 두 점 (없으면 null) */
  sl: [number, number] | null;
  sr: [number, number] | null;
  /** 손목 (화면에 잡혔을 때만) */
  hand: [number, number] | null;
  /** 웃는 정도 0~1. 표정 계수를 못 받았으면 null */
  smile: number | null;
}

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
  /** 고개가 좌우로 기울어 있던 평균 각도(도). 변환 행렬이 있을 때만 */
  headRollDeg: number;
  /** 웃는 표정이었던 시간 비율 (0~1) */
  smileRatio: number;
  /** 표정이 움직인 정도. 0 이면 내내 굳어 있었다는 뜻 */
  expressionRange: number;
  /** 손이 화면에 잡힌 시간 비율 */
  handsVisibleRatio: number;
  /** 손이 움직인 정도 (0 가만히 ~ 1 매우 큼) */
  gestureAmount: number;
  hasFace: boolean;
  hasPose: boolean;
  /** 표정 계수를 받았는지 (모델 옵션이 꺼져 있거나 옛 기록이면 false) */
  hasExpression: boolean;
  /** 손이 충분히 잡혀 손짓을 말할 수 있는지 */
  hasHands: boolean;
}

interface FaceFrame {
  centerX: number;
  centerY: number;
  height: number;
  yawAsym: number; // 0 정면
  gazeOffset: number; // |평균 홍채 오프셋 - 0.5| (가로)
  /** 눈꺼풀 사이 홍채 높이 0~1 (아래일수록 큼). 눈을 감아 못 재면 null */
  gazeY: number | null;
  /** 눈높이에서 코까지 거리 / 얼굴 높이. 고개를 숙일수록 작아진다 (행렬이 없을 때의 대비책) */
  pitch: number;
  /** 변환 행렬에서 낸 고개 각도. 모델이 행렬을 주지 않으면 null */
  angles: HeadAngles | null;
  /** 웃는 정도 0~1. 표정 계수가 없으면 null */
  smile: number | null;
}
interface PoseFrame {
  midX: number;
  midY: number;
  tiltDeg: number;
  /** 화면에 잡힌 손목 위치(어깨 너비로 정규화). 안 잡히면 null */
  handX: number | null;
  handY: number | null;
  /** 겹쳐 그리기용 원본 좌표 */
  slX: number;
  slY: number;
  srX: number;
  srY: number;
  /** 손목 화면 좌표 (잡혔을 때만) */
  handRawX: number | null;
  handRawY: number | null;
}

function extractFace(
  lm: NormalizedLandmark[],
  matrix: ArrayLike<number> | null,
  smile: number | null,
): FaceFrame {
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

  /*
   * 세로 시선. 위·아래 눈꺼풀 사이에서 홍채가 어느 높이에 있는지를 본다(0 위, 1 아래).
   *
   * <p>가로만 재던 때에는 눈을 아래로 내려도 값이 그대로여서, 대본을 보고 있어도 "카메라를
   * 보고 있다"고 나왔다. 여기에는 정답인 기준값이 없다 — 카메라가 눈높이보다 위에 있으면
   * 똑바로 봐도 홍채가 내려가 보인다. 그래서 절대값으로 판정하지 않고, 점검 화면에서
   * 카메라를 볼 때의 값을 기준으로 잡아 두고 그로부터 얼마나 내려갔는지만 본다.
   *
   * <p>눈을 감으면 눈꺼풀 간격이 0 에 가까워져 값이 튄다. 그때는 잴 수 없는 것으로 두고
   * null 을 돌려준다(깜박임을 시선 이탈로 세지 않는다).
   */
  const lidRatio = (iris: NormalizedLandmark, up: NormalizedLandmark, down: NormalizedLandmark) => {
    const open = down.y - up.y;
    return open > MIN_LID_OPEN ? (iris.y - up.y) / open : null;
  };
  const vl = lidRatio(lm[IRIS_L], lm[LID_L_UP], lm[LID_L_DOWN]);
  const vr = lidRatio(lm[IRIS_R], lm[LID_R_UP], lm[LID_R_DOWN]);
  const gazeY = vl !== null && vr !== null ? (vl + vr) / 2 : null;
  // 고개를 숙이면 눈-코 간격이 짧아 보인다(원근 단축). 얼굴 높이로 나눠 거리에 영향받지 않게 한다.
  const eyeY = (lm[EYE_L_INNER].y + lm[EYE_L_OUTER].y + lm[EYE_R_INNER].y + lm[EYE_R_OUTER].y) / 4;
  const height = maxY - minY;
  const pitch = height > 0 ? (nose.y - eyeY) / height : 0;
  return {
    centerX: (minX + maxX) / 2,
    centerY: (minY + maxY) / 2,
    height,
    yawAsym,
    gazeOffset,
    gazeY,
    pitch,
    angles: headAnglesFromMatrix(matrix),
    smile,
  };
}

function extractPose(lm: NormalizedLandmark[]): PoseFrame | null {
  const sl = lm[SHOULDER_L];
  const sr = lm[SHOULDER_R];
  if (!sl || !sr || (sl.visibility ?? 0) < 0.5 || (sr.visibility ?? 0) < 0.5) return null;
  // 화면에서는 오른쪽 어깨가 왼쪽에 잡혀 x 차이가 음수가 되기 쉽다.
  // 그대로 atan2 를 쓰면 반듯하게 앉아도 180도 근처가 나오므로, 가로 성분은 절댓값으로 눕혀
  // "수평에서 몇 도 벗어났는지"(0~90)만 남긴다.
  const tiltDeg = Math.abs((Math.atan2(sr.y - sl.y, Math.abs(sr.x - sl.x)) * 180) / Math.PI);

  /*
   * 손은 앉은 웹캠 화면에서 자주 잘린다. 잡힌 손목만 쓰고, 어깨 너비로 나눠 카메라와의
   * 거리에 영향받지 않게 한다 (가까이 앉으면 모든 움직임이 커 보인다).
   */
  const span = Math.hypot(sr.x - sl.x, sr.y - sl.y) || 1;
  const midX = (sl.x + sr.x) / 2;
  const midY = (sl.y + sr.y) / 2;
  const hands = [lm[WRIST_L], lm[WRIST_R]].filter((w) => w && (w.visibility ?? 0) >= VISIBLE);
  const handX = hands.length ? mean(hands.map((w) => (w.x - midX) / span)) : null;
  const handY = hands.length ? mean(hands.map((w) => (w.y - midY) / span)) : null;

  return {
    midX,
    midY,
    tiltDeg,
    handX,
    handY,
    slX: sl.x,
    slY: sl.y,
    srX: sr.x,
    srY: sr.y,
    handRawX: hands.length ? mean(hands.map((w) => w.x)) : null,
    handRawY: hands.length ? mean(hands.map((w) => w.y)) : null,
  };
}

function std(values: number[], mean: number): number {
  if (values.length === 0) return 0;
  const v = values.reduce((a, x) => a + (x - mean) ** 2, 0) / values.length;
  return Math.sqrt(v);
}
function mean(values: number[]): number {
  return values.length ? values.reduce((a, x) => a + x, 0) / values.length : 0;
}
/**
 * 표정 계수에서 "웃는 정도"만 꺼낸다.
 *
 * <p>MediaPipe 는 52가지 계수를 주지만 면접에서 뜻이 분명한 것만 쓴다. 입꼬리 양쪽 값을
 * 평균해 0~1 로 본다. 감정을 분류하는 게 아니라 얼굴이 움직였는지를 보는 용도다.
 */
function smileOf(blendshapes: { categories: Array<{ categoryName: string; score: number }> } | undefined): number | null {
  if (!blendshapes?.categories?.length) return null;
  let sum = 0;
  let found = 0;
  for (const c of blendshapes.categories) {
    if (c.categoryName === 'mouthSmileLeft' || c.categoryName === 'mouthSmileRight') {
      sum += c.score;
      found += 1;
    }
  }
  return found > 0 ? sum / found : null;
}

/** 저장 자리를 아끼려고 소수 셋째 자리에서 끊는다 (화면에 그릴 때 그 이상은 의미 없다) */
const r3 = (x: number) => Math.round(x * 1000) / 1000;

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
  /** 리포트에서 영상 위에 겹쳐 그릴 프레임별 값 */
  samples: VisionSample[];
}

/** 값들의 중앙값. 한두 프레임이 튀어도 흔들리지 않는다 */
function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

/** 답변 첫 2초(20프레임)의 중앙값을 그 사람의 기준 자세로 본다. 표본이 적으면 전체 중앙값. */
function baseline(values: number[]): number {
  if (values.length === 0) return 0;
  const head = values.slice(0, Math.min(20, values.length));
  const sample = head.length >= 5 ? head : values;
  const sorted = [...sample].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

/**
 * 점검 화면에서 잡아 둔 "이 사람이 카메라를 볼 때"의 자세.
 *
 * <p>고개를 얼마나 숙였는지·눈을 얼마나 내렸는지에는 만인 공통의 정답값이 없다. 앉은키도
 * 다르고, 노트북 카메라가 눈높이보다 위에 있으면 똑바로 봐도 눈이 내려가 보인다. 그래서
 * 기준이 필요한데, 예전에는 그 기준을 답변 첫 2초에서 잡았다 — 처음부터 숙이고 있으면
 * 그 자세가 정상으로 등록돼 아무리 아래를 봐도 잡히지 않았다.
 *
 * <p>점검 화면에서는 사람이 제 얼굴을 보느라 카메라 쪽을 본다. 거기서 재는 것이 맞다.
 */
/** isOnCamera 가 보는 값만 추린 것. 테스트에서 프레임 전체를 지어내지 않아도 되게 한다 */
export interface GazeFrame {
  gazeOffset: number;
  gazeY: number | null;
  angles: HeadAngles | null;
}

export interface GazeBaseline {
  /** 카메라를 볼 때의 고개 각도(도). 행렬을 못 받으면 null */
  pitchDeg: number | null;
  /** 카메라를 볼 때의 눈꺼풀 사이 홍채 높이. 못 재면 null */
  gazeY: number | null;
}

/** 기준보다 고개가 이만큼(도) 더 내려가면 아래를 보고 있다고 본다 */
const DOWN_PITCH_DEG = 12;
/** 기준보다 눈이 이만큼 더 내려가면 아래를 보고 있다고 본다 (눈꺼풀 간격 대비) */
const DOWN_GAZE_Y = 0.18;

/**
 * 정면인지. 변환 행렬에서 낸 각도로 보고, 행렬을 못 받는 환경에서는 옛 근사로 떨어진다.
 * 고개 숙임은 여기 넣지 않는다 — 그것은 기준선과 비교해야 해서 isOnCamera 가 맡는다.
 */
const isFrontal = (f: FaceFrame) => (f.angles ? offAxisDeg(f.angles) < FRONTAL_DEG : f.yawAsym < 0.2);

/**
 * 카메라를 보고 있는지. 가로(홍채)·고개·세로(눈)를 함께 본다.
 *
 * <p>기준을 못 잡았으면 그 항목은 빼고 판정한다. 모르는 것을 나쁘게 치지 않는다.
 */
export const isOnCamera = (f: GazeFrame, base: GazeBaseline | null) => {
  if (f.gazeOffset >= 0.15) return false;
  if (base?.pitchDeg != null && f.angles && f.angles.pitchDeg - base.pitchDeg > DOWN_PITCH_DEG) return false;
  if (base?.gazeY != null && f.gazeY != null && f.gazeY - base.gazeY > DOWN_GAZE_Y) return false;
  return true;
};

/** 기준선보다 이만큼 낮아지면 "고개를 숙였다"고 본다 (얼굴 높이 대비) */
const PITCH_DROP = 0.03;
/** 기준선 대비 목 길이가 이 비율 아래로 줄면 "구부정하다"고 본다 */
const NECK_SHRINK = 0.85;

function summarize(acc: Accumulator, base: GazeBaseline | null): NonverbalMetrics {
  const total = acc.total || 1;
  const face = acc.face;
  const faceRatio = face.length / total;
  const inFrameRatio = face.length ? face.filter(inFrame).length / face.length : 0;
  const frontalRatio = face.length ? face.filter(isFrontal).length / face.length : 0;
  /*
   * 예전에는 아래를 보는지 판정이 아예 없어서, 대본을 내려다보며 답해도 "카메라 응시 100%"
   * 가 나왔다 — 가로 홍채 위치만 봤고(눈을 내려도 그대로), 정면 판정은 고개 숙임을 일부러
   * 뺐고(offAxisDeg), 고개 숙임 지표의 기준선은 답변 첫 2초였다. 셋 다 통과해서, 틀린 값이
   * 아니라 반드시 만점이 나오는 구조였다.
   */
  const gazeRatio = face.length
    ? face.filter((f) => isFrontal(f) && isOnCamera(f, base)).length / face.length
    : 0;
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

  // 고개 갸우뚱: 행렬이 있을 때만 (평균 기울기)
  const rolls = face.map((f) => f.angles).filter((a): a is HeadAngles => a != null);
  const headRollDeg = rolls.length ? Math.round(mean(rolls.map((a) => Math.abs(a.rollDeg))) * 10) / 10 : 0;

  // 표정: 웃는 정도가 얼마나 오래, 얼마나 움직였는지
  const smiles = face.map((f) => f.smile).filter((v): v is number => v != null);
  const smileRatio = smiles.length ? smiles.filter((v) => v > SMILE_ON).length / smiles.length : 0;
  // 최댓값과 최솟값의 차. 0 에 가까우면 내내 같은 표정이었다는 뜻이다
  const expressionRange = smiles.length
    ? Math.round((Math.max(...smiles) - Math.min(...smiles)) * 100) / 100
    : 0;

  // 손짓: 잡힌 시간과 움직인 폭
  const handsSeen = pose.filter((p) => p.handX != null);
  const handsVisibleRatio = pose.length ? handsSeen.length / pose.length : 0;
  const hx = handsSeen.map((p) => p.handX as number);
  const hy = handsSeen.map((p) => p.handY as number);
  const gestureAmount = handsSeen.length >= 5
    ? clamp01((std(hx, mean(hx)) + std(hy, mean(hy))) * 2)
    : 0;

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
    headRollDeg,
    smileRatio: Math.round(smileRatio * 100) / 100,
    expressionRange,
    handsVisibleRatio: Math.round(handsVisibleRatio * 100) / 100,
    gestureAmount: Math.round(gestureAmount * 100) / 100,
    hasFace: face.length >= 5,
    hasPose: pose.length >= 5,
    hasExpression: smiles.length >= 5,
    // 절반 넘게 잡혀야 손짓을 말할 수 있다. 잠깐 스친 것으로 판단하면 틀린 말을 한다
    hasHands: handsSeen.length >= 5 && handsVisibleRatio >= 0.5,
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

function buildFaceEvents(face: FaceFrame[], t: number[], base: GazeBaseline | null): ClipEvent[] {
  const pitchBase = baseline(face.map((f) => f.pitch));
  /*
   * 판정은 요약(summarize)과 같은 함수를 쓴다. 예전에는 여기만 옛 근사값(yawAsym)을 써서,
   * 요약은 "시선 이탈 없음" 인데 타임라인에는 이탈 구간이 찍히는 일이 있었다. 주석에는
   * 같은 기준이라고 적혀 있었지만 실제로는 달랐다.
   */
  const conds: Array<{ kind: ClipEventKind; bad: (f: FaceFrame) => boolean }> = [
    { kind: 'offframe', bad: (f) => !inFrame(f) },
    { kind: 'nonfrontal', bad: (f) => !isFrontal(f) },
    { kind: 'gaze', bad: (f) => isFrontal(f) && !isOnCamera(f, base) },
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

/*
 * 아래 숫자도 일반적인 권장 범위지 정답이 아니다 (delivery.ts 의 임계값과 같은 성격).
 * 화면에서는 단정 대신 "조금 ~한 편"으로 적고, 재지 못한 경우는 warn 이 아니라 none 으로 둔다.
 */
export const FRAMING_OK = 0.8;
export const FRONTAL_OK = 0.7;
export const GAZE_OK = 0.6;
export const MOVEMENT_WARN = 0.5;
export const POSTURE_OK = 0.7;
export const TILT_WARN = 7;
/** 고개 떨굼·구부정은 이 비율을 넘으면 알린다 (답변 시간의 20%) */
export const HEAD_DOWN_WARN = 0.2;
export const SLOUCH_WARN = 0.2;
/** 정면에서 이만큼(도) 넘게 벗어나 있으면 정면이 아니라고 본다 */
export const FRONTAL_DEG = 15;
/** 고개가 이만큼(도) 넘게 기울어 있으면 알린다 */
export const ROLL_WARN = 8;
/** 웃는 정도가 이 값을 넘으면 "웃는 표정"으로 센다 */
const SMILE_ON = 0.2;
/** 표정이 움직인 폭이 이보다 작으면 내내 굳어 있었다고 본다 */
export const EXPRESSION_FLAT = 0.15;
/** 손짓이 이보다 크면 과하다고 본다 */
export const GESTURE_BUSY = 0.35;

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
        : row('얼굴 위치', pct(m.inFrameRatio), 'warn', '화면을 조금 벗어난 편이에요. 얼굴을 화면 가운데에 두세요'),
    );
    rows.push(
      m.frontalRatio >= FRONTAL_OK
        ? row('정면 유지', pct(m.frontalRatio), 'good')
        : row('정면 유지', pct(m.frontalRatio), 'warn', '고개가 조금 돌아간 편이에요. 어깨와 고개를 카메라 쪽으로 맞춰 보세요'),
    );
    rows.push(
      m.gazeRatio >= GAZE_OK
        ? row('카메라 응시', pct(m.gazeRatio), 'good')
        : row('카메라 응시', pct(m.gazeRatio), 'warn', '시선이 렌즈를 조금 비껴간 편이에요. 화면 말고 렌즈를 보며 말해 보세요'),
    );
    rows.push(
      m.headMovement <= MOVEMENT_WARN
        ? row('고개 흔들림', '안정적', 'good')
        : row('고개 흔들림', '조금 잦음', 'warn', '고개가 자주 움직인 편이에요. 말할 때 턱을 한자리에 두어 보세요'),
    );
    rows.push(
      m.headDownRatio <= HEAD_DOWN_WARN
        ? row('고개 각도', '든 상태 유지', 'good')
        : row('고개 각도', `숙임 ${pct(m.headDownRatio)}`, 'warn', '말할 때 고개가 내려가는 편이에요. 화면을 눈높이까지 올려 보세요'),
    );
  } else {
    // 인식 실패는 사용자가 고칠 점이 아니다. 고칠 것으로 세지 않고 안내만 한다
    rows.push(row('얼굴 인식', '재지 못함', 'none', '조명을 밝히고 카메라와의 거리를 맞춰 보세요'));
  }
  if (m.hasPose) {
    rows.push(
      m.slouchRatio <= SLOUCH_WARN
        ? row('상체 자세', '바르게 유지', 'good')
        : row('상체 자세', `구부정 ${pct(m.slouchRatio)}`, 'warn', '등이 조금 굽은 편이에요. 어깨를 열어 앉아 보세요'),
    );
    rows.push(
      m.postureStable >= POSTURE_OK
        ? row('상체 안정', '안정적', 'good')
        : row('상체 안정', '조금 흔들림', 'warn', '상체가 자주 움직인 편이에요. 등을 의자에 붙이고 앉아 보세요'),
    );
    rows.push(
      m.postureTiltDeg <= TILT_WARN
        ? row('어깨 수평', '반듯함', 'good')
        : row('어깨 수평', `${m.postureTiltDeg}° 기울어짐`, 'warn', '한쪽으로 조금 기운 편이에요. 양쪽 팔을 같은 높이에 두어 보세요'),
    );
  }

  // 고개 갸우뚱 (변환 행렬을 받은 기록에서만)
  if (m.hasFace && m.headRollDeg > 0) {
    rows.push(
      m.headRollDeg <= ROLL_WARN
        ? row('고개 기울기', '반듯함', 'good')
        : row('고개 기울기', `${m.headRollDeg}° 기울어짐`, 'warn', '고개가 한쪽으로 조금 기운 편이에요. 화면 속 내 모습으로 한 번 맞춰 보세요'),
    );
  }

  /*
   * 표정. 웃으라고 요구하지 않는다 — 면접에서 웃는 게 늘 정답은 아니다. 내내 한 표정으로
   * 굳어 있었는지만 알린다.
   */
  if (m.hasExpression) {
    rows.push(
      m.expressionRange >= EXPRESSION_FLAT
        ? row('표정', `웃는 표정 ${pct(m.smileRatio)}`, 'good')
        : row('표정', '거의 그대로', 'warn', '표정이 내내 굳어 있던 편이에요. 첫 인사만이라도 입꼬리를 올려 보세요'),
    );
  } else {
    rows.push(row('표정', '재지 못함', 'none', '얼굴이 또렷하게 잡혀야 표정을 볼 수 있어요'));
  }

  // 손짓. 화면에 손이 잡힌 기록에서만 말한다 (앉은 화면에서는 자주 잘린다)
  if (m.hasHands) {
    rows.push(
      m.gestureAmount <= GESTURE_BUSY
        ? row('손짓', '차분함', 'good')
        : row('손짓', '조금 잦음', 'warn', '손이 자주 움직인 편이에요. 손은 책상 위에 가볍게 두어 보세요'),
    );
  } else if (m.hasPose) {
    rows.push(row('손짓', '재지 못함', 'none', '손이 화면에 거의 안 잡혔어요'));
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
    // 새로 생긴 값들. 옛 기록에는 없으므로 0 으로 보고, 있는지 여부는 아래 플래그로 가린다
    headRollDeg: avg((m) => m.headRollDeg ?? 0),
    smileRatio: avg((m) => m.smileRatio ?? 0),
    expressionRange: avg((m) => m.expressionRange ?? 0),
    handsVisibleRatio: avg((m) => m.handsVisibleRatio ?? 0),
    gestureAmount: avg((m) => m.gestureAmount ?? 0),
    hasExpression: list.some((m) => m.hasExpression),
    hasHands: list.some((m) => m.hasHands),
    postureStable: avg((m) => m.postureStable),
    postureTiltDeg: Math.round(avg((m) => m.postureTiltDeg) * 10) / 10,
    hasFace: list.some((m) => m.hasFace),
    hasPose: list.some((m) => m.hasPose),
  };
}

export type VisionStatus = 'idle' | 'loading' | 'ready' | 'unsupported' | 'error';

/**
 * MediaPipe Face/Pose Landmarker 로 녹화 구간의 비언어 신호를 모은다.
 * 마운트 시 모델을 미리 로드(prewarm)하고, start()~stop() 사이에만 프레임을 분석한다.
 */
export function useVision(videoRef: React.RefObject<HTMLVideoElement | null>) {
  const faceRef = useRef<FaceLandmarker | null>(null);
  const poseRef = useRef<PoseLandmarker | null>(null);
  const accRef = useRef<Accumulator>({
    total: 0,
    startPerf: 0,
    face: [],
    faceT: [],
    pose: [],
    neck: [],
    neckT: [],
    samples: [],
  });
  const activeRef = useRef(false);
  const rafRef = useRef<number | null>(null);
  const lastRef = useRef(0);
  /** 점검 화면에서 잡은 "카메라를 볼 때"의 자세. 문항이 바뀌어도 그대로 쓴다 */
  const baseRef = useRef<GazeBaseline | null>(null);
  /** 캘리브레이션 중 모은 표본. 끝낼 때 중앙값만 남기고 버린다 */
  const calibRef = useRef<{ pitchDeg: number[]; gazeY: number[] }>({ pitchDeg: [], gazeY: [] });
  /** 지금 도는 루프가 무엇을 하는 중인지 */
  const modeRef = useRef<'off' | 'calib' | 'rec'>('off');
  const [status, setStatus] = useState<VisionStatus>(() =>
    typeof WebAssembly === 'undefined' ? 'unsupported' : 'loading',
  );

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
            // 고개 각도(행렬)와 표정 계수. 추론은 어차피 도므로 받아 쓰는 비용은 거의 없다
            outputFacialTransformationMatrixes: true,
            outputFaceBlendshapes: true,
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
    accRef.current = {
      total: 0,
      startPerf: performance.now(),
      face: [],
      faceT: [],
      pose: [],
      neck: [],
      neckT: [],
      samples: [],
    };
    lastRef.current = 0;
    activeRef.current = true;
    // 기준(baseRef)은 그대로 둔다. 점검에서 한 번 잡고 문항 내내 쓴다
    modeRef.current = 'rec';

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
            const matrix = fr.facialTransformationMatrixes?.[0]?.data ?? null;
            faceFrame = extractFace(fr.faceLandmarks[0], matrix, smileOf(fr.faceBlendshapes?.[0]));
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
          // 리포트에서 되돌려 볼 수 있게 이 순간의 값을 남긴다
          if (faceFrame) {
            const box = boxOf(faceFrame);
            const pf = accRef.current.pose[accRef.current.pose.length - 1];
            const fresh = pr.landmarks.length > 0 ? pf : undefined;
            accRef.current.samples.push({
              t: Math.round(now - accRef.current.startPerf),
              x: r3(box.x),
              y: r3(box.y),
              w: r3(box.w),
              h: r3(box.h),
              yaw: faceFrame.angles ? Math.round(faceFrame.angles.yawDeg) : null,
              pitch: faceFrame.angles ? Math.round(faceFrame.angles.pitchDeg) : null,
              roll: faceFrame.angles ? Math.round(faceFrame.angles.rollDeg) : null,
              gaze: r3(faceFrame.gazeOffset),
              frontal: faceFrame.angles
                ? offAxisDeg(faceFrame.angles) < FRONTAL_DEG
                : faceFrame.yawAsym < 0.2,
              sl: fresh ? [r3(fresh.slX), r3(fresh.slY)] : null,
              sr: fresh ? [r3(fresh.srX), r3(fresh.srY)] : null,
              hand:
                fresh && fresh.handRawX != null && fresh.handRawY != null
                  ? [r3(fresh.handRawX), r3(fresh.handRawY)]
                  : null,
              smile: faceFrame.smile == null ? null : r3(faceFrame.smile),
            });
          }

        } catch {
          /* 개별 프레임 분석 실패는 무시 */
        }
      }
      rafRef.current = requestAnimationFrame(tick);
    }
    rafRef.current = requestAnimationFrame(tick);
  }, [status, videoRef]);

  /**
   * 점검 화면에서 "카메라를 볼 때"의 자세를 모으기 시작한다.
   *
   * <p>여기서는 사람이 제 얼굴을 보느라 카메라 쪽을 향한다. 그 자세를 기준으로 삼아야
   * 답변 중에 얼마나 내려갔는지를 말할 수 있다 — 답변 첫 2초를 기준으로 삼던 예전 방식은
   * 처음부터 숙이고 있는 사람에게는 그 숙인 자세를 정상으로 등록해 버렸다.
   */
  const calibrate = useCallback(() => {
    if (status !== 'ready' || activeRef.current) return;
    calibRef.current = { pitchDeg: [], gazeY: [] };
    modeRef.current = 'calib';
    activeRef.current = true;
    lastRef.current = 0;

    function look() {
      if (!activeRef.current || modeRef.current !== 'calib') return;
      const video = videoRef.current;
      const face = faceRef.current;
      const now = performance.now();
      if (video && video.readyState >= 2 && face && now - lastRef.current >= DETECT_INTERVAL_MS) {
        lastRef.current = now;
        try {
          const fr = face.detectForVideo(video, now);
          if (fr.faceLandmarks.length > 0) {
            const matrix = fr.facialTransformationMatrixes?.[0]?.data ?? null;
            const f = extractFace(fr.faceLandmarks[0], matrix, null);
            if (f.angles) calibRef.current.pitchDeg.push(f.angles.pitchDeg);
            if (f.gazeY !== null) calibRef.current.gazeY.push(f.gazeY);
          }
        } catch {
          /* 개별 프레임 분석 실패는 무시 */
        }
      }
      rafRef.current = requestAnimationFrame(look);
    }
    rafRef.current = requestAnimationFrame(look);
  }, [status, videoRef]);

  /** 모은 표본의 중앙값을 기준으로 굳힌다. 표본이 모자라면 기준을 세우지 않는다 */
  const endCalibrate = useCallback(() => {
    if (modeRef.current !== 'calib') return;
    activeRef.current = false;
    modeRef.current = 'off';
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    const { pitchDeg, gazeY } = calibRef.current;
    /*
     * 잠깐 스쳐 본 몇 프레임으로 기준을 세우면 그 기준이 틀린다. 틀린 기준은 없느니만
     * 못하므로(멀쩡히 보고 있는데 아래를 본다고 한다) 모자라면 null 로 둔다 — 그 항목은
     * 판정에서 빠진다.
     */
    baseRef.current = {
      pitchDeg: pitchDeg.length >= MIN_CALIB_FRAMES ? median(pitchDeg) : null,
      gazeY: gazeY.length >= MIN_CALIB_FRAMES ? median(gazeY) : null,
    };
  }, []);

  const stop = useCallback((): {
    metrics: NonverbalMetrics;
    events: ClipEvent[];
    samples: VisionSample[];
  } | null => {
    activeRef.current = false;
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    const acc = accRef.current;
    if (acc.total === 0) return null;
    return {
      metrics: summarize(acc, baseRef.current),
      events: [...buildFaceEvents(acc.face, acc.faceT, baseRef.current), ...buildSlouchEvents(acc.neck, acc.neckT)].sort(
        (a, b) => a.startMs - b.startMs,
      ),
      samples: acc.samples,
    };
  }, []);

  return { status, start, stop, calibrate, endCalibrate };
}
