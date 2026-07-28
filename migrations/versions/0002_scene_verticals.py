"""Scene, representation, search, and vertical records.

Generated once from the v1.1.0 canonical schema and retained as append-only DDL.
"""
from __future__ import annotations

import os
from alembic import op

revision = '0002_scene_verticals'
down_revision = '0001_foundation_control_plane'
branch_labels = None
depends_on = None

SQL = {'postgresql': ['CREATE TABLE provider_manifests (\n'
                '\tprovider_id VARCHAR(128) NOT NULL, \n'
                '\tversion VARCHAR(64) NOT NULL, \n'
                '\tsource_url TEXT NOT NULL, \n'
                '\tsource_revision VARCHAR(128) NOT NULL, \n'
                '\timage_digest VARCHAR(128), \n'
                '\tlicense_id VARCHAR(128) NOT NULL, \n'
                '\tapproval_state VARCHAR(32) NOT NULL, \n'
                '\tallowed_classifications_json JSON NOT NULL, \n'
                '\tallowed_purposes_json JSON NOT NULL, \n'
                '\tallowed_regions_json JSON NOT NULL, \n'
                '\tretention_days INTEGER, \n'
                '\texpires_at TIMESTAMP WITH TIME ZONE, \n'
                '\tmanifest_hash VARCHAR(64) NOT NULL, \n'
                '\tsigned_by VARCHAR(128), \n'
                '\tPRIMARY KEY (provider_id)\n'
                ')',
                'CREATE TABLE model_manifests (\n'
                '\tmodel_id VARCHAR(128) NOT NULL, \n'
                '\tversion VARCHAR(64) NOT NULL, \n'
                '\tcheckpoint_hash VARCHAR(128) NOT NULL, \n'
                '\tcode_revision VARCHAR(128) NOT NULL, \n'
                '\tcode_license VARCHAR(128) NOT NULL, \n'
                '\tweights_license VARCHAR(128) NOT NULL, \n'
                '\tdataset_terms_json JSON NOT NULL, \n'
                '\toutput_terms TEXT NOT NULL, \n'
                '\tapproval_state VARCHAR(32) NOT NULL, \n'
                '\tcommercial_use BOOLEAN NOT NULL, \n'
                '\tallowed_purposes_json JSON NOT NULL, \n'
                '\texpires_at TIMESTAMP WITH TIME ZONE, \n'
                '\tmanifest_hash VARCHAR(64) NOT NULL, \n'
                '\tPRIMARY KEY (model_id)\n'
                ')',
                'CREATE TABLE scene_commits (\n'
                '\tcommit_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tscene_id VARCHAR(64) NOT NULL, \n'
                '\tbranch VARCHAR(128) NOT NULL, \n'
                '\tparent_ids_json JSON NOT NULL, \n'
                '\tmessage TEXT NOT NULL, \n'
                '\tsemantic_snapshot_json JSON NOT NULL, \n'
                '\tsnapshot_hash VARCHAR(64) NOT NULL, \n'
                '\tcreated_by VARCHAR(128) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tsupersedes_commit_id VARCHAR(64), \n'
                '\tPRIMARY KEY (commit_id)\n'
                ')',
                'CREATE INDEX ix_scene_commits_project_id ON scene_commits (project_id)',
                'CREATE INDEX ix_scene_commits_scene_id ON scene_commits (scene_id)',
                'CREATE INDEX ix_scene_commits_tenant_id ON scene_commits (tenant_id)',
                'CREATE TABLE scene_branches (\n'
                '\tbranch_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tscene_id VARCHAR(64) NOT NULL, \n'
                '\tname VARCHAR(128) NOT NULL, \n'
                '\thead_commit_id VARCHAR(64) NOT NULL, \n'
                '\tprotected BOOLEAN NOT NULL, \n'
                '\tPRIMARY KEY (branch_id), \n'
                '\tCONSTRAINT uq_scene_branch UNIQUE (tenant_id, project_id, scene_id, name)\n'
                ')',
                'CREATE INDEX ix_scene_branches_project_id ON scene_branches (project_id)',
                'CREATE INDEX ix_scene_branches_scene_id ON scene_branches (scene_id)',
                'CREATE INDEX ix_scene_branches_tenant_id ON scene_branches (tenant_id)',
                'CREATE TABLE scene_entities (\n'
                '\tentity_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tscene_id VARCHAR(64) NOT NULL, \n'
                '\tentity_type VARCHAR(128) NOT NULL, \n'
                '\tname VARCHAR(512) NOT NULL, \n'
                '\tattributes_json JSON NOT NULL, \n'
                '\tsource_class VARCHAR(64) NOT NULL, \n'
                '\tauthority_class VARCHAR(64) NOT NULL, \n'
                '\tconfidence FLOAT NOT NULL, \n'
                '\tprovenance_json JSON NOT NULL, \n'
                '\tpolicy_json JSON NOT NULL, \n'
                '\tstable_support_json JSON NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tsuperseded_at TIMESTAMP WITH TIME ZONE, \n'
                '\tPRIMARY KEY (entity_id)\n'
                ')',
                'CREATE INDEX ix_scene_entities_entity_type ON scene_entities (entity_type)',
                'CREATE INDEX ix_scene_entities_project_id ON scene_entities (project_id)',
                'CREATE INDEX ix_scene_entities_scene_id ON scene_entities (scene_id)',
                'CREATE INDEX ix_scene_entities_tenant_id ON scene_entities (tenant_id)',
                'CREATE TABLE representations (\n'
                '\trepresentation_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tscene_id VARCHAR(64) NOT NULL, \n'
                '\tasset_id VARCHAR(64) NOT NULL, \n'
                '\tkind VARCHAR(32) NOT NULL, \n'
                '\tprovider_id VARCHAR(128) NOT NULL, \n'
                '\tcoordinate_frame_id VARCHAR(64) NOT NULL, \n'
                '\tsource_class VARCHAR(64) NOT NULL, \n'
                '\tauthority_class VARCHAR(64) NOT NULL, \n'
                '\tlossy BOOLEAN NOT NULL, \n'
                '\tintended_uses_json JSON NOT NULL, \n'
                '\tprohibited_uses_json JSON NOT NULL, \n'
                '\tquality_json JSON NOT NULL, \n'
                '\tprovenance_json JSON NOT NULL, \n'
                '\tsupport_map_json JSON NOT NULL, \n'
                '\tstate VARCHAR(32) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (representation_id)\n'
                ')',
                'CREATE INDEX ix_representations_asset_id ON representations (asset_id)',
                'CREATE INDEX ix_representations_kind ON representations (kind)',
                'CREATE INDEX ix_representations_project_id ON representations (project_id)',
                'CREATE INDEX ix_representations_provider_id ON representations (provider_id)',
                'CREATE INDEX ix_representations_scene_id ON representations (scene_id)',
                'CREATE INDEX ix_representations_tenant_id ON representations (tenant_id)',
                'CREATE TABLE representation_bindings (\n'
                '\tbinding_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tscene_id VARCHAR(64) NOT NULL, \n'
                '\tcommit_id VARCHAR(64) NOT NULL, \n'
                '\trepresentation_id VARCHAR(64) NOT NULL, \n'
                '\trole VARCHAR(64) NOT NULL, \n'
                '\tpublished_by VARCHAR(128) NOT NULL, \n'
                '\tpublished_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tsuperseded_at TIMESTAMP WITH TIME ZONE, \n'
                '\tPRIMARY KEY (binding_id)\n'
                ')',
                'CREATE INDEX ix_representation_bindings_commit_id ON representation_bindings (commit_id)',
                'CREATE INDEX ix_representation_bindings_project_id ON representation_bindings (project_id)',
                'CREATE INDEX ix_representation_bindings_representation_id ON representation_bindings '
                '(representation_id)',
                'CREATE INDEX ix_representation_bindings_scene_id ON representation_bindings (scene_id)',
                'CREATE INDEX ix_representation_bindings_tenant_id ON representation_bindings (tenant_id)',
                'CREATE TABLE measurements (\n'
                '\tmeasurement_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tscene_id VARCHAR(64) NOT NULL, \n'
                '\tentity_id VARCHAR(64), \n'
                '\tvalue FLOAT NOT NULL, \n'
                '\tunit VARCHAR(32) NOT NULL, \n'
                '\tuncertainty FLOAT NOT NULL, \n'
                '\tsource_asset_ids_json JSON NOT NULL, \n'
                '\tcalibration_json JSON NOT NULL, \n'
                '\tverifier_id VARCHAR(128), \n'
                '\tverified_at TIMESTAMP WITH TIME ZONE, \n'
                '\tauthority_class VARCHAR(64) NOT NULL, \n'
                '\tcreated_by VARCHAR(128) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (measurement_id)\n'
                ')',
                'CREATE INDEX ix_measurements_entity_id ON measurements (entity_id)',
                'CREATE INDEX ix_measurements_project_id ON measurements (project_id)',
                'CREATE INDEX ix_measurements_scene_id ON measurements (scene_id)',
                'CREATE INDEX ix_measurements_tenant_id ON measurements (tenant_id)',
                'CREATE TABLE consent_grants (\n'
                '\tgrant_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tsubject_id VARCHAR(128) NOT NULL, \n'
                '\tgranted_by VARCHAR(128) NOT NULL, \n'
                '\tpurposes_json JSON NOT NULL, \n'
                '\taudiences_json JSON NOT NULL, \n'
                '\tscopes_json JSON NOT NULL, \n'
                '\tderivative_policy_json JSON NOT NULL, \n'
                '\texpires_at TIMESTAMP WITH TIME ZONE, \n'
                '\trevoked_at TIMESTAMP WITH TIME ZONE, \n'
                '\trevoked_by VARCHAR(128), \n'
                '\tstate VARCHAR(32) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (grant_id)\n'
                ')',
                'CREATE INDEX ix_consent_grants_project_id ON consent_grants (project_id)',
                'CREATE INDEX ix_consent_grants_subject_id ON consent_grants (subject_id)',
                'CREATE INDEX ix_consent_grants_tenant_id ON consent_grants (tenant_id)',
                'CREATE TABLE search_documents (\n'
                '\tdocument_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tentity_id VARCHAR(64), \n'
                '\tasset_id VARCHAR(64), \n'
                '\ttext TEXT NOT NULL, \n'
                '\tterms_json JSON NOT NULL, \n'
                '\tembedding_json JSON, \n'
                '\tspatial_bounds_json JSON, \n'
                '\ttemporal_start TIMESTAMP WITH TIME ZONE, \n'
                '\ttemporal_end TIMESTAMP WITH TIME ZONE, \n'
                '\tpolicy_json JSON NOT NULL, \n'
                '\tsource_hash VARCHAR(64) NOT NULL, \n'
                '\tPRIMARY KEY (document_id)\n'
                ')',
                'CREATE INDEX ix_search_documents_asset_id ON search_documents (asset_id)',
                'CREATE INDEX ix_search_documents_entity_id ON search_documents (entity_id)',
                'CREATE INDEX ix_search_documents_project_id ON search_documents (project_id)',
                'CREATE INDEX ix_search_documents_tenant_id ON search_documents (tenant_id)',
                'CREATE TABLE exports (\n'
                '\texport_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tformat VARCHAR(64) NOT NULL, \n'
                '\tstatus VARCHAR(32) NOT NULL, \n'
                '\tmanifest_json JSON NOT NULL, \n'
                '\troot_hash VARCHAR(64) NOT NULL, \n'
                '\tpath TEXT NOT NULL, \n'
                '\tcreated_by VARCHAR(128) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (export_id)\n'
                ')',
                'CREATE INDEX ix_exports_project_id ON exports (project_id)',
                'CREATE INDEX ix_exports_tenant_id ON exports (tenant_id)',
                'CREATE TABLE construction_records (\n'
                '\trecord_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\trecord_type VARCHAR(128) NOT NULL, \n'
                '\tparent_id VARCHAR(64), \n'
                '\tentity_id VARCHAR(64), \n'
                '\tstate VARCHAR(64) NOT NULL, \n'
                '\tdata_json JSON NOT NULL, \n'
                '\tevidence_asset_ids_json JSON NOT NULL, \n'
                '\tcreated_by VARCHAR(128) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tsuperseded_at TIMESTAMP WITH TIME ZONE, \n'
                '\tPRIMARY KEY (record_id)\n'
                ')',
                'CREATE INDEX ix_construction_records_entity_id ON construction_records (entity_id)',
                'CREATE INDEX ix_construction_records_parent_id ON construction_records (parent_id)',
                'CREATE INDEX ix_construction_records_project_id ON construction_records (project_id)',
                'CREATE INDEX ix_construction_records_record_type ON construction_records (record_type)',
                'CREATE INDEX ix_construction_records_tenant_id ON construction_records (tenant_id)',
                'CREATE TABLE memory_records (\n'
                '\trecord_id VARCHAR(64) NOT NULL, \n'
                '\ttenant_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\trecord_type VARCHAR(128) NOT NULL, \n'
                '\tsubject_id VARCHAR(128), \n'
                '\trelated_ids_json JSON NOT NULL, \n'
                '\tdata_json JSON NOT NULL, \n'
                '\tsource_class VARCHAR(64) NOT NULL, \n'
                '\tconfidence FLOAT NOT NULL, \n'
                '\tevidence_asset_ids_json JSON NOT NULL, \n'
                '\taudience VARCHAR(32) NOT NULL, \n'
                '\tgenerated_lineage_json JSON, \n'
                '\tcreated_by VARCHAR(128) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tsuperseded_at TIMESTAMP WITH TIME ZONE, \n'
                '\tPRIMARY KEY (record_id)\n'
                ')',
                'CREATE INDEX ix_memory_records_project_id ON memory_records (project_id)',
                'CREATE INDEX ix_memory_records_record_type ON memory_records (record_type)',
                'CREATE INDEX ix_memory_records_subject_id ON memory_records (subject_id)',
                'CREATE INDEX ix_memory_records_tenant_id ON memory_records (tenant_id)',
                'ALTER TABLE search_documents ADD COLUMN spatial_envelope geometry(GeometryZ, 0)',
                'CREATE INDEX ix_search_documents_spatial_envelope_gist ON search_documents USING GIST '
                '(spatial_envelope)'],
 'sqlite': ['CREATE TABLE provider_manifests (\n'
            '\tprovider_id VARCHAR(128) NOT NULL, \n'
            '\tversion VARCHAR(64) NOT NULL, \n'
            '\tsource_url TEXT NOT NULL, \n'
            '\tsource_revision VARCHAR(128) NOT NULL, \n'
            '\timage_digest VARCHAR(128), \n'
            '\tlicense_id VARCHAR(128) NOT NULL, \n'
            '\tapproval_state VARCHAR(32) NOT NULL, \n'
            '\tallowed_classifications_json JSON NOT NULL, \n'
            '\tallowed_purposes_json JSON NOT NULL, \n'
            '\tallowed_regions_json JSON NOT NULL, \n'
            '\tretention_days INTEGER, \n'
            '\texpires_at DATETIME, \n'
            '\tmanifest_hash VARCHAR(64) NOT NULL, \n'
            '\tsigned_by VARCHAR(128), \n'
            '\tPRIMARY KEY (provider_id)\n'
            ')',
            'CREATE TABLE model_manifests (\n'
            '\tmodel_id VARCHAR(128) NOT NULL, \n'
            '\tversion VARCHAR(64) NOT NULL, \n'
            '\tcheckpoint_hash VARCHAR(128) NOT NULL, \n'
            '\tcode_revision VARCHAR(128) NOT NULL, \n'
            '\tcode_license VARCHAR(128) NOT NULL, \n'
            '\tweights_license VARCHAR(128) NOT NULL, \n'
            '\tdataset_terms_json JSON NOT NULL, \n'
            '\toutput_terms TEXT NOT NULL, \n'
            '\tapproval_state VARCHAR(32) NOT NULL, \n'
            '\tcommercial_use BOOLEAN NOT NULL, \n'
            '\tallowed_purposes_json JSON NOT NULL, \n'
            '\texpires_at DATETIME, \n'
            '\tmanifest_hash VARCHAR(64) NOT NULL, \n'
            '\tPRIMARY KEY (model_id)\n'
            ')',
            'CREATE TABLE scene_commits (\n'
            '\tcommit_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tscene_id VARCHAR(64) NOT NULL, \n'
            '\tbranch VARCHAR(128) NOT NULL, \n'
            '\tparent_ids_json JSON NOT NULL, \n'
            '\tmessage TEXT NOT NULL, \n'
            '\tsemantic_snapshot_json JSON NOT NULL, \n'
            '\tsnapshot_hash VARCHAR(64) NOT NULL, \n'
            '\tcreated_by VARCHAR(128) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tsupersedes_commit_id VARCHAR(64), \n'
            '\tPRIMARY KEY (commit_id)\n'
            ')',
            'CREATE INDEX ix_scene_commits_project_id ON scene_commits (project_id)',
            'CREATE INDEX ix_scene_commits_scene_id ON scene_commits (scene_id)',
            'CREATE INDEX ix_scene_commits_tenant_id ON scene_commits (tenant_id)',
            'CREATE TABLE scene_branches (\n'
            '\tbranch_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tscene_id VARCHAR(64) NOT NULL, \n'
            '\tname VARCHAR(128) NOT NULL, \n'
            '\thead_commit_id VARCHAR(64) NOT NULL, \n'
            '\tprotected BOOLEAN NOT NULL, \n'
            '\tPRIMARY KEY (branch_id), \n'
            '\tCONSTRAINT uq_scene_branch UNIQUE (tenant_id, project_id, scene_id, name)\n'
            ')',
            'CREATE INDEX ix_scene_branches_project_id ON scene_branches (project_id)',
            'CREATE INDEX ix_scene_branches_scene_id ON scene_branches (scene_id)',
            'CREATE INDEX ix_scene_branches_tenant_id ON scene_branches (tenant_id)',
            'CREATE TABLE scene_entities (\n'
            '\tentity_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tscene_id VARCHAR(64) NOT NULL, \n'
            '\tentity_type VARCHAR(128) NOT NULL, \n'
            '\tname VARCHAR(512) NOT NULL, \n'
            '\tattributes_json JSON NOT NULL, \n'
            '\tsource_class VARCHAR(64) NOT NULL, \n'
            '\tauthority_class VARCHAR(64) NOT NULL, \n'
            '\tconfidence FLOAT NOT NULL, \n'
            '\tprovenance_json JSON NOT NULL, \n'
            '\tpolicy_json JSON NOT NULL, \n'
            '\tstable_support_json JSON NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tsuperseded_at DATETIME, \n'
            '\tPRIMARY KEY (entity_id)\n'
            ')',
            'CREATE INDEX ix_scene_entities_entity_type ON scene_entities (entity_type)',
            'CREATE INDEX ix_scene_entities_project_id ON scene_entities (project_id)',
            'CREATE INDEX ix_scene_entities_scene_id ON scene_entities (scene_id)',
            'CREATE INDEX ix_scene_entities_tenant_id ON scene_entities (tenant_id)',
            'CREATE TABLE representations (\n'
            '\trepresentation_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tscene_id VARCHAR(64) NOT NULL, \n'
            '\tasset_id VARCHAR(64) NOT NULL, \n'
            '\tkind VARCHAR(32) NOT NULL, \n'
            '\tprovider_id VARCHAR(128) NOT NULL, \n'
            '\tcoordinate_frame_id VARCHAR(64) NOT NULL, \n'
            '\tsource_class VARCHAR(64) NOT NULL, \n'
            '\tauthority_class VARCHAR(64) NOT NULL, \n'
            '\tlossy BOOLEAN NOT NULL, \n'
            '\tintended_uses_json JSON NOT NULL, \n'
            '\tprohibited_uses_json JSON NOT NULL, \n'
            '\tquality_json JSON NOT NULL, \n'
            '\tprovenance_json JSON NOT NULL, \n'
            '\tsupport_map_json JSON NOT NULL, \n'
            '\tstate VARCHAR(32) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (representation_id)\n'
            ')',
            'CREATE INDEX ix_representations_asset_id ON representations (asset_id)',
            'CREATE INDEX ix_representations_kind ON representations (kind)',
            'CREATE INDEX ix_representations_project_id ON representations (project_id)',
            'CREATE INDEX ix_representations_provider_id ON representations (provider_id)',
            'CREATE INDEX ix_representations_scene_id ON representations (scene_id)',
            'CREATE INDEX ix_representations_tenant_id ON representations (tenant_id)',
            'CREATE TABLE representation_bindings (\n'
            '\tbinding_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tscene_id VARCHAR(64) NOT NULL, \n'
            '\tcommit_id VARCHAR(64) NOT NULL, \n'
            '\trepresentation_id VARCHAR(64) NOT NULL, \n'
            '\trole VARCHAR(64) NOT NULL, \n'
            '\tpublished_by VARCHAR(128) NOT NULL, \n'
            '\tpublished_at DATETIME NOT NULL, \n'
            '\tsuperseded_at DATETIME, \n'
            '\tPRIMARY KEY (binding_id)\n'
            ')',
            'CREATE INDEX ix_representation_bindings_commit_id ON representation_bindings (commit_id)',
            'CREATE INDEX ix_representation_bindings_project_id ON representation_bindings (project_id)',
            'CREATE INDEX ix_representation_bindings_representation_id ON representation_bindings (representation_id)',
            'CREATE INDEX ix_representation_bindings_scene_id ON representation_bindings (scene_id)',
            'CREATE INDEX ix_representation_bindings_tenant_id ON representation_bindings (tenant_id)',
            'CREATE TABLE measurements (\n'
            '\tmeasurement_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tscene_id VARCHAR(64) NOT NULL, \n'
            '\tentity_id VARCHAR(64), \n'
            '\tvalue FLOAT NOT NULL, \n'
            '\tunit VARCHAR(32) NOT NULL, \n'
            '\tuncertainty FLOAT NOT NULL, \n'
            '\tsource_asset_ids_json JSON NOT NULL, \n'
            '\tcalibration_json JSON NOT NULL, \n'
            '\tverifier_id VARCHAR(128), \n'
            '\tverified_at DATETIME, \n'
            '\tauthority_class VARCHAR(64) NOT NULL, \n'
            '\tcreated_by VARCHAR(128) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (measurement_id)\n'
            ')',
            'CREATE INDEX ix_measurements_entity_id ON measurements (entity_id)',
            'CREATE INDEX ix_measurements_project_id ON measurements (project_id)',
            'CREATE INDEX ix_measurements_scene_id ON measurements (scene_id)',
            'CREATE INDEX ix_measurements_tenant_id ON measurements (tenant_id)',
            'CREATE TABLE consent_grants (\n'
            '\tgrant_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tsubject_id VARCHAR(128) NOT NULL, \n'
            '\tgranted_by VARCHAR(128) NOT NULL, \n'
            '\tpurposes_json JSON NOT NULL, \n'
            '\taudiences_json JSON NOT NULL, \n'
            '\tscopes_json JSON NOT NULL, \n'
            '\tderivative_policy_json JSON NOT NULL, \n'
            '\texpires_at DATETIME, \n'
            '\trevoked_at DATETIME, \n'
            '\trevoked_by VARCHAR(128), \n'
            '\tstate VARCHAR(32) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (grant_id)\n'
            ')',
            'CREATE INDEX ix_consent_grants_project_id ON consent_grants (project_id)',
            'CREATE INDEX ix_consent_grants_subject_id ON consent_grants (subject_id)',
            'CREATE INDEX ix_consent_grants_tenant_id ON consent_grants (tenant_id)',
            'CREATE TABLE search_documents (\n'
            '\tdocument_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tentity_id VARCHAR(64), \n'
            '\tasset_id VARCHAR(64), \n'
            '\ttext TEXT NOT NULL, \n'
            '\tterms_json JSON NOT NULL, \n'
            '\tembedding_json JSON, \n'
            '\tspatial_bounds_json JSON, \n'
            '\ttemporal_start DATETIME, \n'
            '\ttemporal_end DATETIME, \n'
            '\tpolicy_json JSON NOT NULL, \n'
            '\tsource_hash VARCHAR(64) NOT NULL, \n'
            '\tPRIMARY KEY (document_id)\n'
            ')',
            'CREATE INDEX ix_search_documents_asset_id ON search_documents (asset_id)',
            'CREATE INDEX ix_search_documents_entity_id ON search_documents (entity_id)',
            'CREATE INDEX ix_search_documents_project_id ON search_documents (project_id)',
            'CREATE INDEX ix_search_documents_tenant_id ON search_documents (tenant_id)',
            'CREATE TABLE exports (\n'
            '\texport_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tformat VARCHAR(64) NOT NULL, \n'
            '\tstatus VARCHAR(32) NOT NULL, \n'
            '\tmanifest_json JSON NOT NULL, \n'
            '\troot_hash VARCHAR(64) NOT NULL, \n'
            '\tpath TEXT NOT NULL, \n'
            '\tcreated_by VARCHAR(128) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (export_id)\n'
            ')',
            'CREATE INDEX ix_exports_project_id ON exports (project_id)',
            'CREATE INDEX ix_exports_tenant_id ON exports (tenant_id)',
            'CREATE TABLE construction_records (\n'
            '\trecord_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\trecord_type VARCHAR(128) NOT NULL, \n'
            '\tparent_id VARCHAR(64), \n'
            '\tentity_id VARCHAR(64), \n'
            '\tstate VARCHAR(64) NOT NULL, \n'
            '\tdata_json JSON NOT NULL, \n'
            '\tevidence_asset_ids_json JSON NOT NULL, \n'
            '\tcreated_by VARCHAR(128) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tsuperseded_at DATETIME, \n'
            '\tPRIMARY KEY (record_id)\n'
            ')',
            'CREATE INDEX ix_construction_records_entity_id ON construction_records (entity_id)',
            'CREATE INDEX ix_construction_records_parent_id ON construction_records (parent_id)',
            'CREATE INDEX ix_construction_records_project_id ON construction_records (project_id)',
            'CREATE INDEX ix_construction_records_record_type ON construction_records (record_type)',
            'CREATE INDEX ix_construction_records_tenant_id ON construction_records (tenant_id)',
            'CREATE TABLE memory_records (\n'
            '\trecord_id VARCHAR(64) NOT NULL, \n'
            '\ttenant_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\trecord_type VARCHAR(128) NOT NULL, \n'
            '\tsubject_id VARCHAR(128), \n'
            '\trelated_ids_json JSON NOT NULL, \n'
            '\tdata_json JSON NOT NULL, \n'
            '\tsource_class VARCHAR(64) NOT NULL, \n'
            '\tconfidence FLOAT NOT NULL, \n'
            '\tevidence_asset_ids_json JSON NOT NULL, \n'
            '\taudience VARCHAR(32) NOT NULL, \n'
            '\tgenerated_lineage_json JSON, \n'
            '\tcreated_by VARCHAR(128) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tsuperseded_at DATETIME, \n'
            '\tPRIMARY KEY (record_id)\n'
            ')',
            'CREATE INDEX ix_memory_records_project_id ON memory_records (project_id)',
            'CREATE INDEX ix_memory_records_record_type ON memory_records (record_type)',
            'CREATE INDEX ix_memory_records_subject_id ON memory_records (subject_id)',
            'CREATE INDEX ix_memory_records_tenant_id ON memory_records (tenant_id)']}

DROP_TABLES = ['memory_records', 'construction_records', 'exports', 'search_documents', 'consent_grants', 'measurements', 'representation_bindings', 'representations', 'scene_entities', 'scene_branches', 'scene_commits', 'model_manifests', 'provider_manifests']

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
