interface BusinessCardProps {
  items: string[];
}

/** 주요 사업. API 가 이름 문자열만 주므로 이름 카드 그리드로 표시한다. */
export function BusinessCard({ items }: BusinessCardProps) {
  return (
    <section
      aria-labelledby="business-card-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <h2
        className="text-xl font-extrabold text-slate-950"
        id="business-card-title"
      >
        주요 사업
      </h2>
      <ul className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {items.map((name) => (
          <li
            className="flex min-h-20 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 px-3 py-4 text-center text-sm font-bold text-slate-900"
            key={name}
          >
            {name}
          </li>
        ))}
      </ul>
    </section>
  );
}
