-- Progress 07 immutable-audit privilege policy. Apply as a privileged migration/operator step.
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_events FROM PUBLIC;
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_events FROM sip;
GRANT SELECT, INSERT ON TABLE audit_events TO sip;
-- PostgreSQL superusers and object owners remain outside SQL-level denial; production
-- deployment must use a distinct owner role unavailable to application workloads.
