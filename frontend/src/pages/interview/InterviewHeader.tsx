import { SiteHeader } from '../../components/layout/SiteHeader';

/** 모의 면접 화면 상단. 전역 헤더를 그대로 쓰고, 화면 이름만 로고 옆에 붙인다. */
export function InterviewHeader({ breadcrumb }: { breadcrumb?: string }) {
  return <SiteHeader breadcrumb={breadcrumb ?? '모의 면접'} />;
}
