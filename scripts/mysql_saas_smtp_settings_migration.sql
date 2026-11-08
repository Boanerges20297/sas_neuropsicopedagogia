-- SMTP administration: no cleartext credentials; one service identity only.
USE neuro_diagnosis;
CREATE TABLE IF NOT EXISTS saas_smtp_settings (
 id TINYINT UNSIGNED NOT NULL PRIMARY KEY,
 sender VARCHAR(254) NOT NULL,
 password_cipher VARBINARY(1024) NOT NULL,
 enabled BOOLEAN NOT NULL DEFAULT FALSE,
 test_nonce BINARY(16) NULL,
 test_digest BINARY(32) NULL,
 test_expires_at DATETIME NULL,
 test_attempts TINYINT UNSIGNED NOT NULL DEFAULT 0,
 test_sent_at DATETIME NULL,
 verified_at DATETIME NULL,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
   ON UPDATE CURRENT_TIMESTAMP,
 updated_by BIGINT UNSIGNED NOT NULL,
 CONSTRAINT fk_neuro_smtp_admin FOREIGN KEY (updated_by) REFERENCES users(id),
 CONSTRAINT chk_saas_smtp_only_one CHECK (id=1)
) ENGINE=InnoDB;
