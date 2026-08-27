import {
  createBrowserRouter,
  createMemoryRouter,
  type RouteObject,
} from 'react-router-dom';
import { CompanyDetailPage } from '../pages/company-detail/CompanyDetailPage';
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
