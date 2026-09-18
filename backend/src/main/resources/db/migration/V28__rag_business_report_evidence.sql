ALTER TABLE rag_evidence
    DROP CONSTRAINT rag_evidence_source_type_check;

ALTER TABLE rag_evidence
    ADD CONSTRAINT rag_evidence_source_type_check CHECK (source_type IN (
        'COMPANY_PROFILE', 'COMPANY_METRIC', 'COMPANY_TEXT',
        'SEGMENT_METRIC', 'COMPANY_ACTIVITY', 'DART_BUSINESS_REPORT'
    ));
