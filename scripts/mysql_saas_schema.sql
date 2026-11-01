-- Neuro-Diagnosis SaaS | MySQL 8.4 / InnoDB | Schema v1
-- Execucao local, sem conversao automatica do SQLite existente.
-- Um tenant por profissional por padrao; administradora pode ter tenant proprio.
-- Registros clinicos sao privados, inclusive de outros profissionais.
CREATE DATABASE IF NOT EXISTS neuro_diagnosis
    CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE neuro_diagnosis;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(160) NOT NULL,
    email VARCHAR(254) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    global_role ENUM('superadmin','admin','professional','patient') NOT NULL DEFAULT 'patient',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_users_email(email)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS tenants (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(180) NOT NULL,
    slug VARCHAR(120) NOT NULL,
    owner_user_id BIGINT UNSIGNED NOT NULL,
    status ENUM('pending','active','suspended') NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_tenants_slug (slug),
    KEY ix_tenants_owner (owner_user_id),
    CONSTRAINT fk_tenants_owner FOREIGN KEY (owner_user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS tenant_members (
    tenant_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    membership_role ENUM('owner','professional','assistant','patient') NOT NULL,
    status ENUM('active','pending','suspended') NOT NULL DEFAULT 'active',
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(tenant_id,user_id),
    KEY ix_tenant_members_user(user_id,status),
    CONSTRAINT fk_tenant_members_tenant FOREIGN KEY(tenant_id) REFERENCES tenants(id),
    CONSTRAINT fk_tenant_members_user FOREIGN KEY(user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS professional_profiles (
    user_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    profession ENUM('psicologo','neuropsicopedagogo','outro') NOT NULL,
    registry_code VARCHAR(100) NULL,
    verification_status ENUM('pending','verified','rejected') NOT NULL DEFAULT 'pending',
    verified_at DATETIME NULL,
    verified_by BIGINT UNSIGNED NULL,
    CONSTRAINT fk_prof_profiles_user FOREIGN KEY(user_id) REFERENCES users(id),
    CONSTRAINT fk_prof_profiles_verifier FOREIGN KEY(verified_by) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS clients (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    professional_user_id BIGINT UNSIGNED NOT NULL,
    patient_user_id BIGINT UNSIGNED NULL,
    nome VARCHAR(180) NOT NULL,
    birth_date DATE NULL,
    email VARCHAR(254) NULL,
    status ENUM('active','inactive','archived') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_client_tenant (id,tenant_id),
    KEY ix_clients_tenant_professional (tenant_id,professional_user_id,status),
    CONSTRAINT fk_clients_tenant FOREIGN KEY(tenant_id) REFERENCES tenants(id),
    CONSTRAINT fk_clients_professional FOREIGN KEY(professional_user_id) REFERENCES users(id),
    CONSTRAINT fk_clients_user FOREIGN KEY(patient_user_id) REFERENCES users(id),
    CONSTRAINT fk_clients_member FOREIGN KEY(tenant_id,professional_user_id)
        REFERENCES tenant_members(tenant_id,user_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS test_categories (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NULL,
    nome VARCHAR(160) NOT NULL,
    descricao TEXT NULL,
    created_by BIGINT UNSIGNED NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_categories_scope (tenant_id,active),
    CONSTRAINT fk_categories_tenant FOREIGN KEY(tenant_id) REFERENCES tenants(id),
    CONSTRAINT fk_categories_user FOREIGN KEY(created_by) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS tests (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NULL,
    category_id BIGINT UNSIGNED NULL,
    title VARCHAR(240) NOT NULL,
    description TEXT NULL,
    created_by BIGINT UNSIGNED NOT NULL,
    visibility ENUM('private','global') NOT NULL DEFAULT 'private',
    status ENUM('draft','pending','approved','archived') NOT NULL DEFAULT 'draft',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY ix_tests_tenant_status (tenant_id,status,active),
    KEY ix_tests_visibility (visibility,status,active),
    CONSTRAINT chk_tests_scope CHECK
        ((visibility='global' AND tenant_id IS NULL) OR
         (visibility='private' AND tenant_id IS NOT NULL)),
    CONSTRAINT fk_tests_tenant FOREIGN KEY(tenant_id) REFERENCES tenants(id),
    CONSTRAINT fk_tests_category FOREIGN KEY(category_id) REFERENCES test_categories(id),
    CONSTRAINT fk_tests_author FOREIGN KEY(created_by) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS test_versions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    test_id BIGINT UNSIGNED NOT NULL,
    version_number INT UNSIGNED NOT NULL,
    definition_json JSON NOT NULL,
    status ENUM('draft','approved','retired') NOT NULL DEFAULT 'draft',
    created_by BIGINT UNSIGNED NOT NULL,
    approved_by BIGINT UNSIGNED NULL,
    approved_at DATETIME NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_test_versions (test_id,version_number),
    CONSTRAINT fk_versions_test FOREIGN KEY(test_id) REFERENCES tests(id),
    CONSTRAINT fk_versions_author FOREIGN KEY(created_by) REFERENCES users(id),
    CONSTRAINT fk_versions_approver FOREIGN KEY(approved_by) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS assessments (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    client_id BIGINT UNSIGNED NOT NULL,
    test_version_id BIGINT UNSIGNED NOT NULL,
    responsible_user_id BIGINT UNSIGNED NOT NULL,
    status ENUM('pending','in_progress','submitted','reviewed','cancelled') NOT NULL DEFAULT 'pending',
    started_at DATETIME NULL,
    submitted_at DATETIME NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_assessment_tenant (id,tenant_id),
    KEY ix_assessments_scope (tenant_id,responsible_user_id,status),
    CONSTRAINT fk_assessments_tenant FOREIGN KEY(tenant_id) REFERENCES tenants(id),
    CONSTRAINT fk_assessments_client_same_tenant FOREIGN KEY(client_id,tenant_id)
        REFERENCES clients(id,tenant_id),
    CONSTRAINT fk_assessments_version FOREIGN KEY(test_version_id) REFERENCES test_versions(id),
    CONSTRAINT fk_assessments_member FOREIGN KEY(tenant_id,responsible_user_id)
        REFERENCES tenant_members(tenant_id,user_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS assessment_responses (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    assessment_id BIGINT UNSIGNED NOT NULL,
    question_key VARCHAR(100) NOT NULL,
    answer_json JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_answers_assessment_question(assessment_id,question_key),
    KEY ix_answers_tenant_assessment (tenant_id,assessment_id),
    CONSTRAINT fk_answers_assessment_same_tenant FOREIGN KEY(assessment_id,tenant_id)
        REFERENCES assessments(id,tenant_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS assessment_invitations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    assessment_id BIGINT UNSIGNED NOT NULL,
    token_hash CHAR(64) NOT NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_invite_token (token_hash),
    CONSTRAINT fk_invitations_assessment_same_tenant FOREIGN KEY(assessment_id,tenant_id)
        REFERENCES assessments(id,tenant_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS review_requests (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    entity_type ENUM('test','professional','other') NOT NULL,
    entity_id BIGINT UNSIGNED NOT NULL,
    action VARCHAR(80) NOT NULL,
    requested_by BIGINT UNSIGNED NOT NULL,
    status ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',
    decided_by BIGINT UNSIGNED NULL,
    decided_at DATETIME NULL,
    reason TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_review_pending (status,created_at),
    CONSTRAINT fk_reviews_tenant FOREIGN KEY(tenant_id) REFERENCES tenants(id),
    CONSTRAINT fk_reviews_requester FOREIGN KEY(requested_by) REFERENCES users(id),
    CONSTRAINT fk_reviews_decider FOREIGN KEY(decided_by) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS audit_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NULL,
    actor_id BIGINT UNSIGNED NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(80) NOT NULL,
    resource_id BIGINT UNSIGNED NULL,
    access_reason VARCHAR(500) NULL,
    outcome ENUM('allowed','denied','failed') NOT NULL,
    correlation_id CHAR(36) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_audit_tenant_time (tenant_id,created_at),
    KEY ix_audit_actor_time (actor_id,created_at),
    CONSTRAINT fk_audit_tenant FOREIGN KEY(tenant_id) REFERENCES tenants(id),
    CONSTRAINT fk_audit_actor FOREIGN KEY(actor_id) REFERENCES users(id)
) ENGINE=InnoDB;

-- Credencial somente para a aplicacao, exclusivamente neste notebook.
-- MySQL imprime a senha aleatoria uma unica vez: NAO compartilhe.
CREATE USER IF NOT EXISTS 'neuro_app'@'localhost' IDENTIFIED BY RANDOM PASSWORD;
GRANT SELECT, INSERT, UPDATE, DELETE ON neuro_diagnosis.* TO 'neuro_app'@'localhost';

SELECT 'SCHEMA_READY' AS status,
       (SELECT COUNT(*) FROM information_schema.tables
         WHERE table_schema='neuro_diagnosis' AND table_type='BASE TABLE') AS tables_created;
