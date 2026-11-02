-- Neuro-Diagnosis SaaS professional identity fields; additive and repeatable.
-- Existing professional/admin rows remain valid without details (NULL).
-- This schema must be applied before deploying code requiring these fields.
USE neuro_diagnosis;
CREATE TABLE IF NOT EXISTS professional_details (
    user_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    cpf_digest CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    cpf_encrypted VARBINARY(512) NOT NULL,
    practice_area ENUM('psicologia','neuropsicopedagogia','psiquiatria','psicopedagogia') NOT NULL,
    birth_date DATE NOT NULL,
    phone VARCHAR(11) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_professional_cpf_digest(cpf_digest),
    CONSTRAINT fk_professional_details_user FOREIGN KEY(user_id) REFERENCES users(id)
) ENGINE=InnoDB;
