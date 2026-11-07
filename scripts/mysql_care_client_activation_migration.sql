-- Scoped activation of an existing patient/guardian login for one clinical client.
-- A patient user is one login, but activation is per clinician and per child.
-- This table never stores clinical narratives. No portal routes opened.
USE neuro_diagnosis;

CREATE TABLE IF NOT EXISTS care_portal_client_activations (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT UNSIGNED NOT NULL,
  client_id BIGINT UNSIGNED NOT NULL,
  professional_user_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  status ENUM('pending','active','revoked') NOT NULL DEFAULT 'pending',
  activated_by BIGINT UNSIGNED NULL,
  activated_at DATETIME NULL,
  revoked_at DATETIME NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_portal_client_activation (tenant_id,client_id,user_id),
  KEY ix_portal_activation_user (user_id,status),
  CONSTRAINT chk_portal_client_activation CHECK (
    status<>'active' OR (activated_by IS NOT NULL AND activated_at IS NOT NULL)
  ),
  CONSTRAINT fk_portal_activation_patient FOREIGN KEY (client_id,tenant_id)
    REFERENCES clients(id,tenant_id),
  CONSTRAINT fk_portal_activation_owner FOREIGN KEY (tenant_id,professional_user_id)
    REFERENCES tenant_members(tenant_id,user_id),
  CONSTRAINT fk_portal_activation_login FOREIGN KEY(user_id) REFERENCES users(id),
  CONSTRAINT fk_portal_activation_actor FOREIGN KEY(activated_by) REFERENCES users(id)
) ENGINE=InnoDB;

-- Login lifecycle is separate from per-client authorization.
-- A suspended user must NEVER be reactivated by a different professional.
CREATE TABLE IF NOT EXISTS care_portal_login_requests (
  user_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
  status ENUM('pending','active','suspended') NOT NULL DEFAULT 'pending',
  requested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  activated_by BIGINT UNSIGNED NULL,
  activated_at DATETIME NULL,
  CONSTRAINT chk_login_request_active CHECK (
    status<>'active' OR (activated_by IS NOT NULL AND activated_at IS NOT NULL)
  ),
  CONSTRAINT fk_portal_login_request_user FOREIGN KEY(user_id) REFERENCES users(id),
  CONSTRAINT fk_portal_login_request_actor FOREIGN KEY(activated_by) REFERENCES users(id)
) ENGINE=InnoDB;
