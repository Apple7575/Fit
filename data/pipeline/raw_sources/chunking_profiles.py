"""사업보고서 청킹 실험 프로필의 정본."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkingProfile:
    name: str
    text_max_chars: int
    table_max_chars: int


_PROFILES = {
    profile.name: profile
    for profile in (
        ChunkingProfile("structural-800-v1", 800, 800),
        ChunkingProfile("structural-1500-v2", 1500, 1500),
        ChunkingProfile("adaptive-v1", 1200, 800),
    )
}


def get_chunking_profile(name: str) -> ChunkingProfile:
    try:
        return _PROFILES[name]
    except KeyError as error:
        raise ValueError(f"지원하지 않는 청킹 프로필입니다: {name}") from error


def chunking_profile_names() -> tuple[str, ...]:
    return tuple(_PROFILES)
