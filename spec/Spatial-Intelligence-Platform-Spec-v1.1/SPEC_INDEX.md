---
spec_id: SIP-INDEX
title: "Complete Specification Index"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: governance
normative: false
---

# Complete Specification Index

This index covers the complete SIP 1.1.0 Markdown baseline. Paths are repository-relative.


## 00-governance

- [Document Control and Authority](00-governance/000_document_control.md) — `00-governance/000_document_control.md` · normative
- [Normative Language and Requirement IDs](00-governance/001_normative_language.md) — `00-governance/001_normative_language.md` · normative
- [Scope, Boundaries, and Non-Goals](00-governance/002_scope_and_non_goals.md) — `00-governance/002_scope_and_non_goals.md` · normative
- [Product and Engineering Principles](00-governance/003_product_principles.md) — `00-governance/003_product_principles.md` · normative
- [Stakeholders, Personas, and Responsibilities](00-governance/004_stakeholders_and_personas.md) — `00-governance/004_stakeholders_and_personas.md` · normative
- [Requirements Traceability Matrix](00-governance/005_requirements_traceability.md) — `00-governance/005_requirements_traceability.md` · normative
- [Assumptions, Open Questions, and Experiment Register](00-governance/006_open_questions_and_assumptions.md) — `00-governance/006_open_questions_and_assumptions.md` · normative
- [Program Risk Register](00-governance/007_risk_register.md) — `00-governance/007_risk_register.md` · normative
- [Dependency, Dataset, and Model Governance](00-governance/008_license_and_model_governance.md) — `00-governance/008_license_and_model_governance.md` · normative
- [Data Ethics, Truthfulness, and Human Dignity](00-governance/009_data_ethics_and_truthfulness.md) — `00-governance/009_data_ethics_and_truthfulness.md` · normative

## 20-architecture

- [System Context and External Boundaries](20-architecture/200_system_context.md) — `20-architecture/200_system_context.md` · normative
- [Logical Architecture](20-architecture/201_logical_architecture.md) — `20-architecture/201_logical_architecture.md` · normative
- [Deployment Profiles and Topology](20-architecture/202_deployment_architecture.md) — `20-architecture/202_deployment_architecture.md` · normative
- [Implementation Repository Architecture](20-architecture/203_repository_architecture.md) — `20-architecture/203_repository_architecture.md` · normative
- [Service Catalog and Ownership](20-architecture/204_service_catalog.md) — `20-architecture/204_service_catalog.md` · normative
- [Event-Driven Workflows and State Machines](20-architecture/205_event_driven_workflows.md) — `20-architecture/205_event_driven_workflows.md` · normative
- [Identity, Tenancy, Authorization, and Sharing](20-architecture/206_identity_tenancy_permissions.md) — `20-architecture/206_identity_tenancy_permissions.md` · normative
- [Offline-First Operation and Synchronization](20-architecture/207_offline_first_sync.md) — `20-architecture/207_offline_first_sync.md` · normative
- [Observability, Quality Telemetry, and Audit Correlation](20-architecture/208_observability.md) — `20-architecture/208_observability.md` · normative
- [Failure Domains, Resilience, and Degraded Modes](20-architecture/209_failure_domains_and_resilience.md) — `20-architecture/209_failure_domains_and_resilience.md` · normative
- [Architecture Decision Record Process](20-architecture/210_architecture_decisions.md) — `20-architecture/210_architecture_decisions.md` · normative
- [Hybrid Representation Services and Trust Boundaries](20-architecture/211_hybrid_representation_services.md) — `20-architecture/211_hybrid_representation_services.md` · normative

## 30-capture

- [Capture Strategy and Source Abstraction](30-capture/300_capture_strategy.md) — `30-capture/300_capture_strategy.md` · normative
- [First-Party iOS Capture Application](30-capture/301_ios_app.md) — `30-capture/301_ios_app.md` · normative
- [ARKit, LiDAR, RGB, Mesh, and IMU Acquisition](30-capture/302_arkit_lidar_rgb_imu.md) — `30-capture/302_arkit_lidar_rgb_imu.md` · normative
- [Polycam Raw Export Adapter](30-capture/303_polycam_adapter.md) — `30-capture/303_polycam_adapter.md` · normative
- [Canonical Spatial Capture Package](30-capture/304_canonical_capture_package.md) — `30-capture/304_canonical_capture_package.md` · normative
- [Calibration and Known-Scale Controls](30-capture/305_calibration.md) — `30-capture/305_calibration.md` · normative
- [Timestamping and Sensor Synchronization](30-capture/306_time_sync.md) — `30-capture/306_time_sync.md` · normative
- [Live Capture Guidance and Coverage Quality](30-capture/307_capture_guidance_quality.md) — `30-capture/307_capture_guidance_quality.md` · normative
- [Capture Persistence, Resume, and Recovery](30-capture/308_session_resume_recovery.md) — `30-capture/308_session_resume_recovery.md` · normative
- [Capture-Time Privacy and Sensitive-Region Controls](30-capture/309_privacy_redaction_at_capture.md) — `30-capture/309_privacy_redaction_at_capture.md` · normative
- [Future Sensor and Platform Extensions](30-capture/310_multi_sensor_future.md) — `30-capture/310_multi_sensor_future.md` · normative
- [Field Capture Standard Operating Procedures](30-capture/311_field_capture_sops.md) — `30-capture/311_field_capture_sops.md` · normative

## 40-reconstruction

- [LingBot-Map Integration Adapter](40-reconstruction/400_lingbot_integration.md) — `40-reconstruction/400_lingbot_integration.md` · normative
- [LingBot-Map Operating Envelope and Guardrails](40-reconstruction/401_lingbot_limitations_guardrails.md) — `40-reconstruction/401_lingbot_limitations_guardrails.md` · normative
- [Pose Alignment, Scale, and Coordinate Registration](40-reconstruction/402_pose_alignment_scale.md) — `40-reconstruction/402_pose_alignment_scale.md` · normative
- [Factor Graph, Loop Closure, and Global Optimization](40-reconstruction/403_factor_graph_loop_closure.md) — `40-reconstruction/403_factor_graph_loop_closure.md` · normative
- [Depth Observation Normalization and Fusion](40-reconstruction/404_depth_fusion.md) — `40-reconstruction/404_depth_fusion.md` · normative
- [Volumetric Integration and Metric Surface Generation](40-reconstruction/405_tsdf_voxel_fusion.md) — `40-reconstruction/405_tsdf_voxel_fusion.md` · normative
- [Meshing, Texturing, and Level of Detail](40-reconstruction/406_meshing_texturing_lod.md) — `40-reconstruction/406_meshing_texturing_lod.md` · normative
- [Gaussian Splat Visual Reconstruction](40-reconstruction/407_gaussian_splats.md) — `40-reconstruction/407_gaussian_splats.md` · normative
- [Dynamic People, Objects, and Scene Layers](40-reconstruction/408_dynamic_objects.md) — `40-reconstruction/408_dynamic_objects.md` · normative
- [Cross-Session Relocalization and Registration](40-reconstruction/409_cross_session_registration.md) — `40-reconstruction/409_cross_session_registration.md` · normative
- [Temporal Change Detection and Semantic Diff](40-reconstruction/410_change_detection.md) — `40-reconstruction/410_change_detection.md` · normative
- [Quality, Uncertainty, and Acceptance Classification](40-reconstruction/411_quality_uncertainty.md) — `40-reconstruction/411_quality_uncertainty.md` · normative
- [Geometry and Reconstruction Benchmark Program](40-reconstruction/412_benchmarking.md) — `40-reconstruction/412_benchmarking.md` · normative
- [GPU Compute Profiles and Resource Scheduling](40-reconstruction/413_gpu_compute_profiles.md) — `40-reconstruction/413_gpu_compute_profiles.md` · normative
- [Pipeline Reproducibility and Run Manifests](40-reconstruction/414_pipeline_reproducibility.md) — `40-reconstruction/414_pipeline_reproducibility.md` · normative
- [Splat-to-Surface and Hybrid Representation](40-reconstruction/415_splat_surface_hybrid_representation.md) — `40-reconstruction/415_splat_surface_hybrid_representation.md` · normative
- [Splat-Surface Provider Contract](40-reconstruction/416_splat_surface_provider_contract.md) — `40-reconstruction/416_splat_surface_provider_contract.md` · normative
- [Bidirectional Mesh-Splat Interoperability](40-reconstruction/417_bidirectional_mesh_splat_interop.md) — `40-reconstruction/417_bidirectional_mesh_splat_interop.md` · normative
- [Splat and Surface Editing, Cleanup, and Derived LODs](40-reconstruction/418_splat_editing_cleanup.md) — `40-reconstruction/418_splat_editing_cleanup.md` · normative

## 50-data

- [Coordinate Frames, Units, and Transform Semantics](50-data/500_coordinate_frames_units.md) — `50-data/500_coordinate_frames_units.md` · normative
- [Persistent Semantic Scene Graph](50-data/501_scene_graph.md) — `50-data/501_scene_graph.md` · normative
- [Geometry and Visual Asset Model](50-data/502_geometry_asset_model.md) — `50-data/502_geometry_asset_model.md` · normative
- [Evidence, Assertions, Provenance, and Chain of Derivation](50-data/503_evidence_provenance.md) — `50-data/503_evidence_provenance.md` · normative
- [Spatial Git: Commits, Branches, Diffs, and Merges](50-data/504_temporal_spatial_git.md) — `50-data/504_temporal_spatial_git.md` · normative
- [Annotations, Spatial Anchors, and Measurements](50-data/505_annotations_anchors_measurements.md) — `50-data/505_annotations_anchors_measurements.md` · normative
- [Ontology, Taxonomy, and Extensibility](50-data/506_ontology_taxonomy.md) — `50-data/506_ontology_taxonomy.md` · normative
- [Transactional, Spatial, Search, and Graph Storage](50-data/507_storage_database_schema.md) — `50-data/507_storage_database_schema.md` · normative
- [Immutable Asset Storage and Content Addressing](50-data/508_asset_storage_content_addressing.md) — `50-data/508_asset_storage_content_addressing.md` · normative
- [Spatial, Temporal, Text, Vector, and Graph Search](50-data/509_search_indexing.md) — `50-data/509_search_indexing.md` · normative
- [Open Interchange and Export Format Profiles](50-data/510_interchange_formats.md) — `50-data/510_interchange_formats.md` · normative
- [BIM, IFC 4.3, BCF, and Design/As-Built Mapping](50-data/511_bim_ifc_bcf.md) — `50-data/511_bim_ifc_bcf.md` · normative
- [Digital Twin Timeline and State Projection](50-data/512_digital_twin_versioning.md) — `50-data/512_digital_twin_versioning.md` · normative
- [Retention, Legal Hold, Deletion, and Portability](50-data/513_data_retention_deletion.md) — `50-data/513_data_retention_deletion.md` · normative
- [Hybrid Representation Asset Contract](50-data/514_hybrid_representation_asset_contract.md) — `50-data/514_hybrid_representation_asset_contract.md` · normative

## 60-platform

- [API Design, Versioning, and Error Semantics](60-platform/600_api_guidelines.md) — `60-platform/600_api_guidelines.md` · normative
- [REST Resource API](60-platform/601_rest_api.md) — `60-platform/601_rest_api.md` · normative
- [Internal Worker and Streaming Contracts](60-platform/602_grpc_worker_api.md) — `60-platform/602_grpc_worker_api.md` · normative
- [Domain Event Catalog](60-platform/603_event_catalog.md) — `60-platform/603_event_catalog.md` · normative
- [Pipeline Job Orchestration and Review Gates](60-platform/604_job_orchestration.md) — `60-platform/604_job_orchestration.md` · normative
- [Web Spatial Viewer and Evidence Interface](60-platform/605_web_viewer.md) — `60-platform/605_web_viewer.md` · normative
- [Desktop Expert Review Application](60-platform/606_desktop_review.md) — `60-platform/606_desktop_review.md` · normative
- [Spatial Query Language and Saved Views](60-platform/607_spatial_query_language.md) — `60-platform/607_spatial_query_language.md` · normative
- [Spatial LLM and Agent Tooling](60-platform/608_spatial_llm_agents.md) — `60-platform/608_spatial_llm_agents.md` · normative
- [Model Registry and Deployment Control](60-platform/609_model_registry.md) — `60-platform/609_model_registry.md` · normative
- [Adapter and Plugin SDK](60-platform/610_plugin_sdk.md) — `60-platform/610_plugin_sdk.md` · normative
- [Import, Export, Packaging, and Migration](60-platform/611_import_export.md) — `60-platform/611_import_export.md` · normative
- [Collaboration, Review, Tasks, and Notifications](60-platform/612_notifications_collaboration.md) — `60-platform/612_notifications_collaboration.md` · normative
- [Hybrid Scene Runtime](60-platform/613_hybrid_scene_runtime.md) — `60-platform/613_hybrid_scene_runtime.md` · normative
- [Splat-Surface APIs, Jobs, and Domain Events](60-platform/614_splat_surface_api_and_events.md) — `60-platform/614_splat_surface_api_and_events.md` · normative

## 70-construction

- [Construction Spatial Reference Overview](70-construction/700_vertical_overview.md) — `70-construction/700_vertical_overview.md` · normative
- [Construction Project and Spatial Hierarchy](70-construction/701_project_building_floor_room.md) — `70-construction/701_project_building_floor_room.md` · normative
- [Existing-Condition Survey and As-Built Workflow](70-construction/702_field_survey_as_built.md) — `70-construction/702_field_survey_as_built.md` · normative
- [Fire Alarm Spatial Documentation](70-construction/703_fire_alarm.md) — `70-construction/703_fire_alarm.md` · normative
- [Access Control and Door Intelligence](70-construction/704_access_control.md) — `70-construction/704_access_control.md` · normative
- [BAS, Mechanical, Electrical, and Equipment Documentation](70-construction/705_bas_mechanical_electrical.md) — `70-construction/705_bas_mechanical_electrical.md` · normative
- [Drawings, Specifications, RFIs, Submittals, and Spatial Linking](70-construction/706_drawings_specs_rfis_submittals.md) — `70-construction/706_drawings_specs_rfis_submittals.md` · normative
- [Deficiencies, Punch, Testing, and Commissioning](70-construction/707_punch_deficiency_commissioning.md) — `70-construction/707_punch_deficiency_commissioning.md` · normative
- [Measurement Authority and Field Verification](70-construction/708_measurements_truth_hierarchy.md) — `70-construction/708_measurements_truth_hierarchy.md` · normative
- [Construction Progress and Change Tracking](70-construction/709_progress_change_tracking.md) — `70-construction/709_progress_change_tracking.md` · normative
- [BIM Handoff and Facility Operations](70-construction/710_bim_handoff_facility_operations.md) — `70-construction/710_bim_handoff_facility_operations.md` · normative
- [Construction Reports, Views, and Deliverables](70-construction/711_construction_reporting.md) — `70-construction/711_construction_reporting.md` · normative
- [Construction Vertical Acceptance Tests](70-construction/712_construction_acceptance_tests.md) — `70-construction/712_construction_acceptance_tests.md` · normative
- [Construction Demonstration Scenario](70-construction/713_construction_demo_scenario.md) — `70-construction/713_construction_demo_scenario.md` · normative
- [Hybrid Representation for Construction and Facility Operations](70-construction/714_hybrid_representation_construction.md) — `70-construction/714_hybrid_representation_construction.md` · normative

## 80-liveforever

- [LiveForever Spatial Memory Overview](80-liveforever/800_vertical_overview.md) — `80-liveforever/800_vertical_overview.md` · normative
- [Memory Graph and Narrative Data Model](80-liveforever/801_memory_graph.md) — `80-liveforever/801_memory_graph.md` · normative
- [Interview Agent, Recording, and Conversational Capture](80-liveforever/802_interview_agent.md) — `80-liveforever/802_interview_agent.md` · normative
- [Places, Objects, People, and Relationships](80-liveforever/803_places_objects_people.md) — `80-liveforever/803_places_objects_people.md` · normative
- [Photographs, Video, Letters, Documents, and Archives](80-liveforever/804_photos_video_documents.md) — `80-liveforever/804_photos_video_documents.md` · normative
- [Voice, Likeness, Avatar, and Simulated Presence](80-liveforever/805_voice_avatar_presence.md) — `80-liveforever/805_voice_avatar_presence.md` · normative
- [Spatial and Temporal Memory Reconstruction](80-liveforever/806_memory_reconstruction.md) — `80-liveforever/806_memory_reconstruction.md` · normative
- [Conflicting Memories, Corrections, and Family Disputes](80-liveforever/807_conflicting_memories.md) — `80-liveforever/807_conflicting_memories.md` · normative
- [Consent, Privacy, Family Governance, and Posthumous Administration](80-liveforever/808_consent_privacy_family_governance.md) — `80-liveforever/808_consent_privacy_family_governance.md` · normative
- [AI Truth Labels and Evidence View](80-liveforever/809_ai_truth_labels.md) — `80-liveforever/809_ai_truth_labels.md` · normative
- [LiveForever Experience and Narrative Design](80-liveforever/810_experience_design.md) — `80-liveforever/810_experience_design.md` · normative
- [Long-Term Preservation and Digital Legacy](80-liveforever/811_long_term_preservation.md) — `80-liveforever/811_long_term_preservation.md` · normative
- [LiveForever Vertical Acceptance Tests](80-liveforever/812_liveforever_acceptance_tests.md) — `80-liveforever/812_liveforever_acceptance_tests.md` · normative
- [LiveForever Demonstration Scenario](80-liveforever/813_liveforever_demo_scenario.md) — `80-liveforever/813_liveforever_demo_scenario.md` · normative
- [Hybrid Representation for LiveForever Spatial Memories](80-liveforever/814_hybrid_representation_liveforever.md) — `80-liveforever/814_hybrid_representation_liveforever.md` · normative

## 90-security-ops

- [Threat Model](90-security-ops/900_threat_model.md) — `90-security-ops/900_threat_model.md` · normative
- [Security Architecture and Zero-Trust Controls](90-security-ops/901_security_architecture.md) — `90-security-ops/901_security_architecture.md` · normative
- [Encryption and Key Management](90-security-ops/902_encryption_key_management.md) — `90-security-ops/902_encryption_key_management.md` · normative
- [Privacy Engineering and Compliance Controls](90-security-ops/903_privacy_compliance.md) — `90-security-ops/903_privacy_compliance.md` · normative
- [Audit, Integrity, and Chain of Custody](90-security-ops/904_audit_chain_of_custody.md) — `90-security-ops/904_audit_chain_of_custody.md` · normative
- [SRE Runbooks and Incident Operations](90-security-ops/905_sre_runbooks.md) — `90-security-ops/905_sre_runbooks.md` · normative
- [Backup, Restore, and Disaster Recovery](90-security-ops/906_backup_restore_dr.md) — `90-security-ops/906_backup_restore_dr.md` · normative
- [Cloud, Hybrid, Edge, and Local Deployment](90-security-ops/907_cloud_hybrid_deployment.md) — `90-security-ops/907_cloud_hybrid_deployment.md` · normative
- [AWS Reference Architecture](90-security-ops/908_aws_reference_architecture.md) — `90-security-ops/908_aws_reference_architecture.md` · normative
- [Cost, Capacity, and Unit Economics Model](90-security-ops/909_cost_capacity_model.md) — `90-security-ops/909_cost_capacity_model.md` · normative
- [Performance and Scalability Budgets](90-security-ops/910_performance_budgets.md) — `90-security-ops/910_performance_budgets.md` · normative
- [CI/CD, Software Supply Chain, and Release Engineering](90-security-ops/911_ci_cd_supply_chain.md) — `90-security-ops/911_ci_cd_supply_chain.md` · normative
- [Support, Customer Operations, and Safe Diagnostics](90-security-ops/912_support_operations.md) — `90-security-ops/912_support_operations.md` · normative
- [External Spatial Provider Security and Governance](90-security-ops/913_external_spatial_provider_governance.md) — `90-security-ops/913_external_spatial_provider_governance.md` · normative

## 95-testing-delivery

- [Master Test Strategy](95-testing-delivery/950_test_strategy.md) — `95-testing-delivery/950_test_strategy.md` · normative
- [Unit, Contract, Integration, and End-to-End Tests](95-testing-delivery/951_unit_integration_e2e.md) — `95-testing-delivery/951_unit_integration_e2e.md` · normative
- [Sensor, Calibration, and Geometry Validation](95-testing-delivery/952_sensor_geometry_tests.md) — `95-testing-delivery/952_sensor_geometry_tests.md` · normative
- [Security, Privacy, Consent, and Abuse Testing](95-testing-delivery/953_security_privacy_tests.md) — `95-testing-delivery/953_security_privacy_tests.md` · normative
- [Dataset and Benchmark Curation Plan](95-testing-delivery/954_dataset_benchmark_plan.md) — `95-testing-delivery/954_dataset_benchmark_plan.md` · normative
- [Release Gates and Promotion Evidence](95-testing-delivery/955_release_gates.md) — `95-testing-delivery/955_release_gates.md` · normative
- [MVP Definition and Build Plan](95-testing-delivery/956_mvp_plan.md) — `95-testing-delivery/956_mvp_plan.md` · normative
- [Product and Research Roadmap](95-testing-delivery/957_roadmap.md) — `95-testing-delivery/957_roadmap.md` · normative
- [Sequenced Epic Backlog](95-testing-delivery/958_epic_backlog.md) — `95-testing-delivery/958_epic_backlog.md` · normative
- [Developer Onboarding and Local Environment](95-testing-delivery/959_developer_onboarding.md) — `95-testing-delivery/959_developer_onboarding.md` · normative
- [Definition of Done](95-testing-delivery/960_definition_of_done.md) — `95-testing-delivery/960_definition_of_done.md` · normative
- [Splat-Surface Benchmark and Acceptance Plan](95-testing-delivery/961_splat_surface_benchmark_acceptance.md) — `95-testing-delivery/961_splat_surface_benchmark_acceptance.md` · normative

## 99-appendices

- [Splat-Surface Research and Dependency Audit](99-appendices/989_splat_surface_research_and_dependency_audit.md) — `99-appendices/989_splat_surface_research_and_dependency_audit.md` · informative
- [Source Repository and Research Audit](99-appendices/990_source_repo_audit.md) — `99-appendices/990_source_repo_audit.md` · informative
- [Dependency and License Decision Matrix](99-appendices/991_dependency_license_matrix.md) — `99-appendices/991_dependency_license_matrix.md` · informative
- [API and Event Examples](99-appendices/992_api_examples.md) — `99-appendices/992_api_examples.md` · informative
- [Canonical Schema Examples](99-appendices/993_schema_examples.md) — `99-appendices/993_schema_examples.md` · informative
- [Architecture and Workflow Diagrams](99-appendices/994_mermaid_diagrams.md) — `99-appendices/994_mermaid_diagrams.md` · informative
- [Failure Mode and Recovery Catalog](99-appendices/995_failure_mode_catalog.md) — `99-appendices/995_failure_mode_catalog.md` · normative
- [Glossary](99-appendices/996_glossary.md) — `99-appendices/996_glossary.md` · informative
- [External References](99-appendices/997_reference_links.md) — `99-appendices/997_reference_links.md` · informative
- [Initial Architecture Decision Log](99-appendices/998_decision_log.md) — `99-appendices/998_decision_log.md` · informative
- [Specification and Release Readiness Checklist](99-appendices/999_spec_completion_checklist.md) — `99-appendices/999_spec_completion_checklist.md` · informative

## Root documents

- [Specification Changelog](CHANGELOG.md) — `CHANGELOG.md` · informative
- [Contributing to the Specification](CONTRIBUTING_TO_SPEC.md) — `CONTRIBUTING_TO_SPEC.md` · informative
- [Binding Decision Summary](DECISION_SUMMARY.md) — `DECISION_SUMMARY.md` · normative
- [Implementation Kickoff Prompt](IMPLEMENTATION_KICKOFF_PROMPT.md) — `IMPLEMENTATION_KICKOFF_PROMPT.md` · informative
- [Implementation Sequence](IMPLEMENTATION_SEQUENCE.md) — `IMPLEMENTATION_SEQUENCE.md` · normative
- [Master Engineering Specification](MASTER_SPECIFICATION.md) — `MASTER_SPECIFICATION.md` · normative
- [Migration from SIP v1.0 to v1.1](MIGRATION_FROM_1.0.md) — `MIGRATION_FROM_1.0.md` · normative
- [Spatial Intelligence Platform (SIP)](README.md) — `README.md` · normative
- [Repository Blueprint](REPOSITORY_BLUEPRINT.md) — `REPOSITORY_BLUEPRINT.md` · normative
- [Version 1.1 Hybrid Representation Changeset](V1_1_HYBRID_REPRESENTATION_CHANGESET.md) — `V1_1_HYBRID_REPRESENTATION_CHANGESET.md` · normative
- [SIP v1.1 Hybrid Representation Migration Operator Guide](V1_1_MIGRATION_GUIDE.md) — `V1_1_MIGRATION_GUIDE.md` · informative
