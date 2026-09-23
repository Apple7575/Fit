import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { SiteHeader } from '../../components/layout/SiteHeader';
import { CompanyLogo } from '../../features/company-summary/CompanyLogo';
import { CompanySearchForm } from '../../features/company-search/CompanySearchForm';
import {
  addRecentCompany,
  clearRecentCompanies,
  getRecentCompanies,
  type RecentCompany,
} from '../../features/company-search/recent';
import { FEATURED_COMPANIES } from '../home/featuredCompanies';

/** 첫 화면 배경. 기업 요약 화면처럼 영상 위에서 시작해 두 화면이 같은 인상을 갖게 한다 */
const HERO_VIDEO = '/company-media/search-hero.mp4';
const HERO_POSTER = '/company-media/search-hero.jpg';

/**
 * 기업 분석 시작 페이지.
 *
 * <p>기업 요약 화면이 사진 위 흰 글씨로 시작하는데 여기만 흰 종이라 다른 서비스처럼 보였다.
 * 그래서 위쪽을 영상 띠로 두고 제목·검색창·최근 본 기업을 그 위에 얹는다. 검색해서 들어가면
 * 같은 언어가 이어진다. 결과와 추천 기업은 아래 흰 바탕에서 읽는다.
 */
export function CompanySearchPage() {
  const navigate = useNavigate();
  const [recent, setRecent] = useState<RecentCompany[]>(() => getRecentCompanies());
  // 영상 위에서는 헤더를 투명하게 띄우고, 첫 화면을 벗어나면 흰 유리로 되돌린다
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 80);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const open = (company: RecentCompany) => {
    addRecentCompany(company);
    navigate(`/companies/${company.corpCode}/overview`);
  };

  return (
    <div className="relative flex min-h-screen flex-col bg-slate-50">
      <SiteHeader floating scrolled={scrolled} />

      {/*
        화면 전체가 영상 한 장. 헤더도 그 위에 투명하게 뜬다. 바로 볼 수 있는 기업도 그 위에 얹는다.

        overflow-hidden 은 두지 않는다. 검색칸 아래로 펼쳐지는 추천 목록이 창이 낮을 때
        이 장의 밑변을 넘어 잘려 나갔다. 배경(영상·그라데이션)은 모두 inset-0 이라 제 상자를
        벗어나지 않으니 잘라낼 것도 없다.
      */}
      <section className="relative isolate bg-slate-950 text-white">
        <div aria-hidden="true" className="absolute inset-0">
          <video
            autoPlay
            className="size-full object-cover"
            loop
            muted
            playsInline
            poster={HERO_POSTER}
            preload="metadata"
            src={HERO_VIDEO}
          />
          {/* 가운데 글씨와 아래 카드가 모두 읽히도록, 위아래를 더 눌러 둔다 */}
          <div className="absolute inset-0 bg-gradient-to-b from-slate-950/60 via-slate-950/55 to-slate-950/90" />
          {/* 아래로 갈수록 어둡게. 기업 목록이 영상 위에서도 또렷하게 읽힌다 */}
          <div className="absolute inset-x-0 bottom-0 h-52 bg-gradient-to-b from-transparent to-slate-950" />
        </div>

        <div className="relative mx-auto flex min-h-[100svh] w-full max-w-[1100px] flex-col px-6 pt-24 pb-16">
          <div className="flex flex-1 flex-col justify-center">
            <h1 className="display-lg text-center text-balance">어느 회사를 볼까요?</h1>
            <p className="mt-3 text-center text-[15px] break-keep text-white/70">
              공시와 뉴스로 만든 분석을 회사 이름으로 찾아보세요.
            </p>

            <div className="mx-auto mt-8 w-full max-w-2xl text-left text-slate-900">
              <CompanySearchForm onPick={open} />
            </div>

            {/* 다시 찾을 회사는 검색창 바로 아래에서 집게 한다. 처음 온 사람에게는 빈 줄을 보여 주지 않는다 */}
            {recent.length > 0 && (
              <section aria-labelledby="recent-title" className="mt-4">
                <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2">
                  <p className="flex items-center gap-2 text-[12px] font-semibold text-white/50">
                    <span id="recent-title">최근 본 기업</span>
                    <button
                      className="text-white/35 transition hover:text-white/80"
                      onClick={() => {
                        clearRecentCompanies();
                        setRecent([]);
                      }}
                      type="button"
                    >
                      지우기
                    </button>
                  </p>
                  <ul className="flex flex-wrap justify-center gap-1.5">
                    {recent.map((company) => (
                      <li key={company.corpCode}>
                        <button
                          className="rounded-full px-3 py-1 text-[13px] font-semibold text-white/80 ring-1 ring-white/20 transition hover:bg-white hover:text-slate-950"
                          onClick={() => open(company)}
                          type="button"
                        >
                          {company.corpName}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              </section>
            )}
          </div>

          <div className="mt-10 pt-6">
            <section aria-labelledby="featured-title">
              <p className="text-center text-[12px] font-semibold text-white/50" id="featured-title">
                바로 볼 수 있는 기업
              </p>
              <ul className="mx-auto mt-3 grid max-w-4xl grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
                {FEATURED_COMPANIES.map((company) => (
                  <li key={company.corpCode}>
                    <Link
                      className="flex items-center gap-2 rounded-xl bg-white/10 px-2.5 py-2 ring-1 ring-white/20 backdrop-blur transition hover:-translate-y-0.5 hover:bg-white hover:text-slate-950"
                      onClick={() => addRecentCompany({ corpCode: company.corpCode, corpName: company.name })}
                      to={`/companies/${company.corpCode}/overview`}
                    >
                      {/* 로고는 장식이다. 읽어 주는 이름은 회사명 하나로 둔다 */}
                      <span aria-hidden="true" className="shrink-0">
                        <CompanyLogo
                          className="rounded-lg"
                          corpCode={company.corpCode}
                          corpName={company.name}
                          homepageUrl={`https://${company.site}`}
                          size={24}
                        />
                      </span>
                      <span className="min-w-0 truncate text-[13px] font-semibold">{company.name}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </div>
      </section>

    </div>
  );
}
