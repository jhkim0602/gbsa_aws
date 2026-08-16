-- Remove local browser-test and parity positions, keeping only the seeded demo position.
-- Children are deleted before parents because every FK uses NO ACTION.
BEGIN;

CREATE TEMP TABLE doomed_positions AS
SELECT position_id
FROM positions
WHERE title <> '로컬 데모 백엔드 엔지니어';

CREATE TEMP TABLE doomed_versions AS
SELECT competency_model_version_id
FROM competency_model_versions
WHERE position_id IN (SELECT position_id FROM doomed_positions);

CREATE TEMP TABLE doomed_invitations AS
SELECT invitation_id
FROM invitations
WHERE position_id IN (SELECT position_id FROM doomed_positions);

CREATE TEMP TABLE doomed_sessions AS
SELECT interview_session_id
FROM interview_sessions
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);

CREATE TEMP TABLE doomed_submissions AS
SELECT submission_id
FROM submissions
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);

-- Interview turn and report leaves.
DELETE FROM question_source_references
WHERE interview_session_id IN (SELECT interview_session_id FROM doomed_sessions);
DELETE FROM question_rationales
WHERE interview_session_id IN (SELECT interview_session_id FROM doomed_sessions);
DELETE FROM interview_turns
WHERE interview_session_id IN (SELECT interview_session_id FROM doomed_sessions);
DELETE FROM interview_command_results
WHERE interview_session_id IN (SELECT interview_session_id FROM doomed_sessions);
DELETE FROM recording_chunks
WHERE interview_session_id IN (SELECT interview_session_id FROM doomed_sessions);
DELETE FROM recording_assets
WHERE interview_session_id IN (SELECT interview_session_id FROM doomed_sessions);
DELETE FROM equipment_checks
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);
DELETE FROM interview_strategies
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);
DELETE FROM interview_sessions
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);

-- Reporting and human review leaves.
DELETE FROM evidence
WHERE report_item_id IN (
  SELECT report_item_id FROM report_items
  WHERE report_id IN (
    SELECT report_id FROM reports
    WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations)
  )
);
DELETE FROM report_items
WHERE report_id IN (
  SELECT report_id FROM reports
  WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations)
);
DELETE FROM human_reviews
WHERE report_id IN (
  SELECT report_id FROM reports
  WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations)
);
DELETE FROM reports
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);

-- Submission analysis leaves.
DELETE FROM claim_conflicts
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);
DELETE FROM candidate_claims
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);
DELETE FROM candidate_verification_maps
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);
DELETE FROM verification_targets
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);
DELETE FROM retrieval_documents
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);
DELETE FROM candidate_code_units
WHERE git_commit_analysis_id IN (
  SELECT git_commit_analysis_id FROM git_commit_analyses
  WHERE repository_analysis_id IN (
    SELECT repository_analysis_id FROM git_repository_analyses
    WHERE submission_id IN (SELECT submission_id FROM doomed_submissions)
  )
);
DELETE FROM git_commit_analyses
WHERE repository_analysis_id IN (
  SELECT repository_analysis_id FROM git_repository_analyses
  WHERE submission_id IN (SELECT submission_id FROM doomed_submissions)
);
DELETE FROM git_repository_analyses
WHERE submission_id IN (SELECT submission_id FROM doomed_submissions);
DELETE FROM submissions
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);
DELETE FROM submission_upload_intents
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);

-- Applicant access and consent leaves.
DELETE FROM applicant_access_sessions
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);
DELETE FROM applicant_access_tokens
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);
DELETE FROM consent_records
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);
DELETE FROM applicant_profiles
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);
DELETE FROM invitation_state_history
WHERE invitation_id IN (SELECT invitation_id FROM doomed_invitations);

-- Company management parents.
DELETE FROM invitations
WHERE position_id IN (SELECT position_id FROM doomed_positions);
DELETE FROM evaluation_criteria
WHERE competency_model_version_id IN (SELECT competency_model_version_id FROM doomed_versions);
DELETE FROM job_requirements
WHERE competency_model_version_id IN (SELECT competency_model_version_id FROM doomed_versions);
DELETE FROM competency_model_versions
WHERE position_id IN (SELECT position_id FROM doomed_positions);
DELETE FROM positions
WHERE position_id IN (SELECT position_id FROM doomed_positions);

COMMIT;
