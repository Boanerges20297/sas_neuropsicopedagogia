-- Neuro-Diagnosis: record an explicit request to provision/link a portal account.
-- No automatic login, invite, test release or clinical access.
-- Requires mysql_saas_schema.sql; safely repeatable.
USE neuro_diagnosis;

CREATE TABLE IF NOT EXISTS care_portal_access_requests (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    client_id BIGINT UNSIGNED NOT NULL,
    professional_user_id BIGINT UNSIGNED NOT NULL,
    status ENUM('pending','linked','cancelled') NOT NULL DEFAULT 'pending',
    requested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_portal_access_request_client (tenant_id,client_id),
    KEY ix_portal_access_request_prof (tenant_id,professional_user_id,status),
    CONSTRAINT fk_portal_access_request_client
        FOREIGN KEY (client_id,tenant_id) REFERENCES clients(id,tenant_id),
    CONSTRAINT fk_portal_access_request_member
        FOREIGN KEY (tenant_id,professional_user_id) REFERENCES tenant_members(tenant_id,user_id)
) ENGINE=InnoDB;
