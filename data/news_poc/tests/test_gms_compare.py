"""외부 모델 응답 누락·중복과 혼합 방식의 전달 조건을 검증한다."""
import sys
import unittest
import json
import tempfile
from unittest.mock import patch
from pathlib import Path
from data.news_poc.experiments.gms_compare import validate_results, main


class GmsTests(unittest.TestCase):
    def test_predict_only_does_not_manufacture_accuracy(self):
        """사람 정답이 없는 입력도 예측하되 정확도 지표는 만들지 않는다."""
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'data.json';out=root/'out'
            source.write_text(json.dumps([dict(sample_id='a',company='A',title='title',human_verified=False,expected_relevance=None)]))
            response=dict(status='success',results=[dict(sample_id='a',predicted='related',reason='why')],seconds=1,estimated_credits=1)
            argv=['gms_compare','--input',str(source),'--out',str(out),'--model','gemini-2.5-flash-lite','--predict-only']
            with patch.object(sys,'argv',argv),patch('data.news_poc.experiments.gms_compare.load_key',return_value='fake'),patch('data.news_poc.experiments.gms_compare.request_batch',return_value=response):
                main()
            usage=json.loads((out/'gemini-2.5-flash-lite/run.json').read_text())
            self.assertNotIn('accuracy',usage)
            self.assertFalse((out/'gemini-2.5-flash-lite/metrics.json').exists())
            self.assertTrue((out/'gemini-2.5-flash-lite/predictions.json').exists())

    def test_selected_model_and_prompt_are_used_without_sending_gold(self):
        """V2 재평가가 다른 모델을 과금 호출하거나 검수 정답을 전송하지 않아야 한다."""
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/'data.json'; prompt=root/'prompt.txt'; out=root/'out'
            source.write_text(json.dumps([dict(sample_id='a',company='company',title='title',
                                               human_verified=True,expected_relevance='related',review_reason='secret')]),encoding='utf-8')
            prompt.write_text('new policy',encoding='utf-8')
            response=dict(status='success',results=[dict(sample_id='a',predicted='related',reason='why')],
                          seconds=1,estimated_credits=1)
            argv=['gms_compare','--input',str(source),'--out',str(out),'--model','gemini-2.5-flash-lite','--prompt-file',str(prompt)]
            with patch.object(sys,'argv',argv), patch('data.news_poc.experiments.gms_compare.load_key',return_value='fake'), patch('data.news_poc.experiments.gms_compare.request_batch',return_value=response) as request:
                main()
            self.assertEqual(request.call_count,1)
            self.assertEqual(request.call_args.args[0],'gemini-2.5-flash-lite')
            self.assertEqual(request.call_args.kwargs['prompt'],'new policy')
            self.assertNotIn('expected_relevance',request.call_args.args[1][0])
            self.assertNotIn('review_reason',request.call_args.args[1][0])
            self.assertFalse((out/'gpt-4.1-mini').exists())
            # 같은 결과 폴더에 새 프롬프트를 넣으면 예전 응답을 재사용하거나 덮어쓰지 않는다.
            prompt.write_text('different policy',encoding='utf-8')
            with patch.object(sys,'argv',argv), patch('data.news_poc.experiments.gms_compare.load_key',return_value='fake'), patch('data.news_poc.experiments.gms_compare.request_batch') as request:
                with self.assertRaises(ValueError):
                    main()
                request.assert_not_called()

    def test_missing_duplicate_and_invalid_labels_rejected(self):
        for results in [[], [{'sample_id':'a','predicted':'related'}]*2,
                        [{'sample_id':'a','predicted':'yes'}]]:
            with self.assertRaises(ValueError):
                validate_results({'results':results}, ['a'])

    def test_results_aligned_by_id(self):
        rows=[{'sample_id':i,'predicted':'related','reason':'근거'} for i in ['b','a']]
        self.assertEqual([r['sample_id'] for r in validate_results({'results':rows},['a','b'])],['a','b'])
