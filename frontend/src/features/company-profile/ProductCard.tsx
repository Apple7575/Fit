interface ProductCardProps {
  items: string[];
}

/** 주요 제품. 이름 배지 나열. */
export function ProductCard({ items }: ProductCardProps) {
  return (
    <section
      aria-labelledby="product-card-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <h2
        className="text-xl font-extrabold text-slate-950"
        id="product-card-title"
      >
        주요 제품
      </h2>
      <ul className="mt-5 flex flex-wrap gap-2.5">
        {items.map((name) => (
          <li
            className="rounded-full border border-blue-100 bg-blue-50 px-4 py-2 text-sm font-bold text-blue-700"
            key={name}
          >
            {name}
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs text-slate-400">
        * 주요 제품은 대표 제품 기준으로 선정되었습니다.
      </p>
    </section>
  );
}
