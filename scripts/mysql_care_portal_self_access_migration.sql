-- Adult patients use their OWN existing patient login, never a second clinical account.
-- Staged identity evidence and purpose-specific grants. No public routes.
-- ADDITIVE, idempotent; run after patient-intake and guardian portal migrations.
USE neuro_diagnosis;

CREATE TABLE IF NOT EXISTS care_portal_self_links (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT UNSIGNED NOT NULL,
  client_id BIGINT UNSIGNED NOT NULL,
  professional_user_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  verification_status ENUM('pending','verified','revoked') NOT NULL DEFAULT 'pending',
  verification_evidence_ref VARCHAR(200) NULL,
  verified_by BIGINT UNSIGNED NULL,
  verified_at DATETIME NULL,
  consent_evidence_ref VARCHAR(200) NULL,
  consent_at DATETIME NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_self_patient (tenant_id,client_id),
  UNIQUE KEY uq_self_link_full_scope
    (id,tenant_id,client_id,professional_user_id,user_id),
  KEY ix_self_links_user (user_id,verification_status),
  CONSTRAINT chk_self_verified CHECK (
    verification_status<>'verified' OR
    (verified_by IS NOT NULL AND verified_at IS NOT NULL
     AND verification_evidence_ref IS NOT NULL AND verification_evidence_ref<>''
     AND consent_evidence_ref IS NOT NULL AND consent_evidence_ref<>''
     AND consent_at IS NOT NULL)),
  CONSTRAINT fk_self_link_client FOREIGN KEY (client_id,tenant_id)
    REFERENCES clients(id,tenant_id),
  CONSTRAINT fk_self_link_member FOREIGN KEY (tenant_id,professional_user_id)
    REFERENCES tenant_members(tenant_id,user_id),
  CONSTRAINT fk_self_link_user FOREIGN KEY(user_id) REFERENCES users(id),
  CONSTRAINT fk_self_link_verifier FOREIGN KEY(verified_by) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS care_portal_self_grants (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT UNSIGNED NOT NULL,
  client_id BIGINT UNSIGNED NOT NULL,
  professional_user_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  self_link_id BIGINT UNSIGNED NOT NULL,
  permission_scope ENUM('appointments','released_documents') NOT NULL,
  status ENUM('pending','active','revoked') NOT NULL DEFAULT 'pending',
  expires_at DATETIME NOT NULL,
  authorized_by BIGINT UNSIGNED NULL,
  authorized_at DATETIME NULL,
  revoked_at DATETIME NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_self_grant_scope (self_link_id,permission_scope),
  KEY ix_self_grants_user (user_id,tenant_id,client_id,status),
  CONSTRAINT chk_self_grant_active CHECK (
    status<>'active' OR
    (authorized_by=professional_user_id AND authorized_at IS NOT NULL)),
  CONSTRAINT fk_self_grant_link
    FOREIGN KEY (self_link_id,tenant_id,client_id,professional_user_id,user_id)
    REFERENCES care_portal_self_links
      (id,tenant_id,client_id,professional_user_id,user_id),
  CONSTRAINT fk_self_grant_author FOREIGN KEY(authorized_by) REFERENCES users(id)
) ENGINE=InnoDB;

-- Purpose-specific acknowledgement is independent of family or self identity.
-- Creation of this record never grants portal access by itself.
CREATE TABLE IF NOT EXISTS care_portal_consents (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT UNSIGNED NOT NULL,
  client_id BIGINT UNSIGNED NOT NULL,
  professional_user_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  permission_scope ENUM('appointments','released_documents') NOT NULL,
  status ENUM('pending','accepted','revoked') NOT NULL DEFAULT 'pending',
  consent_evidence_ref VARCHAR(200) NULL,
  consent_at DATETIME NULL,
  confirmed_by_user_id BIGINT UNSIGNED NULL,
  expires_at DATETIME NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_portal_consent_scope
    (tenant_id,client_id,user_id,permission_scope),
  CONSTRAINT chk_portal_consent_accepted CHECK (
    status<>'accepted' OR
    (consent_evidence_ref IS NOT NULL AND consent_evidence_ref<>''
     AND consent_at IS NOT NULL AND confirmed_by_user_id=user_id)),
  CONSTRAINT fk_portal_consent_client FOREIGN KEY (client_id,tenant_id)
    REFERENCES clients(id,tenant_id),
  CONSTRAINT fk_portal_consent_member FOREIGN KEY (tenant_id,professional_user_id)
    REFERENCES tenant_members(tenant_id,user_id),
  CONSTRAINT fk_portal_consent_user FOREIGN KEY(user_id) REFERENCES users(id),
  CONSTRAINT fk_portal_consent_confirmer FOREIGN KEY(confirmed_by_user_id)
    REFERENCES users(id)
) ENGINE=InnoDB;
