import { render, screen } from '@testing-library/react';
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

const { parseJobPosting, parseJobPostingImages, registerJobPosting } = await import('./api');

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
  await user.click(screen.getByRole('button', { name: '확인' }));
  await screen.findByDisplayValue('삼성전자');
}

/** 한 화면에 한 가지만 둔다. AI 검토는 문항을 쓰는 화면에 있다. */
async function goToItems(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: '문항 1' }));
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

    await user.type(screen.getByDisplayValue('2026 상반기 백엔드'), '!');

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
    expect(screen.getByRole('button', { name: '확인' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: '이미지 1장으로 확인' }));

    expect(vi.mocked(parseJobPostingImages).mock.calls[0][0]).toHaveLength(1);
    expect(screen.getByLabelText('지원 회사')).toHaveValue('뷰웍스');
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
    await user.click(screen.getByRole('button', { name: '이미지 1장으로 확인' }));

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
});
