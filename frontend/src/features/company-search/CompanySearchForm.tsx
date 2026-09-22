import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { MAX_KEYWORD, searchCompanies } from './api';
import { qwertyToHangul } from './qwertyToHangul';
import type { Company } from '../../types/company';

type CompanySearchFormProps = {
  onSearch?: (keyword: string) => void;
  /** 칸 아래 추천에서 회사를 고른 경우. 주면 검색을 거치지 않고 그 회사로 바로 간다. */
  onPick?: (company: Company) => void;
};

/**
 * 글자를 멈춘 뒤 이만큼 지나면 찾아본다.
 *
 * <p>한 글자마다 부르면 "삼성전자" 를 치는 동안 네 번을 부르고, 앞선 응답이 뒤늦게 와서
 * 목록이 되돌아가기도 한다. 0.2초는 다음 글자를 누르는 사이보다 짧아 멈춘 것처럼 보이지 않는다.
 */
const TYPING_PAUSE_MS = 200;

/**
 * 칸 아래에 펼쳐 둘 최대 개수. 더 보려면 검색을 눌러 아래 목록에서 본다.
 *
 * <p>다섯이면 창 높이 640px 짜리 노트북에서도 목록이 화면 안에 들어온다. 여섯이면 마지막
 * 줄이 접히는 곳에 걸린다.
 */
const MAX_SUGGESTIONS = 5;

/**
 * 친 글자로 시작하는 회사를 앞에 세운다.
 *
 * <p>서버는 이름 어디에 있든 찾아 주므로 "삼" 을 치면 "삼성전자" 와 "한국삼공" 이 뒤섞인다.
 * 찾는 사람은 앞글자를 치고 있으니 그것부터 보여 준다.
 */
const startsWithFirst = (items: Company[], keyword: string) => [
  ...items.filter((company) => company.corpName.startsWith(keyword)),
  ...items.filter((company) => !company.corpName.startsWith(keyword)),
];

export function CompanySearchForm({ onSearch, onPick }: CompanySearchFormProps) {
  const [keyword, setKeyword] = useState('');
  const [suggestions, setSuggestions] = useState<Company[]>([]);
  const [open, setOpen] = useState(false);
  /** 키보드로 짚고 있는 줄. -1 이면 아무것도 안 짚은 상태다 */
  const [active, setActive] = useState(-1);
  /** 자판을 안 바꾸고 친 것으로 보여 한글로 되돌려 찾은 경우. 무엇을 무엇으로 바꿨는지 알린다 */
  const [swap, setSwap] = useState<{ from: string; to: string } | null>(null);
  const listId = useId();
  const inFlight = useRef<AbortController | null>(null);

  const trimmedKeyword = keyword.trim();
  const canSearch = trimmedKeyword.length > 0;
  /*
   * 칸을 비우면 지난 결과는 곧바로 없는 것으로 친다. 상태를 비우지 않고 여기서 거르는
   * 것은, 칸이 비었다는 사실만으로 다시 그릴 일을 만들지 않기 위해서다.
   */
  const visible = trimmedKeyword === '' ? [] : suggestions;
  const showList = open && visible.length > 0;

  useEffect(() => () => inFlight.current?.abort(), []);

  useEffect(() => {
    if (trimmedKeyword === '') {
      inFlight.current?.abort();
      return;
    }

    const timer = setTimeout(() => {
      inFlight.current?.abort();
      const controller = new AbortController();
      inFlight.current = controller;

      const run = async () => {
        let found = await searchCompanies(trimmedKeyword, controller.signal);
        let matched = trimmedKeyword;
        let swapped: { from: string; to: string } | null = null;

        /*
         * 빈손일 때만 자판을 안 바꾸고 친 것으로 보고 한 번 더 찾는다("tka" → "삼").
         * 처음부터 바꿔 찾으면 치지도 않은 말을 찾아 주는 셈이 된다.
         */
        if (found.items.length === 0) {
          const hangul = qwertyToHangul(trimmedKeyword);
          if (hangul !== trimmedKeyword) {
            const retry = await searchCompanies(hangul, controller.signal);
            if (retry.items.length > 0) {
              found = retry;
              matched = hangul;
              swapped = { from: trimmedKeyword, to: hangul };
            }
          }
        }

        if (controller.signal.aborted) return;
        setSuggestions(startsWithFirst(found.items, matched).slice(0, MAX_SUGGESTIONS));
        setSwap(swapped);
        setActive(-1);
        setOpen(true);
      };

      run().catch(() => {
        // 추천은 거들 뿐이다. 실패하면 조용히 접는다 — 검색 단추는 그대로 쓸 수 있다
        if (controller.signal.aborted) return;
        setSuggestions([]);
        setSwap(null);
      });
    }, TYPING_PAUSE_MS);

    return () => clearTimeout(timer);
  }, [trimmedKeyword]);

  const close = () => {
    setOpen(false);
    setActive(-1);
  };

  const pick = (company: Company) => {
    setKeyword(company.corpName);
    close();
    if (onPick) {
      onPick(company);
      return;
    }
    onSearch?.(company.corpName);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!canSearch) {
      return;
    }

    close();
    onSearch?.(trimmedKeyword);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    // 한글을 조합하는 중에는 방향키·엔터가 글자를 고르는 데 쓰인다. 가로채지 않는다
    if (event.nativeEvent.isComposing) return;

    if (event.key === 'Escape') {
      close();
      return;
    }

    if (visible.length === 0) return;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setOpen(true);
      setActive((index) => (index + 1) % visible.length);
      return;
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setOpen(true);
      setActive((index) => (index <= 0 ? visible.length - 1 : index - 1));
      return;
    }

    // 짚어 둔 줄이 있으면 엔터는 그 회사로 간다. 없으면 여느 때처럼 검색이 된다
    if (event.key === 'Enter' && showList && active >= 0) {
      event.preventDefault();
      pick(visible[active]);
    }
  };

  return (
    /* 추천은 칸 바로 아래에 겹쳐 뜬다. 칸 밖으로 초점이 나가면 접는다 */
    <div
      className="relative w-full"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) close();
      }}
    >
      <form className="w-full" onSubmit={handleSubmit} role="search">
        <label className="sr-only" htmlFor="company-search-keyword">
          기업명
        </label>
        <div className="flex items-center gap-2 rounded-full border border-slate-300 bg-white p-2 shadow-sm transition focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-100 sm:gap-3">
          <svg
            aria-hidden="true"
            className="ml-2 size-5 shrink-0 text-slate-400 sm:ml-3"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" strokeLinecap="round" />
          </svg>
          <input
            aria-activedescendant={showList && active >= 0 ? `${listId}-${active}` : undefined}
            aria-autocomplete="list"
            aria-controls={listId}
            aria-expanded={showList}
            autoComplete="off"
            className="min-w-0 flex-1 bg-transparent text-base text-slate-900 outline-none placeholder:text-slate-400"
            id="company-search-keyword"
            // 긴 글을 붙여 넣어도 여기서 잘린다. 기업명은 이보다 길 수 없다
            maxLength={MAX_KEYWORD}
            onChange={(event) => setKeyword(event.target.value)}
            onFocus={() => setOpen(true)}
            onKeyDown={handleKeyDown}
            placeholder="기업명을 입력하세요"
            spellCheck={false}
            type="search"
            value={keyword}
          />
          <button
            className="shrink-0 rounded-full bg-blue-600 px-5 py-2.5 text-sm font-bold text-white transition hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:bg-slate-300 sm:px-6"
            disabled={!canSearch}
            type="submit"
          >
            검색
          </button>
        </div>
      </form>

      {showList && (
        <ul
          aria-label="기업 추천"
          className="absolute top-full right-0 left-0 z-30 mt-2 rounded-2xl border border-slate-200 bg-white p-1.5 text-left shadow-xl"
          id={listId}
          role="listbox"
        >
          {/* 말없이 바꿔 찾으면 내가 안 친 말이 나온 것으로 보인다. 무엇을 바꿨는지 먼저 알린다 */}
          {swap && (
            <li className="px-3 pt-1 pb-2 text-[12px] text-slate-500" role="presentation">
              한글로 바꿔 찾았어요 · <span className="font-semibold text-slate-700">{swap.from}</span>{' '}
              → <span className="font-semibold text-slate-700">{swap.to}</span>
            </li>
          )}
          {visible.map((company, index) => (
            /*
             * 단추를 겹쳐 넣지 않는다 — 목록 안의 줄은 방향키로 짚고 엔터로 고른다.
             * 누를 때는 mousedown 으로 받는다. click 을 기다리면 그 전에 칸에서 초점이
             * 빠지면서 목록이 먼저 접혀 눌리지 않는다.
             */
            <li
              aria-selected={index === active}
              className={`flex h-14 cursor-pointer items-center justify-between gap-3 rounded-xl px-3 transition ${
                index === active ? 'bg-slate-100' : 'hover:bg-slate-50'
              }`}
              id={`${listId}-${index}`}
              key={company.corpCode}
              onMouseDown={() => pick(company)}
              onMouseEnter={() => setActive(index)}
              role="option"
            >
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-[15px] font-semibold text-slate-800">
                  {company.corpName}
                </span>
                <span className="truncate text-[12px] text-slate-400">
                  {company.industryName ?? '업종 정보 없음'}
                </span>
              </span>
              <span className="shrink-0 rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-500">
                {company.stockCode ?? '비상장'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
