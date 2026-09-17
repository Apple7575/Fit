"""Build incremental evidence embeddings; emit one JSON result per invocation."""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.company_context.retrieval.vector import FastEmbedEncoder  # noqa: E402
from pipeline.rag_corpus.embedding_build import (  # noqa: E402
    ALLOWED_SOURCE_TYPES, DEFAULT_MODEL, DEFAULT_VERSION, EmbeddingBuildError,
    build_embeddings,
)
from scripts.build_rag_corpus import connect, resolve_company_codes  # noqa: E402


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("Invalid command arguments")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = JsonArgumentParser(description="변경된 RAG 근거의 문서 임베딩 구축")
    parser.add_argument("--corp-code", action="append")
    parser.add_argument("--source-type", action="append", choices=sorted(ALLOWED_SOURCE_TYPES))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.batch_size <= 0 or not args.model.strip() or not args.version.strip():
        parser.error("Invalid model, version or batch size")
    if len(args.model) > 200 or len(args.version) > 40:
        parser.error("Model or version exceeds storage limits")
    if args.source_type is not None:
        args.source_type = list(dict.fromkeys(args.source_type))
    return args


@contextmanager
def silence_dependency_output():
    streams = (sys.stdout, sys.stderr)
    with open(os.devnull, "w") as sink, ExitStack() as stack:
        for stream in streams:
            stream.flush()
        # Preconfigured logging sinks retain the old stream; also isolate its FD.
        for descriptor in (1, 2):
            saved = os.dup(descriptor)
            stack.callback(os.close, saved)
            stack.callback(os.dup2, saved, descriptor)
            os.dup2(sink.fileno(), descriptor)
        with redirect_stdout(sink), redirect_stderr(sink):
            try:
                yield
            finally:
                sink.flush()
                for stream in streams:
                    stream.flush()


def main(argv: Iterable[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        with silence_dependency_output():
            corp_codes = resolve_company_codes(connect, args.corp_code)
            encoder = None if args.dry_run else FastEmbedEncoder(args.model)
            summary = build_embeddings(connect, encoder, model=args.model, version=args.version,
                                       corp_codes=corp_codes, source_types=args.source_type,
                                       batch_size=args.batch_size, dry_run=args.dry_run)
        payload = {"status": "success", **asdict(summary)}
    except Exception as error:
        # DB and model exception messages can contain credentials or signed URLs.
        payload = {"status": "failed", "error": type(error).__name__}
        if isinstance(error, EmbeddingBuildError):
            payload.update(asdict(error.summary))
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
