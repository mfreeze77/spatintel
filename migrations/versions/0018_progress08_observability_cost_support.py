"""Progress 08 observability, SLO, cost, capacity, and support controls.

Revision ID: 0018_progress08_observability_cost_support
Revises: 0017_progress07_security_privacy_readiness
Create Date: 2026-07-30
"""
from __future__ import annotations

import os
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0018_progress08_observability_cost_support"
down_revision: Union[str, None] = "0017_progress07_security_privacy_readiness"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _indexes(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column], unique=False)


def upgrade() -> None:
    op.create_table(
        'telemetry_records',
        sa.Column('telemetry_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('telemetry_type', sa.String(length=32), nullable=False),
        sa.Column('service', sa.String(length=128), nullable=False),
        sa.Column('release', sa.String(length=128), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('trace_id', sa.String(length=32), nullable=True),
        sa.Column('operation_id', sa.String(length=64), nullable=True),
        sa.Column('route_template', sa.String(length=256), nullable=True),
        sa.Column('stage', sa.String(length=64), nullable=True),
        sa.Column('model_id', sa.String(length=128), nullable=True),
        sa.Column('checkpoint_hash', sa.String(length=64), nullable=True),
        sa.Column('capture_profile', sa.String(length=128), nullable=True),
        sa.Column('hardware_profile', sa.String(length=128), nullable=True),
        sa.Column('execution_profile', sa.String(length=64), nullable=True),
        sa.Column('queue_class', sa.String(length=64), nullable=True),
        sa.Column('vertical', sa.String(length=64), nullable=True),
        sa.Column('severity', sa.String(length=16), nullable=False),
        sa.Column('outcome', sa.String(length=64), nullable=False),
        sa.Column('stable_error_code', sa.String(length=128), nullable=True),
        sa.Column('payload_json', sa.JSON(), nullable=False),
        sa.Column('labels_json', sa.JSON(), nullable=False),
        sa.Column('payload_hash', sa.String(length=64), nullable=False),
        sa.Column('created_by', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('telemetry_id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.project_id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('payload_hash'),
    )
    op.create_index('ix_telemetry_correlation', 'telemetry_records', ['tenant_id', 'project_id', 'correlation_id'], unique=False)
    op.create_index('ix_telemetry_records_capture_profile', 'telemetry_records', ['capture_profile'], unique=False)
    op.create_index('ix_telemetry_records_checkpoint_hash', 'telemetry_records', ['checkpoint_hash'], unique=False)
    op.create_index('ix_telemetry_records_correlation_id', 'telemetry_records', ['correlation_id'], unique=False)
    op.create_index('ix_telemetry_records_created_at', 'telemetry_records', ['created_at'], unique=False)
    op.create_index('ix_telemetry_records_execution_profile', 'telemetry_records', ['execution_profile'], unique=False)
    op.create_index('ix_telemetry_records_hardware_profile', 'telemetry_records', ['hardware_profile'], unique=False)
    op.create_index('ix_telemetry_records_model_id', 'telemetry_records', ['model_id'], unique=False)
    op.create_index('ix_telemetry_records_operation_id', 'telemetry_records', ['operation_id'], unique=False)
    op.create_index('ix_telemetry_records_outcome', 'telemetry_records', ['outcome'], unique=False)
    op.create_index('ix_telemetry_records_project_id', 'telemetry_records', ['project_id'], unique=False)
    op.create_index('ix_telemetry_records_queue_class', 'telemetry_records', ['queue_class'], unique=False)
    op.create_index('ix_telemetry_records_route_template', 'telemetry_records', ['route_template'], unique=False)
    op.create_index('ix_telemetry_records_service', 'telemetry_records', ['service'], unique=False)
    op.create_index('ix_telemetry_records_severity', 'telemetry_records', ['severity'], unique=False)
    op.create_index('ix_telemetry_records_stable_error_code', 'telemetry_records', ['stable_error_code'], unique=False)
    op.create_index('ix_telemetry_records_stage', 'telemetry_records', ['stage'], unique=False)
    op.create_index('ix_telemetry_records_telemetry_type', 'telemetry_records', ['telemetry_type'], unique=False)
    op.create_index('ix_telemetry_records_tenant_id', 'telemetry_records', ['tenant_id'], unique=False)
    op.create_index('ix_telemetry_records_trace_id', 'telemetry_records', ['trace_id'], unique=False)
    op.create_index('ix_telemetry_records_vertical', 'telemetry_records', ['vertical'], unique=False)
    op.create_index('ix_telemetry_scope_time', 'telemetry_records', ['tenant_id', 'project_id', 'created_at'], unique=False)

    op.create_table(
        'resilience_profiles',
        sa.Column('profile_id', sa.String(length=64), nullable=False),
        sa.Column('component', sa.String(length=128), nullable=False),
        sa.Column('version', sa.String(length=64), nullable=False),
        sa.Column('owner', sa.String(length=128), nullable=False),
        sa.Column('blast_radius', sa.String(length=64), nullable=False),
        sa.Column('retry_safety', sa.String(length=64), nullable=False),
        sa.Column('recovery_point_seconds', sa.Integer(), nullable=False),
        sa.Column('recovery_time_seconds', sa.Integer(), nullable=False),
        sa.Column('degraded_behavior_json', sa.JSON(), nullable=False),
        sa.Column('dependencies_json', sa.JSON(), nullable=False),
        sa.Column('profile_hash', sa.String(length=64), nullable=False),
        sa.Column('created_by', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('profile_id'),
        sa.UniqueConstraint('profile_hash'),
        sa.UniqueConstraint('component', 'version', name='uq_resilience_component_version'),
    )
    op.create_index('ix_resilience_profiles_component', 'resilience_profiles', ['component'], unique=False)

    op.create_table(
        'compute_profiles',
        sa.Column('compute_profile_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('revision', sa.String(length=64), nullable=False),
        sa.Column('resolution', sa.String(length=64), nullable=False),
        sa.Column('dtype', sa.String(length=32), nullable=False),
        sa.Column('backend', sa.String(length=64), nullable=False),
        sa.Column('model_id', sa.String(length=128), nullable=False),
        sa.Column('checkpoint_hash', sa.String(length=64), nullable=False),
        sa.Column('window_policy_json', sa.JSON(), nullable=False),
        sa.Column('memory_limit_mb', sa.Integer(), nullable=False),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False),
        sa.Column('output_class', sa.String(length=64), nullable=False),
        sa.Column('quality_tier', sa.String(length=64), nullable=False),
        sa.Column('cuda_version', sa.String(length=64), nullable=True),
        sa.Column('driver_constraint', sa.String(length=128), nullable=True),
        sa.Column('container_digest', sa.String(length=160), nullable=False),
        sa.Column('tenant_isolation', sa.String(length=64), nullable=False),
        sa.Column('oom_fallback_json', sa.JSON(), nullable=False),
        sa.Column('expected_runtime_seconds', sa.Float(), nullable=False),
        sa.Column('peak_vram_mb', sa.Integer(), nullable=False),
        sa.Column('peak_ram_mb', sa.Integer(), nullable=False),
        sa.Column('cost_stage_weights_json', sa.JSON(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('profile_hash', sa.String(length=64), nullable=False),
        sa.Column('created_by', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('compute_profile_id'),
        sa.UniqueConstraint('profile_hash'),
        sa.UniqueConstraint('name', 'revision', name='uq_compute_profile_revision'),
    )
    op.create_index('ix_compute_profiles_name', 'compute_profiles', ['name'], unique=False)

    op.create_table(
        'slo_definitions',
        sa.Column('slo_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=True),
        sa.Column('project_id', sa.String(length=64), nullable=True),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('target_type', sa.String(length=64), nullable=False),
        sa.Column('dimensions_json', sa.JSON(), nullable=False),
        sa.Column('indicator_json', sa.JSON(), nullable=False),
        sa.Column('objective', sa.Float(), nullable=False),
        sa.Column('percentile', sa.Float(), nullable=False),
        sa.Column('window_seconds', sa.Integer(), nullable=False),
        sa.Column('budget_json', sa.JSON(), nullable=False),
        sa.Column('degradation_behavior', sa.String(length=256), nullable=False),
        sa.Column('evidence_class', sa.String(length=64), nullable=False),
        sa.Column('owner', sa.String(length=128), nullable=False),
        sa.Column('version', sa.String(length=64), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('definition_hash', sa.String(length=64), nullable=False),
        sa.Column('created_by', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('slo_id'),
        sa.UniqueConstraint('definition_hash'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'name', 'version', name='uq_slo_scope_name_version'),
    )
    op.create_index('ix_slo_definitions_name', 'slo_definitions', ['name'], unique=False)
    op.create_index('ix_slo_definitions_project_id', 'slo_definitions', ['project_id'], unique=False)
    op.create_index('ix_slo_definitions_tenant_id', 'slo_definitions', ['tenant_id'], unique=False)

    op.create_table(
        'slo_measurements',
        sa.Column('measurement_id', sa.String(length=64), nullable=False),
        sa.Column('slo_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=True),
        sa.Column('project_id', sa.String(length=64), nullable=True),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('numerator', sa.Float(), nullable=False),
        sa.Column('denominator', sa.Float(), nullable=False),
        sa.Column('observed_value', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('dimensions_json', sa.JSON(), nullable=False),
        sa.Column('source_profile', sa.String(length=128), nullable=False),
        sa.Column('source_manifest_hash', sa.String(length=64), nullable=False),
        sa.Column('evidence_hash', sa.String(length=64), nullable=False),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('measurement_id'),
        sa.ForeignKeyConstraint(['slo_id'], ['slo_definitions.slo_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('evidence_hash'),
    )
    op.create_index('ix_slo_measurements_project_id', 'slo_measurements', ['project_id'], unique=False)
    op.create_index('ix_slo_measurements_slo_id', 'slo_measurements', ['slo_id'], unique=False)
    op.create_index('ix_slo_measurements_tenant_id', 'slo_measurements', ['tenant_id'], unique=False)

    op.create_table(
        'performance_budgets',
        sa.Column('performance_budget_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=True),
        sa.Column('profile_type', sa.String(length=32), nullable=False),
        sa.Column('profile_name', sa.String(length=128), nullable=False),
        sa.Column('input_class_json', sa.JSON(), nullable=False),
        sa.Column('hardware_profile', sa.String(length=128), nullable=False),
        sa.Column('execution_profile', sa.String(length=64), nullable=False),
        sa.Column('model_id', sa.String(length=128), nullable=True),
        sa.Column('checkpoint_hash', sa.String(length=64), nullable=True),
        sa.Column('queue_class', sa.String(length=64), nullable=True),
        sa.Column('vertical', sa.String(length=64), nullable=True),
        sa.Column('percentile', sa.Float(), nullable=False),
        sa.Column('warm_state', sa.String(length=16), nullable=False),
        sa.Column('concurrency', sa.Integer(), nullable=False),
        sa.Column('budgets_json', sa.JSON(), nullable=False),
        sa.Column('degradation_behavior', sa.String(length=256), nullable=False),
        sa.Column('evidence_class', sa.String(length=64), nullable=False),
        sa.Column('version', sa.String(length=64), nullable=False),
        sa.Column('budget_hash', sa.String(length=64), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('performance_budget_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('budget_hash'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'profile_type', 'profile_name', 'version', name='uq_perf_budget_scope_profile_version'),
    )
    op.create_index('ix_performance_budgets_checkpoint_hash', 'performance_budgets', ['checkpoint_hash'], unique=False)
    op.create_index('ix_performance_budgets_execution_profile', 'performance_budgets', ['execution_profile'], unique=False)
    op.create_index('ix_performance_budgets_hardware_profile', 'performance_budgets', ['hardware_profile'], unique=False)
    op.create_index('ix_performance_budgets_model_id', 'performance_budgets', ['model_id'], unique=False)
    op.create_index('ix_performance_budgets_profile_name', 'performance_budgets', ['profile_name'], unique=False)
    op.create_index('ix_performance_budgets_profile_type', 'performance_budgets', ['profile_type'], unique=False)
    op.create_index('ix_performance_budgets_project_id', 'performance_budgets', ['project_id'], unique=False)
    op.create_index('ix_performance_budgets_queue_class', 'performance_budgets', ['queue_class'], unique=False)
    op.create_index('ix_performance_budgets_tenant_id', 'performance_budgets', ['tenant_id'], unique=False)
    op.create_index('ix_performance_budgets_vertical', 'performance_budgets', ['vertical'], unique=False)

    op.create_table(
        'price_catalogs',
        sa.Column('price_catalog_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('version', sa.String(length=128), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('effective_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('prices_json', sa.JSON(), nullable=False),
        sa.Column('source_reference', sa.String(length=512), nullable=False),
        sa.Column('source_hash', sa.String(length=64), nullable=False),
        sa.Column('supersedes_price_catalog_id', sa.String(length=64), nullable=True),
        sa.Column('catalog_hash', sa.String(length=64), nullable=False),
        sa.Column('created_by', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('price_catalog_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('catalog_hash'),
        sa.UniqueConstraint('tenant_id', 'version', name='uq_price_catalog_tenant_version'),
    )
    op.create_index('ix_price_catalogs_supersedes_price_catalog_id', 'price_catalogs', ['supersedes_price_catalog_id'], unique=False)
    op.create_index('ix_price_catalogs_tenant_id', 'price_catalogs', ['tenant_id'], unique=False)

    op.create_table(
        'cost_estimates',
        sa.Column('estimate_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('operation_id', sa.String(length=64), nullable=True),
        sa.Column('capture_id', sa.String(length=64), nullable=True),
        sa.Column('run_id', sa.String(length=64), nullable=False),
        sa.Column('compute_profile_id', sa.String(length=64), nullable=False),
        sa.Column('price_catalog_id', sa.String(length=64), nullable=False),
        sa.Column('input_class_json', sa.JSON(), nullable=False),
        sa.Column('stage_estimates_json', sa.JSON(), nullable=False),
        sa.Column('total_amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('estimate_hash', sa.String(length=64), nullable=False),
        sa.Column('state', sa.String(length=32), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('estimate_id'),
        sa.ForeignKeyConstraint(['compute_profile_id'], ['compute_profiles.compute_profile_id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['price_catalog_id'], ['price_catalogs.price_catalog_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('estimate_hash'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'run_id', name='uq_cost_estimate_run'),
    )
    op.create_index('ix_cost_estimates_capture_id', 'cost_estimates', ['capture_id'], unique=False)
    op.create_index('ix_cost_estimates_compute_profile_id', 'cost_estimates', ['compute_profile_id'], unique=False)
    op.create_index('ix_cost_estimates_operation_id', 'cost_estimates', ['operation_id'], unique=False)
    op.create_index('ix_cost_estimates_price_catalog_id', 'cost_estimates', ['price_catalog_id'], unique=False)
    op.create_index('ix_cost_estimates_project_id', 'cost_estimates', ['project_id'], unique=False)
    op.create_index('ix_cost_estimates_run_id', 'cost_estimates', ['run_id'], unique=False)
    op.create_index('ix_cost_estimates_tenant_id', 'cost_estimates', ['tenant_id'], unique=False)

    op.create_table(
        'actual_costs',
        sa.Column('actual_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('operation_id', sa.String(length=64), nullable=True),
        sa.Column('capture_id', sa.String(length=64), nullable=True),
        sa.Column('run_id', sa.String(length=64), nullable=False),
        sa.Column('stage', sa.String(length=64), nullable=False),
        sa.Column('model_id', sa.String(length=128), nullable=True),
        sa.Column('checkpoint_hash', sa.String(length=64), nullable=True),
        sa.Column('price_catalog_id', sa.String(length=64), nullable=False),
        sa.Column('usage_json', sa.JSON(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('actual_hash', sa.String(length=64), nullable=False),
        sa.Column('idempotency_key', sa.String(length=256), nullable=False),
        sa.Column('recorded_by', sa.String(length=128), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('actual_id'),
        sa.ForeignKeyConstraint(['price_catalog_id'], ['price_catalogs.price_catalog_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('actual_hash'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'idempotency_key', name='uq_actual_cost_idempotency'),
    )
    op.create_index('ix_actual_costs_capture_id', 'actual_costs', ['capture_id'], unique=False)
    op.create_index('ix_actual_costs_checkpoint_hash', 'actual_costs', ['checkpoint_hash'], unique=False)
    op.create_index('ix_actual_costs_model_id', 'actual_costs', ['model_id'], unique=False)
    op.create_index('ix_actual_costs_operation_id', 'actual_costs', ['operation_id'], unique=False)
    op.create_index('ix_actual_costs_price_catalog_id', 'actual_costs', ['price_catalog_id'], unique=False)
    op.create_index('ix_actual_costs_project_id', 'actual_costs', ['project_id'], unique=False)
    op.create_index('ix_actual_costs_run_id', 'actual_costs', ['run_id'], unique=False)
    op.create_index('ix_actual_costs_stage', 'actual_costs', ['stage'], unique=False)
    op.create_index('ix_actual_costs_tenant_id', 'actual_costs', ['tenant_id'], unique=False)

    op.create_table(
        'budget_policies',
        sa.Column('budget_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=True),
        sa.Column('revision', sa.String(length=64), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('period_seconds', sa.Integer(), nullable=False),
        sa.Column('soft_limit', sa.Float(), nullable=False),
        sa.Column('hard_limit', sa.Float(), nullable=False),
        sa.Column('concurrency_limit', sa.Integer(), nullable=False),
        sa.Column('storage_limit_bytes', sa.BigInteger(), nullable=False),
        sa.Column('retention_limit_days', sa.Integer(), nullable=False),
        sa.Column('anomaly_threshold', sa.Float(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('policy_hash', sa.String(length=64), nullable=False),
        sa.Column('created_by', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('budget_id'),
        sa.UniqueConstraint('policy_hash'),
    )
    op.create_index('ix_budget_policies_project_id', 'budget_policies', ['project_id'], unique=False)
    op.create_index('ix_budget_policies_tenant_id', 'budget_policies', ['tenant_id'], unique=False)

    op.create_table(
        'budget_reservations',
        sa.Column('reservation_id', sa.String(length=64), nullable=False),
        sa.Column('budget_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('operation_id', sa.String(length=64), nullable=True),
        sa.Column('estimate_id', sa.String(length=64), nullable=False),
        sa.Column('idempotency_key', sa.String(length=256), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('state', sa.String(length=32), nullable=False),
        sa.Column('requested_by', sa.String(length=128), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('released_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('release_reason', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('reservation_id'),
        sa.ForeignKeyConstraint(['estimate_id'], ['cost_estimates.estimate_id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['budget_id'], ['budget_policies.budget_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'idempotency_key', name='uq_budget_reservation_idempotency'),
    )
    op.create_index('ix_budget_reservations_budget_id', 'budget_reservations', ['budget_id'], unique=False)
    op.create_index('ix_budget_reservations_estimate_id', 'budget_reservations', ['estimate_id'], unique=False)
    op.create_index('ix_budget_reservations_operation_id', 'budget_reservations', ['operation_id'], unique=False)
    op.create_index('ix_budget_reservations_project_id', 'budget_reservations', ['project_id'], unique=False)
    op.create_index('ix_budget_reservations_state', 'budget_reservations', ['state'], unique=False)
    op.create_index('ix_budget_reservations_tenant_id', 'budget_reservations', ['tenant_id'], unique=False)

    op.create_table(
        'budget_overrides',
        sa.Column('override_id', sa.String(length=64), nullable=False),
        sa.Column('budget_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('requested_by', sa.String(length=128), nullable=False),
        sa.Column('approved_by', sa.String(length=128), nullable=True),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('additional_amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('state', sa.String(length=32), nullable=False),
        sa.Column('override_hash', sa.String(length=64), nullable=False),
        sa.Column('approval_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_by', sa.String(length=128), nullable=True),
        sa.PrimaryKeyConstraint('override_id'),
        sa.ForeignKeyConstraint(['budget_id'], ['budget_policies.budget_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('override_hash'),
        sa.UniqueConstraint('approval_hash'),
    )
    op.create_index('ix_budget_overrides_budget_id', 'budget_overrides', ['budget_id'], unique=False)
    op.create_index('ix_budget_overrides_project_id', 'budget_overrides', ['project_id'], unique=False)
    op.create_index('ix_budget_overrides_state', 'budget_overrides', ['state'], unique=False)
    op.create_index('ix_budget_overrides_tenant_id', 'budget_overrides', ['tenant_id'], unique=False)

    op.create_table(
        'anomaly_alerts',
        sa.Column('alert_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=False),
        sa.Column('metric_name', sa.String(length=128), nullable=False),
        sa.Column('observed_value', sa.Float(), nullable=False),
        sa.Column('baseline_value', sa.Float(), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=False),
        sa.Column('state', sa.String(length=32), nullable=False),
        sa.Column('evidence_json', sa.JSON(), nullable=False),
        sa.Column('alert_hash', sa.String(length=64), nullable=False),
        sa.Column('created_by', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', sa.String(length=128), nullable=True),
        sa.Column('suppressed_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('suppression_approved_by', sa.String(length=128), nullable=True),
        sa.PrimaryKeyConstraint('alert_id'),
        sa.UniqueConstraint('alert_hash'),
    )
    op.create_index('ix_anomaly_alerts_category', 'anomaly_alerts', ['category'], unique=False)
    op.create_index('ix_anomaly_alerts_project_id', 'anomaly_alerts', ['project_id'], unique=False)
    op.create_index('ix_anomaly_alerts_tenant_id', 'anomaly_alerts', ['tenant_id'], unique=False)

    op.create_table(
        'queue_snapshots',
        sa.Column('snapshot_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=True),
        sa.Column('project_id', sa.String(length=64), nullable=True),
        sa.Column('queue_class', sa.String(length=64), nullable=False),
        sa.Column('depth', sa.Integer(), nullable=False),
        sa.Column('in_flight', sa.Integer(), nullable=False),
        sa.Column('retries', sa.Integer(), nullable=False),
        sa.Column('oldest_age_seconds', sa.Float(), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False),
        sa.Column('sampled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('snapshot_hash', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('snapshot_id'),
        sa.UniqueConstraint('snapshot_hash'),
    )
    op.create_index('ix_queue_snapshots_project_id', 'queue_snapshots', ['project_id'], unique=False)
    op.create_index('ix_queue_snapshots_queue_class', 'queue_snapshots', ['queue_class'], unique=False)
    op.create_index('ix_queue_snapshots_tenant_id', 'queue_snapshots', ['tenant_id'], unique=False)

    op.create_table(
        'capacity_plans',
        sa.Column('capacity_plan_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=True),
        sa.Column('profile_name', sa.String(length=128), nullable=False),
        sa.Column('measurement_window_json', sa.JSON(), nullable=False),
        sa.Column('scene_minutes', sa.Float(), nullable=False),
        sa.Column('frames', sa.BigInteger(), nullable=False),
        sa.Column('area_m2', sa.Float(), nullable=False),
        sa.Column('peak_concurrency', sa.Integer(), nullable=False),
        sa.Column('headroom_ratio', sa.Float(), nullable=False),
        sa.Column('required_capacity_json', sa.JSON(), nullable=False),
        sa.Column('evidence_class', sa.String(length=64), nullable=False),
        sa.Column('source_manifest_hash', sa.String(length=64), nullable=False),
        sa.Column('plan_hash', sa.String(length=64), nullable=False),
        sa.Column('created_by', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('capacity_plan_id'),
        sa.UniqueConstraint('plan_hash'),
    )
    op.create_index('ix_capacity_plans_tenant_id', 'capacity_plans', ['tenant_id'], unique=False)
    op.create_index('ix_capacity_plans_project_id', 'capacity_plans', ['project_id'], unique=False)
    op.create_index('ix_capacity_plans_profile_name', 'capacity_plans', ['profile_name'], unique=False)

    op.create_table(
        'cost_reconciliations',
        sa.Column('reconciliation_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('run_id', sa.String(length=64), nullable=False),
        sa.Column('estimate_id', sa.String(length=64), nullable=False),
        sa.Column('actual_ids_json', sa.JSON(), nullable=False),
        sa.Column('estimated_amount', sa.Float(), nullable=False),
        sa.Column('actual_amount', sa.Float(), nullable=False),
        sa.Column('delta_amount', sa.Float(), nullable=False),
        sa.Column('ratio', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('catalog_hashes_json', sa.JSON(), nullable=False),
        sa.Column('reconciliation_hash', sa.String(length=64), nullable=False),
        sa.Column('created_by', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('reconciliation_id'),
        sa.UniqueConstraint('reconciliation_hash'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'run_id', name='uq_cost_reconciliation_run'),
    )
    op.create_index('ix_cost_reconciliations_tenant_id', 'cost_reconciliations', ['tenant_id'], unique=False)
    op.create_index('ix_cost_reconciliations_project_id', 'cost_reconciliations', ['project_id'], unique=False)
    op.create_index('ix_cost_reconciliations_run_id', 'cost_reconciliations', ['run_id'], unique=False)
    op.create_index('ix_cost_reconciliations_estimate_id', 'cost_reconciliations', ['estimate_id'], unique=False)

    op.create_table(
        'support_access_grants',
        sa.Column('grant_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('resource_scope_json', sa.JSON(), nullable=False),
        sa.Column('purpose', sa.String(length=128), nullable=False),
        sa.Column('personnel_json', sa.JSON(), nullable=False),
        sa.Column('requested_by', sa.String(length=128), nullable=False),
        sa.Column('approved_by', sa.String(length=128), nullable=True),
        sa.Column('approval_hash', sa.String(length=64), nullable=False),
        sa.Column('state', sa.String(length=32), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_by', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('grant_id'),
        sa.UniqueConstraint('approval_hash'),
    )
    op.create_index('ix_support_access_grants_project_id', 'support_access_grants', ['project_id'], unique=False)
    op.create_index('ix_support_access_grants_state', 'support_access_grants', ['state'], unique=False)
    op.create_index('ix_support_access_grants_tenant_id', 'support_access_grants', ['tenant_id'], unique=False)

    op.create_table(
        'support_bundles',
        sa.Column('bundle_id', sa.String(length=64), nullable=False),
        sa.Column('grant_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('bundle_path', sa.String(), nullable=False),
        sa.Column('zip_hash', sa.String(length=64), nullable=False),
        sa.Column('root_hash', sa.String(length=64), nullable=False),
        sa.Column('scope_hash', sa.String(length=64), nullable=False),
        sa.Column('manifest_json', sa.JSON(), nullable=False),
        sa.Column('state', sa.String(length=32), nullable=False),
        sa.Column('created_by', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('bundle_id'),
        sa.ForeignKeyConstraint(['grant_id'], ['support_access_grants.grant_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('zip_hash'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'scope_hash', name='uq_support_bundle_scope'),
    )
    op.create_index('ix_support_bundles_grant_id', 'support_bundles', ['grant_id'], unique=False)
    op.create_index('ix_support_bundles_project_id', 'support_bundles', ['project_id'], unique=False)
    op.create_index('ix_support_bundles_tenant_id', 'support_bundles', ['tenant_id'], unique=False)

    op.create_table(
        'support_tickets',
        sa.Column('ticket_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('risk_class', sa.String(length=64), nullable=False),
        sa.Column('issue_type', sa.String(length=128), nullable=False),
        sa.Column('summary', sa.String(), nullable=False),
        sa.Column('affected_release', sa.String(length=128), nullable=True),
        sa.Column('remediation_reference', sa.String(length=512), nullable=True),
        sa.Column('retention_json', sa.JSON(), nullable=False),
        sa.Column('routed_role', sa.String(length=64), nullable=False),
        sa.Column('state', sa.String(length=32), nullable=False),
        sa.Column('created_by', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_by', sa.String(length=128), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('ticket_id'),
    )
    op.create_index('ix_support_tickets_project_id', 'support_tickets', ['project_id'], unique=False)
    op.create_index('ix_support_tickets_tenant_id', 'support_tickets', ['tenant_id'], unique=False)

    op.create_table(
        'game_day_exercises',
        sa.Column('exercise_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=True),
        sa.Column('project_id', sa.String(length=64), nullable=True),
        sa.Column('scenario', sa.String(length=128), nullable=False),
        sa.Column('runbook_reference', sa.String(length=512), nullable=False),
        sa.Column('participants_json', sa.JSON(), nullable=False),
        sa.Column('observations_json', sa.JSON(), nullable=False),
        sa.Column('corrective_requirements_json', sa.JSON(), nullable=False),
        sa.Column('test_ids_json', sa.JSON(), nullable=False),
        sa.Column('evidence_hash', sa.String(length=64), nullable=False),
        sa.Column('state', sa.String(length=32), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint('exercise_id'),
        sa.UniqueConstraint('evidence_hash'),
    )
    op.create_index('ix_game_day_exercises_project_id', 'game_day_exercises', ['project_id'], unique=False)
    op.create_index('ix_game_day_exercises_tenant_id', 'game_day_exercises', ['tenant_id'], unique=False)

    op.create_table(
        'after_action_reviews',
        sa.Column('review_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=True),
        sa.Column('project_id', sa.String(length=64), nullable=True),
        sa.Column('incident_reference', sa.String(length=128), nullable=False),
        sa.Column('findings_json', sa.JSON(), nullable=False),
        sa.Column('corrective_requirements_json', sa.JSON(), nullable=False),
        sa.Column('test_ids_json', sa.JSON(), nullable=False),
        sa.Column('owner', sa.String(length=128), nullable=False),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('state', sa.String(length=32), nullable=False),
        sa.Column('review_hash', sa.String(length=64), nullable=False),
        sa.Column('created_by', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('review_id'),
        sa.UniqueConstraint('review_hash'),
    )
    op.create_index('ix_after_action_reviews_incident_reference', 'after_action_reviews', ['incident_reference'], unique=False)
    op.create_index('ix_after_action_reviews_project_id', 'after_action_reviews', ['project_id'], unique=False)
    op.create_index('ix_after_action_reviews_tenant_id', 'after_action_reviews', ['tenant_id'], unique=False)



    op.create_table(
        'incident_actions',
        sa.Column('incident_action_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=True),
        sa.Column('incident_reference', sa.String(length=128), nullable=False),
        sa.Column('runbook_reference', sa.String(length=512), nullable=False),
        sa.Column('action_type', sa.String(length=128), nullable=False),
        sa.Column('command_reference', sa.String(length=512), nullable=True),
        sa.Column('decision_json', sa.JSON(), nullable=False),
        sa.Column('evidence_references_json', sa.JSON(), nullable=False),
        sa.Column('validation_json', sa.JSON(), nullable=False),
        sa.Column('rollback_json', sa.JSON(), nullable=False),
        sa.Column('communication_json', sa.JSON(), nullable=False),
        sa.Column('sensitive_copy_created', sa.Boolean(), nullable=False),
        sa.Column('action_hash', sa.String(length=64), nullable=False),
        sa.Column('actor_id', sa.String(length=128), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('incident_action_id'),
        sa.UniqueConstraint('action_hash'),
    )
    op.create_index('ix_incident_actions_tenant_id', 'incident_actions', ['tenant_id'], unique=False)
    op.create_index('ix_incident_actions_project_id', 'incident_actions', ['project_id'], unique=False)
    op.create_index('ix_incident_actions_incident_reference', 'incident_actions', ['incident_reference'], unique=False)
    op.create_index('ix_incident_actions_action_type', 'incident_actions', ['action_type'], unique=False)



def downgrade() -> None:
    if os.environ.get("SIP_ALLOW_DESTRUCTIVE_DOWNGRADE") != "1":
        raise RuntimeError("destructive downgrade denied; set SIP_ALLOW_DESTRUCTIVE_DOWNGRADE=1 only in an isolated recovery rehearsal")
    required = {
        "SIP_VERIFIED_BACKUP_REFERENCE": os.environ.get("SIP_VERIFIED_BACKUP_REFERENCE", ""),
        "SIP_DOWNGRADE_DRY_RUN_REFERENCE": os.environ.get("SIP_DOWNGRADE_DRY_RUN_REFERENCE", ""),
        "SIP_DOWNGRADE_AUDIT_REFERENCE": os.environ.get("SIP_DOWNGRADE_AUDIT_REFERENCE", ""),
    }
    invalid = [name for name, value in required.items() if re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None]
    rehearsal = os.environ.get("SIP_DOWNGRADE_REHEARSAL_ID", "")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}", rehearsal) is None:
        invalid.append("SIP_DOWNGRADE_REHEARSAL_ID")
    if invalid:
        raise RuntimeError("destructive downgrade denied; verified backup, dry-run, audit, and rehearsal evidence are required: " + ", ".join(invalid))
    for table in (
        "incident_actions",
        "after_action_reviews",
        "game_day_exercises",
        "support_tickets",
        "support_bundles",
        "cost_reconciliations",
        "capacity_plans",
        "support_access_grants",
        "queue_snapshots",
        "anomaly_alerts",
        "budget_overrides",
        "budget_reservations",
        "budget_policies",
        "actual_costs",
        "cost_estimates",
        "price_catalogs",
        "slo_measurements",
        "performance_budgets",
        "slo_definitions",
        "compute_profiles",
        "resilience_profiles",
        "telemetry_records",
    ):
        op.drop_table(table)
