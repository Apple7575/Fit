"""관련성 모델 비교·예측 배치 실행기. 최대 400건 PoC용."""
import argparse
import hashlib
import json
import urllib.error
from pathlib import Path
from data.news_poc.pipeline.metrics import summarize_predictions
from data.news_poc.pipeline.gms_client import (PROMPT, MODELS, validate_results, load_key, request_batch)

def main():
    """5건 파일럿 후 10건씩 진행하며 성공 기록에서만 전체 평가를 계산한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--env', type=Path, default=Path('data/.env'))
    parser.add_argument('--model', choices=MODELS, help='생략하면 기존 두 모델을 모두 실행')
    parser.add_argument('--prompt-file', type=Path, help='생략하면 원래 V1 프롬프트 사용')
    parser.add_argument('--predict-only', action='store_true', help='정답 없이 예측만 저장; 정확도 미계산')
    args = parser.parse_args()
    prompt = args.prompt_file.read_text(encoding='utf-8') if args.prompt_file else PROMPT
    if not prompt.strip():
        raise ValueError('Prompt must not be empty')
    rows = json.loads(args.input.read_text(encoding='utf-8'))
    assert 0 < len(rows) <= 400
    if not args.predict_only:
        assert all(r['human_verified'] for r in rows)
    inputs = [{k:r.get(k) for k in ('sample_id','company','title','description')} for r in rows]
    digest = hashlib.sha256((prompt+json.dumps(inputs,ensure_ascii=False)).encode()).hexdigest()
    key = load_key(args.env)
    args.out.mkdir(parents=True,exist_ok=True)
    def save(path,value):
        path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    batches = [inputs[:5]] + [inputs[i:i+10] for i in range(5,len(inputs),10)]
    for model in ([args.model] if args.model else MODELS):
        folder = args.out/model
        folder.mkdir(exist_ok=True)
        predictions=[]; records=[]
        for number,batch in enumerate(batches):
            path = folder/f'batch-{number:03}.json'
            if path.exists():
                record=json.loads(path.read_text(encoding='utf-8'))
                if record.get('input_hash') != digest or record.get('status') != 'success':
                    raise ValueError('Existing batch needs inspection; no automatic paid retry')
            else:
                try:
                    record=request_batch(model,batch,key,prompt=prompt)
                except urllib.error.HTTPError as error:
                    # 제한 원인을 확인할 수 있도록 응답만 보존하고 키가 반사되면 지운다.
                    detail=error.read(4096).decode('utf-8',errors='replace').replace(key,'[REDACTED]')
                    record=dict(status='http_error',http_status=error.code,
                                retry_after=error.headers.get('Retry-After'),detail=detail)
                except (urllib.error.URLError, TimeoutError, KeyError, ValueError):
                    record=dict(status='request_or_response_error')
                record['input_hash']=digest
                save(path,record)
            if record['status'] != 'success':
                print(model, 'STOP', record['status'], record.get('http_status',''),flush=True)
                break
            predictions.extend(record['results']); records.append(record)
            print(model,len(predictions),'/',len(rows),flush=True)
        if len(predictions)==len(rows):
            metrics={} if args.predict_only else summarize_predictions([r['expected_relevance'] for r in rows],[r['predicted'] for r in predictions])
            metrics.update(estimated_credits=sum(r['estimated_credits'] for r in records),
                           request_seconds=sum(r['seconds'] for r in records),requests=len(records),input_hash=digest,
                           dataset_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
                           prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest())
            save(folder/'predictions.json',predictions)
            save(folder/('run.json' if args.predict_only else 'metrics.json'),metrics)


if __name__ == '__main__':
    main()
