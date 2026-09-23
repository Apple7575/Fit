import { useEffect, useRef } from 'react';
import { Icon } from './icons';

interface ResumePromptProps {
  /** 끊긴 면접의 회사. 없으면 "모의 면접" */
  company: string | null;
  position: string | null;
  /** "3시간 전" 같은 상대 시각 */
  when: string;
  /** 몇 번째 문항까지 답했는지. 셀 수 없으면 null */
  answered: number | null;
  total: number | null;
  onResume: () => void;
  onDismiss: () => void;
  /** 이 면접에 대해 다시 묻지 않기 */
  onMute: () => void;
}

/**
 * 끊긴 면접이 있을 때 목록에 들어오면 묻는 창.
 *
 * <p>첫 화면 한가운데에 카드로 띄워 두었더니, 가운데 정렬인 제목·설명 사이에 왼쪽 정렬
 * 상자가 끼어 따로 놀았고 '이어서 진행'과 '새 면접 시작' 두 단추가 서로 눈에 띄려고
 * 다퉜다. 이어서 할지 말지는 들어온 순간 한 번 정하면 되는 일이라 창으로 묻는다.
 *
 * <p>닫으면 그만이다. 다시 뜨지 않게 막지는 않는다 — 끊긴 면접은 계속 거기 있고, 페이지를
 * 다시 열었다는 것은 대개 그 면접을 하러 온 것이다. 다만 한 번 닫으면 그 화면에서는
 * 다시 묻지 않는다(목록을 보러 온 사람을 계속 막아서는 안 된다).
 */
export function ResumePrompt({
  company,
  position,
  when,
  answered,
  total,
  onResume,
  onDismiss,
  onMute,
}: ResumePromptProps) {
  const resumeRef = useRef<HTMLButtonElement>(null);
  // 창을 열기 전에 어디에 있었는지. 닫을 때 그 자리로 초점을 돌려준다
  const openerRef = useRef<Element | null>(null);

  useEffect(() => {
    openerRef.current = document.activeElement;
    resumeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onDismiss();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      (openerRef.current as HTMLElement | null)?.focus?.();
    };
  }, [onDismiss]);

  return (
    <div
      aria-labelledby="resume-title"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-6 backdrop-blur-sm"
      // 바깥을 누르면 닫힌다. 안쪽 클릭이 올라와 닫히지 않게 대상까지 확인한다
      onClick={(event) => {
        if (event.target === event.currentTarget) onDismiss();
      }}
      role="dialog"
    >
      <div className="w-full max-w-sm rounded-3xl bg-white p-6 text-center shadow-2xl">
        <span
          aria-hidden="true"
          className="mx-auto flex size-12 items-center justify-center rounded-full bg-slate-900 text-white"
        >
          <Icon name="redo" />
        </span>

        <h2 className="mt-4 text-[18px] font-extrabold text-slate-950" id="resume-title">
          하던 면접이 남아 있어요
        </h2>

        {/* 어느 면접인지가 이 창의 알맹이다. 회사·직무를 제목 다음으로 크게 둔다 */}
        <p className="mt-3 text-[15px] font-bold break-keep wrap-anywhere text-slate-900">
          {company || '모의 면접'}
          {position && <span className="font-semibold text-slate-500"> · {position}</span>}
        </p>
        <p className="mt-1 text-[12px] text-slate-400">
          {answered !== null && total !== null && `${total}문항 중 ${answered}개 답함 · `}
          {when} 중단
        </p>

        <div className="mt-6 flex flex-col gap-2">
          <button
            className="rounded-xl bg-slate-900 px-4 py-3 text-sm font-bold text-white transition hover:bg-slate-700"
            onClick={onResume}
            ref={resumeRef}
            type="button"
          >
            이어서 진행하기
          </button>
          <button
            className="rounded-xl px-4 py-2.5 text-sm font-semibold text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
            onClick={onDismiss}
            type="button"
          >
            나중에 할게요
          </button>
        </div>

        {/*
          목록에 들어올 때마다 뜨는 창을 끌 길은 있어야 한다. 다만 끄더라도 아래 '내 모의
          면접' 목록에는 그대로 남으므로, 마음이 바뀌면 거기서 이어서 할 수 있다.
        */}
        <button
          className="mt-3 text-[12px] font-semibold text-slate-400 underline-offset-2 transition hover:text-slate-600 hover:underline"
          onClick={onMute}
          type="button"
        >
          이 면접은 다시 묻지 않기
        </button>
      </div>
    </div>
  );
}
