-- MySQL 8, additive and idempotent. Apply after mysql_saas_schema.sql.
-- TOTP secrets are application-encrypted, never sent to logs.
USE neuro_diagnosis;

CREATE TABLE IF NOT EXISTS saas_mfa_factors (
    user_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    required BOOLEAN NOT NULL DEFAULT FALSE,
    secret_cipher VARBINARY(512) NULL,
    pending_cipher VARBINARY(512) NULL,
    pending_at DATETIME NULL,
    enabled_at DATETIME NULL,
    last_used_step BIGINT NOT NULL DEFAULT -1,
    failed_attempts INT UNSIGNED NOT NULL DEFAULT 0,
    locked_until DATETIME NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_saas_mfa_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT chk_saas_mfa_active CHECK
      ((enabled_at IS NULL AND secret_cipher IS NULL)
        OR (enabled_at IS NOT NULL AND secret_cipher IS NOT NULL))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS saas_mfa_recovery_codes (
    user_id BIGINT UNSIGNED NOT NULL,
    code_digest BINARY(32) NOT NULL,
    used_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(user_id,code_digest),
    CONSTRAINT fk_saas_mfa_recovery_user
      FOREIGN KEY (user_id) REFERENCES saas_mfa_factors(user_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS saas_mfa_trusted_devices (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    token_digest BINARY(32) NOT NULL,
    user_agent_digest BINARY(32) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    last_seen_at DATETIME NULL,
    revoked_at DATETIME NULL,
    UNIQUE KEY uq_saas_mfa_device_token(token_digest),
    KEY ix_saas_mfa_device_owner(user_id,expires_at,revoked_at),
    CONSTRAINT fk_saas_mfa_device_user
      FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;
