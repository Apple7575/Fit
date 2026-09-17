-- 서비스 회원(자체 이메일/비밀번호 로그인). user 는 예약어라 테이블명은 users 를 쓴다.
CREATE TABLE users (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email         VARCHAR(255) NOT NULL,
    password_hash VARCHAR(100) NOT NULL,
    nickname      VARCHAR(50)  NOT NULL,
    role          VARCHAR(20)  NOT NULL DEFAULT 'ROLE_USER',
    status        VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT users_email_uk     UNIQUE (email),
    CONSTRAINT users_role_check   CHECK (role   IN ('ROLE_USER', 'ROLE_ADMIN')),
    CONSTRAINT users_status_check CHECK (status IN ('ACTIVE', 'SUSPENDED', 'WITHDRAWN'))
);

COMMENT ON TABLE  users               IS '서비스 회원. 이메일/비밀번호 자체 로그인';
COMMENT ON COLUMN users.password_hash IS 'BCrypt 해시. 평문은 저장하지 않는다';
