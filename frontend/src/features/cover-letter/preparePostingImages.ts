/** 조각 한 장의 상한. AI 쪽 OCR 상한(8MB)과 맞춘다. */
export const MAX_POSTING_IMAGE_BYTES = 8 * 1024 * 1024;

/** 한 번에 보낼 총량. 프록시 client_max_body_size(20m) 보다 여유를 둔다. */
export const MAX_POSTING_IMAGES_BYTES = 16 * 1024 * 1024;

/** 서버가 받는 이미지 수 상한(UPLOAD_OCR_MAX_IMAGES)과 같다. */
export const MAX_POSTING_IMAGE_PIECES = 8;

/**
 * 조각 높이. 서버가 OCR 할 때 쓰는 타일 높이와 같게 둔다 — 어차피 같은 크기로 잘릴 것을
 * 여기서 미리 자르는 것이라, 다르게 잡으면 서버가 한 번 더 자른다.
 */
const BAND_HEIGHT = 4000;

/**
 * 자를 위치를 이 범위 안에서 옮겨 글자가 없는 가로줄을 찾는다.
 *
 * 경계에서 글자가 반으로 갈리면 모델이 안 보이는 부분을 그럴듯한 문장으로 지어낸다
 * (실측: 급여 항목이 원문에 없는 내용으로 바뀌었다). 줄 사이 빈 공간에서 자르면 애초에
 * 갈릴 글자가 없다. 서버 `_blank_cut_row` 와 같은 방식이다.
 */
const CUT_SEARCH = 150;
/** 한 가로줄의 밝기 최대-최소 차이가 이 값 이하면 글자가 없는 줄로 본다. */
const BLANK_ROW_SPREAD = 8;

/** 이보다 넓으면 줄인다. 더 줄이면 글자가 뭉개져 OCR 정확도가 떨어진다. */
const MAX_WIDTH = 2000;

/**
 * 조각 하나가 이 크기를 넘으면 화질을 한 단계 낮춰 다시 인코딩한다.
 *
 * 사진·그라데이션이 많은 공고는 같은 크기라도 몇 배 무겁다. 서버·프록시 한도에 기대지 말고
 * 여기서 확실히 맞춰 둔다 — 한도를 넘으면 413 이라 사용자는 이유를 알 수 없다.
 */
const TARGET_PIECE_BYTES = 1_500_000;

/**
 * 동시에 인코딩할 조각 수. 조각마다 캔버스를 잡으므로 메모리가 그만큼 곱해진다
 * (2000x4000 이면 장당 30MB 남짓). 속도와 메모리의 절충값이다.
 */
const ENCODE_CONCURRENCY = 4;
const JPEG_QUALITIES = [0.85, 0.7, 0.55];

/**
 * 붙여넣은 공고 이미지를 업로드할 수 있는 조각들로 만든다.
 *
 * <p>사용자는 공고를 "전체 페이지 캡처" 한 장으로 넣는 일이 많다. 그런 PNG 는 세로가 1만
 * px을 넘고 용량도 십수 MB 라 그대로 보내면 프록시가 413 으로 끊는다. 통째로 다시 그려
 * 줄이려 해도 캔버스가 너무 커져 실패한다 — 그래서 **가로로 띠 모양으로 잘라** 조각마다
 * JPEG 로 인코딩한다. 캔버스는 한 번에 2000×4000 을 넘지 않는다.
 *
 * <p>해상도는 최대한 지킨다. 줄이면 글자가 뭉개져 OCR 이 못 읽는다.
 *
 * <p>캔버스를 못 쓰는 환경(테스트 등)에서는 원본을 그대로 돌려준다. 크기 검사는 호출
 * 쪽에서 하므로 여기서 실패해도 흐름이 끊기지 않는다.
 */
export async function preparePostingImages(
  files: File[],
  onPiece?: (done: number) => void,
): Promise<File[]> {
  const pieces: File[] = [];
  // 조각은 동시에 끝나므로 완료 순서가 뒤섞인다. 누적 개수만 센다.
  let done = 0;
  for (const file of files) {
    if (pieces.length >= MAX_POSTING_IMAGE_PIECES) break;
    const room = MAX_POSTING_IMAGE_PIECES - pieces.length;
    pieces.push(...(await splitIntoBands(file, room, () => onPiece?.(++done))));
  }
  return pieces;
}

/** 목표 크기에 들어올 때까지 화질을 낮춰 가며 인코딩한다. 끝까지 못 맞추면 마지막 결과. */
async function encodeWithinTarget(canvas: HTMLCanvasElement): Promise<Blob | null> {
  let last: Blob | null = null;
  for (const quality of JPEG_QUALITIES) {
    last = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, 'image/jpeg', quality);
    });
    if (!last || last.size <= TARGET_PIECE_BYTES) break;
  }
  return last;
}

/** 조각을 ENCODE_CONCURRENCY 개씩 동시에 처리한다. 결과는 입력 순서를 지킨다. */
async function mapWithLimit<T, R>(
  items: T[],
  limit: number,
  run: (item: T, index: number) => Promise<R>,
): Promise<R[]> {
  const results = new Array<R>(items.length);
  let next = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (next < items.length) {
      const index = next++;
      results[index] = await run(items[index], index);
    }
  });
  await Promise.all(workers);
  return results;
}

/**
 * 자를 구간을 정한다. 경계는 글자가 없는 가로줄로 옮긴다.
 *
 * 빈 줄을 못 찾으면(사진·빈틈없는 표) 원래 자리에서 자른다 — 더 나빠지지는 않는다.
 */
function planCuts(
  source: ImageBitmap,
  scale: number,
  width: number,
  height: number,
  room: number,
): Array<{ top: number; bottom: number }> {
  const probe = document.createElement('canvas');
  const probeContext = probe.getContext('2d', { willReadFrequently: true });
  const cuts: Array<{ top: number; bottom: number }> = [];
  let top = 0;
  while (top < height && cuts.length < room) {
    let bottom = Math.min(top + BAND_HEIGHT, height);
    if (bottom < height && probeContext) {
      bottom = findBlankRow(probe, probeContext, source, scale, width, top, bottom, height);
    }
    cuts.push({ top, bottom });
    top = bottom;
  }
  probe.width = probe.height = 0;
  return cuts;
}

function findBlankRow(
  probe: HTMLCanvasElement,
  context: CanvasRenderingContext2D,
  source: ImageBitmap,
  scale: number,
  width: number,
  top: number,
  target: number,
  height: number,
): number {
  const lowest = Math.max(top + 1, target - CUT_SEARCH);
  const highest = Math.min(height, target + CUT_SEARCH);
  if (highest <= lowest) return target;

  const strip = highest - lowest;
  probe.width = width;
  probe.height = strip;
  context.drawImage(source, 0, lowest / scale, source.width, strip / scale, 0, 0, width, strip);
  const { data } = context.getImageData(0, 0, width, strip);

  const isBlank = (row: number) => {
    let min = 255;
    let max = 0;
    // 가로는 전부 본다. 건너뛰면 얇은 획을 놓쳐 글자 있는 줄을 빈 줄로 보게 된다.
    // 글자가 있는 줄은 대개 몇 픽셀 만에 걸러지므로 비용은 크지 않다.
    for (let x = 0; x < width; x += 1) {
      // 밝기만 보면 되므로 녹색 채널로 근사한다(픽셀마다 4바이트).
      const value = data[(row * width + x) * 4 + 1];
      if (value < min) min = value;
      if (value > max) max = value;
      if (max - min > BLANK_ROW_SPREAD) return false;
    }
    return true;
  };

  // 자를 자리에서 가까운 쪽부터 본다. 처음 만나는 빈 줄이 곧 가장 가까운 빈 줄이라
  // 300줄을 다 훑지 않고 멈춘다.
  const center = target - lowest;
  for (let offset = 0; offset < strip; offset += 1) {
    for (const row of offset === 0 ? [center] : [center - offset, center + offset]) {
      if (row >= 0 && row < strip && isBlank(row)) return lowest + row;
    }
  }
  return target;
}

async function splitIntoBands(
  file: File,
  room: number,
  onPiece?: () => void,
): Promise<File[]> {
  let bitmap: ImageBitmap | null = null;
  try {
    bitmap = await createImageBitmap(file);
    const source = bitmap;
    const scale = Math.min(1, MAX_WIDTH / source.width);
    const width = Math.round(source.width * scale);
    const height = Math.round(source.height * scale);
    if (!document.createElement('canvas').getContext('2d')) return [file];

    const base = (file.name || 'posting').replace(/\.[^.]+$/, '');
    // 자르는 자리를 먼저 정한다. 글자 한가운데를 자르면 모델이 안 보이는 부분을 지어내므로
    // 줄 사이 빈 공간으로 옮긴다.
    const cuts = planCuts(source, scale, width, height, room);

    // 조각마다 캔버스를 따로 둬야 동시에 인코딩할 수 있다. 하나를 돌려쓰면 앞 조각이
    // 끝나야 다음을 그릴 수 있어 조각 수에 그대로 비례한다(6조각 6.6초 → 1.2초).
    const encoded = await mapWithLimit(cuts, ENCODE_CONCURRENCY, async (cut, index) => {
      const { top, bottom } = cut;
      const bandHeight = bottom - top;
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = bandHeight;
      const context = canvas.getContext('2d');
      if (!context) return null;
      // 원본 좌표로 환산해 이 구간만 그린다. 캔버스는 조각 크기를 넘지 않는다.
      context.drawImage(source, 0, top / scale, source.width, bandHeight / scale, 0, 0, width, bandHeight);
      const blob = await encodeWithinTarget(canvas);
      // 그린 내용을 버려 메모리를 바로 돌려준다. 동시에 여러 장을 들고 있기 때문이다.
      canvas.width = canvas.height = 0;
      onPiece?.();
      return blob ? new File([blob], `${base}-${index + 1}.jpg`, { type: 'image/jpeg' }) : null;
    });

    const pieces = encoded.filter((piece): piece is File => piece !== null);
    return pieces.length > 0 ? pieces : [file];
  } catch {
    return [file];
  } finally {
    bitmap?.close();
  }
}
