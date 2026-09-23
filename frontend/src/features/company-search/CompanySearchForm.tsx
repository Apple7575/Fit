import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { displayName } from '../company-summary/companyName';
import { MAX_KEYWORD } from './api';
import { searchWithFallback } from './searchWithFallback';
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
 * 목록이 차지할 최대 높이.
 *
 * <p>예전에는 다섯 줄만 보여 주고 나머지는 "검색" 을 눌러 페이지 아래 목록에서 보게 했다.
 * 그런데 찾는 사람은 칸에 치고 있는데 결과는 화면 아래 딴 곳에 생기니, 검색이 됐는지조차
 * 알기 어려웠다. 결과는 친 자리 바로 아래에서 다 본다 — 넘치면 이 안에서 굴린다.
 *
 * <p>창 높이에 맞춰 잡는다. 고정값이면 낮은 노트북에서 목록이 화면 밖으로 흘러내린다.
 */
const LIST_MAX_HEIGHT = 'max-h-[min(60svh,26rem)]';

export function CompanySearchForm({ onSearch, onPick }: CompanySearchFormProps) {
  const [keyword, setKeyword] = useState('');
  const [suggestions, setSuggestions] = useState<Company[]>([]);
  const [open, setOpen] = useState(false);
  /** 키보드로 짚고 있는 줄. -1 이면 아무것도 안 짚은 상태다 */
  const [active, setActive] = useState(-1);
  /**
   * 방금 찾아본 말. 지금 친 말과 같을 때만 결과가 이 말의 것이다.
   *
   * <p>"찾아봤는지" 를 따로 켜고 끄지 않는다. 글자가 바뀔 때마다 끄려면 효과 안에서 상태를
   * 건드려야 하고, 그러면 한 번 더 그린다. 두 말을 견주면 그릴 때 알 수 있다.
   */
  const [searchedFor, setSearchedFor] = useState('');
  const listId = useId();
  const inFlight = useRef<AbortController | null>(null);

  const trimmedKeyword = keyword.trim();
  const canSearch = trimmedKeyword.length > 0;
  /*
   * 칸을 비우면 지난 결과는 곧바로 없는 것으로 친다. 상태를 비우지 않고 여기서 거르는
   * 것은, 칸이 비었다는 사실만으로 다시 그릴 일을 만들지 않기 위해서다.
   */
  const visible = trimmedKeyword === '' ? [] : suggestions;
  /*
   * 찾은 것이 없어도 목록은 연다. 예전에는 조용히 접혀서, 친 이름이 없는 것인지 아직
   * 찾는 중인지 알 수 없었다. 다만 이 말로 실제 찾아본 뒤에만 연다.
   */
  const searched = searchedFor !== '' && searchedFor === trimmedKeyword;
  const showList = open && trimmedKeyword !== '' && (visible.length > 0 || searched);

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
        // 친 그대로 못 찾으면 말을 바꿔 가며 한 번 더 찾는다 (자판·영문 약어)
        const found = await searchWithFallback(trimmedKeyword, controller.signal);

        if (controller.signal.aborted) return;
        setSuggestions(found.items);
        setSearchedFor(trimmedKeyword);
        setActive(-1);
        setOpen(true);
      };

      run().catch(() => {
        // 실패했을 때는 빈손과 구분해 접어 둔다. 없는 것처럼 말하면 안 된다
        if (controller.signal.aborted) return;
        setSuggestions([]);
        setSearchedFor('');
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

  /*
   * 결과는 칸 바로 아래 목록에 이미 떠 있다. 그래서 "검색" 은 따로 결과를 만드는 것이
   * 아니라 가장 잘 맞는 곳으로 들어가는 단추다 — 짚어 둔 줄이 없으면 맨 윗줄로 간다.
   *
   * <p>찾은 것이 없으면 목록을 열어 둔 채로 둔다. 아무 일도 일어나지 않는 것처럼 보이지만
   * 그 자리에 "찾지 못했어요" 가 떠 있다.
   */
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSearch) return;

    if (visible.length > 0) {
      pick(visible[active >= 0 ? active : 0]);
      return;
    }

    setOpen(true);
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
        <div className="flex items-center gap-2 rounded-full border border-slate-300 bg-white p-2 shadow-sm transition sm:gap-3">
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
        /*
         * 둥근 모서리는 이 바깥 상자가 맡고, 굴리는 것은 안쪽 목록이 맡는다. 한 상자에
         * 둘 다 맡기면 스크롤 막대가 모서리 안쪽에 그려져 오른쪽 두 귀퉁이만 각이 진다.
         */
        <div className="absolute top-full right-0 left-0 z-30 mt-2 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl">
          <ul
            aria-label="기업 검색 결과"
            className={`overflow-y-auto overscroll-contain p-1.5 text-left ${LIST_MAX_HEIGHT}`}
            id={listId}
            role="listbox"
          >
          {visible.length === 0 && (
            <li className="px-3 py-6 text-center text-[13px] text-slate-500" role="presentation">
              찾은 기업이 없어요.
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
                {/* 공시명이 한글 음차라 아무도 그렇게 부르지 않는 곳이 있다("케이티" → KT) */}
                <span className="truncate text-[15px] font-semibold text-slate-800">
                  {displayName(company.corpName)}
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
        </div>
      )}
    </div>
  );
}
