import { describe, expect, it } from 'vitest';
import { ApiError } from './client';
import { userMessage } from './errorMessage';

describe('userMessage', () => {
  it('서버끼리 쓰는 고정 문구는 사람이 읽을 말로 갈아 끼운다', () => {
    const error = new ApiError(400, 'INVALID_PARAMETER', '요청 파라미터가 올바르지 않습니다.');

    expect(userMessage(error, '저장하지 못했어요.')).toBe(
      '입력한 내용을 다시 확인해 주세요. 너무 길거나 형식이 맞지 않는 칸이 있어요.',
    );
  });

  it('서버가 어느 칸인지 짚어 말해 주면 그 말을 그대로 전한다', () => {
    // 같은 INVALID_PARAMETER 라도 서버가 준비한 안내가 우리 일반론보다 정확하다.
    const error = new ApiError(400, 'INVALID_PARAMETER', '답변은 4000자까지 저장할 수 있습니다.');

    expect(userMessage(error, '저장하지 못했어요.')).toBe('답변은 4000자까지 저장할 수 있습니다.');
  });

  it('갈아 끼울 목록에 없는 코드는 서버 문구를 그대로 쓴다', () => {
    const error = new ApiError(404, 'COVER_LETTER_NOT_FOUND', '자소서를 찾을 수 없습니다.');

    expect(userMessage(error, '불러오지 못했어요.')).toBe('자소서를 찾을 수 없습니다.');
  });

  it('서버가 아닌 곳에서 끊기면 화면이 준비한 말을 쓴다', () => {
    expect(userMessage(new TypeError('Failed to fetch'), '연결이 끊겼어요.')).toBe('연결이 끊겼어요.');
  });
});
