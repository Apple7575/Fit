import { useEffect, useState } from 'react';
import { updateCoverLetter } from '../cover-letter/api';
import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { Spinner } from '../../components/common/Spinner';
import type { QueryState } from '../../hooks/useApiQuery';
import type { CoverLetter, CoverLetterInput } from '../cover-letter/types';

interface AnswerSelection {
  itemIndex: number;
  start: number;
  end: number;
  original: string;
  draft: string;
  left: number;
  top: number;
}

const BUBBLE_WIDTH = 320;
const BUBBLE_HEIGHT = 210;

const selectionElement = (node: Node) =>
  node.nodeType === Node.ELEMENT_NODE ? (node as Element) : node.parentElement;

/**
 * 검토 방에 함께 띄우는 자소서 원문.
 * 코치가 무엇을 보고 말하는지 확인하려면 대화와 원문이 같은 화면에 있어야 한다.
 *
 * <p>조회는 하지 않는다. 방에서 불러온 원문을 왼쪽의 넓은 영역에 표시한다.
 */
export function DocumentPanel({
  state,
  retry,
}: {
  state: QueryState<CoverLetter>;
  retry: () => void;
}) {
  const [selection, setSelection] = useState<AnswerSelection | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (!selection) return;
    const close = () => setSelection(null);
    window.addEventListener('resize', close);
    window.addEventListener('scroll', close, { passive: true });
    return () => {
      window.removeEventListener('resize', close);
      window.removeEventListener('scroll', close);
    };
  }, [selection]);

  if (state.status === 'loading') {
    return <LoadingScreen compact message="자소서를 불러오는 중" />;
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

  const captureSelection = () => {
    window.setTimeout(() => {
      const browserSelection = window.getSelection();
      if (!browserSelection || browserSelection.isCollapsed || browserSelection.rangeCount === 0) {
        setSelection(null);
        return;
      }

      const range = browserSelection.getRangeAt(0);
      const startElement = selectionElement(range.startContainer);
      const endElement = selectionElement(range.endContainer);
      const answer = startElement?.closest<HTMLElement>('[data-cover-letter-answer]');
      if (!answer || !answer.contains(endElement)) return;

      const itemIndex = Number(answer.dataset.coverLetterAnswer);
      if (!Number.isInteger(itemIndex) || !letter.items[itemIndex]) return;

      const prefix = document.createRange();
      prefix.selectNodeContents(answer);
      prefix.setEnd(range.startContainer, range.startOffset);
      const start = prefix.toString().length;
      const original = range.toString();
      if (original.trim() === '') return;

      const rect = range.getBoundingClientRect();
      const left = Math.max(
        12,
        Math.min(window.innerWidth - BUBBLE_WIDTH - 12, rect.left + rect.width / 2 - BUBBLE_WIDTH / 2),
      );
      const below = rect.bottom + 10;
      const top =
        below + BUBBLE_HEIGHT <= window.innerHeight
          ? below
          : Math.max(12, rect.top - BUBBLE_HEIGHT - 10);

      setSaveError(null);
      setSelection({
        itemIndex,
        start,
        end: start + original.length,
        original,
        draft: original,
        left,
        top,
      });
    }, 0);
  };

  const saveSelection = async () => {
    if (!selection) return;
    const selectedItem = letter.items[selection.itemIndex];
    const nextAnswer =
      selectedItem.answer.slice(0, selection.start) +
      selection.draft +
      selectedItem.answer.slice(selection.end);

    if (selectedItem.charLimit > 0 && nextAnswer.length > selectedItem.charLimit) {
      setSaveError(`수정하면 ${selectedItem.charLimit}자를 넘습니다.`);
      return;
    }

    const input: CoverLetterInput = {
      title: letter.title,
      targetCompany: letter.targetCompany,
      targetPosition: letter.targetPosition,
      jobContextId: letter.jobContextId,
      items: letter.items.map((item, index) =>
        index === selection.itemIndex ? { ...item, answer: nextAnswer } : item,
      ),
    };

    setSaving(true);
    setSaveError(null);
    try {
      await updateCoverLetter(letter.id, input);
      window.getSelection()?.removeAllRanges();
      setSelection(null);
      retry();
    } catch {
      setSaveError('수정 내용을 저장하지 못했습니다. 다시 시도해 주세요.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
    <article
      className="flex min-h-[420px] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white md:min-h-[520px] xl:min-h-[calc(100vh-10rem)]"
      onPointerUp={captureSelection}
    >
      <header className="border-b border-slate-100 px-4 py-3">
        <p className="text-[12px] font-semibold text-slate-400">검토 중인 자소서</p>
        <h2 className="mt-1 text-[15px] font-extrabold break-keep wrap-anywhere text-slate-950">
          {letter.title}
        </h2>
        <p className="mt-1 flex flex-wrap items-center gap-x-2 text-[12px] text-slate-500">
          {meta && <span>{meta}</span>}
        </p>
      </header>

      {letter.items.length === 0 ? (
        <p className="px-4 py-6 text-[13px] text-slate-400">아직 작성한 문항이 없습니다.</p>
      ) : (
        <ol className="flex-1 divide-y divide-slate-100">
          {letter.items.map((item, i) => (
            <li className="px-4 py-5" key={i}>
              <div className="flex items-start gap-2.5">
                <span className="mt-0.5 shrink-0 rounded-md bg-slate-100 px-2 py-1 text-[10px] font-bold text-slate-500">
                  문항 {i + 1}
                </span>
                <h3 className="min-w-0 pt-0.5 text-[14px] font-bold leading-6 break-keep wrap-anywhere text-slate-900">
                  {item.question}
                </h3>
              </div>

              <div className="mt-3 rounded-xl border border-slate-100 bg-slate-50/80 px-3.5 py-3">
                <p className="mb-1.5 text-[10px] font-bold tracking-wide text-slate-400">답변</p>
                <p
                  className="cursor-text text-[13px] leading-6 break-keep wrap-anywhere whitespace-pre-wrap text-slate-600 selection:bg-blue-200 selection:text-slate-900"
                  data-cover-letter-answer={i}
                  title="문장을 드래그하면 선택한 부분만 수정할 수 있습니다"
                >
                  {item.answer || <span className="text-slate-400">아직 비어 있어요</span>}
                </p>
                <p className="mt-2 text-right text-[11px] tabular-nums text-slate-400">
                  {item.answer.length}
                  {item.charLimit > 0 && ` / ${item.charLimit}`}자
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </article>

    {selection && (
      <aside
        aria-label="선택한 문장 수정"
        className="fixed z-50 w-[calc(100vw-24px)] max-w-[320px] rounded-2xl border border-blue-200 bg-white p-3 shadow-2xl"
        style={{ left: selection.left, top: selection.top }}
      >
        <div className="mb-2 flex items-center justify-between gap-3">
          <p className="text-[12px] font-bold text-slate-800">선택한 부분 수정</p>
          <button
            type="button"
            aria-label="수정 말풍선 닫기"
            onClick={() => setSelection(null)}
            className="text-lg leading-none text-slate-400 hover:text-slate-700"
          >
            ×
          </button>
        </div>
        <p className="mb-2 line-clamp-2 text-[11px] leading-4 text-slate-400">
          선택: {selection.original}
        </p>
        <textarea
          autoFocus
          value={selection.draft}
          rows={3}
          aria-label="선택한 부분의 수정 내용"
          onChange={(event) => {
            setSelection((current) => current ? { ...current, draft: event.target.value } : current);
            if (saveError) setSaveError(null);
          }}
          className="w-full resize-none rounded-xl border border-slate-200 px-3 py-2 text-[13px] leading-5 text-slate-800 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
        />
        {saveError && <p role="alert" className="mt-1 text-[11px] font-medium text-red-600">{saveError}</p>}
        <div className="mt-2 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => setSelection(null)}
            className="rounded-lg px-3 py-1.5 text-[12px] font-semibold text-slate-500 hover:bg-slate-100"
          >
            취소
          </button>
          <button
            type="button"
            disabled={saving || selection.draft === selection.original}
            onClick={() => void saveSelection()}
            className="inline-flex items-center rounded-lg bg-blue-600 px-3 py-1.5 text-[12px] font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
          >
            {saving && <Spinner className="mr-1.5" />}
            {saving ? '저장 중…' : '적용'}
          </button>
        </div>
      </aside>
    )}
    </>
  );
}
