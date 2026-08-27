import { useParams } from 'react-router-dom';

export function CompanyDetailPage() {
  const { companyId } = useParams();

  return (
    <main className="page-shell">
      <h1>기업 상세</h1>
      <p>기업 코드: {companyId}</p>
    </main>
  );
}
