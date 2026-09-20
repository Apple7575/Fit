import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CoverLetterWorkspace } from './CoverLetterWorkspace';
import type { CoverLetterInput } from './types';

vi.mock('./api', () => ({
  parseJobPosting: vi.fn(),
  registerJobPosting: vi.fn(),
}));

vi.mock('./CompanyPicker', () => ({
  CompanyPicker: ({ value, onChange }: { value: string; onChange: (next: string) => void }) => (
    <input aria-label="지원 회사" value={value} onChange={(event) => onChange(event.target.value)} />
  ),
}));

const { parseJobPosting, registerJobPosting } = await import('./api');

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

describe('CoverLetterWorkspace', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('저장은 공고를 분석하지 않고 자소서만 넘긴다', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);

    render(
      <CoverLetterWorkspace initial={initial} isLoggedIn onSave={onSave} onReview={vi.fn()} />,
    );
    await confirmPosting(user);
    await user.click(screen.getByRole('button', { name: '저장' }));

    expect(registerJobPosting).not.toHaveBeenCalled();
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it('등록하지 않은 공고는 저장을 받는 쪽에 함께 넘겨 뒤에서 붙이게 한다', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);

    render(
      <CoverLetterWorkspace initial={initial} isLoggedIn onSave={onSave} onReview={vi.fn()} />,
    );
    await confirmPosting(user);
    await user.click(screen.getByRole('button', { name: '저장' }));

    expect(onSave.mock.calls[0][1]).toEqual({
      url: 'https://jobs.example.com/1',
      sourceKey: 'key-1',
    });
  });

  it('공고가 없으면 넘길 것도 없다', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);

    render(
      <CoverLetterWorkspace initial={initial} isLoggedIn onSave={onSave} onReview={vi.fn()} />,
    );
    await user.click(screen.getByRole('button', { name: '저장' }));

    expect(onSave.mock.calls[0][1]).toBeNull();
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

  it('저장하는 동안 AI 검토 버튼이 공고 분석 중으로 바뀌지 않는다', async () => {
    const user = userEvent.setup();
    let release = () => {};
    const onSave = vi.fn().mockReturnValue(new Promise<void>((resolve) => (release = resolve)));

    render(
      <CoverLetterWorkspace initial={initial} isLoggedIn onSave={onSave} onReview={vi.fn()} />,
    );
    await confirmPosting(user);
    await user.click(screen.getByRole('button', { name: '저장' }));

    expect(screen.getByRole('button', { name: 'AI 검토' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '공고 분석 중…' })).not.toBeInTheDocument();
    release();
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
    await user.click(screen.getByRole('button', { name: 'AI 검토' }));

    expect(registerJobPosting).toHaveBeenCalledWith(
      'https://jobs.example.com/1',
      '삼성전자',
      '백엔드 개발',
      'key-1',
    );
    expect(onReview.mock.calls[0][0].jobContextId).toBe('ctx-9');
  });
});
