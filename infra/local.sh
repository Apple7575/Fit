#!/usr/bin/env bash
# 로컬 실행 진입점. 인자 없이 실행하면 전부 컨테이너로 뜬다.
#   ./infra/local.sh          기본 - 빌드 후 전체 기동
#   ./infra/local.sh front    프론트를 반복 수정할 때 (postgres + backend 만)
#   ./infra/local.sh back     백엔드를 반복 수정할 때 (postgres 만)
#   ./infra/local.sh stop | reset | logs [서비스]
#
# 스크립트 없이 같은 일 (edge 네트워크는 미리 만들어야 한다):
#   docker compose --env-file .env.local -f docker-compose.yml -f docker-compose.local.yml up -d --build
set -euo pipefail

cd "$(dirname "$0")"

ENV_FILE=.env.local
EXAMPLE=.env.local.example
DC=(docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.local.yml)

info()  { printf '%s\n' "$*"; }
warn()  { printf '  ! %s\n' "$*" >&2; }
die()   { printf '\n오류: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- 사전 점검

ensure_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        cp "$EXAMPLE" "$ENV_FILE"
        info "      $ENV_FILE      없음 -> $EXAMPLE 에서 생성했습니다"
        return
    fi

    # 예제에만 있는 키를 찾는다. 예제가 늘어났을 때 조용히 어긋나는 것을 막는다.
    local missing
    missing=$(comm -23 \
        <(grep -oE '^[A-Z_]+=' "$EXAMPLE" | sort -u) \
        <(grep -oE '^[A-Z_]+=' "$ENV_FILE" | sort -u) | tr -d '=' | tr '\n' ' ')

    if [ -n "${missing// /}" ]; then
        info "      $ENV_FILE      있음"
        warn "$EXAMPLE 에만 있는 항목: ${missing% }"
        warn "필요하면 $ENV_FILE 에 추가하세요."
    else
        info "      $ENV_FILE      OK"
    fi

    # 없으면 compose 가 엉뚱한 오류를 내거나 다른 프로젝트 이름으로 별도 스택을 만든다.
    local key gone=""
    for key in ENV_NAME COMPOSE_PROJECT_NAME TAG POSTGRES_PASSWORD; do
        grep -qE "^$key=." "$ENV_FILE" || gone="$gone $key"
    done
    [ -z "$gone" ] || die "$ENV_FILE 에 필수 항목이 없습니다:$gone
       $EXAMPLE 을 보고 채우거나, $ENV_FILE 을 지우고 다시 실행하세요."
}

port_in_use() {
    command -v netstat >/dev/null 2>&1 || return 1
    netstat -an 2>/dev/null | grep -E "[:.]$1[[:space:]]" | grep -iq "listen"
}

check_ports() {
    local port busy=""
    for port in "$@"; do
        port_in_use "$port" && busy="$busy $port"
    done

    if [ -n "$busy" ]; then
        info "      포트            사용 중:$busy"
        warn "다른 프로그램이 쓰고 있습니다. 종료하거나 $ENV_FILE 의 POSTGRES_PORT 를 바꾸세요."
    else
        info "      포트            OK"
    fi
}

preflight() {
    info "[1/4] 사전 점검"

    docker info >/dev/null 2>&1 || die "Docker 가 실행 중이 아닙니다. Docker Desktop 을 켜고 다시 시도하세요."
    info "      Docker          OK"

    ensure_env_file

    local pg_port
    pg_port=$(grep -oE '^POSTGRES_PORT=[0-9]+' "$ENV_FILE" | cut -d= -f2 || true)

    # 우리 스택이 떠 있으면 포트를 쥔 것이 자기 자신이다.
    if [ -z "$("${DC[@]}" ps -q 2>/dev/null)" ]; then
        check_ports "$@" ${pg_port:-5432}
    fi

    docker network inspect edge >/dev/null 2>&1 || docker network create edge >/dev/null
}

# ---------------------------------------------------------------- 기동

wait_healthy() {
    local deadline=$((SECONDS + 240)) unhealthy state cid
    info "[4/4] 헬스체크"

    while [ $SECONDS -lt $deadline ]; do
        unhealthy=""
        for svc in "$@"; do
            cid=$("${DC[@]}" ps -q "$svc" 2>/dev/null || true)
            [ -n "$cid" ] || { unhealthy="$unhealthy $svc"; continue; }

            state=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || echo unknown)
            case "$state" in
                healthy|running) ;;
                *) unhealthy="$unhealthy $svc" ;;
            esac
        done

        if [ -z "$unhealthy" ]; then
            info "      $* 전부 정상"
            return 0
        fi
        sleep 3
    done

    warn "아직 준비되지 않은 서비스:$unhealthy"
    warn "로그를 확인하세요:  ./infra/local.sh logs$unhealthy"
    return 1
}

ALL_SERVICES="postgres backend frontend ai"

# all 에서 front/back 으로 옮길 때 남는 컨테이너를 정리한다. 두면 낡은 화면이 계속 보인다.
stop_others() {
    local wanted=" $* " extra=""
    for svc in $ALL_SERVICES; do
        case "$wanted" in
            *" $svc "*) ;;
            *) extra="$extra $svc" ;;
        esac
    done

    if [ -n "$extra" ]; then
        # shellcheck disable=SC2086
        "${DC[@]}" stop $extra >/dev/null 2>&1 || true
        info "      쓰지 않는 컨테이너 정지:$extra"
    fi
}

up() {
    local mode=$1; shift
    local services=("$@")

    info "[2/4] 이미지 빌드 (첫 실행은 3~5분 걸립니다)"
    "${DC[@]}" build "${services[@]}"

    info "[3/4] 기동"
    stop_others "${services[@]}"
    "${DC[@]}" up -d "${services[@]}"

    wait_healthy "${services[@]}" || true

    printf '\n'
    case "$mode" in
        all)
            info "  화면    http://localhost:3000"
            info "  API     http://localhost:8080/actuator/health"
            info "  AI      http://localhost:8000/docs"
            ;;
        front)
            info "  다음    cd frontend && npm run dev:api   ->  http://localhost:5173"
            info "  API     http://localhost:8080/actuator/health"
            ;;
        back)
            local pg_pw pg_port
            pg_pw=$(grep -oE '^POSTGRES_PASSWORD=.*' "$ENV_FILE" | cut -d= -f2- || true)
            pg_port=$(grep -oE '^POSTGRES_PORT=[0-9]+' "$ENV_FILE" | cut -d= -f2 || true)

            info "  다음    IDE 에서 local 프로파일로 백엔드 실행  ->  http://localhost:8080"
            info "          VM options       -Dspring.profiles.active=local"
            info "          환경변수         POSTGRES_PASSWORD=$pg_pw"
            info "  DB      localhost:${pg_port:-5432}  (사용자 ssafy)"
            ;;
    esac

    printf '\n'
    info "  ※ 로컬 DB 에는 기업 데이터가 없습니다. 검색 결과가 비어 있는 것은 정상입니다."
    info "    로그      ./infra/local.sh logs backend"
    info "    초기화    ./infra/local.sh reset"
}

# ---------------------------------------------------------------- 명령

case "${1:-all}" in
    all)
        preflight 3000 8080 8000
        up all postgres backend frontend ai
        ;;
    front)
        preflight 8080
        up front postgres backend
        ;;
    back)
        preflight
        up back postgres
        ;;
    stop)
        "${DC[@]}" down
        ;;
    reset)
        printf '로컬 DB 를 완전히 삭제합니다. 계속할까요? [y/N] '
        read -r answer
        case "$answer" in
            [yY]) "${DC[@]}" down -v && info "삭제했습니다. ./infra/local.sh 로 다시 시작하세요." ;;
            *)    info "취소했습니다." ;;
        esac
        ;;
    logs)
        shift
        "${DC[@]}" logs -f --tail 100 "$@"
        ;;
    *)
        die "알 수 없는 명령: $1  (사용법은 파일 상단 주석 참고)"
        ;;
esac
