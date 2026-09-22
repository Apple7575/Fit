/**
 * 아직 자료가 없는 카드.
 *
 * <p>없을 때 카드를 통째로 지우면 화면이 고장 난 것처럼 비어 보인다. 자리를 지키고
 * 무엇이 없는지, 왜 없는지를 한 줄로 말해 준다. (실패는 여기가 아니라 InlineNotice 가 맡는다)
 */
export function EmptyCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-[var(--radius-card)] border border-dashed border-slate-200 bg-white/60 p-5">
      <h2 className="text-[15px] font-extrabold text-slate-400">{title}</h2>
      <p className="mt-1.5 text-[13px] leading-6 break-keep text-slate-400">{children}</p>
    </section>
  );
}
