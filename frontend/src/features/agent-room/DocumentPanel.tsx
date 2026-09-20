import { Link } from 'react-router-dom';
import type { QueryState } from '../../hooks/useApiQuery';
import type { CoverLetter } from '../cover-letter/types';

/**
 * 검토 방에 함께 띄우는 자소서 원문.
 * 코치가 무엇을 보고 말하는지 확인하려면 대화와 원문이 같은 화면에 있어야 한다.
 *
 * <p>조회는 하지 않는다. 넓은 화면의 오른쪽 칸과 좁은 화면의 접이식 자리 양쪽에 그려지는데,
 * 각자 조회하면 같은 자소서를 두 번 부른다(화면에 안 보여도 컴포넌트는 돈다).
 */
export function DocumentPanel({
  state,
  retry,
  /** 틀(테두리)을 그릴지. 접이식 안에서는 바깥 상자가 이미 있어 끈다 */
  framed = true,
}: {
  state: QueryState<CoverLetter>;
  retry: () => void;
  framed?: boolean;
}) {

  if (state.status === 'loading') {
    return (
      <p className="text-[13px] text-slate-400" role="status">
        자소서를 불러오는 중…
      </p>
    );
  }

  if (state.status === 'error') {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4" role="alert">
        <p className="text-[13px] text-slate-600">자소서를 불러오지 못했습니다.</p>
        <button className="mt-1 text-[12px] font-semibold text-blue-600 underline" onClick={retry} type="button">
          다시 시도
        </button>
      </div>
    );
  }

  const letter = state.data;
  const meta = [letter.targetCompany, letter.targetPosition].filter(Boolean).join(' · ');

  return (
    <article className={framed ? 'overflow-hidden rounded-2xl border border-slate-200 bg-white' : ''}>
      <header className="border-b border-slate-100 px-4 py-3">
        {framed && <p className="text-[12px] font-semibold text-slate-400">검토 중인 자소서</p>}
        <h2 className={`text-[15px] font-extrabold break-keep text-slate-950 ${framed ? 'mt-1' : ''}`}>
          {letter.title}
        </h2>
        <p className="mt-1 flex flex-wrap items-center gap-x-2 text-[12px] text-slate-500">
          {meta && <span>{meta}</span>}
          <Link className="font-semibold text-blue-600 hover:underline" to={`/cover-letters/${letter.id}`}>
            수정하기
          </Link>
        </p>
      </header>

      {letter.items.length === 0 ? (
        <p className="px-4 py-6 text-[13px] text-slate-400">아직 작성한 문항이 없습니다.</p>
      ) : (
        <ol className="divide-y divide-slate-100">
          {letter.items.map((item, i) => (
            <li className="px-4 py-4" key={i}>
              <p className="flex items-baseline gap-2">
                <span className="text-[12px] font-extrabold text-slate-300">{i + 1}</span>
                <span className="text-[13px] font-bold break-keep text-slate-800">{item.question}</span>
              </p>
              <p className="mt-2 text-[13px] leading-6 break-keep whitespace-pre-wrap text-slate-600">
                {item.answer || <span className="text-slate-400">아직 비어 있어요</span>}
              </p>
              <p className="mt-2 text-[12px] tabular-nums text-slate-400">
                {item.answer.length}
                {item.charLimit > 0 && ` / ${item.charLimit}`}자
              </p>
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}
