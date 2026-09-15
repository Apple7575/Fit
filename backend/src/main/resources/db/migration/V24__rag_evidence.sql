CREATE TABLE rag_evidence (
    evidence_id       VARCHAR(96)  PRIMARY KEY,
    corp_code         VARCHAR(8)   NOT NULL REFERENCES company (corp_code),
    source_type       VARCHAR(40)  NOT NULL,
    source_identity   VARCHAR(500) NOT NULL,
    title             VARCHAR(300) NOT NULL,
    content           TEXT         NOT NULL,
    reference_period  VARCHAR(20),
    published_at      TIMESTAMPTZ  NOT NULL,
    source_url        TEXT,
    quality           VARCHAR(20)  NOT NULL,
    metadata          JSONB        NOT NULL DEFAULT '{}'::jsonb,
    content_hash      CHAR(64)     NOT NULL,
    source_updated_at TIMESTAMPTZ,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT rag_evidence_source_identity_uk UNIQUE (source_identity),
    CONSTRAINT rag_evidence_source_type_check CHECK (source_type IN (
        'COMPANY_PROFILE', 'COMPANY_METRIC', 'COMPANY_TEXT',
        'SEGMENT_METRIC', 'COMPANY_ACTIVITY'
    )),
    CONSTRAINT rag_evidence_quality_check
        CHECK (quality IN ('PRIMARY', 'VERIFIED', 'UNVERIFIED')),
    CONSTRAINT rag_evidence_content_check CHECK (btrim(content) <> ''),
    CONSTRAINT rag_evidence_hash_check CHECK (content_hash ~ '^[0-9a-f]{64}$')
);

CREATE INDEX rag_evidence_company_published_idx
    ON rag_evidence (corp_code, published_at DESC);
CREATE INDEX rag_evidence_company_source_published_idx
    ON rag_evidence (corp_code, source_type, published_at DESC);
