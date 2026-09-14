"""컨테이너 진입점. ai/ 에 있는 FastAPI 앱을 하나의 프로세스로 띄운다.

    /health            전체 상태
    /jd/...            jd_coaching — JD 기반 자소서 코칭 (/jd/internal/..., /jd/docs)

프록시가 /ai/ 를 떼고 넘기므로 외부 주소는 /ai/jd/... 가 된다. 앱이 늘면 여기서
같은 방식으로 mount 한다(예: /rag). AI_ROOT_PATH(=/ai) 를 uvicorn root_path 로 넣어
각 앱의 /docs 가 맞는 openapi 경로를 가리키게 한다.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

LOGGER = logging.getLogger("ai.serve")


def build_app() -> FastAPI:
    from ai.jd_coaching.api import app as jd_app

    # Starlette 의 mount 는 하위 앱의 lifespan 을 실행하지 않는다. 직접 열어 준다.
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        async with jd_app.router.lifespan_context(jd_app):
            yield

    root = FastAPI(
        title="Company Analysis AI",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @root.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "services": {"jd": "/jd"}}

    root.mount("/jd", jd_app)
    return root


app = build_app()


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run(
        "ai.serve:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        root_path=os.environ.get("AI_ROOT_PATH", "").strip(),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
