import { Link } from 'react-router-dom';
import { DEMO_COMPANY } from '../../data/homepageDemo';
import { Reveal } from './Reveal';

const CARDS = [
  {
    no: '01',
    title: '성장 신호',
    body: '최근 5년간 매출과 직원 수의 변화를 함께 확인합니다.',
    path: `/companies/${DEMO_COMPANY.corpCode}/growth`,
  },
  {
    no: '02',
    title: '집중 신호',
    body: '투자와 인력이 향한 분야를 근거와 함께 봅니다.',
    path: `/companies/${DEMO_COMPANY.corpCode}/focus`,
  },
  {
    no: '03',
    title: '최근 이슈',
    body: '최근 핵심 이슈를 날짜·출처와 함께 봅니다.',
    path: `/companies/${DEMO_COMPANY.corpCode}/issues`,
  },
];

/** Scene 09 — 앞의 다섯 탭을 취준생에게 필요한 세 가지로 다시 묶는다. */
export function TakeawayScene() {
  return (
    <section aria-labelledby="takeaway-title" className="landing-section bg-white">
      <div className="landing-container">
        <Reveal>
          <h2
            className="scene-title text-center font-extrabold tracking-tight text-slate-950"
            id="takeaway-title"
          >
            그래서 지원 전에,
            <br />
            세 가지만 기억하면 됩니다.
          </h2>
        </Reveal>

        <ul className="mt-12 grid gap-4 md:grid-cols-3">
          {CARDS.map((card, i) => (
            <Reveal as="li" delay={i * 120} key={card.no}>
              <div className="landing-card flex h-full flex-col">
                <span className="text-xs font-extrabold text-blue-600">{card.no}</span>
                <h3 className="mt-2 text-xl font-extrabold text-slate-950">{card.title}</h3>
                <p className="mt-3 flex-1 text-sm leading-6 text-slate-500">{card.body}</p>
                <Link
                  className="mt-5 inline-flex items-center gap-1 self-end text-sm font-bold text-blue-700 underline-offset-4 hover:underline"
                  to={card.path}
                >
                  근거 보기 <span aria-hidden="true">›</span>
                </Link>
              </div>
            </Reveal>
          ))}
        </ul>

        <Reveal className="mt-14 text-center" delay={200}>
          <p className="body-large text-slate-500">
            기분이 결론을 대신 내리지 않습니다.
            <br />
            <strong className="font-bold text-slate-900">
              판단에 필요한 근거를 짧게 연결합니다.
            </strong>
          </p>
        </Reveal>
      </div>
    </section>
  );
}
