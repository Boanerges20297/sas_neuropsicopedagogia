-- Neuro-Diagnosis: private clinical encounter and assessment workflow.
-- Additive except allowing appointment_id NULL for walk-in visits.
-- Requires mysql_saas_schema + mysql_care_workflow_migration.
USE neuro_diagnosis;

ALTER TABLE care_encounters MODIFY COLUMN appointment_id BIGINT UNSIGNED NULL;

-- Idempotent composite keys enforce the full clinical ownership tuple.
SET @has_scope_index = (SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema=DATABASE() AND table_name='care_encounters'
    AND index_name='uq_encounter_full_scope');
SET @scope_sql = IF(@has_scope_index=0,
  'ALTER TABLE care_encounters ADD UNIQUE KEY uq_encounter_full_scope (id,tenant_id,client_id,professional_user_id)',
  'SELECT 1');
PREPARE stmt FROM @scope_sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_scope_index = (SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema=DATABASE() AND table_name='assessments'
    AND index_name='uq_assessment_full_scope');
SET @scope_sql = IF(@has_scope_index=0,
  'ALTER TABLE assessments ADD UNIQUE KEY uq_assessment_full_scope (id,tenant_id,client_id,responsible_user_id)',
  'SELECT 1');
PREPARE stmt FROM @scope_sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS care_encounter_starts (
 id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
 tenant_id BIGINT UNSIGNED NOT NULL,
 client_id BIGINT UNSIGNED NOT NULL,
 professional_user_id BIGINT UNSIGNED NOT NULL,
 encounter_id BIGINT UNSIGNED NOT NULL,
 request_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uq_encounter_start_request (tenant_id,professional_user_id,request_id),
 UNIQUE KEY uq_encounter_start_id (encounter_id),
 CONSTRAINT fk_enc_start_encounter FOREIGN KEY(encounter_id,tenant_id,client_id,professional_user_id)
    REFERENCES care_encounters(id,tenant_id,client_id,professional_user_id),
 CONSTRAINT fk_enc_start_client FOREIGN KEY(client_id,tenant_id) REFERENCES clients(id,tenant_id),
 CONSTRAINT fk_enc_start_member FOREIGN KEY(tenant_id,professional_user_id) REFERENCES tenant_members(tenant_id,user_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS care_encounter_notes (
 id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
 encounter_id BIGINT UNSIGNED NOT NULL,
 revision INT UNSIGNED NOT NULL,
 ciphertext LONGBLOB NOT NULL,
 edited_by BIGINT UNSIGNED NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uq_encounter_revision (encounter_id,revision),
 KEY ix_encounter_notes_editor (edited_by,created_at),
 CONSTRAINT fk_enc_notes_encounter FOREIGN KEY(encounter_id) REFERENCES care_encounters(id),
 CONSTRAINT fk_enc_notes_editor FOREIGN KEY(edited_by) REFERENCES users(id)
) ENGINE=InnoDB;

-- Diagnostic labels are recorded by the clinician only; never auto-inferred.
CREATE TABLE IF NOT EXISTS care_diagnosis_records (
 id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
 tenant_id BIGINT UNSIGNED NOT NULL,
 client_id BIGINT UNSIGNED NOT NULL,
 professional_user_id BIGINT UNSIGNED NOT NULL,
 encounter_id BIGINT UNSIGNED NOT NULL,
 code VARCHAR(32) NULL,
 label VARCHAR(160) NOT NULL,
 certainty ENUM('hypothesis','confirmed','excluded') NOT NULL DEFAULT 'hypothesis',
 recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 KEY ix_care_diagnosis_scope (tenant_id,professional_user_id,certainty,recorded_at),
 CONSTRAINT fk_care_diag_client FOREIGN KEY(client_id,tenant_id) REFERENCES clients(id,tenant_id),
 CONSTRAINT fk_care_diag_encounter FOREIGN KEY(encounter_id,tenant_id,client_id,professional_user_id)
    REFERENCES care_encounters(id,tenant_id,client_id,professional_user_id),
 CONSTRAINT fk_care_diag_member FOREIGN KEY(tenant_id,professional_user_id) REFERENCES tenant_members(tenant_id,user_id)
) ENGINE=InnoDB;

-- The approved version is immutable; the application mode does not modify the test.
CREATE TABLE IF NOT EXISTS care_assessment_workflows (
 assessment_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
 tenant_id BIGINT UNSIGNED NOT NULL,
 client_id BIGINT UNSIGNED NOT NULL,
 professional_user_id BIGINT UNSIGNED NOT NULL,
 encounter_id BIGINT UNSIGNED NULL,
 mode ENUM('professional','portal') NOT NULL,
 delivery_status ENUM('ready','awaiting_portal_access') NOT NULL DEFAULT 'ready',
 revision INT UNSIGNED NOT NULL DEFAULT 0,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 KEY ix_assessment_mode_scope (tenant_id,professional_user_id,client_id,mode),
 CONSTRAINT fk_care_aw_assessment FOREIGN KEY(assessment_id,tenant_id,client_id,professional_user_id)
    REFERENCES assessments(id,tenant_id,client_id,responsible_user_id),
 CONSTRAINT fk_care_aw_client FOREIGN KEY(client_id,tenant_id) REFERENCES clients(id,tenant_id),
 CONSTRAINT fk_care_aw_member FOREIGN KEY(tenant_id,professional_user_id) REFERENCES tenant_members(tenant_id,user_id),
 CONSTRAINT fk_care_aw_encounter FOREIGN KEY(encounter_id,tenant_id,client_id,professional_user_id)
    REFERENCES care_encounters(id,tenant_id,client_id,professional_user_id)
) ENGINE=InnoDB;

-- Existing assessment_responses(answer_json) is intentionally not used for clinical answers.
-- Encrypted answers prevent exposing content as plaintext JSON in MySQL.
CREATE TABLE IF NOT EXISTS care_assessment_private_answers (
 id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
 tenant_id BIGINT UNSIGNED NOT NULL,
 assessment_id BIGINT UNSIGNED NOT NULL,
 question_key VARCHAR(100) NOT NULL,
 ciphertext LONGBLOB NOT NULL,
 edited_by BIGINT UNSIGNED NOT NULL,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 UNIQUE KEY uq_care_private_answer (assessment_id,question_key),
 CONSTRAINT fk_care_answer_assessment FOREIGN KEY(assessment_id,tenant_id)
   REFERENCES assessments(id,tenant_id),
 CONSTRAINT fk_care_answer_editor FOREIGN KEY(edited_by) REFERENCES users(id)
) ENGINE=InnoDB;
