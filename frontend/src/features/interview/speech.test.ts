import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useSpeech } from './hooks';

/** 브라우저의 SpeechRecognition 을 대신한다. 결과는 시험 쪽에서 직접 밀어 넣는다. */
class FakeRecognition {
  static last: FakeRecognition | null = null;
  lang = '';
  continuous = false;
  interimResults = false;
  onresult: ((e: unknown) => void) | null = null;
  onend: (() => void) | null = null;
  onerror: ((e: unknown) => void) | null = null;
  started = false;

  constructor() {
    FakeRecognition.last = this;
  }
  start() {
    this.started = true;
  }
  stop() {
    this.started = false;
  }

  /** 확정·미확정 조각을 한 번에 흘려보낸다 */
  emit(segments: Array<{ text: string; final: boolean }>) {
    const results: Record<number | string, unknown> = { length: segments.length };
    segments.forEach((s, i) => {
      results[i] = { isFinal: s.final, 0: { transcript: s.text } };
    });
    this.onresult?.({ resultIndex: 0, results });
  }
}

describe('useSpeech', () => {
  beforeEach(() => {
    (window as unknown as { SpeechRecognition: unknown }).SpeechRecognition = FakeRecognition;
    FakeRecognition.last = null;
  });
  afterEach(() => {
    delete (window as unknown as { SpeechRecognition?: unknown }).SpeechRecognition;
    vi.restoreAllMocks();
  });

  it('녹화 전에 타이핑해 둔 글 뒤에 이어 받아쓴다', () => {
    // 이어붙이지 않으면 첫 마디가 들어오는 순간 적어 둔 글이 통째로 사라졌다
    const seen: string[] = [];
    const { result } = renderHook(() => useSpeech());
    act(() => result.current.start((t) => seen.push(t), '미리 적어 둔 답변입니다.'));
    act(() => FakeRecognition.last?.emit([{ text: '그리고 말로 덧붙입니다', final: true }]));
    expect(seen.at(-1)).toBe('미리 적어 둔 답변입니다. 그리고 말로 덧붙입니다');
  });

  it('적어 둔 글이 없으면 그대로 받아쓴다', () => {
    const seen: string[] = [];
    const { result } = renderHook(() => useSpeech());
    act(() => result.current.start((t) => seen.push(t)));
    act(() => FakeRecognition.last?.emit([{ text: '안녕하세요', final: true }]));
    expect(seen.at(-1)).toBe('안녕하세요');
  });

  it('공백만 적혀 있으면 앞에 붙이지 않는다', () => {
    const seen: string[] = [];
    const { result } = renderHook(() => useSpeech());
    act(() => result.current.start((t) => seen.push(t), '   '));
    act(() => FakeRecognition.last?.emit([{ text: '안녕하세요', final: true }]));
    expect(seen.at(-1)).toBe('안녕하세요');
  });

  it('확정 전 조각도 적어 둔 글 뒤에 붙는다', () => {
    const seen: string[] = [];
    const { result } = renderHook(() => useSpeech());
    act(() => result.current.start((t) => seen.push(t), '앞말'));
    act(() => FakeRecognition.last?.emit([{ text: '말하는', final: false }]));
    expect(seen.at(-1)).toBe('앞말 말하는');
  });
});
