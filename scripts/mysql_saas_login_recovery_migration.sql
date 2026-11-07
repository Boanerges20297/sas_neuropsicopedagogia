-- Additive auth abuse controls; database counters shared across Gunicorn workers.
-- Never stores plaintext email OTPs or source IP addresses.
USE neuro_diagnosis;

CREATE TABLE IF NOT EXISTS saas_login_attempt_limits (
  principal_digest BINARY(32) NOT NULL PRIMARY KEY,
  failures SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  started_at DATETIME NOT NULL,
  cooldown_until DATETIME NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  KEY ix_login_attempts_updated (updated_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS saas_password_recovery_otp (
  user_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
  nonce BINARY(16) NOT NULL,
  digest BINARY(32) NOT NULL,
  expires_at DATETIME NOT NULL,
  attempts_left TINYINT UNSIGNED NOT NULL DEFAULT 3,
  last_sent_at DATETIME NOT NULL,
  send_window_at DATETIME NOT NULL,
  sends_in_window TINYINT UNSIGNED NOT NULL DEFAULT 1,
  used_at DATETIME NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_neuro_recovery_user FOREIGN KEY (user_id) REFERENCES users(id),
  KEY ix_recovery_expiry (expires_at)
) ENGINE=InnoDB;
