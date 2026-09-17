"""관련성 라벨과 집계. 모델 실행이나 네트워크 호출은 하지 않는다."""
LABELS=['related','unrelated','uncertain']

def summarize_predictions(gold,predicted):
    """보류도 별도 클래스로 평가하고 관련 정답을 보류한 경우 누락에 포함한다."""
    if not len(gold) or len(gold) != len(predicted):
        raise ValueError('Gold and predictions must have the same nonzero length')
    matrix={a:{b:0 for b in LABELS} for a in LABELS}
    for a,b in zip(gold,predicted):matrix[a][b]+=1
    f1s=[]
    for label in LABELS:
        tp=matrix[label][label]
        fp=sum(matrix[a][label] for a in LABELS if a!=label)
        fn=sum(matrix[label][b] for b in LABELS if b!=label)
        f1s.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.)
    tp=matrix['related']['related']
    accepted=sum(matrix[a]['related'] for a in LABELS)
    positive=sum(matrix['related'].values())
    return dict(n=len(gold),macro_f1=sum(f1s)/3,accuracy=sum(matrix[a][a] for a in LABELS)/len(gold),
                related_precision=tp/accepted if accepted else 0.,related_recall=tp/positive if positive else 0.,
                missed_related=positive-tp,false_related=matrix['unrelated']['related'],
                uncertain_as_related=matrix['uncertain']['related'],uncertain_correct=matrix['uncertain']['uncertain'],
                confusion=matrix)
