-- NeuroCore evidence checklist v0.2: additive, idempotent, strictly tenant-scoped.
-- Contains DOCUMENTATION STATUSES only, not diagnostic conclusions.
USE neuro_diagnosis;

CREATE TABLE IF NOT EXISTS neurocore_evidence_reviews (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT UNSIGNED NOT NULL,
  client_id BIGINT UNSIGNED NOT NULL,
  professional_user_id BIGINT UNSIGNED NOT NULL,
  topic ENUM('tea','tdah') NOT NULL,
  knowledge_version VARCHAR(30) NOT NULL,
  evidence_json JSON NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_nc_evidence_owner_topic (tenant_id, client_id, professional_user_id, topic),
  KEY ix_nc_evidence_owner (tenant_id, professional_user_id, updated_at),
  CONSTRAINT fk_nc_client_same_tenant FOREIGN KEY(client_id, tenant_id)
    REFERENCES clients(id,tenant_id),
  CONSTRAINT fk_nc_professional_member FOREIGN KEY(tenant_id,professional_user_id)
    REFERENCES tenant_members(tenant_id,user_id)
) ENGINE=InnoDB;
