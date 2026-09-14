FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/ai/requirements.txt
RUN pip install --no-cache-dir -r /app/ai/requirements.txt

COPY . /app/ai

EXPOSE 8000

# deploy.sh 는 healthy 가 될 때까지 기다린다. 헬스체크가 없으면 배포가 롤백된다.
# slim 이미지에는 curl 이 없어 파이썬으로 확인한다.
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)" || exit 1

CMD ["python", "-m", "ai.serve"]
