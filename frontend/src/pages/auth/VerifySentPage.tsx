import { Link, useLocation } from 'react-router-dom';
import { AuthLayout } from '../../components/layout/AuthLayout';

interface VerifySentState {
  email?: string;
}

export function VerifySentPage() {
  const location = useLocation();
  const email = (location.state as VerifySentState | null)?.email;

  return (
    <AuthLayout
      character="hamster"
      headline="메일함을 확인해 주세요"
      lines={['인증 링크를 보냈어요', '스팸함도 한 번 봐 주세요', '링크를 누르면 바로 끝나요']}
      pose="mail"
    >
      <div className="text-center">
        <span className="mb-4 inline-flex size-14 items-center justify-center rounded-full bg-blue-50 text-2xl">
          ✉️
        </span>
        <h1 className="mb-3 text-2xl font-extrabold tracking-tight text-slate-950">
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
      </div>
    </AuthLayout>
  );
}
