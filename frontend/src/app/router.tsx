import {
  createBrowserRouter,
  createMemoryRouter,
  Navigate,
  type RouteObject,
} from 'react-router-dom';
import { CompanyComparisonTab } from '../pages/company-detail/CompanyComparisonTab';
import { CompanyGrowthTab } from '../pages/company-detail/CompanyGrowthTab';
import { CompanyDetailPage } from '../pages/company-detail/CompanyDetailPage';
import { CompanyOverviewTab } from '../pages/company-detail/CompanyOverviewTab';
import { HomePage } from '../pages/home/HomePage';
import { NotFoundPage } from '../pages/not-found/NotFoundPage';

const routes: RouteObject[] = [
  {
    path: '/',
    element: <HomePage />,
  },
  {
    path: '/companies/:companyId',
    element: <CompanyDetailPage />,
    children: [
      { index: true, element: <Navigate replace to="overview" /> },
      { path: 'overview', element: <CompanyOverviewTab /> },
      { path: 'growth', element: <CompanyGrowthTab /> },
      { path: 'comparison', element: <CompanyComparisonTab /> },
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
