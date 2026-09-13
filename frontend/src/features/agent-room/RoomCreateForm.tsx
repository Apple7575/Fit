import { useState } from 'react';
import { ApiError } from '../../api/client';
import { useCoverLetters } from '../cover-letter/queries';
import { createRoom } from './api';
import { AgentConfigFields } from './AgentConfigFields';
import { isDraftComplete, toConfigPayload, type ConfigDraft } from './configDraft';
import { useAgents, useJobRoles } from './queries';

interface RoomCreateFormProps {
  onCreated: (roomId: number) => void;
}

/**
 * 검토 방을 만든다.
 *
 * <p>에이전트를 1명만 고르면 전담 방, 2명 이상이면 합동 논의 방이다. 총괄은 고르지 않는다 —
 * 2명 이상일 때 서버가 붙인다.
 */
export function RoomCreateForm({ onCreated }: RoomCreateFormProps) {
  const { state: agents } = useAgents();
  const { state: jobRoles } = useJobRoles();
  const { state: coverLetters } = useCoverLetters();

  const [coverLetterId, setCoverLetterId] = useState<string>('');
  const [title, setTitle] = useState('');
  const [drafts, setDrafts] = useState<Record<string, ConfigDraft>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (agents.status !== 'success' || jobRoles.status !== 'success') {
    return (
      <p role="status" className="text-[14px] text-slate-400">
        에이전트 목록을 불러오는 중…
      </p>
    );
  }

  const selectable = agents.data.filter((agent) => agent.selectable);
  const chosen = Object.keys(drafts);

  const toggle = (agentKey: string) =>
    setDrafts((current) => {
      if (agentKey in current) {
        const { [agentKey]: _removed, ...rest } = current;
        return rest;
      }
      return { ...current, [agentKey]: {} };
    });

  const everyChosenComplete = selectable
    .filter((agent) => agent.agentKey in drafts)
    .every((agent) => isDraftComplete(drafts[agent.agentKey], agent.configSchema));

  const canSubmit =
    coverLetterId !== '' && title.trim() !== '' && chosen.length > 0 && everyChosenComplete;

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const room = await createRoom({
        coverLetterId: Number(coverLetterId),
        title: title.trim(),
        agents: selectable
          .filter((agent) => agent.agentKey in drafts)
          .map((agent) => ({
            agentKey: agent.agentKey,
            config: toConfigPayload(drafts[agent.agentKey], agent.configSchema),
          })),
      });
      onCreated(room.roomId);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : '방을 만들지 못했습니다. 잠시 후 다시 시도해 주세요.',
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section aria-label="검토 방 만들기" className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="mb-4 text-[16px] font-semibold text-slate-800">검토 방 만들기</h2>

      <div className="mb-4">
        <label htmlFor="room-cover-letter" className="mb-1.5 block text-[12px] font-medium text-slate-500">
          검토할 자소서
        </label>
        <select
          id="room-cover-letter"
          value={coverLetterId}
          onChange={(event) => setCoverLetterId(event.target.value)}
          className="h-[42px] w-full rounded-lg border border-slate-200 bg-white px-3 text-[15px] text-slate-800"
        >
          <option value="">자소서를 고르세요</option>
          {coverLetters.status === 'success' &&
            coverLetters.data.map((letter) => (
              <option key={letter.id} value={letter.id}>
                {letter.title}
              </option>
            ))}
        </select>
        {coverLetters.status === 'success' && coverLetters.data.length === 0 && (
          <p className="mt-1.5 text-[12px] text-slate-400">
            저장된 자소서가 없습니다. 자소서를 먼저 저장해 주세요.
          </p>
        )}
      </div>

      <div className="mb-4">
        <label htmlFor="room-title" className="mb-1.5 block text-[12px] font-medium text-slate-500">
          방 이름
        </label>
        <input
          id="room-title"
          value={title}
          maxLength={120}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="예: 네이버 백엔드 합동 검토"
          className="h-[42px] w-full rounded-lg border border-slate-200 bg-white px-3 text-[15px] text-slate-800 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
        />
      </div>

      <fieldset className="mb-2">
        <legend className="mb-1.5 text-[12px] font-medium text-slate-500">
          참여 에이전트 · 1명이면 전담 방, 2명 이상이면 합동 방입니다
        </legend>
        <div className="flex flex-col gap-3">
          {selectable.map((agent) => {
            const picked = agent.agentKey in drafts;
            return (
              <div key={agent.agentKey} className="rounded-lg border border-slate-200 p-3">
                <label className="flex items-start gap-2.5">
                  <input
                    type="checkbox"
                    checked={picked}
                    onChange={() => toggle(agent.agentKey)}
                    className="mt-1"
                  />
                  <span>
                    <span className="block text-[14px] font-semibold text-slate-800">{agent.name}</span>
                    <span className="block text-[12px] text-slate-500">{agent.description}</span>
                  </span>
                </label>

                {picked && Object.keys(agent.configSchema).length > 0 && (
                  <div className="mt-3 border-t border-slate-100 pt-3">
                    <AgentConfigFields
                      schema={agent.configSchema}
                      draft={drafts[agent.agentKey]}
                      onChange={(next) =>
                        setDrafts((current) => ({ ...current, [agent.agentKey]: next }))
                      }
                      jobRoles={jobRoles.data}
                      disabled={submitting}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </fieldset>

      {chosen.length >= 2 && (
        <p className="mb-2 text-[12px] text-slate-500">
          총괄 에이전트가 자동 참여하여 모든 피드백을 종합합니다.
        </p>
      )}

      {error && (
        <p role="alert" className="mb-2 text-[13px] font-medium text-red-600">
          {error}
        </p>
      )}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={submit}
          disabled={!canSubmit || submitting}
          className="rounded-lg bg-blue-600 px-4 py-2 text-[14px] font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
        >
          {submitting ? '만드는 중…' : '방 만들기'}
        </button>
      </div>
    </section>
  );
}
