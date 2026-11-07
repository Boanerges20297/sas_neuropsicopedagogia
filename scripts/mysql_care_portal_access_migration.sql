-- Future portal access foundation. NO routes or automatic sharing.
-- Must run after mysql_care_workflow_migration.sql.
-- A contact alone is NOT a login and grants are PENDING by default.
USE neuro_diagnosis;

CREATE TABLE IF NOT EXISTS care_portal_identity_links (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT UNSIGNED NOT NULL,
  client_id BIGINT UNSIGNED NOT NULL,
  professional_user_id BIGINT UNSIGNED NOT NULL,
  contact_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  verification_status ENUM('pending','verified','revoked') NOT NULL DEFAULT 'pending',
  verification_evidence_ref VARCHAR(200) NULL,
  verified_by BIGINT UNSIGNED NULL,
  verified_at DATETIME NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_portal_contact_link (contact_id),
  UNIQUE KEY uq_portal_link_all_scope
    (id,tenant_id,client_id,professional_user_id,user_id),
  KEY ix_portal_identity_user (user_id,verification_status),
  CONSTRAINT chk_portal_verified CHECK (
    verification_status<>'verified' OR
    (verified_by IS NOT NULL AND verified_at IS NOT NULL AND
     verification_evidence_ref IS NOT NULL)),
  CONSTRAINT fk_portal_identity_contact
    FOREIGN KEY (contact_id,tenant_id,client_id,professional_user_id)
    REFERENCES care_client_contacts(id,tenant_id,client_id,professional_user_id),
  CONSTRAINT fk_portal_identity_user FOREIGN KEY(user_id) REFERENCES users(id),
  CONSTRAINT fk_portal_identity_verifier FOREIGN KEY(verified_by) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS care_portal_grants (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT UNSIGNED NOT NULL,
  client_id BIGINT UNSIGNED NOT NULL,
  professional_user_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  identity_link_id BIGINT UNSIGNED NOT NULL,
  permission_scope ENUM('appointments','released_documents') NOT NULL,
  status ENUM('pending','active','revoked') NOT NULL DEFAULT 'pending',
  expires_at DATETIME NOT NULL,
  authorized_by BIGINT UNSIGNED NULL,
  authorized_at DATETIME NULL,
  revoked_at DATETIME NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_portal_grant_scope (identity_link_id,permission_scope),
  KEY ix_portal_user_scope (user_id,tenant_id,client_id,status),
  CONSTRAINT chk_portal_active CHECK (
    status<>'active' OR
    (authorized_by IS NOT NULL AND authorized_at IS NOT NULL)),
  CONSTRAINT fk_portal_grant_identity
    FOREIGN KEY (identity_link_id,tenant_id,client_id,professional_user_id,user_id)
    REFERENCES care_portal_identity_links
      (id,tenant_id,client_id,professional_user_id,user_id),
  CONSTRAINT fk_portal_grant_author FOREIGN KEY(authorized_by) REFERENCES users(id)
) ENGINE=InnoDB;
