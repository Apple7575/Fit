import { Link, useLocation } from 'react-router-dom';

export function VerifySentPage() {
  const location = useLocation();
  const email = (location.state as { email?: string } | null)?.email;

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 text-center">
      <h1 className="mb-4 text-2xl font-extrabold tracking-tight text-slate-950">
        인증 메일을 보냈습니다
      </h1>
      <p className="text-sm text-slate-600">
        {email ? `${email} 로 ` : '가입하신 이메일로 '}
        인증 링크를 보냈습니다. 메일의 링크를 눌러 인증을 완료해 주세요.
      </p>
      <p className="mt-6 text-sm text-slate-600">
        메일을 받지 못했다면{' '}
        <Link className="font-semibold text-blue-600 hover:text-blue-700" to="/signup">
          다시 가입
        </Link>
        해 주세요.
      </p>
    </main>
  );
}
