import {
  createBrowserRouter,
  createMemoryRouter,
  Navigate,
  type RouteObject,
} from 'react-router-dom';
import { COMPANY_SECTIONS } from '../features/company-detail/questions';
import { AgentRoomListPage } from '../pages/agent-room/AgentRoomListPage';
import { AgentRoomPage } from '../pages/agent-room/AgentRoomPage';
import { CompanyDetailPage } from '../pages/company-detail/CompanyDetailPage';
import { CompanySearchPage } from '../pages/companies/CompanySearchPage';
import { CompanyOverviewTab } from '../pages/company-detail/CompanyOverviewTab';
import { CoverLetterListPage } from '../pages/cover-letter/CoverLetterListPage';
import { CoverLetterWorkspacePage } from '../pages/cover-letter/CoverLetterWorkspacePage';
import { InterviewListPage } from '../pages/interview/InterviewListPage';
import { InterviewWorkspacePage } from '../pages/interview/InterviewWorkspacePage';
import { HomePage } from '../pages/home/HomePage';
import { LoginPage } from '../pages/auth/LoginPage';
import { SignupPage } from '../pages/auth/SignupPage';
import { VerifyPage } from '../pages/auth/VerifyPage';
import { VerifySentPage } from '../pages/auth/VerifySentPage';
import { NotFoundPage } from '../pages/not-found/NotFoundPage';

const routes: RouteObject[] = [
  {
    path: '/',
    element: <HomePage />,
  },
  {
    path: '/companies',
    element: <CompanySearchPage />,
  },
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/signup',
    element: <SignupPage />,
  },
  {
    path: '/verify-sent',
    element: <VerifySentPage />,
  },
  {
    path: '/verify',
    element: <VerifyPage />,
  },
  {
    path: '/cover-letters',
    element: <CoverLetterListPage />,
  },
  {
    path: '/cover-letters/new',
    element: <CoverLetterWorkspacePage />,
  },
  {
    path: '/cover-letters/:id',
    element: <CoverLetterWorkspacePage />,
  },
  {
    path: '/interviews',
    element: <InterviewListPage />,
  },
  {
    path: '/interviews/new',
    element: <InterviewWorkspacePage />,
  },
  {
    path: '/interviews/:id',
    element: <InterviewWorkspacePage />,
  },
  {
    path: '/agent-rooms',
    element: <AgentRoomListPage />,
  },
  {
    path: '/agent-rooms/:roomId',
    element: <AgentRoomPage />,
  },
  {
    path: '/companies/:companyId',
    element: <CompanyDetailPage />,
    children: [
      { index: true, element: <Navigate replace to="overview" /> },
      { path: 'overview', element: <CompanyOverviewTab /> },
      /*
       * 다섯 구획은 요약 한 장에 모두 이어 붙었다(CompanyOverviewTab). 구획만 따로 그리는
       * 화면을 남겨 두면 거기서는 그 구획밖에 안 보여, 한 페이지에 다 있다는 약속이 깨진다.
       * 예전 주소·북마크·공유 링크는 요약의 해당 자리로 보낸다 (요약이 해시를 보고 데려간다).
       */
      ...COMPANY_SECTIONS.map((section) => ({
        path: section,
        element: <Navigate replace to={`../overview#${section}`} />,
      })),
    ],
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
];

export const createAppRouter = (initialEntries?: string[]) => {
  if (initialEntries) {
    return createMemoryRouter(routes, { initialEntries });
  }

  return createBrowserRouter(routes);
};
