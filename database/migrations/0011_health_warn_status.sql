-- "warn": the check works but reports an advisory (e.g. pending OS updates). Existing rows are untouched.
ALTER TABLE project_health_results DROP CONSTRAINT project_health_results_status_check;
ALTER TABLE project_health_results ADD CONSTRAINT project_health_results_status_check
 CHECK (status IN ('pass','warn','fail','unknown','skipped'));
