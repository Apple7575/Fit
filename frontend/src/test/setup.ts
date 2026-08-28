import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// vitest 의 globals 옵션을 켜지 않았기 때문에 Testing Library 의 자동 정리가
// 동작하지 않는다. 테스트 간에 렌더링 결과가 남지 않도록 직접 정리한다.
afterEach(() => {
  cleanup();
});
