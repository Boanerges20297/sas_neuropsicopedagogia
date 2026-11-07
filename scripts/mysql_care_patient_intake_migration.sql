-- Patient != account holder: adult self or child under one existing guardian login.
-- Additive. Runs after mysql_care_workflow_migration.sql.
USE neuro_diagnosis;

CREATE TABLE IF NOT EXISTS care_patient_intakes (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    client_id BIGINT UNSIGNED NOT NULL,
    professional_user_id BIGINT UNSIGNED NOT NULL,
    representation_mode ENUM('self','guardian') NOT NULL,
    initial_report_encrypted BLOB NULL,
    guardian_contact_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_care_patient_intake (tenant_id,client_id),
    KEY ix_care_intake_professional (tenant_id,professional_user_id),
    CONSTRAINT chk_care_intake_guardian CHECK
        ((representation_mode='self' AND guardian_contact_id IS NULL)
         OR (representation_mode='guardian' AND guardian_contact_id IS NOT NULL)),
    CONSTRAINT fk_care_intake_patient
        FOREIGN KEY (client_id,tenant_id) REFERENCES clients(id,tenant_id),
    CONSTRAINT fk_care_intake_professional
        FOREIGN KEY (tenant_id,professional_user_id)
        REFERENCES tenant_members(tenant_id,user_id),
    CONSTRAINT fk_care_intake_guardian_contact
        FOREIGN KEY (guardian_contact_id,tenant_id,client_id,professional_user_id)
        REFERENCES care_client_contacts(id,tenant_id,client_id,professional_user_id)
) ENGINE=InnoDB;
