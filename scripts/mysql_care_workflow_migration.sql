-- Neuro-Diagnosis: care journey foundation (MySQL 8, ADDITIVE, repeatable).
-- Apply only after verified backup, before new Flask code is brought up.
-- Portal access remains DISABLED until guardian verification/consent is implemented.
USE neuro_diagnosis;

CREATE TABLE IF NOT EXISTS care_client_contacts (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT UNSIGNED NOT NULL,
  client_id BIGINT UNSIGNED NOT NULL,
  professional_user_id BIGINT UNSIGNED NOT NULL,
  full_name VARCHAR(160) NOT NULL,
  contact_role ENUM('legal_guardian','authorized_contact') NOT NULL,
  email VARCHAR(254) NULL,
  verification_status ENUM('unverified','verified','revoked') NOT NULL DEFAULT 'unverified',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_care_contacts_client (tenant_id,client_id,professional_user_id),
  UNIQUE KEY uq_care_contact_all_scope (id,tenant_id,client_id,professional_user_id),
  CONSTRAINT fk_care_contact_client FOREIGN KEY (client_id,tenant_id)
      REFERENCES clients(id,tenant_id),
  CONSTRAINT fk_care_contact_member FOREIGN KEY (tenant_id,professional_user_id)
      REFERENCES tenant_members(tenant_id,user_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS care_appointments (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT UNSIGNED NOT NULL,
  client_id BIGINT UNSIGNED NOT NULL,
  professional_user_id BIGINT UNSIGNED NOT NULL,
  request_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  service_type ENUM('initial','follow_up','assessment','feedback') NOT NULL,
  modality ENUM('in_person','remote') NOT NULL DEFAULT 'in_person',
  timezone_name VARCHAR(60) NOT NULL DEFAULT 'America/Fortaleza',
  starts_at_utc DATETIME NOT NULL,
  ends_at_utc DATETIME NOT NULL,
  status ENUM('scheduled','confirmed','completed','cancelled','no_show') NOT NULL DEFAULT 'scheduled',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_care_request (tenant_id,professional_user_id,request_id),
  UNIQUE KEY uq_care_appointment_scope (id,tenant_id),
  UNIQUE KEY uq_care_appointment_full_scope (id,tenant_id,client_id,professional_user_id),
  KEY ix_care_professional_schedule (tenant_id,professional_user_id,starts_at_utc),
  KEY ix_care_client_schedule (tenant_id,client_id,starts_at_utc),
  CONSTRAINT chk_care_interval CHECK (ends_at_utc > starts_at_utc),
  CONSTRAINT fk_care_appt_client FOREIGN KEY(client_id,tenant_id)
      REFERENCES clients(id,tenant_id),
  CONSTRAINT fk_care_appt_member FOREIGN KEY(tenant_id,professional_user_id)
      REFERENCES tenant_members(tenant_id,user_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS care_encounters (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT UNSIGNED NOT NULL,
  appointment_id BIGINT UNSIGNED NOT NULL,
  client_id BIGINT UNSIGNED NOT NULL,
  professional_user_id BIGINT UNSIGNED NOT NULL,
  status ENUM('draft','signed') NOT NULL DEFAULT 'draft',
  opened_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  signed_at DATETIME NULL,
  UNIQUE KEY uq_care_encounter_appointment (appointment_id),
  KEY ix_care_encounters_prof (tenant_id,professional_user_id,opened_at),
  CONSTRAINT fk_care_encounter_appt FOREIGN KEY(appointment_id,tenant_id,client_id,professional_user_id)
      REFERENCES care_appointments(id,tenant_id,client_id,professional_user_id),
  CONSTRAINT fk_care_encounter_client FOREIGN KEY(client_id,tenant_id)
      REFERENCES clients(id,tenant_id),
  CONSTRAINT fk_care_encounter_member FOREIGN KEY(tenant_id,professional_user_id)
      REFERENCES tenant_members(tenant_id,user_id)
) ENGINE=InnoDB;


-- Professional availability + patient requests, no public or unverified access.
-- A slot is a clinician-owned availability window; confirmed requests create
-- a normal care_appointments row while preserving immutable history.
CREATE TABLE IF NOT EXISTS care_schedule_slots (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT UNSIGNED NOT NULL,
  professional_user_id BIGINT UNSIGNED NOT NULL,
  starts_at_utc DATETIME NOT NULL,
  ends_at_utc DATETIME NOT NULL,
  service_type ENUM('initial','follow_up','assessment','feedback') NOT NULL,
  modality ENUM('in_person','remote') NOT NULL DEFAULT 'in_person',
  status ENUM('open','pending','booked','closed') NOT NULL DEFAULT 'open',
  pending_user_id BIGINT UNSIGNED NULL,
  pending_client_id BIGINT UNSIGNED NULL,
  requested_at DATETIME NULL,
  appointment_id BIGINT UNSIGNED NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY ix_schedule_slot_start (tenant_id,professional_user_id,starts_at_utc),
  KEY ix_schedule_bookable (tenant_id,professional_user_id,status,starts_at_utc),
  KEY ix_schedule_patient (pending_user_id,pending_client_id,status),
  CONSTRAINT chk_schedule_slot_interval CHECK (ends_at_utc>starts_at_utc),
  CONSTRAINT chk_schedule_slot_state CHECK (
    (status IN ('open','closed') AND pending_user_id IS NULL
     AND pending_client_id IS NULL AND appointment_id IS NULL)
    OR (status='pending' AND pending_user_id IS NOT NULL
        AND pending_client_id IS NOT NULL AND appointment_id IS NULL)
    OR (status='booked' AND pending_user_id IS NOT NULL
        AND pending_client_id IS NOT NULL AND appointment_id IS NOT NULL)),
  CONSTRAINT fk_schedule_member FOREIGN KEY(tenant_id,professional_user_id)
    REFERENCES tenant_members(tenant_id,user_id),
  CONSTRAINT fk_schedule_patient_user FOREIGN KEY(pending_user_id)
    REFERENCES users(id),
  CONSTRAINT fk_schedule_patient FOREIGN KEY(pending_client_id,tenant_id)
    REFERENCES clients(id,tenant_id),
  CONSTRAINT fk_schedule_appointment FOREIGN KEY(appointment_id,tenant_id)
    REFERENCES care_appointments(id,tenant_id)
) ENGINE=InnoDB;
