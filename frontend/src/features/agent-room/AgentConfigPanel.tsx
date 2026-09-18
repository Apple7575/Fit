import { useState } from 'react';
import { ApiError } from '../../api/client';
import { updateAgentConfig } from './api';
import { AgentConfigFields } from './AgentConfigFields';
import {
  isDraftComplete,
  toConfigPayload,
  toDraft,
  type ConfigDraft,
} from './configDraft';
import type { AgentCatalogEntry, RoomAgent } from './types';

interface AgentConfigPanelProps {
  roomId: number;
  agent: RoomAgent;
  catalog: AgentCatalogEntry | undefined;
  onSaved: () => void;
}

/** 방에 들어온 에이전트 하나의 설정을 바꾼다. 방을 다시 만들지 않는다. */
export function AgentConfigPanel({
  roomId,
  agent,
  catalog,
  onSaved,
}: AgentConfigPanelProps) {
  const [draft, setDraft] = useState<ConfigDraft>(() => toDraft(agent));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!catalog) {
    return (
      <p className="text-[13px] text-slate-400" role="status">
        에이전트 정보를 불러오는 중입니다…
      </p>
    );
  }

  const schema = catalog.configSchema;
  const complete = isDraftComplete(draft, schema);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await updateAgentConfig(roomId, agent.agentKey, toConfigPayload(draft, schema));
      onSaved();
    } catch (caught) {
      // 인덱싱이 없는 기업·대화 중 변경은 서버가 막는다. 그대로 보여준다.
      setError(
        caught instanceof ApiError
          ? caught.message
          : '설정을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.',
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <section
      aria-label={`${catalog.name} 설정`}
      className="rounded-xl border border-slate-200 bg-white p-4"
    >
      <header className="mb-3">
        <h3 className="text-[15px] font-semibold text-slate-800">{catalog.name} 설정</h3>
        <p className="mt-0.5 text-[12px] text-slate-500">{catalog.dataSource}</p>
      </header>

      <AgentConfigFields
        schema={schema}
        draft={draft}
        onChange={setDraft}
        disabled={saving}
      />

      {error && (
        <p role="alert" className="mt-3 text-[13px] font-medium text-red-600">
          {error}
        </p>
      )}

      {Object.keys(schema).length > 0 && (
        <div className="mt-4 flex items-center justify-end gap-2">
          {!complete && (
            <span className="text-[12px] text-slate-400">필수 항목을 채워 주세요</span>
          )}
          <button
            type="button"
            onClick={save}
            disabled={saving || !complete}
            className="rounded-lg bg-blue-600 px-4 py-2 text-[14px] font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
          >
            {saving ? '저장 중…' : '저장'}
          </button>
        </div>
      )}
    </section>
  );
}
