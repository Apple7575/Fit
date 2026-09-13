import { CompanyMultiPicker } from './CompanyMultiPicker';
import type { ConfigDraft } from './configDraft';
import type { ConfigField, JobRoleOption, RoomCompany } from './types';

interface AgentConfigFieldsProps {
  schema: Record<string, ConfigField>;
  draft: ConfigDraft;
  onChange: (draft: ConfigDraft) => void;
  jobRoles: JobRoleOption[];
  disabled?: boolean;
}

/**
 * 에이전트 설정 입력칸을 configSchema 로 그린다.
 *
 * <p>에이전트마다 폼을 따로 만들지 않는다. 에이전트가 늘어도 서버가 스키마만 내려주면 화면은
 * 그대로 동작한다. 다만 기업·직무는 단순 입력칸으로는 고를 수 없어 항목 이름으로 전용 위젯을
 * 붙이고, 나머지는 type 을 보고 일반 입력칸을 쓴다.
 */
export function AgentConfigFields({
  schema,
  draft,
  onChange,
  jobRoles,
  disabled = false,
}: AgentConfigFieldsProps) {
  const entries = Object.entries(schema);
  if (entries.length === 0) {
    return <p className="text-[13px] text-slate-400">설정할 것이 없는 에이전트입니다.</p>;
  }

  const set = (name: string, value: unknown) => onChange({ ...draft, [name]: value });

  return (
    <div className="flex flex-col gap-4">
      {entries.map(([name, field]) => (
        <div key={name}>
          <label className="mb-1.5 block text-[12px] font-medium text-slate-500">
            {field.description}
            {!field.required && <span className="ml-1 text-slate-400">(선택)</span>}
          </label>

          {name === 'corpCodes' ? (
            <CompanyMultiPicker
              value={(draft.corpCodes as RoomCompany[] | undefined) ?? []}
              onChange={(companies) => set('corpCodes', companies)}
              disabled={disabled}
            />
          ) : name === 'jobRole' ? (
            <ul className="flex flex-wrap gap-1.5" aria-label="지원 직무">
              {jobRoles.map((role) => {
                const selected = draft.jobRole === role.key;
                return (
                  <li key={role.key}>
                    <button
                      type="button"
                      disabled={disabled || !role.ready}
                      aria-pressed={selected}
                      title={role.ready ? role.topics.join(' · ') : '지식베이스가 아직 준비되지 않았습니다'}
                      onClick={() => set('jobRole', role.key)}
                      className={`rounded-full px-3 py-1 text-[13px] transition ${
                        selected
                          ? 'bg-emerald-50 font-semibold text-emerald-800'
                          : 'border border-slate-200 text-slate-600 hover:bg-slate-50'
                      } disabled:cursor-not-allowed disabled:border-dashed disabled:text-slate-300 disabled:hover:bg-transparent`}
                    >
                      {role.name}
                      {!role.ready && <span className="ml-1 text-[11px]">준비 중</span>}
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <input
              type={field.type === 'number' ? 'number' : 'text'}
              value={(draft[name] as string | number | undefined) ?? ''}
              disabled={disabled}
              aria-label={field.description}
              onChange={(event) =>
                set(
                  name,
                  field.type === 'number'
                    ? event.target.value === ''
                      ? ''
                      : Number(event.target.value)
                    : event.target.value,
                )
              }
              className="h-[42px] w-full rounded-lg border border-slate-200 bg-white px-3 text-[15px] text-slate-800 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
            />
          )}
        </div>
      ))}
    </div>
  );
}
