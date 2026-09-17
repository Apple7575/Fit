-- 이메일 인증(링크 방식). 가입은 PENDING 으로 만들고, 링크 인증 후 ACTIVE 가 된다.
ALTER TABLE users DROP CONSTRAINT users_status_check;
ALTER TABLE users ADD CONSTRAINT users_status_check
    CHECK (status IN ('ACTIVE', 'SUSPENDED', 'WITHDRAWN', 'PENDING'));

CREATE TABLE email_verification_token (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at    TIMESTAMPTZ,

    CONSTRAINT email_verification_token_hash_uk UNIQUE (token_hash)
);
CREATE INDEX email_verification_token_user_idx ON email_verification_token (user_id);

COMMENT ON TABLE  email_verification_token            IS '이메일 인증 링크 토큰(유저당 1개, 재발급 시 교체)';
COMMENT ON COLUMN email_verification_token.token_hash IS '원문 토큰의 SHA-256 해시(hex). 원문은 메일 링크에만';
