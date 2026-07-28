"""Foundation and canonical control plane.

Generated once from the v1.1.0 canonical schema and retained as append-only DDL.
"""
from __future__ import annotations

import os
from alembic import op

revision = '0001_foundation_control_plane'
down_revision = None
branch_labels = None
depends_on = None

SQL = {'postgresql': ['CREATE EXTENSION IF NOT EXISTS postgis',
                'CREATE TABLE tenants (\n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tname VARCHAR(256) NOT NULL, \n'
                '\tstatus VARCHAR(32) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (tenant_id)\n'
                ')',
                'CREATE TABLE projects (\n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tname VARCHAR(256) NOT NULL, \n'
                '\tvertical VARCHAR(64) NOT NULL, \n'
                '\tclassification VARCHAR(64) NOT NULL, \n'
                '\tstatus VARCHAR(32) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (project_id), \n'
                '\tFOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT\n'
                ')',
                'CREATE INDEX ix_projects_tenant_id ON projects (tenant_id)',
                'CREATE TABLE identities (\n'
                '\tidentity_id VARCHAR(128) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tidentity_type VARCHAR(32) NOT NULL, \n'
                '\tdisplay_name VARCHAR(256) NOT NULL, \n'
                '\tdisabled BOOLEAN NOT NULL, \n'
                '\tattributes_json JSON NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (identity_id), \n'
                '\tFOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT\n'
                ')',
                'CREATE INDEX ix_identities_tenant_id ON identities (tenant_id)',
                'CREATE TABLE role_bindings (\n'
                '\tbinding_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64), \n'
                '\tidentity_id VARCHAR(128) NOT NULL, \n'
                '\trole VARCHAR(64) NOT NULL, \n'
                '\tpurposes_json JSON NOT NULL, \n'
                '\tspatial_restrictions_json JSON NOT NULL, \n'
                '\texpires_at TIMESTAMP WITH TIME ZONE, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (binding_id), \n'
                '\tFOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT, \n'
                '\tFOREIGN KEY(project_id) REFERENCES projects (project_id) ON DELETE RESTRICT, \n'
                '\tFOREIGN KEY(identity_id) REFERENCES identities (identity_id) ON DELETE RESTRICT\n'
                ')',
                'CREATE INDEX ix_role_bindings_identity_id ON role_bindings (identity_id)',
                'CREATE INDEX ix_role_bindings_project_id ON role_bindings (project_id)',
                'CREATE INDEX ix_role_bindings_tenant_id ON role_bindings (tenant_id)',
                'CREATE TABLE assets (\n'
                '\tsha256 VARCHAR(64) NOT NULL, \n'
                '\tbyte_count INTEGER NOT NULL, \n'
                '\tmedia_type VARCHAR(256) NOT NULL, \n'
                '\tstorage_key TEXT NOT NULL, \n'
                '\tencryption_metadata JSON NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (sha256)\n'
                ')',
                'CREATE TABLE asset_refs (\n'
                '\tasset_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tsha256 VARCHAR(64) NOT NULL, \n'
                '\toriginal_name VARCHAR(512) NOT NULL, \n'
                '\tclassification VARCHAR(64) NOT NULL, \n'
                '\tretention_class VARCHAR(64) NOT NULL, \n'
                '\tsource_class VARCHAR(64) NOT NULL, \n'
                '\tauthority_class VARCHAR(64) NOT NULL, \n'
                '\tprovenance_json JSON NOT NULL, \n'
                '\tlegal_hold BOOLEAN NOT NULL, \n'
                '\tcreated_by VARCHAR(128) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\ttombstoned_at TIMESTAMP WITH TIME ZONE, \n'
                '\tPRIMARY KEY (asset_id), \n'
                '\tFOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT, \n'
                '\tFOREIGN KEY(project_id) REFERENCES projects (project_id) ON DELETE RESTRICT, \n'
                '\tFOREIGN KEY(sha256) REFERENCES assets (sha256) ON DELETE RESTRICT\n'
                ')',
                'CREATE INDEX ix_asset_refs_project_id ON asset_refs (project_id)',
                'CREATE INDEX ix_asset_refs_sha256 ON asset_refs (sha256)',
                'CREATE INDEX ix_asset_refs_tenant_id ON asset_refs (tenant_id)',
                'CREATE TABLE multipart_uploads (\n'
                '\tupload_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\texpected_sha256 VARCHAR(64) NOT NULL, \n'
                '\texpected_bytes INTEGER NOT NULL, \n'
                '\tmedia_type VARCHAR(256) NOT NULL, \n'
                '\tmetadata_json JSON NOT NULL, \n'
                '\tstate VARCHAR(32) NOT NULL, \n'
                '\tcreated_by VARCHAR(128) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tcompleted_at TIMESTAMP WITH TIME ZONE, \n'
                '\tPRIMARY KEY (upload_id)\n'
                ')',
                'CREATE INDEX ix_multipart_uploads_project_id ON multipart_uploads (project_id)',
                'CREATE INDEX ix_multipart_uploads_tenant_id ON multipart_uploads (tenant_id)',
                'CREATE TABLE multipart_chunks (\n'
                '\tchunk_id VARCHAR(64) NOT NULL, \n'
                '\tupload_id VARCHAR(64) NOT NULL, \n'
                '\tpart_number INTEGER NOT NULL, \n'
                '\tsha256 VARCHAR(64) NOT NULL, \n'
                '\tbyte_count INTEGER NOT NULL, \n'
                '\tpath TEXT NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (chunk_id), \n'
                '\tCONSTRAINT uq_upload_part UNIQUE (upload_id, part_number), \n'
                '\tFOREIGN KEY(upload_id) REFERENCES multipart_uploads (upload_id) ON DELETE CASCADE\n'
                ')',
                'CREATE INDEX ix_multipart_chunks_upload_id ON multipart_chunks (upload_id)',
                'CREATE TABLE audit_events (\n'
                '\taudit_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64), \n'
                '\tactor_id VARCHAR(128) NOT NULL, \n'
                '\taction VARCHAR(128) NOT NULL, \n'
                '\tresource_type VARCHAR(128) NOT NULL, \n'
                '\tresource_id VARCHAR(128) NOT NULL, \n'
                '\toutcome VARCHAR(32) NOT NULL, \n'
                '\tdetails_json JSON NOT NULL, \n'
                '\toccurred_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tprevious_hash VARCHAR(64) NOT NULL, \n'
                '\tevent_hash VARCHAR(64) NOT NULL, \n'
                '\tsignature VARCHAR(128) NOT NULL, \n'
                '\tPRIMARY KEY (audit_id), \n'
                '\tUNIQUE (event_hash)\n'
                ')',
                'CREATE INDEX ix_audit_events_action ON audit_events (action)',
                'CREATE INDEX ix_audit_events_project_id ON audit_events (project_id)',
                'CREATE INDEX ix_audit_events_tenant_id ON audit_events (tenant_id)',
                'CREATE TABLE operations (\n'
                '\toperation_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\toperation_type VARCHAR(128) NOT NULL, \n'
                '\tidempotency_key VARCHAR(256) NOT NULL, \n'
                '\tinput_manifest_hash VARCHAR(64) NOT NULL, \n'
                '\tinput_json JSON NOT NULL, \n'
                '\tstate VARCHAR(32) NOT NULL, \n'
                '\tprogress FLOAT NOT NULL, \n'
                '\tattempt INTEGER NOT NULL, \n'
                '\tmax_attempts INTEGER NOT NULL, \n'
                '\tlease_owner VARCHAR(128), \n'
                '\tlease_expires_at TIMESTAMP WITH TIME ZONE, \n'
                '\tcheckpoint_json JSON NOT NULL, \n'
                '\toutput_json JSON NOT NULL, \n'
                '\toutput_hash VARCHAR(64), \n'
                '\terror_json JSON NOT NULL, \n'
                '\tcancel_requested BOOLEAN NOT NULL, \n'
                '\tcreated_by VARCHAR(128) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (operation_id), \n'
                '\tCONSTRAINT uq_operation_idempotency UNIQUE (tenant_id, project_id, operation_type, '
                'idempotency_key)\n'
                ')',
                'CREATE INDEX ix_operations_operation_type ON operations (operation_type)',
                'CREATE INDEX ix_operations_project_id ON operations (project_id)',
                'CREATE INDEX ix_operations_state ON operations (state)',
                'CREATE INDEX ix_operations_tenant_id ON operations (tenant_id)',
                'CREATE TABLE outbox_events (\n'
                '\tevent_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64), \n'
                '\tevent_type VARCHAR(128) NOT NULL, \n'
                '\tschema_version VARCHAR(32) NOT NULL, \n'
                '\taggregate_type VARCHAR(128) NOT NULL, \n'
                '\taggregate_id VARCHAR(128) NOT NULL, \n'
                '\tpayload_json JSON NOT NULL, \n'
                '\tpayload_hash VARCHAR(64) NOT NULL, \n'
                '\toccurred_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tpublished_at TIMESTAMP WITH TIME ZONE, \n'
                '\tdelivery_attempts INTEGER NOT NULL, \n'
                '\tPRIMARY KEY (event_id)\n'
                ')',
                'CREATE INDEX ix_outbox_events_event_type ON outbox_events (event_type)',
                'CREATE INDEX ix_outbox_events_project_id ON outbox_events (project_id)',
                'CREATE INDEX ix_outbox_events_tenant_id ON outbox_events (tenant_id)',
                'CREATE TABLE coordinate_frames (\n'
                '\tframe_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tname VARCHAR(256) NOT NULL, \n'
                '\tparent_frame_id VARCHAR(64), \n'
                '\tconvention VARCHAR(128) NOT NULL, \n'
                '\tunits VARCHAR(32) NOT NULL, \n'
                '\ttransform_json JSON, \n'
                '\tuncertainty_m FLOAT, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (frame_id)\n'
                ')',
                'CREATE INDEX ix_coordinate_frames_parent_frame_id ON coordinate_frames (parent_frame_id)',
                'CREATE INDEX ix_coordinate_frames_project_id ON coordinate_frames (project_id)',
                'CREATE INDEX ix_coordinate_frames_tenant_id ON coordinate_frames (tenant_id)'],
 'sqlite': ['CREATE TABLE tenants (\n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tname VARCHAR(256) NOT NULL, \n'
            '\tstatus VARCHAR(32) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (tenant_id)\n'
            ')',
            'CREATE TABLE projects (\n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tname VARCHAR(256) NOT NULL, \n'
            '\tvertical VARCHAR(64) NOT NULL, \n'
            '\tclassification VARCHAR(64) NOT NULL, \n'
            '\tstatus VARCHAR(32) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (project_id), \n'
            '\tFOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT\n'
            ')',
            'CREATE INDEX ix_projects_tenant_id ON projects (tenant_id)',
            'CREATE TABLE identities (\n'
            '\tidentity_id VARCHAR(128) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tidentity_type VARCHAR(32) NOT NULL, \n'
            '\tdisplay_name VARCHAR(256) NOT NULL, \n'
            '\tdisabled BOOLEAN NOT NULL, \n'
            '\tattributes_json JSON NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (identity_id), \n'
            '\tFOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT\n'
            ')',
            'CREATE INDEX ix_identities_tenant_id ON identities (tenant_id)',
            'CREATE TABLE role_bindings (\n'
            '\tbinding_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64), \n'
            '\tidentity_id VARCHAR(128) NOT NULL, \n'
            '\trole VARCHAR(64) NOT NULL, \n'
            '\tpurposes_json JSON NOT NULL, \n'
            '\tspatial_restrictions_json JSON NOT NULL, \n'
            '\texpires_at DATETIME, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (binding_id), \n'
            '\tFOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT, \n'
            '\tFOREIGN KEY(project_id) REFERENCES projects (project_id) ON DELETE RESTRICT, \n'
            '\tFOREIGN KEY(identity_id) REFERENCES identities (identity_id) ON DELETE RESTRICT\n'
            ')',
            'CREATE INDEX ix_role_bindings_identity_id ON role_bindings (identity_id)',
            'CREATE INDEX ix_role_bindings_project_id ON role_bindings (project_id)',
            'CREATE INDEX ix_role_bindings_tenant_id ON role_bindings (tenant_id)',
            'CREATE TABLE assets (\n'
            '\tsha256 VARCHAR(64) NOT NULL, \n'
            '\tbyte_count INTEGER NOT NULL, \n'
            '\tmedia_type VARCHAR(256) NOT NULL, \n'
            '\tstorage_key TEXT NOT NULL, \n'
            '\tencryption_metadata JSON NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (sha256)\n'
            ')',
            'CREATE TABLE asset_refs (\n'
            '\tasset_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tsha256 VARCHAR(64) NOT NULL, \n'
            '\toriginal_name VARCHAR(512) NOT NULL, \n'
            '\tclassification VARCHAR(64) NOT NULL, \n'
            '\tretention_class VARCHAR(64) NOT NULL, \n'
            '\tsource_class VARCHAR(64) NOT NULL, \n'
            '\tauthority_class VARCHAR(64) NOT NULL, \n'
            '\tprovenance_json JSON NOT NULL, \n'
            '\tlegal_hold BOOLEAN NOT NULL, \n'
            '\tcreated_by VARCHAR(128) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\ttombstoned_at DATETIME, \n'
            '\tPRIMARY KEY (asset_id), \n'
            '\tFOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT, \n'
            '\tFOREIGN KEY(project_id) REFERENCES projects (project_id) ON DELETE RESTRICT, \n'
            '\tFOREIGN KEY(sha256) REFERENCES assets (sha256) ON DELETE RESTRICT\n'
            ')',
            'CREATE INDEX ix_asset_refs_project_id ON asset_refs (project_id)',
            'CREATE INDEX ix_asset_refs_sha256 ON asset_refs (sha256)',
            'CREATE INDEX ix_asset_refs_tenant_id ON asset_refs (tenant_id)',
            'CREATE TABLE multipart_uploads (\n'
            '\tupload_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\texpected_sha256 VARCHAR(64) NOT NULL, \n'
            '\texpected_bytes INTEGER NOT NULL, \n'
            '\tmedia_type VARCHAR(256) NOT NULL, \n'
            '\tmetadata_json JSON NOT NULL, \n'
            '\tstate VARCHAR(32) NOT NULL, \n'
            '\tcreated_by VARCHAR(128) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tcompleted_at DATETIME, \n'
            '\tPRIMARY KEY (upload_id)\n'
            ')',
            'CREATE INDEX ix_multipart_uploads_project_id ON multipart_uploads (project_id)',
            'CREATE INDEX ix_multipart_uploads_tenant_id ON multipart_uploads (tenant_id)',
            'CREATE TABLE multipart_chunks (\n'
            '\tchunk_id VARCHAR(64) NOT NULL, \n'
            '\tupload_id VARCHAR(64) NOT NULL, \n'
            '\tpart_number INTEGER NOT NULL, \n'
            '\tsha256 VARCHAR(64) NOT NULL, \n'
            '\tbyte_count INTEGER NOT NULL, \n'
            '\tpath TEXT NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (chunk_id), \n'
            '\tCONSTRAINT uq_upload_part UNIQUE (upload_id, part_number), \n'
            '\tFOREIGN KEY(upload_id) REFERENCES multipart_uploads (upload_id) ON DELETE CASCADE\n'
            ')',
            'CREATE INDEX ix_multipart_chunks_upload_id ON multipart_chunks (upload_id)',
            'CREATE TABLE audit_events (\n'
            '\taudit_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64), \n'
            '\tactor_id VARCHAR(128) NOT NULL, \n'
            '\taction VARCHAR(128) NOT NULL, \n'
            '\tresource_type VARCHAR(128) NOT NULL, \n'
            '\tresource_id VARCHAR(128) NOT NULL, \n'
            '\toutcome VARCHAR(32) NOT NULL, \n'
            '\tdetails_json JSON NOT NULL, \n'
            '\toccurred_at DATETIME NOT NULL, \n'
            '\tprevious_hash VARCHAR(64) NOT NULL, \n'
            '\tevent_hash VARCHAR(64) NOT NULL, \n'
            '\tsignature VARCHAR(128) NOT NULL, \n'
            '\tPRIMARY KEY (audit_id), \n'
            '\tUNIQUE (event_hash)\n'
            ')',
            'CREATE INDEX ix_audit_events_action ON audit_events (action)',
            'CREATE INDEX ix_audit_events_project_id ON audit_events (project_id)',
            'CREATE INDEX ix_audit_events_tenant_id ON audit_events (tenant_id)',
            'CREATE TABLE operations (\n'
            '\toperation_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\toperation_type VARCHAR(128) NOT NULL, \n'
            '\tidempotency_key VARCHAR(256) NOT NULL, \n'
            '\tinput_manifest_hash VARCHAR(64) NOT NULL, \n'
            '\tinput_json JSON NOT NULL, \n'
            '\tstate VARCHAR(32) NOT NULL, \n'
            '\tprogress FLOAT NOT NULL, \n'
            '\tattempt INTEGER NOT NULL, \n'
            '\tmax_attempts INTEGER NOT NULL, \n'
            '\tlease_owner VARCHAR(128), \n'
            '\tlease_expires_at DATETIME, \n'
            '\tcheckpoint_json JSON NOT NULL, \n'
            '\toutput_json JSON NOT NULL, \n'
            '\toutput_hash VARCHAR(64), \n'
            '\terror_json JSON NOT NULL, \n'
            '\tcancel_requested BOOLEAN NOT NULL, \n'
            '\tcreated_by VARCHAR(128) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tupdated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (operation_id), \n'
            '\tCONSTRAINT uq_operation_idempotency UNIQUE (tenant_id, project_id, operation_type, idempotency_key)\n'
            ')',
            'CREATE INDEX ix_operations_operation_type ON operations (operation_type)',
            'CREATE INDEX ix_operations_project_id ON operations (project_id)',
            'CREATE INDEX ix_operations_state ON operations (state)',
            'CREATE INDEX ix_operations_tenant_id ON operations (tenant_id)',
            'CREATE TABLE outbox_events (\n'
            '\tevent_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64), \n'
            '\tevent_type VARCHAR(128) NOT NULL, \n'
            '\tschema_version VARCHAR(32) NOT NULL, \n'
            '\taggregate_type VARCHAR(128) NOT NULL, \n'
            '\taggregate_id VARCHAR(128) NOT NULL, \n'
            '\tpayload_json JSON NOT NULL, \n'
            '\tpayload_hash VARCHAR(64) NOT NULL, \n'
            '\toccurred_at DATETIME NOT NULL, \n'
            '\tpublished_at DATETIME, \n'
            '\tdelivery_attempts INTEGER NOT NULL, \n'
            '\tPRIMARY KEY (event_id)\n'
            ')',
            'CREATE INDEX ix_outbox_events_event_type ON outbox_events (event_type)',
            'CREATE INDEX ix_outbox_events_project_id ON outbox_events (project_id)',
            'CREATE INDEX ix_outbox_events_tenant_id ON outbox_events (tenant_id)',
            'CREATE TABLE coordinate_frames (\n'
            '\tframe_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tname VARCHAR(256) NOT NULL, \n'
            '\tparent_frame_id VARCHAR(64), \n'
            '\tconvention VARCHAR(128) NOT NULL, \n'
            '\tunits VARCHAR(32) NOT NULL, \n'
            '\ttransform_json JSON, \n'
            '\tuncertainty_m FLOAT, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (frame_id)\n'
            ')',
            'CREATE INDEX ix_coordinate_frames_parent_frame_id ON coordinate_frames (parent_frame_id)',
            'CREATE INDEX ix_coordinate_frames_project_id ON coordinate_frames (project_id)',
            'CREATE INDEX ix_coordinate_frames_tenant_id ON coordinate_frames (tenant_id)']}

DROP_TABLES = ['coordinate_frames', 'outbox_events', 'operations', 'audit_events', 'multipart_chunks', 'multipart_uploads', 'asset_refs', 'assets', 'role_bindings', 'identities', 'projects', 'tenants']

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
