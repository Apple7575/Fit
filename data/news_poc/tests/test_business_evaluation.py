"""사업 목록·관련성 차단·점수 합계·근거 누락을 검증한다."""
import sys
import unittest
from pathlib import Path
from data.news_poc.pipeline.business_analysis import validate_analysis, normalize_analysis


class BusinessTests(unittest.TestCase):
    def test_contract_repair_preserves_judgment_and_existing_reason(self):
        row=self.row()|dict(business_status='multiple',related_business='memory, foundry')
        fixed=normalize_analysis(row,repair_contract=True)
        self.assertIsNone(fixed['related_business'])
        self.assertEqual(fixed['impact'],3)
        self.assertEqual(row['related_business'],'memory, foundry')
        row=self.row()|dict(business_status='insufficient',related_business=None,business_reason='사업 정보 부족')
        fixed=normalize_analysis(row,repair_contract=True)
        self.assertEqual(fixed['abstention_reason'],'사업 정보 부족')
        row['business_reason']=''
        with self.assertRaises(ValueError):
            validate_analysis(normalize_analysis(row,repair_contract=True),'related',['memory'])

    def test_career_scores_use_new_axes_and_reject_legacy_axes(self):
        fields=('company_understanding','job_connection','application_use')
        row=self.row()
        for old,new in zip(('impact','duration','certainty'),fields):
            row[new]=row.pop(old);row[new+'_reason']=row.pop(old+'_reason')
        validate_analysis(row,'related',['memory'],score_fields=fields)
        self.assertEqual(normalize_analysis(row,score_fields=fields)['importance_score'],8)
        with self.assertRaises(ValueError):
            validate_analysis(self.row(),'related',['memory'],score_fields=fields)

    def test_normalization_only_repairs_representation_and_arithmetic(self):
        row=self.row()|dict(related_business=['memory'],importance_score=None)
        fixed=normalize_analysis(row)
        self.assertEqual(fixed['related_business'],'memory')
        self.assertEqual(fixed['importance_score'],8)
        self.assertIsNone(row['importance_score'])
        self.assertEqual(fixed['raw_importance_score'],None)
        validate_analysis(fixed,'related',['memory'])

    def row(self):
        return dict(predicted='related',business_status='specific',related_business='memory',
                    impact=3,duration=2,certainty=3,importance_score=8,
                    business_reason='메모리 증설',impact_reason='증설',duration_reason='장기 계약',certainty_reason='완료',abstention_reason=None)

    def test_valid_score_and_null_abstention(self):
        validate_analysis(self.row(),'related',['memory'])
        row=self.row();row.update(duration=None,importance_score=None,abstention_reason='기간 정보 없음')
        validate_analysis(row,'related',['memory'])

    def test_invalid_sum_unknown_business_and_boolean_rejected(self):
        for change in [dict(importance_score=9),dict(related_business='invented'),dict(impact=True),dict(duration=None),dict(business_status='multiple')]:
            with self.assertRaises(ValueError):validate_analysis(self.row()|change,'related',['memory'])

    def test_unrelated_cannot_receive_scores_or_be_reclassified(self):
        with self.assertRaises(ValueError):validate_analysis(self.row(),'unrelated',['memory'])
