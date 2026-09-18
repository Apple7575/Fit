CREATE TABLE rag_evidence_embedding (
    evidence_id VARCHAR(96) NOT NULL REFERENCES rag_evidence (evidence_id) ON DELETE CASCADE,
    embedding_model VARCHAR(200) NOT NULL,
    embedding_version VARCHAR(40) NOT NULL,
    content_hash CHAR(64) NOT NULL,
    dimension INTEGER NOT NULL CHECK (dimension > 0),
    vector_bytes BYTEA NOT NULL,
    embedded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (evidence_id, embedding_model, embedding_version),
    CONSTRAINT rag_evidence_embedding_hash_check CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT rag_evidence_embedding_size_check CHECK (octet_length(vector_bytes) = dimension * 4)
);

CREATE INDEX rag_evidence_embedding_model_idx
    ON rag_evidence_embedding (embedding_model, embedding_version);
