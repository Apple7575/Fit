import { useAuth } from '../../features/auth/AuthProvider';

/**
 * 랜딩의 자소서 단추. 첫 화면·중간·맨 아래 세 곳이 같은 말을 해야 해서 한곳에 둔다.
 *
 * <p>"로그인 없이" 는 아직 로그인하지 않은 사람을 붙잡는 말이다. 이미 로그인한 사람에게는
 * 맞지 않는 말이라(QA 에서 잡혔다) 문구와 갈 곳을 바꾼다 — 그 사람에게는 새 자소서보다
 * 쓰던 자소서가 있는 목록이 먼저다.
 *
 * <p>세션을 복원하는 잠깐 동안은 비로그인으로 본다. 그 사이에 문구가 한 번 바뀌지만,
 * 로그인한 사람에게 틀린 말을 계속 보여 주는 것보다는 낫다.
 */
export function useCoverLetterCta() {
  const { user } = useAuth();

  return user
    ? { label: '자소서 쓰러 가기', to: '/cover-letters' }
    : { label: '로그인 없이 자소서 써 보기', to: '/cover-letters/new' };
}
