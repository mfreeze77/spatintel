"""Collaboration, notifications, and deletion requests.

Generated once from the v1.1.0 canonical schema and retained as append-only DDL.
"""
from __future__ import annotations

import os
from alembic import op

revision = '0003_collaboration_notifications'
down_revision = '0002_scene_verticals'
branch_labels = None
depends_on = None

SQL = {'postgresql': ['CREATE TABLE collaboration_comments (\n'
                '\tcomment_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tscene_commit_id VARCHAR(64), \n'
                '\tentity_id VARCHAR(64), \n'
                '\tanchor_json JSON, \n'
                '\tbody TEXT NOT NULL, \n'
                '\tbody_hash VARCHAR(64) NOT NULL, \n'
                '\tauthor_id VARCHAR(128) NOT NULL, \n'
                '\tsupersedes_comment_id VARCHAR(64), \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (comment_id)\n'
                ')',
                'CREATE INDEX ix_collaboration_comments_entity_id ON collaboration_comments (entity_id)',
                'CREATE INDEX ix_collaboration_comments_project_id ON collaboration_comments (project_id)',
                'CREATE INDEX ix_collaboration_comments_scene_commit_id ON collaboration_comments (scene_commit_id)',
                'CREATE INDEX ix_collaboration_comments_tenant_id ON collaboration_comments (tenant_id)',
                'CREATE TABLE collaboration_tasks (\n'
                '\ttask_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tentity_id VARCHAR(64), \n'
                '\tstate VARCHAR(32) NOT NULL, \n'
                '\tpriority VARCHAR(32) NOT NULL, \n'
                '\ttitle VARCHAR(512) NOT NULL, \n'
                '\tdescription TEXT NOT NULL, \n'
                '\tassignee_id VARCHAR(128), \n'
                '\tdue_at TIMESTAMP WITH TIME ZONE, \n'
                '\tcreated_by VARCHAR(128) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (task_id)\n'
                ')',
                'CREATE INDEX ix_collaboration_tasks_entity_id ON collaboration_tasks (entity_id)',
                'CREATE INDEX ix_collaboration_tasks_project_id ON collaboration_tasks (project_id)',
                'CREATE INDEX ix_collaboration_tasks_tenant_id ON collaboration_tasks (tenant_id)',
                'CREATE TABLE notifications (\n'
                '\tnotification_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\trecipient_id VARCHAR(128) NOT NULL, \n'
                '\tchannel VARCHAR(32) NOT NULL, \n'
                '\ttemplate_id VARCHAR(128) NOT NULL, \n'
                '\tpayload_json JSON NOT NULL, \n'
                '\tsensitive BOOLEAN NOT NULL, \n'
                '\tstate VARCHAR(32) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (notification_id)\n'
                ')',
                'CREATE INDEX ix_notifications_project_id ON notifications (project_id)',
                'CREATE INDEX ix_notifications_recipient_id ON notifications (recipient_id)',
                'CREATE INDEX ix_notifications_tenant_id ON notifications (tenant_id)',
                'CREATE TABLE deletion_requests (\n'
                '\tdeletion_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tresource_type VARCHAR(128) NOT NULL, \n'
                '\tresource_id VARCHAR(128) NOT NULL, \n'
                '\tdry_run_report JSON NOT NULL, \n'
                '\tbackup_reference VARCHAR(64) NOT NULL, \n'
                '\tstate VARCHAR(32) NOT NULL, \n'
                '\trequested_by VARCHAR(128) NOT NULL, \n'
                '\tapproved_by VARCHAR(128), \n'
                '\texecuted_by VARCHAR(128), \n'
                '\trequested_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tapproved_at TIMESTAMP WITH TIME ZONE, \n'
                '\texecuted_at TIMESTAMP WITH TIME ZONE, \n'
                '\tPRIMARY KEY (deletion_id)\n'
                ')',
                'CREATE INDEX ix_deletion_requests_project_id ON deletion_requests (project_id)',
                'CREATE INDEX ix_deletion_requests_tenant_id ON deletion_requests (tenant_id)',
                'ALTER TABLE projects ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY projects_tenant_isolation ON projects USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE identities ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY identities_tenant_isolation ON identities USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE role_bindings ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY role_bindings_tenant_isolation ON role_bindings USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE asset_refs ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY asset_refs_tenant_isolation ON asset_refs USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY audit_events_tenant_isolation ON audit_events USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE operations ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY operations_tenant_isolation ON operations USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY outbox_events_tenant_isolation ON outbox_events USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE coordinate_frames ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY coordinate_frames_tenant_isolation ON coordinate_frames USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE scene_commits ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY scene_commits_tenant_isolation ON scene_commits USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE scene_branches ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY scene_branches_tenant_isolation ON scene_branches USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE scene_entities ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY scene_entities_tenant_isolation ON scene_entities USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE representations ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY representations_tenant_isolation ON representations USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE representation_bindings ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY representation_bindings_tenant_isolation ON representation_bindings USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE measurements ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY measurements_tenant_isolation ON measurements USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE consent_grants ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY consent_grants_tenant_isolation ON consent_grants USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE search_documents ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY search_documents_tenant_isolation ON search_documents USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE exports ENABLE ROW LEVEL SECURITY',
                "CREATE POLICY exports_tenant_isolation ON exports USING (tenant_id = current_setting('sip.tenant_id', "
                "true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', true))",
                'ALTER TABLE construction_records ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY construction_records_tenant_isolation ON construction_records USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE memory_records ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY memory_records_tenant_isolation ON memory_records USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE collaboration_comments ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY collaboration_comments_tenant_isolation ON collaboration_comments USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE collaboration_tasks ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY collaboration_tasks_tenant_isolation ON collaboration_tasks USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE notifications ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY notifications_tenant_isolation ON notifications USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))',
                'ALTER TABLE deletion_requests ENABLE ROW LEVEL SECURITY',
                'CREATE POLICY deletion_requests_tenant_isolation ON deletion_requests USING (tenant_id = '
                "current_setting('sip.tenant_id', true)) WITH CHECK (tenant_id = current_setting('sip.tenant_id', "
                'true))'],
 'sqlite': ['CREATE TABLE collaboration_comments (\n'
            '\tcomment_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tscene_commit_id VARCHAR(64), \n'
            '\tentity_id VARCHAR(64), \n'
            '\tanchor_json JSON, \n'
            '\tbody TEXT NOT NULL, \n'
            '\tbody_hash VARCHAR(64) NOT NULL, \n'
            '\tauthor_id VARCHAR(128) NOT NULL, \n'
            '\tsupersedes_comment_id VARCHAR(64), \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (comment_id)\n'
            ')',
            'CREATE INDEX ix_collaboration_comments_entity_id ON collaboration_comments (entity_id)',
            'CREATE INDEX ix_collaboration_comments_project_id ON collaboration_comments (project_id)',
            'CREATE INDEX ix_collaboration_comments_scene_commit_id ON collaboration_comments (scene_commit_id)',
            'CREATE INDEX ix_collaboration_comments_tenant_id ON collaboration_comments (tenant_id)',
            'CREATE TABLE collaboration_tasks (\n'
            '\ttask_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tentity_id VARCHAR(64), \n'
            '\tstate VARCHAR(32) NOT NULL, \n'
            '\tpriority VARCHAR(32) NOT NULL, \n'
            '\ttitle VARCHAR(512) NOT NULL, \n'
            '\tdescription TEXT NOT NULL, \n'
            '\tassignee_id VARCHAR(128), \n'
            '\tdue_at DATETIME, \n'
            '\tcreated_by VARCHAR(128) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (task_id)\n'
            ')',
            'CREATE INDEX ix_collaboration_tasks_entity_id ON collaboration_tasks (entity_id)',
            'CREATE INDEX ix_collaboration_tasks_project_id ON collaboration_tasks (project_id)',
            'CREATE INDEX ix_collaboration_tasks_tenant_id ON collaboration_tasks (tenant_id)',
            'CREATE TABLE notifications (\n'
            '\tnotification_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\trecipient_id VARCHAR(128) NOT NULL, \n'
            '\tchannel VARCHAR(32) NOT NULL, \n'
            '\ttemplate_id VARCHAR(128) NOT NULL, \n'
            '\tpayload_json JSON NOT NULL, \n'
            '\tsensitive BOOLEAN NOT NULL, \n'
            '\tstate VARCHAR(32) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (notification_id)\n'
            ')',
            'CREATE INDEX ix_notifications_project_id ON notifications (project_id)',
            'CREATE INDEX ix_notifications_recipient_id ON notifications (recipient_id)',
            'CREATE INDEX ix_notifications_tenant_id ON notifications (tenant_id)',
            'CREATE TABLE deletion_requests (\n'
            '\tdeletion_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tresource_type VARCHAR(128) NOT NULL, \n'
            '\tresource_id VARCHAR(128) NOT NULL, \n'
            '\tdry_run_report JSON NOT NULL, \n'
            '\tbackup_reference VARCHAR(64) NOT NULL, \n'
            '\tstate VARCHAR(32) NOT NULL, \n'
            '\trequested_by VARCHAR(128) NOT NULL, \n'
            '\tapproved_by VARCHAR(128), \n'
            '\texecuted_by VARCHAR(128), \n'
            '\trequested_at DATETIME NOT NULL, \n'
            '\tapproved_at DATETIME, \n'
            '\texecuted_at DATETIME, \n'
            '\tPRIMARY KEY (deletion_id)\n'
            ')',
            'CREATE INDEX ix_deletion_requests_project_id ON deletion_requests (project_id)',
            'CREATE INDEX ix_deletion_requests_tenant_id ON deletion_requests (tenant_id)']}

DROP_TABLES = ['deletion_requests', 'notifications', 'collaboration_tasks', 'collaboration_comments']

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
