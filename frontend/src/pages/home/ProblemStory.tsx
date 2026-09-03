import { SCENES } from '../../data/homepageDemo';
import { Reveal } from './Reveal';

const PILES = [
  '사업보고서 PDF',
  '재무제표',
  '직원현황',
  '타법인 출자현황',
  '주요사항보고서',
  '네이버 뉴스',
  'Google RSS',
  '분기보고서',
  '공시 요약',
];

const QUESTIONS = [
  '어떤 회사인가?',
  '얼마나 성장했나?',
  '어디에 집중하고 있나?',
  '업계에서 어느 위치인가?',
  '최근 무슨 일이 있었나?',
];

/**
 * Scene 02~03 — 흩어진 자료가 다섯 가지 질문으로 정리되는 구간.
 * 실제 PDF 이미지 대신 HTML 카드 9장을 겹쳐 쌓아 자료가 많아 보이게 한다.
 */
export function ProblemStory() {
  return (
    <section
      aria-labelledby="problem-title"
      className="landing-section bg-white"
      id="problem-story"
    >
      <div className="landing-container">
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <div>
            <Reveal>
              <h2
                className="scene-title font-extrabold tracking-tight text-slate-950"
                id="problem-title"
              >
                수백 쪽의 사업보고서.
                <br />
                매일 쏟아지는 뉴스.
              </h2>
            </Reveal>
            <Reveal delay={150}>
              <p className="body-large mt-6 text-slate-500">
                자료는 많지만,
                <br />
                <strong className="font-bold text-slate-900">
                  회사가 어디로 가는지는 잘 보이지 않습니다.
                </strong>
              </p>
            </Reveal>
          </div>

          <Reveal className="relative mx-auto h-72 w-full max-w-md" delay={200}>
            <ul aria-label="흩어진 기업 자료" className="relative h-full">
              {PILES.map((name, i) => (
                <li
                  className="absolute rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-600 shadow-sm"
                  key={name}
                  style={{
                    left: `${(i * 37) % 60}%`,
                    top: `${(i * 23) % 70}%`,
                    transform: `rotate(${((i % 5) - 2) * 4}deg)`,
                  }}
                >
                  {name}
                </li>
              ))}
            </ul>
          </Reveal>
        </div>

        <div className="mt-28 sm:mt-40">
          <Reveal>
            <h2 className="scene-title text-center font-extrabold tracking-tight text-slate-950">
              기분은 다섯 가지 질문만 남깁니다.
            </h2>
          </Reveal>
          <ol className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {QUESTIONS.map((question, i) => (
              <Reveal as="li" delay={i * 90} key={question}>
                <a
                  className="landing-card block h-full transition hover:-translate-y-0.5 hover:border-blue-200"
                  href={`#scene-${SCENES[i].key}`}
                >
                  <span className="text-xs font-extrabold text-blue-600">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span className="mt-2 block text-base font-bold text-slate-900">
                    {question}
                  </span>
                  <span className="mt-3 block text-xs font-semibold text-slate-400">
                    {SCENES[i].tab}
                  </span>
                </a>
              </Reveal>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
