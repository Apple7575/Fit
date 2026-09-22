/**
 * 자판을 한글로 안 바꾸고 친 글자를 한글로 되돌린다. "tka" → "삼".
 *
 * <p>찾는 이름을 아는데도 결과가 없다고 나오는 흔한 이유다. 검색이 빈손으로 끝났을 때만
 * 이걸로 한 번 더 찾아본다 — 처음부터 바꿔 찾으면 치지도 않은 말을 찾아 주는 셈이 된다.
 *
 * <p>두벌식 자판만 다룬다. 한글이 섞여 있거나 영문 알파벳이 하나도 없으면 그대로 돌려준다.
 */

/** 두벌식 자판에서 그 키가 내는 낱자 */
const KEY_TO_JAMO: Record<string, string> = {
  q: 'ㅂ', w: 'ㅈ', e: 'ㄷ', r: 'ㄱ', t: 'ㅅ', y: 'ㅛ', u: 'ㅕ', i: 'ㅑ', o: 'ㅐ', p: 'ㅔ',
  a: 'ㅁ', s: 'ㄴ', d: 'ㅇ', f: 'ㄹ', g: 'ㅎ', h: 'ㅗ', j: 'ㅓ', k: 'ㅏ', l: 'ㅣ',
  z: 'ㅋ', x: 'ㅌ', c: 'ㅊ', v: 'ㅍ', b: 'ㅠ', n: 'ㅜ', m: 'ㅡ',
  Q: 'ㅃ', W: 'ㅉ', E: 'ㄸ', R: 'ㄲ', T: 'ㅆ', O: 'ㅒ', P: 'ㅖ',
};

const CHO = ['ㄱ','ㄲ','ㄴ','ㄷ','ㄸ','ㄹ','ㅁ','ㅂ','ㅃ','ㅅ','ㅆ','ㅇ','ㅈ','ㅉ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ'];
const JUNG = ['ㅏ','ㅐ','ㅑ','ㅒ','ㅓ','ㅔ','ㅕ','ㅖ','ㅗ','ㅘ','ㅙ','ㅚ','ㅛ','ㅜ','ㅝ','ㅞ','ㅟ','ㅠ','ㅡ','ㅢ','ㅣ'];
const JONG = ['','ㄱ','ㄲ','ㄳ','ㄴ','ㄵ','ㄶ','ㄷ','ㄹ','ㄺ','ㄻ','ㄼ','ㄽ','ㄾ','ㄿ','ㅀ','ㅁ','ㅂ','ㅄ','ㅅ','ㅆ','ㅇ','ㅈ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ'];

/** 모아 쓰는 겹모음. "hk" 를 치면 ㅗ 다음 ㅏ 가 와서 ㅘ 가 된다 */
const JUNG_PAIR: Record<string, string> = {
  'ㅗㅏ': 'ㅘ', 'ㅗㅐ': 'ㅙ', 'ㅗㅣ': 'ㅚ',
  'ㅜㅓ': 'ㅝ', 'ㅜㅔ': 'ㅞ', 'ㅜㅣ': 'ㅟ',
  'ㅡㅣ': 'ㅢ',
};

/** 모아 쓰는 겹받침 */
const JONG_PAIR: Record<string, string> = {
  'ㄱㅅ': 'ㄳ', 'ㄴㅈ': 'ㄵ', 'ㄴㅎ': 'ㄶ',
  'ㄹㄱ': 'ㄺ', 'ㄹㅁ': 'ㄻ', 'ㄹㅂ': 'ㄼ', 'ㄹㅅ': 'ㄽ', 'ㄹㅌ': 'ㄾ', 'ㄹㅍ': 'ㄿ', 'ㄹㅎ': 'ㅀ',
  'ㅂㅅ': 'ㅄ',
};

/** 겹받침 뒤에 모음이 오면 뒤쪽 하나가 다음 글자의 첫소리로 넘어간다 ("앉아" → 안 + 자) */
const JONG_SPLIT: Record<string, [string, string]> = {
  'ㄳ': ['ㄱ', 'ㅅ'], 'ㄵ': ['ㄴ', 'ㅈ'], 'ㄶ': ['ㄴ', 'ㅎ'],
  'ㄺ': ['ㄹ', 'ㄱ'], 'ㄻ': ['ㄹ', 'ㅁ'], 'ㄼ': ['ㄹ', 'ㅂ'], 'ㄽ': ['ㄹ', 'ㅅ'],
  'ㄾ': ['ㄹ', 'ㅌ'], 'ㄿ': ['ㄹ', 'ㅍ'], 'ㅀ': ['ㄹ', 'ㅎ'],
  'ㅄ': ['ㅂ', 'ㅅ'],
};

const HANGUL_BASE = 0xac00;

export function qwertyToHangul(typed: string): string {
  // 한글이 이미 섞여 있으면 자판을 바꾼 것이 아니라 그냥 그렇게 친 것이다
  if (/[ㄱ-ㅎㅏ-ㅣ가-힣]/.test(typed)) return typed;
  if (!/[A-Za-z]/.test(typed)) return typed;

  let out = '';
  // 지금 모으고 있는 글자. 첫소리·가운뎃소리는 낱자, 끝소리는 JONG 의 자리번호다
  let cho = '';
  let jung = '';
  let jong = '';

  const flush = () => {
    if (cho && jung) {
      const code =
        HANGUL_BASE + (CHO.indexOf(cho) * 21 + JUNG.indexOf(jung)) * 28 + JONG.indexOf(jong);
      out += String.fromCharCode(code);
    } else {
      // 첫소리만, 또는 모음만 친 조각. 모아지지 않으니 낱자 그대로 남긴다
      out += `${cho}${jung}${jong}`;
    }
    cho = '';
    jung = '';
    jong = '';
  };

  for (const key of typed) {
    const jamo = KEY_TO_JAMO[key];

    // 숫자·공백처럼 자판과 무관한 글자는 앞의 글자를 맺고 그대로 둔다
    if (!jamo) {
      flush();
      out += key;
      continue;
    }

    const isVowel = JUNG.includes(jamo);

    if (isVowel) {
      if (!jung) {
        // 첫소리만 있거나(가) 아무것도 없는 자리(ㅏ). 둘 다 가운뎃소리로 받는다
        jung = jamo;
        continue;
      }
      if (!jong) {
        const paired = JUNG_PAIR[jung + jamo];
        if (paired) {
          jung = paired;
          continue;
        }
        // 겹모음이 안 되는 짝이면 여기서 한 글자를 맺는다
        flush();
        jung = jamo;
        continue;
      }
      // 끝소리를 이미 받았는데 모음이 왔다 — 그 끝소리는 다음 글자의 첫소리였다
      const split = JONG_SPLIT[jong];
      const moved = split ? split[1] : jong;
      jong = split ? split[0] : '';
      flush();
      cho = moved;
      jung = jamo;
      continue;
    }

    // 닿소리
    if (!cho && !jung) {
      cho = jamo;
      continue;
    }
    if (cho && !jung) {
      // 닿소리가 잇따르면 앞엣것은 홀로 남는다 ("ㄱㄴ")
      flush();
      cho = jamo;
      continue;
    }
    if (!jong) {
      if (JONG.includes(jamo)) {
        jong = jamo;
        continue;
      }
      // 끝소리로 못 쓰는 낱자(ㄸ·ㅃ·ㅉ)는 다음 글자의 첫소리다
      flush();
      cho = jamo;
      continue;
    }
    const paired = JONG_PAIR[jong + jamo];
    if (paired) {
      jong = paired;
      continue;
    }
    flush();
    cho = jamo;
  }

  flush();
  return out;
}
