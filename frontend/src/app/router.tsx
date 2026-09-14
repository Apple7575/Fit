import {
  createBrowserRouter,
  createMemoryRouter,
  Navigate,
  type RouteObject,
} from 'react-router-dom';
import { CompanyComparisonTab } from '../pages/company-detail/CompanyComparisonTab';
import { CompanyGrowthTab } from '../pages/company-detail/CompanyGrowthTab';
import { CompanyDetailPage } from '../pages/company-detail/CompanyDetailPage';
import { CompanyFocusTab } from '../pages/company-detail/CompanyFocusTab';
import { CompanyIssuesTab } from '../pages/company-detail/CompanyIssuesTab';
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
    path: '/companies/:companyId',
    element: <CompanyDetailPage />,
    children: [
      { index: true, element: <Navigate replace to="overview" /> },
      { path: 'overview', element: <CompanyOverviewTab /> },
      { path: 'growth', element: <CompanyGrowthTab /> },
      { path: 'focus', element: <CompanyFocusTab /> },
      { path: 'comparison', element: <CompanyComparisonTab /> },
      { path: 'issues', element: <CompanyIssuesTab /> },
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
