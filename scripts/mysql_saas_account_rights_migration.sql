-- Explicit limits for administrator accounts created in-app.
-- Absent row denotes legacy admin with original permissions.
-- Superadmins are unrestricted by this table.
-- Restricting a capability never expands clinical access.
USE neuro_diagnosis;
CREATE TABLE IF NOT EXISTS saas_account_rights (
    user_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    allow_accounts BOOLEAN NOT NULL DEFAULT FALSE,
    allow_professionals BOOLEAN NOT NULL DEFAULT FALSE,
    allow_activations BOOLEAN NOT NULL DEFAULT FALSE,
    allow_clinic BOOLEAN NOT NULL DEFAULT FALSE,
    created_by BIGINT UNSIGNED NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_account_rights_user
      FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_account_rights_creator
      FOREIGN KEY (created_by) REFERENCES users(id)
) ENGINE=InnoDB;
