"""Flyway 마이그레이션에서 현재 유효한 스키마를 읽는다.

DB 에 붙지 않고 SQL 파일만 읽는다. 검증할 때 DB 접속을 요구하면 CI 나 다른 사람
PC 에서 돌지 않고, 무엇보다 "적재 전에 헤더가 맞는지" 를 확인하려면 DB 가 아직
비어 있어도 되어야 한다.

읽는 것은 테이블·컬럼·순서·타입·NULL 허용·키 종류·FK 대상·COMMENT 다. CHECK 식과
인덱스 정의는 키 판정에 필요한 UNIQUE 인덱스만 본다.

파싱할 수 없는 문장을 만나면 조용히 넘기지 않고 예외를 던진다. 스키마 대조가
"모르는 컬럼은 없는 것으로 치고 통과" 하면 검증의 뜻이 없어진다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# backend 의 마이그레이션 폴더. data/ 기준 상대 경로로 찾는다.
MIGRATION_DIR = (
    Path(__file__).resolve().parents[3]
    / "backend"
    / "src"
    / "main"
    / "resources"
    / "db"
    / "migration"
)

# 이 스키마에 실제로 쓰인 타입만 허용한다. 새 타입이 들어오면 여기서 걸려
# 사전(data_fields.csv)을 갱신하라는 신호가 된다.
_SIZED_TYPES = ("VARCHAR", "NUMERIC", "CHAR", "DECIMAL")
_PLAIN_TYPES = (
    "BIGINT", "INTEGER", "SMALLINT", "BOOLEAN", "TEXT[]", "TEXT",
    "JSONB", "JSON", "DATE", "TIMESTAMPTZ", "TIMESTAMP", "UUID",
)
_CONSTRAINT_STARTS = ("CONSTRAINT", "PRIMARY KEY", "UNIQUE", "CHECK", "FOREIGN KEY", "EXCLUDE")


@dataclass
class Column:
    table: str
    name: str
    ordinal: int
    data_type: str
    nullable: bool
    key_type: str = ""            # PK / UK / FK / PK,FK …
    referenced_table: str = ""
    referenced_column: str = ""
    comment: str = ""
    default: str = ""
    identity: bool = False


@dataclass
class Table:
    name: str
    schema: str = "public"
    comment: str = ""
    columns: dict[str, Column] = field(default_factory=dict)

    @property
    def qualified(self) -> str:
        return self.name if self.schema == "public" else f"{self.schema}.{self.name}"

    def ordered(self) -> list[Column]:
        return sorted(self.columns.values(), key=lambda c: c.ordinal)


@dataclass
class Schema:
    tables: dict[str, Table] = field(default_factory=dict)
    seeded_tables: set[str] = field(default_factory=set)   # INSERT INTO 로 값이 들어가는 테이블
    applied_files: list[str] = field(default_factory=list)

    def table(self, name: str) -> Table | None:
        return self.tables.get(name)


def _strip_comments(sql: str) -> str:
    """`--` 줄 주석을 지운다. 문자열 리터럴 안의 `--` 는 건드리지 않는다."""
    out, quoted, i = [], False, 0
    while i < len(sql):
        ch = sql[i]
        if quoted:
            out.append(ch)
            if ch == "'":
                # '' 는 문자열 안의 따옴표다. 문자열이 끝난 것이 아니다.
                if i + 1 < len(sql) and sql[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                quoted = False
            i += 1
            continue
        if ch == "'":
            quoted = True
            out.append(ch)
            i += 1
            continue
        if ch == "-" and sql.startswith("--", i):
            j = sql.find("\n", i)
            i = len(sql) if j == -1 else j
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _split_statements(sql: str) -> list[str]:
    """깊이 0 의 세미콜론으로 문장을 자른다. 괄호·문자열 안의 세미콜론은 무시한다."""
    statements, buf, depth, quoted, i = [], [], 0, False, 0
    while i < len(sql):
        ch = sql[i]
        if quoted:
            buf.append(ch)
            if ch == "'":
                if i + 1 < len(sql) and sql[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                quoted = False
            i += 1
            continue
        if ch == "'":
            quoted = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == ";" and depth == 0:
            statements.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if "".join(buf).strip():
        statements.append("".join(buf).strip())
    return [s for s in statements if s]


def _split_top_level(body: str) -> list[str]:
    """CREATE TABLE 본문을 깊이 0 의 콤마로 자른다."""
    items, buf, depth, quoted, i = [], [], 0, False, 0
    while i < len(body):
        ch = body[i]
        if quoted:
            buf.append(ch)
            if ch == "'":
                if i + 1 < len(body) and body[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                quoted = False
            i += 1
            continue
        if ch == "'":
            quoted = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            items.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if "".join(buf).strip():
        items.append("".join(buf).strip())
    return items


def _parse_type(definition: str) -> tuple[str, str]:
    """컬럼 정의에서 타입과 나머지를 떼어 낸다."""
    text = definition.strip()
    upper = text.upper()
    for name in _SIZED_TYPES:
        if upper.startswith(name):
            m = re.match(rf"{name}\s*(\(\s*\d+\s*(?:,\s*\d+\s*)?\))?", text, re.IGNORECASE)
            size = (m.group(1) or "").replace(" ", "")
            return name + size, text[m.end():].strip()
    for name in _PLAIN_TYPES:
        if upper.startswith(name):
            return name, text[len(name):].strip()
    raise ValueError(f"모르는 컬럼 타입: {definition!r}")


def _add_key(column: Column, kind: str) -> None:
    kinds = [k for k in column.key_type.split(",") if k]
    if kind not in kinds:
        kinds.append(kind)
    column.key_type = ",".join(kinds)


_CREATE_TABLE = re.compile(
    r"^CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:(\w+)\.)?(\w+)\s*\((.*)\)\s*$",
    re.IGNORECASE | re.DOTALL,
)
_ADD_COLUMN = re.compile(
    r"^ALTER\s+TABLE\s+(?:(\w+)\.)?(\w+)\s+ADD\s+(?:COLUMN\s+)?(\w+)\s+(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_COMMENT_ON = re.compile(
    r"^COMMENT\s+ON\s+(TABLE|COLUMN|SCHEMA)\s+([\w.]+)\s+IS\s+'(.*)'$",
    re.IGNORECASE | re.DOTALL,
)
_UNIQUE_INDEX = re.compile(
    r"^CREATE\s+UNIQUE\s+INDEX\s+\w+\s+ON\s+(?:(\w+)\.)?(\w+)\s*\(([^)]*)\)",
    re.IGNORECASE | re.DOTALL,
)
_INSERT_INTO = re.compile(r"^INSERT\s+INTO\s+(?:(\w+)\.)?(\w+)", re.IGNORECASE)
_REFERENCES = re.compile(
    r"REFERENCES\s+(?:\w+\.)?(\w+)\s*\(\s*(\w+)\s*\)", re.IGNORECASE
)
_TABLE_FK = re.compile(
    r"FOREIGN\s+KEY\s*\(([^)]*)\)\s*REFERENCES\s+(?:\w+\.)?(\w+)\s*\(([^)]*)\)",
    re.IGNORECASE | re.DOTALL,
)


def _apply_create_table(schema: Schema, match: re.Match) -> None:
    table = Table(name=match.group(2), schema=(match.group(1) or "public").lower())
    schema.tables[table.name] = table
    pk_columns: list[str] = []
    fks: list[tuple[list[str], str, list[str]]] = []
    uniques: list[list[str]] = []
    ordinal = 0
    for item in _split_top_level(match.group(3)):
        head = item.upper().lstrip()
        if any(head.startswith(k) for k in _CONSTRAINT_STARTS):
            body = item
            if head.startswith("CONSTRAINT"):
                body = re.sub(r"^CONSTRAINT\s+\w+\s+", "", item, flags=re.IGNORECASE)
            kind = body.upper().lstrip()
            if kind.startswith("PRIMARY KEY"):
                pk_columns += [c.strip() for c in re.search(r"\((.*)\)", body, re.DOTALL).group(1).split(",")]
            elif kind.startswith("UNIQUE"):
                uniques.append([c.strip() for c in re.search(r"\((.*)\)", body, re.DOTALL).group(1).split(",")])
            elif kind.startswith("FOREIGN KEY"):
                fk = _TABLE_FK.search(body)
                fks.append((
                    [c.strip() for c in fk.group(1).split(",")],
                    fk.group(2),
                    [c.strip() for c in fk.group(3).split(",")],
                ))
            continue
        name, _, definition = item.partition(" ")
        data_type, rest = _parse_type(definition)
        ordinal += 1
        upper = rest.upper()
        column = Column(
            table=table.name, name=name, ordinal=ordinal, data_type=data_type,
            nullable="NOT NULL" not in upper and "PRIMARY KEY" not in upper,
            identity="GENERATED ALWAYS AS IDENTITY" in upper,
        )
        default = re.search(r"DEFAULT\s+(.+?)(?:\s+(?:NOT\s+NULL|REFERENCES|CHECK|UNIQUE|PRIMARY)\b|$)",
                            rest, re.IGNORECASE | re.DOTALL)
        if default:
            column.default = default.group(1).strip()
        if "PRIMARY KEY" in upper:
            pk_columns.append(name)
        if "UNIQUE" in upper:
            uniques.append([name])
        ref = _REFERENCES.search(rest)
        if ref:
            _add_key(column, "FK")
            column.referenced_table, column.referenced_column = ref.group(1), ref.group(2)
        table.columns[name] = column

    for name in pk_columns:
        _add_key(table.columns[name], "PK")
        table.columns[name].nullable = False
    for names in uniques:
        for name in names:
            _add_key(table.columns[name], "UK")
    for names, target, target_columns in fks:
        for name, target_column in zip(names, target_columns):
            _add_key(table.columns[name], "FK")
            table.columns[name].referenced_table = target
            table.columns[name].referenced_column = target_column


def load(migration_dir: Path | None = None) -> Schema:
    """마이그레이션을 버전 순으로 적용해 현재 스키마를 만든다."""
    directory = migration_dir or MIGRATION_DIR
    files = sorted(
        directory.glob("V*__*.sql"),
        key=lambda p: int(re.match(r"V(\d+)__", p.name).group(1)),
    )
    if not files:
        raise FileNotFoundError(f"마이그레이션을 찾을 수 없다: {directory}")
    schema = Schema()
    for path in files:
        schema.applied_files.append(path.name)
        for statement in _split_statements(_strip_comments(path.read_text(encoding="utf-8"))):
            head = statement.upper().lstrip()
            create = _CREATE_TABLE.match(statement)
            if create:
                _apply_create_table(schema, create)
                continue
            comment = _COMMENT_ON.match(statement)
            if comment:
                target, text = comment.group(2), comment.group(3).replace("''", "'")
                if comment.group(1).upper() == "TABLE":
                    name = target.split(".")[-1]
                    if name in schema.tables:
                        schema.tables[name].comment = text
                elif comment.group(1).upper() == "COLUMN":
                    parts = target.split(".")
                    table = schema.tables.get(parts[-2])
                    if table and parts[-1] in table.columns:
                        table.columns[parts[-1]].comment = text
                continue
            add = _ADD_COLUMN.match(statement)
            if add and not re.match(r"^ALTER\s+TABLE\s+[\w.]+\s+ADD\s+CONSTRAINT", statement, re.IGNORECASE):
                table = schema.tables[add.group(2)]
                data_type, rest = _parse_type(add.group(4))
                upper = rest.upper()
                column = Column(
                    table=table.name, name=add.group(3),
                    ordinal=max((c.ordinal for c in table.columns.values()), default=0) + 1,
                    data_type=data_type,
                    nullable="NOT NULL" not in upper and "PRIMARY KEY" not in upper,
                )
                default = re.search(r"DEFAULT\s+(.+?)$", rest, re.IGNORECASE | re.DOTALL)
                if default:
                    column.default = default.group(1).strip()
                ref = _REFERENCES.search(rest)
                if ref:
                    _add_key(column, "FK")
                    column.referenced_table, column.referenced_column = ref.group(1), ref.group(2)
                table.columns[column.name] = column
                continue
            index = _UNIQUE_INDEX.match(statement)
            if index:
                table = schema.tables.get(index.group(2))
                if table:
                    for raw in index.group(3).split(","):
                        name = raw.strip().split()[0]
                        if name in table.columns:
                            _add_key(table.columns[name], "UK")
                continue
            insert = _INSERT_INTO.match(statement)
            if insert:
                schema.seeded_tables.add(insert.group(2))
                continue
            if any(head.startswith(k) for k in (
                "CREATE INDEX", "CREATE SCHEMA", "CREATE EXTENSION", "ALTER TABLE",
                "DROP INDEX", "DROP TABLE", "UPDATE", "DELETE", "SET",
            )):
                continue
            raise ValueError(f"{path.name}: 파싱하지 못한 문장 — {statement[:120]!r}")
    return schema
