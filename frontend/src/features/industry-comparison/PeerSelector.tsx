import { MAX_PEERS, type IndustryCompany } from './types';

interface PeerSelectorProps {
  candidates: IndustryCompany[];
  selected: readonly string[];
  onChange: (next: string[]) => void;
  /** 후보를 불러오는 중이면 true */
  loading?: boolean;
}

/**
 * 비교 기업 선택. 체크박스 그룹이며 최대 MAX_PEERS 개까지 고를 수 있다.
 * 한도에 닿으면 나머지 후보는 비활성화한다 (해제하면 다시 고를 수 있음).
 */
export function PeerSelector({
  candidates,
  selected,
  onChange,
  loading = false,
}: PeerSelectorProps) {
  const full = selected.length >= MAX_PEERS;

  const toggle = (corpCode: string) => {
    if (selected.includes(corpCode)) {
      onChange(selected.filter((c) => c !== corpCode));
    } else if (!full) {
      onChange([...selected, corpCode]);
    }
  };

  return (
    <fieldset>
      <legend className="text-sm font-bold text-slate-700">
        비교 기업 선택
        <span className="ml-2 text-xs font-medium text-slate-400">
          {selected.length}/{MAX_PEERS}
        </span>
      </legend>

      {loading ? (
        <p className="mt-2 text-sm text-slate-400" role="status">
          비교 후보를 불러오는 중입니다
        </p>
      ) : candidates.length === 0 ? (
        <p className="mt-2 text-sm text-slate-400">
          같은 산업의 비교 후보 기업이 없습니다
        </p>
      ) : (
        <ul className="mt-2 flex flex-wrap gap-2">
          {candidates.map((company) => {
            const checked = selected.includes(company.corpCode);
            const disabled = !checked && full;
            return (
              <li key={company.corpCode}>
                <label
                  className={`inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-semibold transition select-none has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-blue-300 ${
                    checked
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : disabled
                        ? 'cursor-not-allowed border-slate-200 bg-slate-50 text-slate-300'
                        : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400'
                  }`}
                >
                  <input
                    checked={checked}
                    className="sr-only"
                    disabled={disabled}
                    onChange={() => toggle(company.corpCode)}
                    type="checkbox"
                    value={company.corpCode}
                  />
                  {checked && <span aria-hidden="true">✓</span>}
                  {company.corpName}
                </label>
              </li>
            );
          })}
        </ul>
      )}
    </fieldset>
  );
}
