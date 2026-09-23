import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CoverLetterWorkspace } from './CoverLetterWorkspace';
import type { CoverLetterInput } from './types';

vi.mock('./api', () => ({
  parseJobPosting: vi.fn(),
  parseJobPostingImages: vi.fn(),
  registerJobPosting: vi.fn(),
}));

vi.mock('./CompanyPicker', () => ({
  CompanyPicker: ({ value, onChange }: { value: string; onChange: (next: string) => void }) => (
    <input aria-label="지원 회사" value={value} onChange={(event) => onChange(event.target.value)} />
  ),
}));

// 공고의 회사는 DB 에서 찾아본 뒤에 받는다. 기본은 그대로 있는 회사로 둔다
vi.mock('./resolveCompany', () => ({
  resolveCompany: vi.fn(async (name: string) => ({ status: 'found', name })),
}));

const { parseJobPosting, parseJobPostingImages, registerJobPosting } = await import('./api');
const { resolveCompany } = await import('./resolveCompany');

const initial: CoverLetterInput = {
  title: '2026 상반기 백엔드',
  targetCompany: null,
  targetPosition: null,
  items: [{ question: '지원 동기는?', answer: '데이터 파이프라인을 만들고 싶습니다.', charLimit: 500 }],
};

/** 공고를 확인해 둔 상태를 만든다. 여기까지는 등록(분석)을 부르지 않는다. */
async function confirmPosting(user: ReturnType<typeof userEvent.setup>) {
  vi.mocked(parseJobPosting).mockResolvedValue({
    companyName: '삼성전자',
    positions: ['백엔드 개발'],
    sourceUrl: 'https://jobs.example.com/1',
    sourceKey: 'key-1',
  });
  await user.type(screen.getByLabelText('채용공고 URL (선택)'), 'https://jobs.example.com/1');
  await user.click(screen.getByRole('button', { name: '공고 불러오기' }));
  await screen.findByDisplayValue('삼성전자');
}

/** 한 화면에 한 가지만 둔다. AI 검토는 문항을 쓰는 화면에 있다. */
async function goToItems(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: '자기소개서 작성' }));
}

describe('CoverLetterWorkspace', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('저장은 공고 분석 식별자를 받은 뒤 자소서를 넘긴다', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);
    vi.mocked(registerJobPosting).mockResolvedValue({
      jobContextId: 'ctx-9', companyName: '삼성전자', positionName: '백엔드 개발',
      sourceUrl: 'https://jobs.example.com/1',
    });

    render(
      <CoverLetterWorkspace initial={initial} isLoggedIn onSave={onSave} onReview={vi.fn()} />,
    );
    await confirmPosting(user);
    await user.click(screen.getByRole('button', { name: '저장' }));

    expect(registerJobPosting).toHaveBeenCalledTimes(1);
    expect(onSave.mock.calls[0][0].jobContextId).toBe('ctx-9');
  });

  it('공고가 없으면 넘길 것도 없다', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);

    render(
      <CoverLetterWorkspace initial={initial} isLoggedIn onSave={onSave} onReview={vi.fn()} />,
    );
    await user.click(screen.getByRole('button', { name: '저장' }));

    expect(onSave.mock.calls[0][0].jobContextId).toBeNull();
  });

  it('저장하면 그 자리에 저장했다고 알린다', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);

    render(
      <CoverLetterWorkspace initial={initial} isLoggedIn onSave={onSave} onReview={vi.fn()} />,
    );
    expect(screen.queryByText('저장했습니다 ✓')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '저장' }));

    expect(await screen.findByText('저장했습니다 ✓')).toBeInTheDocument();
  });

  it('다시 고치기 시작하면 저장했다는 말을 내린다', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);

    render(
      <CoverLetterWorkspace initial={initial} isLoggedIn onSave={onSave} onReview={vi.fn()} />,
    );
    await user.click(screen.getByRole('button', { name: '저장' }));
    await screen.findByText('저장했습니다 ✓');

    await user.type(screen.getByLabelText('지원 직무 (선택)'), '!');

    expect(screen.queryByText('저장했습니다 ✓')).not.toBeInTheDocument();
  });

  it('공고를 분석하는 동안 AI 검토로 넘어가지 않는다', async () => {
    const user = userEvent.setup();
    let release = (_value: { jobContextId: string; companyName: string; positionName: string; sourceUrl: string }) => {};
    vi.mocked(registerJobPosting).mockReturnValue(new Promise((resolve) => (release = resolve)));
    const onSave = vi.fn().mockResolvedValue(undefined);

    render(
      <CoverLetterWorkspace initial={initial} isLoggedIn onSave={onSave} onReview={vi.fn()} />,
    );
    await confirmPosting(user);
    await user.click(screen.getByRole('button', { name: '저장' }));
    await goToItems(user);

    expect(screen.getByRole('button', { name: '공고 분석 중…' })).toBeDisabled();
    expect(onSave).not.toHaveBeenCalled();
    release({ jobContextId: 'ctx-9', companyName: '삼성전자', positionName: '백엔드 개발', sourceUrl: 'https://jobs.example.com/1' });
    await screen.findByText('저장했습니다 ✓');
    expect(onSave.mock.calls[0][0].jobContextId).toBe('ctx-9');
  });

  it('게스트는 공고 등록을 시도하지 않고 로그인 화면에 넘길 주소를 보존한다', async () => {
    const user = userEvent.setup();
    const onReview = vi.fn().mockResolvedValue(undefined);
    render(<CoverLetterWorkspace initial={initial} isLoggedIn={false} onSave={vi.fn()} onReview={onReview} />);
    await confirmPosting(user);
    await goToItems(user);
    await user.click(screen.getByRole('button', { name: 'AI 검토' }));
    expect(registerJobPosting).not.toHaveBeenCalled();
    expect(onReview.mock.calls[0][1]).toEqual({ url: 'https://jobs.example.com/1', sourceKey: 'key-1' });
  });

  it('공고 분석이 실패하면 이유를 보여 주고 검토 방으로 이동하지 않는다', async () => {
    const user = userEvent.setup();
    const onReview = vi.fn();
    vi.mocked(registerJobPosting).mockRejectedValue(new Error('AI unavailable'));
    render(<CoverLetterWorkspace initial={initial} isLoggedIn onSave={vi.fn()} onReview={onReview} />);
    await confirmPosting(user);
    await goToItems(user);
    await user.click(screen.getByRole('button', { name: 'AI 검토' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('채용공고 분석에 실패했습니다');
    expect(onReview).not.toHaveBeenCalled();
  });

  it('AI 검토는 공고를 등록해 식별자를 붙인 뒤 넘어간다', async () => {
    const user = userEvent.setup();
    const onReview = vi.fn().mockResolvedValue(undefined);
    vi.mocked(registerJobPosting).mockResolvedValue({
      jobContextId: 'ctx-9',
      companyName: '삼성전자',
      positionName: '백엔드 개발',
      sourceUrl: 'https://jobs.example.com/1',
    });

    render(
      <CoverLetterWorkspace initial={initial} isLoggedIn onSave={vi.fn()} onReview={onReview} />,
    );
    await confirmPosting(user);
    await goToItems(user);
    await user.click(screen.getByRole('button', { name: 'AI 검토' }));

    expect(registerJobPosting).toHaveBeenCalledWith(
      'https://jobs.example.com/1',
      '삼성전자',
      '백엔드 개발',
      'key-1',
    );
    expect(onReview.mock.calls[0][0].jobContextId).toBe('ctx-9');
  });

  it('공고 이미지를 붙여넣어 회사·직무를 채운다', async () => {
    const user = userEvent.setup();
    vi.mocked(parseJobPostingImages).mockResolvedValue({
      companyName: '뷰웍스',
      positions: ['영상처리 개발'],
      sourceUrl: '',
      sourceKey: 'img-key',
    });
    render(
      <CoverLetterWorkspace
        initial={initial}
        isLoggedIn
        onSave={vi.fn()}
        onReview={vi.fn()}
      />,
    );

    const file = new File(['fake'], 'posting.png', { type: 'image/png' });
    await user.upload(screen.getByLabelText('공고 이미지 선택'), file);
    // 주소 칸 옆 단추는 주소 전용이다. 이미지만 넣었으면 눌리지 않는다
    expect(screen.getByRole('button', { name: '공고 불러오기' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: '이미지 1장 확인하기' }));

    expect(vi.mocked(parseJobPostingImages).mock.calls[0][0]).toHaveLength(1);
    expect(screen.getByLabelText('지원 회사')).toHaveValue('뷰웍스');
  });

  it('이미지를 읽는 동안 단추 자리에 넣은 장수로 진행을 알린다', async () => {
    const user = userEvent.setup();
    vi.mocked(parseJobPostingImages).mockReturnValue(new Promise(() => {}));
    render(<CoverLetterWorkspace initial={initial} isLoggedIn onSave={vi.fn()} onReview={vi.fn()} />);

    await user.upload(screen.getByLabelText('공고 이미지 선택'), [
      new File(['a'], '삼성전자_공고.png', { type: 'image/png' }),
      new File(['b'], 'image.png', { type: 'image/png' }),
      new File(['c'], '상세요강.jpg', { type: 'image/jpeg' }),
    ]);
    // 넣은 파일의 이름 그대로 보인다
    expect(screen.getByText('삼성전자_공고.png')).toBeInTheDocument();
    expect(screen.getByText('image.png')).toBeInTheDocument();
    expect(screen.getByText('상세요강.jpg')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '이미지 3장 확인하기' }));

    expect(await screen.findByText(/이미지 3장을 확인했어요\. 공고 정보를 읽고 있어요/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '이미지 3장 확인하기' })).not.toBeInTheDocument();
    expect(screen.queryByText(/조각/)).not.toBeInTheDocument();
  });

  it('붙여넣은 이미지를 개별로 뺄 수 있다', async () => {
    const user = userEvent.setup();
    render(
      <CoverLetterWorkspace
        initial={initial}
        isLoggedIn
        onSave={vi.fn()}
        onReview={vi.fn()}
      />,
    );

    await user.upload(
      screen.getByLabelText('공고 이미지 선택'),
      [
        new File(['a'], 'one.png', { type: 'image/png' }),
        new File(['b'], 'two.png', { type: 'image/png' }),
      ],
    );
    expect(screen.getByLabelText('2번 이미지 빼기')).toBeInTheDocument();

    await user.click(screen.getByLabelText('1번 이미지 빼기'));
    expect(screen.queryByLabelText('2번 이미지 빼기')).not.toBeInTheDocument();
    expect(screen.getByLabelText('1번 이미지 빼기')).toBeInTheDocument();
  });

  it('줄여도 너무 큰 이미지는 보내지 않고 안내한다', async () => {
    const user = userEvent.setup();
    render(
      <CoverLetterWorkspace initial={initial} isLoggedIn onSave={vi.fn()} onReview={vi.fn()} />,
    );

    // 전체 페이지 캡처 PNG 는 십수 MB 가 흔하다. 그대로 보내면 프록시가 413 으로 끊는다.
    const huge = new File(['x'], 'long-posting.png', { type: 'image/png' });
    Object.defineProperty(huge, 'size', { value: 9 * 1024 * 1024 });
    await user.upload(screen.getByLabelText('공고 이미지 선택'), huge);
    await user.click(screen.getByRole('button', { name: '이미지 1장 확인하기' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('나눠 캡처');
    expect(vi.mocked(parseJobPostingImages)).not.toHaveBeenCalled();
  });

  describe('저장 전에 잘못된 칸을 짚는다', () => {
    it('빈 답변은 보내지 않고 까닭을 말한다', async () => {
      // 예전에는 그대로 보내고 400 을 받았는데, 받는 자리에 catch 가 없어 아무 말도 안 떴다
      const user = userEvent.setup();
      const onSave = vi.fn().mockResolvedValue(undefined);

      render(<CoverLetterWorkspace initial={initial} isLoggedIn onSave={onSave} onReview={vi.fn()} />);
      await goToItems(user);
      await user.clear(screen.getByLabelText('답변'));
      await user.click(screen.getByRole('button', { name: '저장' }));

      expect(await screen.findByRole('alert')).toHaveTextContent('답변을 입력해 주세요');
      expect(onSave).not.toHaveBeenCalled();
    });

    it('제한을 줄이면 이미 써 둔 답변도 다시 본다', async () => {
      // 입력칸의 maxLength 는 새로 치는 글자만 막는다. 줄이기 전에 쓴 글은 그대로 남는다
      const user = userEvent.setup();
      const onSave = vi.fn().mockResolvedValue(undefined);

      render(<CoverLetterWorkspace initial={initial} isLoggedIn onSave={onSave} onReview={vi.fn()} />);
      await goToItems(user);
      await user.clear(screen.getByLabelText('글자 수 제한'));
      await user.type(screen.getByLabelText('글자 수 제한'), '5');
      await user.click(screen.getByRole('button', { name: '저장' }));

      expect(await screen.findByRole('alert')).toHaveTextContent('넘어요');
      expect(onSave).not.toHaveBeenCalled();
    });

    it('로그인 전에는 쓰다 만 것도 그대로 들고 간다', async () => {
      /*
       * 로그인하지 않았을 때의 '저장' 은 저장이 아니라 초안을 들고 로그인하러 가는 길이다.
       * 여기서 빈 칸을 막으면 쓰다 말고 로그인하려는 사람이 로그인을 못 하게 된다.
       */
      const user = userEvent.setup();
      const onSave = vi.fn().mockResolvedValue(undefined);

      render(
        <CoverLetterWorkspace initial={initial} isLoggedIn={false} onSave={onSave} onReview={vi.fn()} />,
      );
      await goToItems(user);
      await user.clear(screen.getByLabelText('답변'));
      await user.click(screen.getByRole('button', { name: '로그인하고 저장' }));

      expect(onSave).toHaveBeenCalledTimes(1);
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('저장이 실패하면 사람이 읽을 말로 알린다', async () => {
      const user = userEvent.setup();
      const onSave = vi.fn().mockRejectedValue(new Error('boom'));

      render(<CoverLetterWorkspace initial={initial} isLoggedIn onSave={onSave} onReview={vi.fn()} />);
      await user.click(screen.getByRole('button', { name: '저장' }));

      expect(await screen.findByRole('alert')).toHaveTextContent('저장하지 못했어요');
    });
  });

  it('글자 수 제한 칸은 친 글자를 숫자 하나로 정리한다', async () => {
    // "00…050" 을 넣으면 제한은 50 인데 칸에는 친 글자가 그대로 남아 있었다
    const user = userEvent.setup();

    render(<CoverLetterWorkspace initial={initial} isLoggedIn onSave={vi.fn()} onReview={vi.fn()} />);
    await goToItems(user);
    const limit = screen.getByLabelText('글자 수 제한');
    await user.clear(limit);
    await user.type(limit, '0000000000000000000000050');

    expect(limit).toHaveValue('50');
  });

  it('링크가 없을 때의 칸은 한 번에 하나만 펴고, 다시 누르면 접는다', async () => {
    const user = userEvent.setup();
    render(<CoverLetterWorkspace initial={initial} isLoggedIn onSave={vi.fn()} onReview={vi.fn()} />);
    const image = screen.getByRole('button', { name: '이미지 업로드' });
    const manual = screen.getByRole('button', { name: '직접 입력' });

    await user.click(image);
    expect(image).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText(/로 붙여넣으세요/)).toBeInTheDocument();

    // 다른 칸을 펴면 앞의 칸은 접힌다
    await user.click(manual);
    expect(image).toHaveAttribute('aria-pressed', 'false');
    expect(manual).toHaveAttribute('aria-pressed', 'true');
    expect(screen.queryByText(/로 붙여넣으세요/)).not.toBeInTheDocument();

    // 같은 단추를 다시 누르면 접는다
    await user.click(manual);
    expect(manual).toHaveAttribute('aria-pressed', 'false');
  });

  it('제목이 없으면 문항으로 넘어가기 전에 제목 창을 띄운다', async () => {
    const user = userEvent.setup();
    render(
      <CoverLetterWorkspace
        initial={{ ...initial, title: '' }}
        isLoggedIn
        onSave={vi.fn()}
        onReview={vi.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: '문항 쓰러가기 →' }));
    const dialog = screen.getByRole('dialog', { name: '자기소개서 제목을 정해주세요.' });
    const start = screen.getByRole('button', { name: '작성 시작하기 →' });
    expect(start).toBeDisabled();

    // Esc 는 취소다 — 창에서 친 것은 반영하지 않는다
    await user.type(screen.getByLabelText('제목'), '임시');
    await user.keyboard('{Escape}');
    expect(dialog).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '문항 쓰러가기 →' }));
    expect(screen.getByLabelText('제목')).toHaveValue('');
    await user.type(screen.getByLabelText('제목'), '삼성 백엔드');
    await user.keyboard('{Enter}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '이제 문항을 채워볼까요?' })).toBeInTheDocument();
  });

  it('쓰는 중에 제목만 고치고 그 자리에 머문다', async () => {
    const user = userEvent.setup();
    render(<CoverLetterWorkspace initial={initial} isLoggedIn onSave={vi.fn()} onReview={vi.fn()} />);
    await goToItems(user);
    await user.type(screen.getByLabelText('답변'), ' 추가');

    await user.click(screen.getByRole('button', { name: '제목 수정' }));
    expect(screen.getByRole('dialog', { name: '자기소개서 제목을 수정해주세요.' })).toBeInTheDocument();
    const field = screen.getByLabelText('제목');
    expect(field).toHaveValue('2026 상반기 백엔드');

    // 취소하면 그대로다
    await user.clear(field);
    await user.type(field, '버릴 제목');
    await user.click(screen.getByRole('button', { name: '취소' }));
    expect(screen.getByText('2026 상반기 백엔드')).toBeInTheDocument();

    // 비우면 수정할 수 없다
    await user.click(screen.getByRole('button', { name: '제목 수정' }));
    await user.clear(screen.getByLabelText('제목'));
    expect(screen.getByRole('button', { name: '수정하기' })).toBeDisabled();

    await user.type(screen.getByLabelText('제목'), '하반기 백엔드');
    await user.click(screen.getByRole('button', { name: '수정하기' }));
    expect(screen.getByText('하반기 백엔드')).toBeInTheDocument();
    // 기업·직무 단계로 돌아가지 않고, 쓰던 답변도 그대로다
    expect(screen.getByRole('heading', { name: '이제 문항을 채워볼까요?' })).toBeInTheDocument();
    expect(screen.getByLabelText('답변')).toHaveValue('데이터 파이프라인을 만들고 싶습니다. 추가');
  });

  it('이미지는 8장·합계 50MB 까지만 받고, 넘치면 왜 빠졌는지 알린다', async () => {
    const user = userEvent.setup();
    render(<CoverLetterWorkspace initial={initial} isLoggedIn onSave={vi.fn()} onReview={vi.fn()} />);
    const picker = screen.getByLabelText('공고 이미지 선택');

    const nine = Array.from({ length: 9 }, (_, i) => new File(['x'], `p${i}.png`, { type: 'image/png' }));
    await user.upload(picker, nine);
    expect(screen.getByLabelText('8번 이미지 빼기')).toBeInTheDocument();
    expect(screen.queryByLabelText('9번 이미지 빼기')).not.toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('최대 8장');

    // 한 장을 빼면 안내를 내린다. 남은 일곱 장 위로 51MB 짜리는 받지 않는다
    await user.click(screen.getByLabelText('8번 이미지 빼기'));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    const big = new File(['x'], 'big.png', { type: 'image/png' });
    Object.defineProperty(big, 'size', { value: 51 * 1024 * 1024 });
    await user.upload(picker, big);
    expect(screen.queryByLabelText('8번 이미지 빼기')).not.toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('최대 50MB');
  });

  it('DB 에 없는 회사의 공고는 받지 않고 안내 창을 띄운다', async () => {
    const user = userEvent.setup();
    vi.mocked(parseJobPosting).mockResolvedValue({
      companyName: '에스케이쉴더스(주)',
      positions: ['보안관제', '앱기획'],
      sourceUrl: 'https://jobs.example.com/9',
      sourceKey: 'key-9',
    });
    vi.mocked(resolveCompany).mockResolvedValueOnce({ status: 'missing' });
    render(<CoverLetterWorkspace initial={initial} isLoggedIn onSave={vi.fn()} onReview={vi.fn()} />);

    await user.type(screen.getByLabelText('채용공고 URL (선택)'), 'https://jobs.example.com/9');
    await user.click(screen.getByRole('button', { name: '공고 불러오기' }));

    const notice = await screen.findByRole('alertdialog', { name: '아직 등록되지 않은 기업이에요' });
    expect(notice).toHaveTextContent('에스케이쉴더스(주)');
    // 회사도 직무도 채우지 않는다
    expect(screen.getByLabelText('지원 회사')).toHaveValue('');
    expect(screen.queryByText(/직무 2개를 찾았어요/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '확인' }));
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('공고를 읽는 동안에는 문항으로 넘어가지 못한다', async () => {
    const user = userEvent.setup();
    let finish = (_value: Awaited<ReturnType<typeof parseJobPosting>>) => {};
    vi.mocked(parseJobPosting).mockReturnValue(new Promise((resolve) => (finish = resolve)));
    render(<CoverLetterWorkspace initial={initial} isLoggedIn onSave={vi.fn()} onReview={vi.fn()} />);

    await user.type(screen.getByLabelText('채용공고 URL (선택)'), 'https://jobs.example.com/1');
    await user.click(screen.getByRole('button', { name: '공고 불러오기' }));
    expect(screen.getByRole('button', { name: '문항 쓰러가기 →' })).toBeDisabled();

    finish({ companyName: '삼성전자', positions: ['백엔드 개발'], sourceUrl: 'https://jobs.example.com/1', sourceKey: 'k' });
    await screen.findByDisplayValue('삼성전자');
    await waitFor(() => expect(screen.getByRole('button', { name: '문항 쓰러가기 →' })).toBeEnabled());
  });

  it('공고에서 찾은 직무는 둥근 목록에서 고른다', async () => {
    const user = userEvent.setup();
    vi.mocked(parseJobPosting).mockResolvedValue({
      companyName: '삼성전자',
      positions: ['보안관제', 'IT컨설팅'],
      sourceUrl: 'https://jobs.example.com/1',
      sourceKey: 'key-1',
    });
    render(<CoverLetterWorkspace initial={initial} isLoggedIn onSave={vi.fn()} onReview={vi.fn()} />);
    await user.type(screen.getByLabelText('채용공고 URL (선택)'), 'https://jobs.example.com/1');
    await user.click(screen.getByRole('button', { name: '공고 불러오기' }));

    await user.click(await screen.findByRole('button', { name: /지원 직무/ }));
    await user.click(screen.getByRole('option', { name: 'IT컨설팅' }));
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /지원 직무/ })).toHaveTextContent('IT컨설팅');

    // 목록 끝의 '직접 입력' 을 고르면 글자 칸으로 바뀐다
    await user.click(screen.getByRole('button', { name: /지원 직무/ }));
    await user.click(screen.getByRole('option', { name: '+ 직접 입력' }));
    expect(screen.getByRole('textbox', { name: /지원 직무/ })).toHaveValue('');
  });
});
