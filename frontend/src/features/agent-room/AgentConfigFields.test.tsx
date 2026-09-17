import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AgentConfigFields } from './AgentConfigFields';
import type { ConfigField } from './types';

const renderFields = (schema: Record<string, ConfigField>, draft = {}) => {
  const onChange = vi.fn();
  render(<AgentConfigFields schema={schema} draft={draft} onChange={onChange} />);
  return onChange;
};

describe('AgentConfigFields', () => {
  it('설정할 것이 없으면 그렇게 알려준다', () => {
    renderFields({});

    expect(screen.getByText('설정할 것이 없는 에이전트입니다.')).toBeInTheDocument();
  });

  it('corpCodes 항목에는 기업 검색칸이 뜬다', () => {
    renderFields({
      corpCodes: { type: 'array', required: true, description: '분석 대상 기업' },
    });

    expect(screen.getByLabelText('기업명으로 검색')).toBeInTheDocument();
  });

  it('직무는 자소서에서 넘어온 값이 채워진 입력칸으로 뜬다', () => {
    renderFields(
      { jobRole: { type: 'string', required: true, description: '지원 직무' } },
      { jobRole: '서버 개발(Java/Spring)' },
    );

    expect(screen.getByLabelText('지원 직무')).toHaveValue('서버 개발(Java/Spring)');
  });

  it('직무는 고정 목록이 아니라 고쳐 쓸 수 있다', async () => {
    const onChange = renderFields({
      jobRole: { type: 'string', required: true, description: '지원 직무' },
    });

    await userEvent.type(screen.getByLabelText('지원 직무'), 'QA');

    expect(onChange).toHaveBeenCalled();
  });

  it('스키마에 없던 항목도 type 만 보고 입력칸을 그린다', () => {
    renderFields({
      새항목: { type: 'string', required: true, description: '새로 생긴 설정' },
    });

    expect(screen.getByLabelText('새로 생긴 설정')).toBeInTheDocument();
  });

  it('선택 항목은 (선택) 이라고 표시한다', () => {
    renderFields({ limit: { type: 'number', required: false, description: '몇 건까지' } });

    expect(screen.getByText('(선택)')).toBeInTheDocument();
  });
});
