import { ApiError } from './client';

/**
 * 서버가 준 오류를 화면에 그대로 띄워도 되는지 가른다.
 *
 * <p>서버 문구는 대부분 그대로 읽을 만하다("자소서를 찾을 수 없습니다"). 그런데 몇 개는
 * 서버끼리 쓰는 말이라, 받은 사람이 무엇을 해야 할지 알 수 없다 — "요청 파라미터가
 * 올바르지 않습니다" 를 보고 고칠 수 있는 사용자는 없다. 그런 것만 갈아 끼운다.
 *
 * <p>목록에 없는 코드는 서버 문구를 그대로 쓴다. 여기서 모든 문구를 다시 쓰기 시작하면
 * 서버가 문구를 고쳐도 화면은 옛말을 하게 된다.
 */
const REPHRASED: Record<string, string> = {
  /*
   * 화면마다 무엇이 잘못됐는지가 다르므로 여기서는 화면 이름을 대지 않는다. 자소서 전용
   * 문구("제목과 문항을 확인해 주세요")를 적어 두었더니 로그인 화면에서도 그 말이 나왔다.
   * 어느 칸이 문제인지는 각 화면이 보내기 전에 짚어 주는 것이 맞다.
   */
  INVALID_PARAMETER: '입력한 내용을 다시 확인해 주세요. 너무 길거나 형식이 맞지 않는 칸이 있어요.',
  INTERNAL_ERROR: '문제가 생겨 처리하지 못했어요. 잠시 후 다시 시도해 주세요.',
  AGENT_CONFIG_REQUIRED: '코치 설정이 비어 있어요. 방 설정을 확인해 주세요.',
  TURN_IN_PROGRESS: '앞선 요청이 아직 끝나지 않았어요. 답이 올라온 뒤에 보내 주세요.',
};

/**
 * 서버가 할 말이 없을 때 내보내는 고정 문구. 이 말이 왔을 때만 위 문구로 갈아 끼운다.
 *
 * <p>서버도 어느 칸이 문제인지 짚어 말해 줄 때가 있다("답변은 4000자까지 저장할 수 있습니다").
 * 그 말이 우리가 준비한 일반론보다 늘 정확하므로, 코드만 보고 갈아 끼우면 안 된다.
 * 아래 문구는 백엔드 ErrorCode 의 값과 같아야 한다.
 */
const STOCK: Record<string, string> = {
  INVALID_PARAMETER: '요청 파라미터가 올바르지 않습니다.',
  INTERNAL_ERROR: '서버 오류가 발생했습니다.',
};

/**
 * 사용자에게 보여 줄 한 줄. 서버가 아닌 곳에서 끊긴 경우(네트워크 등)에는 fallback 을 쓴다.
 */
export function userMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError)) return fallback;

  const rephrased = error.code ? REPHRASED[error.code] : undefined;
  if (rephrased) {
    const stock = STOCK[error.code];
    // 짚어 주는 말이 왔으면 그대로 전한다. 고정 문구이거나 빈손일 때만 갈아 끼운다.
    if (stock && error.message && error.message !== stock) return error.message;
    return rephrased;
  }

  return error.message || fallback;
}
