import { SiteHeader } from '../../components/layout/SiteHeader';

/**
 * 모의 면접 화면 상단. 전역 헤더를 그대로 쓰고, 화면 이름과 면접 제목만 로고 옆에 붙인다.
 *
 * <p>첫 화면을 영상에 통째로 내주는 목록 화면에서는 기업 화면과 똑같이 투명하게 띄웠다가,
 * 영상을 벗어나면 흰 유리로 돌아온다.
 */
export function InterviewHeader({
  breadcrumb,
  floating = false,
  scrolled = false,
  subnav = false,
}: {
  breadcrumb?: string | string[];
  floating?: boolean;
  scrolled?: boolean;
  /** 리포트처럼 바로 아래 문항 탭 줄이 붙는 화면. 헤더 밑줄을 긋지 않는다 */
  subnav?: boolean;
}) {
  return (
    <SiteHeader
      breadcrumb={breadcrumb ?? '모의 면접'}
      floating={floating}
      scrolled={scrolled}
      subnav={subnav}
    />
  );
}
