"""Retention, legal hold, backup rehearsal, key rotation, quota, and erasure evidence.

Append-only SIP v1.1.0 operational-control migration.
"""
from __future__ import annotations

import os
from alembic import op

revision = "0004_lifecycle_recovery_controls"
down_revision = "0003_collaboration_notifications"
branch_labels = None
depends_on = None

SQL = {'postgresql': ['CREATE TABLE retention_rules (\n'
                '\tretention_rule_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64), \n'
                '\tretention_class VARCHAR(64) NOT NULL, \n'
                '\tpolicy_source TEXT NOT NULL, \n'
                '\tminimum_days INTEGER NOT NULL, \n'
                '\tmaximum_days INTEGER, \n'
                '\tbackup_expiry_days INTEGER NOT NULL, \n'
                '\tdeletion_mode VARCHAR(32) NOT NULL, \n'
                '\tactive BOOLEAN NOT NULL, \n'
                '\tversion INTEGER NOT NULL, \n'
                '\tcreated_by VARCHAR(128) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (retention_rule_id), \n'
                '\tCONSTRAINT uq_retention_rule_version UNIQUE (tenant_id, project_id, retention_class, version), \n'
                '\tFOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT, \n'
                '\tFOREIGN KEY(project_id) REFERENCES projects (project_id) ON DELETE RESTRICT\n'
                ')',
                'CREATE INDEX ix_retention_rules_project_id ON retention_rules (project_id)',
                'CREATE INDEX ix_retention_rules_tenant_id ON retention_rules (tenant_id)',
                'CREATE TABLE legal_holds (\n'
                '\thold_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tresource_type VARCHAR(128) NOT NULL, \n'
                '\tresource_id VARCHAR(128) NOT NULL, \n'
                '\treason TEXT NOT NULL, \n'
                '\tauthority_reference TEXT NOT NULL, \n'
                '\tstate VARCHAR(32) NOT NULL, \n'
                '\tplaced_by VARCHAR(128) NOT NULL, \n'
                '\tplaced_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\treleased_by VARCHAR(128), \n'
                '\treleased_at TIMESTAMP WITH TIME ZONE, \n'
                '\tPRIMARY KEY (hold_id), \n'
                '\tFOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT, \n'
                '\tFOREIGN KEY(project_id) REFERENCES projects (project_id) ON DELETE RESTRICT\n'
                ')',
                'CREATE INDEX ix_legal_hold_resource ON legal_holds (tenant_id, project_id, resource_type, resource_id)',
                'CREATE INDEX ix_legal_holds_project_id ON legal_holds (project_id)',
                'CREATE INDEX ix_legal_holds_tenant_id ON legal_holds (tenant_id)',
                'CREATE TABLE backup_runs (\n'
                '\tbackup_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64), \n'
                '\tprofile VARCHAR(64) NOT NULL, \n'
                '\tbackup_path TEXT NOT NULL, \n'
                '\troot_hash VARCHAR(64) NOT NULL, \n'
                '\tschema_fingerprint VARCHAR(64) NOT NULL, \n'
                '\tstate VARCHAR(32) NOT NULL, \n'
                '\tcreated_by VARCHAR(128) NOT NULL, \n'
                '\tevidence JSON NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tverified_at TIMESTAMP WITH TIME ZONE, \n'
                '\trestore_rehearsed_at TIMESTAMP WITH TIME ZONE, \n'
                '\tPRIMARY KEY (backup_id)\n'
                ')',
                'CREATE INDEX ix_backup_runs_tenant_id ON backup_runs (tenant_id)',
                'CREATE TABLE deletion_evidence (\n'
                '\tevidence_id VARCHAR(64) NOT NULL, \n'
                '\tdeletion_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tresource_type VARCHAR(128) NOT NULL, \n'
                '\tresource_id VARCHAR(128) NOT NULL, \n'
                '\taction VARCHAR(64) NOT NULL, \n'
                '\taffected_references JSON NOT NULL, \n'
                '\tkey_ids JSON NOT NULL, \n'
                '\tresidual_locations JSON NOT NULL, \n'
                '\tbackup_expiry_deadline TIMESTAMP WITH TIME ZONE, \n'
                '\tevidence_hash VARCHAR(64) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (evidence_id), \n'
                '\tFOREIGN KEY(deletion_id) REFERENCES deletion_requests (deletion_id) ON DELETE RESTRICT\n'
                ')',
                'CREATE INDEX ix_deletion_evidence_deletion_id ON deletion_evidence (deletion_id)',
                'CREATE INDEX ix_deletion_evidence_project_id ON deletion_evidence (project_id)',
                'CREATE INDEX ix_deletion_evidence_tenant_id ON deletion_evidence (tenant_id)',
                'CREATE TABLE key_rotations (\n'
                '\trotation_id VARCHAR(64) NOT NULL, \n'
                '\told_key_id VARCHAR(128) NOT NULL, \n'
                '\tnew_key_id VARCHAR(128) NOT NULL, \n'
                '\tobject_count INTEGER NOT NULL, \n'
                '\tciphertext_unchanged BOOLEAN NOT NULL, \n'
                '\tevidence_hash VARCHAR(64) NOT NULL, \n'
                '\tstate VARCHAR(32) NOT NULL, \n'
                '\trotated_by VARCHAR(128) NOT NULL, \n'
                '\trotated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tretired_key_destroyed_at TIMESTAMP WITH TIME ZONE, \n'
                '\tPRIMARY KEY (rotation_id)\n'
                ')',
                'CREATE TABLE quota_policies (\n'
                '\tquota_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64), \n'
                '\tresource_type VARCHAR(64) NOT NULL, \n'
                '\tunit VARCHAR(32) NOT NULL, \n'
                '\tperiod_seconds INTEGER NOT NULL, \n'
                '\tsoft_limit FLOAT NOT NULL, \n'
                '\thard_limit FLOAT NOT NULL, \n'
                '\tactive BOOLEAN NOT NULL, \n'
                '\tcreated_by VARCHAR(128) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (quota_id), \n'
                '\tCONSTRAINT uq_quota_scope_resource UNIQUE (tenant_id, project_id, resource_type)\n'
                ')',
                'CREATE INDEX ix_quota_policies_project_id ON quota_policies (project_id)',
                'CREATE INDEX ix_quota_policies_tenant_id ON quota_policies (tenant_id)',
                'CREATE TABLE usage_ledger (\n'
                '\tusage_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\toperation_id VARCHAR(64), \n'
                '\tresource_type VARCHAR(64) NOT NULL, \n'
                '\tquantity FLOAT NOT NULL, \n'
                '\tunit VARCHAR(32) NOT NULL, \n'
                '\tunit_cost FLOAT NOT NULL, \n'
                '\tcurrency VARCHAR(3) NOT NULL, \n'
                '\tprice_source_version VARCHAR(128) NOT NULL, \n'
                '\testimated BOOLEAN NOT NULL, \n'
                '\tmetadata_json JSON NOT NULL, \n'
                '\toccurred_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (usage_id)\n'
                ')',
                'CREATE INDEX ix_usage_ledger_operation_id ON usage_ledger (operation_id)',
                'CREATE INDEX ix_usage_ledger_project_id ON usage_ledger (project_id)',
                'CREATE INDEX ix_usage_ledger_tenant_id ON usage_ledger (tenant_id)'],
 'sqlite': ['CREATE TABLE retention_rules (\n'
            '\tretention_rule_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64), \n'
            '\tretention_class VARCHAR(64) NOT NULL, \n'
            '\tpolicy_source TEXT NOT NULL, \n'
            '\tminimum_days INTEGER NOT NULL, \n'
            '\tmaximum_days INTEGER, \n'
            '\tbackup_expiry_days INTEGER NOT NULL, \n'
            '\tdeletion_mode VARCHAR(32) NOT NULL, \n'
            '\tactive BOOLEAN NOT NULL, \n'
            '\tversion INTEGER NOT NULL, \n'
            '\tcreated_by VARCHAR(128) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (retention_rule_id), \n'
            '\tCONSTRAINT uq_retention_rule_version UNIQUE (tenant_id, project_id, retention_class, version), \n'
            '\tFOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT, \n'
            '\tFOREIGN KEY(project_id) REFERENCES projects (project_id) ON DELETE RESTRICT\n'
            ')',
            'CREATE INDEX ix_retention_rules_project_id ON retention_rules (project_id)',
            'CREATE INDEX ix_retention_rules_tenant_id ON retention_rules (tenant_id)',
            'CREATE TABLE legal_holds (\n'
            '\thold_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tresource_type VARCHAR(128) NOT NULL, \n'
            '\tresource_id VARCHAR(128) NOT NULL, \n'
            '\treason TEXT NOT NULL, \n'
            '\tauthority_reference TEXT NOT NULL, \n'
            '\tstate VARCHAR(32) NOT NULL, \n'
            '\tplaced_by VARCHAR(128) NOT NULL, \n'
            '\tplaced_at DATETIME NOT NULL, \n'
            '\treleased_by VARCHAR(128), \n'
            '\treleased_at DATETIME, \n'
            '\tPRIMARY KEY (hold_id), \n'
            '\tFOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT, \n'
            '\tFOREIGN KEY(project_id) REFERENCES projects (project_id) ON DELETE RESTRICT\n'
            ')',
            'CREATE INDEX ix_legal_hold_resource ON legal_holds (tenant_id, project_id, resource_type, resource_id)',
            'CREATE INDEX ix_legal_holds_project_id ON legal_holds (project_id)',
            'CREATE INDEX ix_legal_holds_tenant_id ON legal_holds (tenant_id)',
            'CREATE TABLE backup_runs (\n'
            '\tbackup_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64), \n'
            '\tprofile VARCHAR(64) NOT NULL, \n'
            '\tbackup_path TEXT NOT NULL, \n'
            '\troot_hash VARCHAR(64) NOT NULL, \n'
            '\tschema_fingerprint VARCHAR(64) NOT NULL, \n'
            '\tstate VARCHAR(32) NOT NULL, \n'
            '\tcreated_by VARCHAR(128) NOT NULL, \n'
            '\tevidence JSON NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tverified_at DATETIME, \n'
            '\trestore_rehearsed_at DATETIME, \n'
            '\tPRIMARY KEY (backup_id)\n'
            ')',
            'CREATE INDEX ix_backup_runs_tenant_id ON backup_runs (tenant_id)',
            'CREATE TABLE deletion_evidence (\n'
            '\tevidence_id VARCHAR(64) NOT NULL, \n'
            '\tdeletion_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tresource_type VARCHAR(128) NOT NULL, \n'
            '\tresource_id VARCHAR(128) NOT NULL, \n'
            '\taction VARCHAR(64) NOT NULL, \n'
            '\taffected_references JSON NOT NULL, \n'
            '\tkey_ids JSON NOT NULL, \n'
            '\tresidual_locations JSON NOT NULL, \n'
            '\tbackup_expiry_deadline DATETIME, \n'
            '\tevidence_hash VARCHAR(64) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (evidence_id), \n'
            '\tFOREIGN KEY(deletion_id) REFERENCES deletion_requests (deletion_id) ON DELETE RESTRICT\n'
            ')',
            'CREATE INDEX ix_deletion_evidence_deletion_id ON deletion_evidence (deletion_id)',
            'CREATE INDEX ix_deletion_evidence_project_id ON deletion_evidence (project_id)',
            'CREATE INDEX ix_deletion_evidence_tenant_id ON deletion_evidence (tenant_id)',
            'CREATE TABLE key_rotations (\n'
            '\trotation_id VARCHAR(64) NOT NULL, \n'
            '\told_key_id VARCHAR(128) NOT NULL, \n'
            '\tnew_key_id VARCHAR(128) NOT NULL, \n'
            '\tobject_count INTEGER NOT NULL, \n'
            '\tciphertext_unchanged BOOLEAN NOT NULL, \n'
            '\tevidence_hash VARCHAR(64) NOT NULL, \n'
            '\tstate VARCHAR(32) NOT NULL, \n'
            '\trotated_by VARCHAR(128) NOT NULL, \n'
            '\trotated_at DATETIME NOT NULL, \n'
            '\tretired_key_destroyed_at DATETIME, \n'
            '\tPRIMARY KEY (rotation_id)\n'
            ')',
            'CREATE TABLE quota_policies (\n'
            '\tquota_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64), \n'
            '\tresource_type VARCHAR(64) NOT NULL, \n'
            '\tunit VARCHAR(32) NOT NULL, \n'
            '\tperiod_seconds INTEGER NOT NULL, \n'
            '\tsoft_limit FLOAT NOT NULL, \n'
            '\thard_limit FLOAT NOT NULL, \n'
            '\tactive BOOLEAN NOT NULL, \n'
            '\tcreated_by VARCHAR(128) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (quota_id), \n'
            '\tCONSTRAINT uq_quota_scope_resource UNIQUE (tenant_id, project_id, resource_type)\n'
            ')',
            'CREATE INDEX ix_quota_policies_project_id ON quota_policies (project_id)',
            'CREATE INDEX ix_quota_policies_tenant_id ON quota_policies (tenant_id)',
            'CREATE TABLE usage_ledger (\n'
            '\tusage_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\toperation_id VARCHAR(64), \n'
            '\tresource_type VARCHAR(64) NOT NULL, \n'
            '\tquantity FLOAT NOT NULL, \n'
            '\tunit VARCHAR(32) NOT NULL, \n'
            '\tunit_cost FLOAT NOT NULL, \n'
            '\tcurrency VARCHAR(3) NOT NULL, \n'
            '\tprice_source_version VARCHAR(128) NOT NULL, \n'
            '\testimated BOOLEAN NOT NULL, \n'
            '\tmetadata_json JSON NOT NULL, \n'
            '\toccurred_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (usage_id)\n'
            ')',
            'CREATE INDEX ix_usage_ledger_operation_id ON usage_ledger (operation_id)',
            'CREATE INDEX ix_usage_ledger_project_id ON usage_ledger (project_id)',
            'CREATE INDEX ix_usage_ledger_tenant_id ON usage_ledger (tenant_id)']}

DROP_TABLES = [
    "usage_ledger",
    "quota_policies",
    "key_rotations",
    "deletion_evidence",
    "backup_runs",
    "legal_holds",
    "retention_rules",
]

def upgrade() -> None:
    name = op.get_bind().dialect.name
    family = "postgresql" if name == "postgresql" else "sqlite" if name == "sqlite" else None
    if family is None:
        raise RuntimeError(f"unsupported migration dialect: {name}")
    for statement in SQL[family]:
        op.execute(statement)

def downgrade() -> None:
    if os.environ.get("SIP_ALLOW_DESTRUCTIVE_DOWNGRADE") != "1":
        raise RuntimeError(
            "destructive downgrade denied; restore a verified backup or set "
            "SIP_ALLOW_DESTRUCTIVE_DOWNGRADE=1 in an isolated rehearsal"
        )
    for table in DROP_TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
