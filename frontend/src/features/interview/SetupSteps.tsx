import { Icon } from './icons';

/** 설정에서 밟는 단계. 회사 → 직무 → 유형 → 확인 순서다. */
export type SetupStep = 'company' | 'position' | 'type' | 'confirm';

export const STEP_ORDER: SetupStep[] = ['company', 'position', 'type', 'confirm'];

/** 단계마다 큰 글씨로 묻는 한 문장과 그 아래 한 줄 */
export const STEP_COPY: Record<SetupStep, { ask: string; sub: string }> = {
  company: {
    ask: '어느 회사의 면접인가요?',
    sub: '고른 회사의 공시·뉴스에서 질문을 만듭니다.',
  },
  position: {
    ask: '어떤 직무로 지원하나요?',
    sub: '비워 두면 직무를 가리지 않는 질문으로 나옵니다.',
  },
  type: {
    ask: '어떤 면접을 볼까요?',
    sub: '유형에 따라 물어보는 결이 달라집니다.',
  },
  confirm: {
    ask: '이대로 시작할까요?',
    sub: '실제 면접처럼 질문은 미리 보여주지 않습니다.',
  },
};

/**
 * 지금 어디쯤인지 알려주는 줄.
 *
 * <p>네 가지를 한 화면에 늘어놓으면 뭘 먼저 볼지 알 수 없어서 한 번에 하나만 묻는데, 그러면
 * 이번엔 "몇 개나 더 남았지"가 보이지 않는다. 지나온 단계는 눌러서 되돌아갈 수 있게 둔다
 * (앞으로 건너뛰는 건 막는다 — 회사를 안 고르고 유형부터 고를 일은 없다).
 */
export function StepRail({
  at,
  onJump,
}: {
  at: SetupStep;
  onJump: (step: SetupStep) => void;
}) {
  const now = STEP_ORDER.indexOf(at);
  return (
    <ol className="flex items-center gap-1.5">
      {STEP_ORDER.map((step, i) => {
        const done = i < now;
        const here = i === now;
        return (
          <li className="flex items-center gap-1.5" key={step}>
            {i > 0 && <span aria-hidden="true" className="h-px w-4 bg-white/25" />}
            <button
              aria-current={here ? 'step' : undefined}
              className={`flex size-6 items-center justify-center rounded-full text-[11px] font-bold transition ${
                here
                  ? 'bg-white text-slate-950'
                  : done
                    ? 'bg-white/25 text-white hover:bg-white/40'
                    : 'bg-white/10 text-white/40'
              }`}
              disabled={!done}
              onClick={() => onJump(step)}
              type="button"
            >
              {done ? <Icon className="size-3.5" name="check" /> : i + 1}
              <span className="sr-only">
                {i + 1}단계 {STEP_COPY[step].ask}
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * 단계 화면 한 장의 틀. 묻는 문장 → 고르는 자리 → 다음 단추 순서로 세로로만 흐른다.
 * 카드 세 장을 나란히 두던 때와 달리 한 화면에 고를 것이 하나뿐이다.
 */
export function StepCard({
  step,
  children,
  footer,
}: {
  step: SetupStep;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  const copy = STEP_COPY[step];
  return (
    <div className="rounded-3xl bg-white p-6 shadow-xl sm:p-8">
      <h2 className="text-[22px] font-extrabold break-keep text-slate-950">{copy.ask}</h2>
      <p className="mt-1 text-[13px] break-keep text-slate-500">{copy.sub}</p>
      <div className="mt-6">{children}</div>
      <div className="mt-7 flex items-center justify-between gap-3">{footer}</div>
    </div>
  );
}

/** 되돌아가기. 첫 단계에서는 자리만 지킨다(단추가 사라지면 다음 단추가 좌우로 널뛴다) */
export function BackButton({ onClick, show }: { onClick: () => void; show: boolean }) {
  if (!show) return <span />;
  return (
    <button
      className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-[13px] font-semibold text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
      onClick={onClick}
      type="button"
    >
      <Icon className="size-4 rotate-180" name="next" />
      이전
    </button>
  );
}

/** 다음으로. 고르지 않아도 넘어갈 수 있는 단계는 글귀로 그걸 알린다 */
export function NextButton({
  onClick,
  disabled,
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      className="flex items-center gap-1.5 rounded-full bg-slate-900 px-6 py-3 text-[14px] font-bold text-white transition hover:bg-slate-700 disabled:opacity-30 disabled:hover:bg-slate-900"
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {children}
      <Icon className="size-4" name="next" />
    </button>
  );
}
