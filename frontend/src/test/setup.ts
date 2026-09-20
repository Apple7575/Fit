import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';
import { clearApiQueryCache } from '../hooks/useApiQuery';

// vitest 의 globals 옵션을 켜지 않았기 때문에 Testing Library 의 자동 정리가
// 동작하지 않는다. 테스트 간에 렌더링 결과가 남지 않도록 직접 정리한다.
afterEach(() => {
  cleanup();
  // 조회 결과 재사용(reuseMs)은 모듈 단위로 남는다. 테스트마다 fetch 를 새로 세우므로
  // 여기서 비우지 않으면 앞 테스트가 받아 둔 값이 다음 테스트로 새어 든다.
  clearApiQueryCache();
});
