import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AgentConfigFields } from './AgentConfigFields';
import type { ConfigField, JobRoleOption } from './types';

const jobRoles: JobRoleOption[] = [
  { key: 'backend', name: '백엔드', ready: true, topics: ['동시성', '분산 락'] },
  { key: 'data', name: '데이터', ready: false, topics: [] },
];

const renderFields = (schema: Record<string, ConfigField>, draft = {}) => {
  const onChange = vi.fn();
  render(
    <AgentConfigFields schema={schema} draft={draft} onChange={onChange} jobRoles={jobRoles} />,
  );
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

  it('열어 두지 않은 직무는 고를 수 없다', () => {
    renderFields({ jobRole: { type: 'enum', required: true, description: '지원 직무' } });

    expect(screen.getByRole('button', { name: /백엔드/ })).toBeEnabled();
    expect(screen.getByRole('button', { name: /데이터/ })).toBeDisabled();
  });

  it('직무를 고르면 key 로 올려 준다', async () => {
    const onChange = renderFields({
      jobRole: { type: 'enum', required: true, description: '지원 직무' },
    });

    await userEvent.click(screen.getByRole('button', { name: /백엔드/ }));

    expect(onChange).toHaveBeenCalledWith({ jobRole: 'backend' });
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
