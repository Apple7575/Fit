import { useState } from 'react';
import { ApiError, isRateLimited } from '../../api/client';
import { Spinner } from '../../components/common/Spinner';
import { sendMessage } from './api';

interface MessageComposerProps {
  roomId: number;
  coverLetterItemId: number | null;
  selectedItemNumber: number | null;
  needsItemSelection: boolean;
  /** 턴이 도는 동안에는 새 발화를 막는다. 서버도 409 로 막는다. */
  busy: boolean;
  onStarted: (turnId: number) => void;
  /** 이미 검토 턴이 진행 중(409)일 때. 대화를 다시 읽어 busy 로 전환하게 한다. */
  onConflict?: () => void;
}

/**
 * 방에 말을 건다. 이 한 번이 곧 분석 요청이다.
 *
 * <p>문항을 고른 경우에는 그 id 를 함께 보내 글쓰기 담당이 해당 답변 하나만 첨삭하게 한다.
 */
export function MessageComposer({
  roomId,
  coverLetterItemId,
  selectedItemNumber,
  needsItemSelection,
  busy,
  onStarted,
  onConflict,
}: MessageComposerProps) {
  const [content, setContent] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    const text = content.trim();
    if (text === '') {
      setError('무엇을 봐 달라고 할지 적어 주세요.');
      return;
    }
    setSending(true);
    setError(null);
    try {
      const started = await sendMessage(roomId, text, coverLetterItemId ?? undefined);
      setContent('');
      onStarted(started.turnId);
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === 'TURN_IN_PROGRESS') {
        // 이미 도는 턴은 재전송으로 풀리지 않는다. 대화를 다시 읽어 busy 로 전환한다(입력은 보존).
        setError('이미 검토가 진행 중입니다. 끝나면 이어집니다.');
        onConflict?.();
      } else if (caught instanceof ApiError && isRateLimited(caught)) {
        setError('요청이 많습니다. 잠시 후 다시 시도해 주세요.');
      } else {
        setError(
          caught instanceof ApiError
            ? caught.message
            : '보내지 못했습니다. 잠시 후 다시 시도해 주세요.',
        );
      }
    } finally {
      setSending(false);
    }
  };

  const disabled = busy || sending;

  return (
    <div className="shrink-0 border-t border-slate-200 bg-white p-3">
      {selectedItemNumber !== null ? (
        <p className="mb-2 text-[11px] font-semibold text-blue-700">
          문항 {selectedItemNumber}을 중심으로 검토합니다.
        </p>
      ) : needsItemSelection ? (
        <p className="mb-2 text-[11px] font-semibold text-amber-700">
          글쓰기 담당의 첨삭을 받으려면 왼쪽에서 문항 하나를 선택해 주세요.
        </p>
      ) : null}
      {/*
        글자 수와 보내기를 칸 위에 얹어 두었더니, 라벨이 "보내기"(3자) 에서 "전송 중…"
        으로 넓어지는데 얹힌 자리는 76px 로 고정이라 단추가 칸 밖으로 비어져 나왔다.
        얹지 않고 칸 아래 한 줄로 내리면 겹칠 자리 자체가 없다.
      */}
      <div>
        <textarea
          value={content}
          rows={2}
          maxLength={2000}
          disabled={disabled}
          placeholder={
            busy ? '에이전트들이 답하는 중입니다…' : '예: 기술 서술이 충분한지 봐 주세요'
          }
          aria-label="에이전트에게 할 말"
          onChange={(event) => {
            setContent(event.target.value);
            if (error) setError(null);
          }}
          onKeyDown={(event) => {
            if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return;
            event.preventDefault();
            if (!disabled) void submit();
          }}
          className="block min-h-[76px] w-full resize-none rounded-xl border border-slate-200 px-3 py-2 text-[14px] leading-relaxed text-slate-800 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-50"
        />

        <div className="mt-1.5 flex items-center justify-between gap-2">
          <span className="text-[11px] tabular-nums text-slate-400">{content.length} / 2000</span>
          <button
            type="button"
            onClick={submit}
            disabled={disabled}
            className="inline-flex shrink-0 items-center rounded-lg bg-blue-600 px-3 py-1.5 text-[13px] font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
          >
            {/* 답이 오기까지 한참 걸린다. 글자만 바뀌면 눌린 것인지 멈춘 것인지 알 수 없다 */}
            {disabled && <Spinner className="mr-1.5" />}
            {sending ? '전송 중…' : busy ? '진행 중…' : '보내기'}
          </button>
        </div>
      </div>

      {error && (
        <p role="alert" className="mt-1 text-[13px] font-medium text-red-600">
          {error}
        </p>
      )}

    </div>
  );
}
