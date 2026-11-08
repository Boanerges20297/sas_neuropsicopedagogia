-- Additive email ownership proof, MySQL 8; no retrofit of legacy users.
-- Existing accounts without a row retain their historical login until reverified.
-- Newly created accounts have required=1 with verified_at NULL.
USE neuro_diagnosis;

CREATE TABLE IF NOT EXISTS saas_email_verifications (
    user_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    required BOOLEAN NOT NULL DEFAULT TRUE,
    verified_at DATETIME NULL,
    last_sent_at DATETIME NULL,
    send_window_at DATETIME NULL,
    sends_in_window SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
      ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_neuro_email_verification_user
      FOREIGN KEY(user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS saas_email_challenges (
    user_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    requested_email VARCHAR(254) NOT NULL,
    purpose ENUM('registration','change','bootstrap_admin','confirm_current') NOT NULL,
    nonce BINARY(16) NOT NULL,
    digest BINARY(32) NOT NULL,
    expires_at DATETIME NOT NULL,
    attempts_left TINYINT UNSIGNED NOT NULL DEFAULT 5,
    requested_by BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_neuro_email_pending_address(requested_email),
    KEY ix_neuro_email_challenge_expiry(expires_at),
    CONSTRAINT fk_neuro_email_challenge_user
      FOREIGN KEY(user_id) REFERENCES users(id),
    CONSTRAINT fk_neuro_email_challenge_actor
      FOREIGN KEY(requested_by) REFERENCES users(id)
) ENGINE=InnoDB;
