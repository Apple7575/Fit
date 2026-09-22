CREATE TABLE rag_evidence_entity_scope (
    evidence_id VARCHAR(96) PRIMARY KEY REFERENCES rag_evidence (evidence_id) ON DELETE CASCADE,
    scope_name TEXT NOT NULL CHECK (btrim(scope_name) <> ''),
    rcept_no VARCHAR(14) NOT NULL,
    table_index INTEGER NOT NULL CHECK (table_index >= 0),
    rule_version VARCHAR(40) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX rag_evidence_entity_scope_receipt_idx
    ON rag_evidence_entity_scope (rcept_no, table_index);
