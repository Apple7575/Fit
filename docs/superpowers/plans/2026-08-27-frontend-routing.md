# Frontend Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a runnable React frontend with tested routes for the home, company detail, and not-found pages.

**Architecture:** `App` supplies a React Router created in `router.tsx`, while each URL-level screen lives in its own `pages` directory. Routing is verified through a small router factory that creates a browser router in production and a memory router in tests.

**Tech Stack:** React 19.2.8, Vite 8.2.2, TypeScript 6.0.3, React Router, Vitest, Testing Library, jsdom, ESLint

**Spec:** `docs/superpowers/specs/2026-08-27-frontend-routing-design.md`

## Global Constraints

- Use npm as the package manager.
- Keep this task limited to routing scaffolding; do not add search, charts, API calls, or company mock data.
- Use `/`, `/companies/:companyId`, and `*` as the only routes.
- Display the `companyId` route parameter on the company detail placeholder page.
- Test routing behavior before writing page and router production code.

---

### Task 1: Project and test harness

**Files:**
- Delete: `frontend/.gitkeep`
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.app.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/eslint.config.js`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/test/setup.ts`

**Interfaces:**
- Consumes: no application code
- Produces: `npm run dev`, `npm run test`, `npm run lint`, `npm run build`

- [ ] **Step 1: Define the package manifest**

Add React, React DOM, and React Router as runtime dependencies. Add Vite, TypeScript, Vitest, jsdom, Testing Library, ESLint, React type packages, and Vite's React plugin as development dependencies. Define `dev`, `build`, `lint`, `preview`, and `test` scripts.

- [ ] **Step 2: Add TypeScript, Vite, ESLint, and HTML configuration**

Configure `vite.config.ts` with the React plugin and Vitest's jsdom environment. Load `src/test/setup.ts`, which imports `@testing-library/jest-dom/vitest`.

- [ ] **Step 3: Install dependencies**

Run: `npm install`

Expected: `node_modules` and `package-lock.json` are created without dependency resolution errors.

- [ ] **Step 4: Verify the test runner starts**

Run: `npm run test -- --run`

Expected: Vitest exits because no test files exist yet, proving the configured executable starts.

### Task 2: Route behavior via TDD

**Files:**
- Create: `frontend/src/app/router.test.tsx`
- Create: `frontend/src/app/router.tsx`
- Create: `frontend/src/app/App.tsx`
- Create: `frontend/src/pages/home/HomePage.tsx`
- Create: `frontend/src/pages/company-detail/CompanyDetailPage.tsx`
- Create: `frontend/src/pages/not-found/NotFoundPage.tsx`

**Interfaces:**
- Consumes: `createMemoryRouter` and `createBrowserRouter` from React Router
- Produces: `createAppRouter(initialEntries?: string[])` and `App`

- [ ] **Step 1: Write the failing routing tests**

```tsx
import { render, screen } from '@testing-library/react';
import { RouterProvider } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { createAppRouter } from './router';

const renderRoute = (path: string) => {
  render(<RouterProvider router={createAppRouter([path])} />);
};

describe('application routes', () => {
  it('renders the company search home at the root path', () => {
    renderRoute('/');
    expect(screen.getByRole('heading', { name: '기업 검색' })).toBeInTheDocument();
  });

  it('renders the selected company identifier on the detail route', () => {
    renderRoute('/companies/005930');
    expect(screen.getByRole('heading', { name: '기업 상세' })).toBeInTheDocument();
    expect(screen.getByText('기업 코드: 005930')).toBeInTheDocument();
  });

  it('renders a not-found page for unknown paths', () => {
    renderRoute('/unknown');
    expect(screen.getByRole('heading', { name: '페이지를 찾을 수 없습니다' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '홈으로 돌아가기' })).toHaveAttribute('href', '/');
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test -- --run src/app/router.test.tsx`

Expected: FAIL because `./router` does not exist.

- [ ] **Step 3: Implement the minimal pages and router**

Create the three semantic placeholder pages. Implement `createAppRouter(initialEntries?)` so tests use a memory router and production uses a browser router. `CompanyDetailPage` reads `companyId` with `useParams`, and `NotFoundPage` uses a React Router `Link` to `/`.

- [ ] **Step 4: Run the route test to verify it passes**

Run: `npm run test -- --run src/app/router.test.tsx`

Expected: all three tests PASS with no warnings.

### Task 3: Browser entry point and baseline styling

**Files:**
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/styles/global.css`
- Modify: `frontend/src/app/App.tsx`

**Interfaces:**
- Consumes: `App` from `src/app/App.tsx`
- Produces: a browser-rendered application mounted to `#root`

- [ ] **Step 1: Add the browser entry point**

Render `<App />` into the `#root` element under `StrictMode` and import `styles/global.css`.

- [ ] **Step 2: Add minimal global styles**

Set border-box sizing, a system font stack, readable foreground/background colors, and simple placeholder page spacing. Do not introduce a design system or detailed page styling.

- [ ] **Step 3: Run all verification commands**

Run: `npm run test -- --run`

Expected: all routing tests PASS.

Run: `npm run lint`

Expected: ESLint exits with code 0.

Run: `npm run build`

Expected: TypeScript and Vite build `dist` successfully.

- [ ] **Step 4: Review the final diff**

Run: `git status --short` and `git diff --check`

Expected: only the frontend scaffold and the approved design/plan documents are changed, with no whitespace errors.
