import { beforeEach, describe, expect, it } from 'vitest';
import { clearDraft, isPromptMuted, mutePrompt } from './draft';

const USER = 7;

describe('이어서 진행 창 끄기', () => {
  beforeEach(() => localStorage.clear());

  it('끄기 전에는 묻는다', () => {
    expect(isPromptMuted(USER, 'session-a')).toBe(false);
  });

  it('끄면 그 면접은 다시 묻지 않는다', () => {
    mutePrompt(USER, 'session-a');
    expect(isPromptMuted(USER, 'session-a')).toBe(true);
  });

  it('다음에 새로 중단한 면접은 다시 묻는다', () => {
    mutePrompt(USER, 'session-a');
    expect(isPromptMuted(USER, 'session-b')).toBe(false);
  });

  it('다른 사람의 설정을 끌어다 쓰지 않는다', () => {
    mutePrompt(USER, 'session-a');
    expect(isPromptMuted(8, 'session-a')).toBe(false);
  });

  it('초안을 지우면 끈 기록도 같이 지운다', () => {
    mutePrompt(USER, 'session-a');
    clearDraft(USER);
    expect(isPromptMuted(USER, 'session-a')).toBe(false);
  });
});
