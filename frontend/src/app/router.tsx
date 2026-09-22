import {
  createBrowserRouter,
  createMemoryRouter,
  Navigate,
  useSearchParams,
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
import { MyPage } from '../pages/mypage/MyPage';

/**
 * 예전 검토 주소(`/agent-rooms?coverLetterId=…`)를 자소서에 매인 새 주소로 넘긴다.
 *
 * <p>검토 방이 독립 주소였을 때 나간 링크가 있다. 자소서를 들고 온 링크는 그 자소서의
 * 검토로, 맨몸으로 온 링크는 목록으로 보낸다 — 맨몸으로 열어 봐야 어느 자소서를 보는지
 * 알 수 없는 화면이 뜰 뿐이다.
 */
function LegacyReviewRedirect() {
  const [params] = useSearchParams();
  const id = Number(params.get('coverLetterId')) || null;
  return <Navigate replace to={id ? `/cover-letters/${id}/review` : '/cover-letters'} />;
}

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
    path: '/mypage',
    element: <MyPage />,
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
    // 검토는 자소서에 딸린 면이다 — 방은 자소서 id 로만 만들어진다
    path: '/cover-letters/:id/review',
    element: <AgentRoomListPage />,
  },
  {
    // 예전 주소. 들고 온 자소서가 있으면 그 자소서의 검토로, 없으면 목록으로 보낸다
    path: '/agent-rooms',
    element: <LegacyReviewRedirect />,
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
