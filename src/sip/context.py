from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .agents import AgentService
from .assets import AssetService, ContentAddressedStore, LocalContentAddressedStore, S3ContentAddressedStore
from .audit import AuditService
from .collaboration import CollaborationService, NotificationService
from .config import Settings
from .construction import ConstructionService
from .database import Database
from .deployment import DeploymentService
from .exporting import PreservationService
from .lifecycle import AdmissionController, BackupRecoveryService, KeyRotationService, LifecycleService
from .liveforever import LiveForeverService
from .hybrid import HybridControlService
from .model_governance import ModelRegistry
from .operations import OperationService
from .ops_intelligence import OperationsIntelligenceService
from .policy import PolicyService
from .representations import ProviderRegistry, RepresentationPublisher, RepresentationService
from .scene import SceneService
from .scene_runtime import SceneRuntimeService
from .search import SearchService
from .security import EnvelopeCipher, SignedTokenCodec
from .security_ops import SecurityOperationsService
from .spatial_data import SpatialDataService
from .tenancy import TenancyService


@dataclass
class PlatformContext:
    settings: Settings
    database: Database
    store: ContentAddressedStore
    audit: AuditService
    assets: AssetService
    tenancy: TenancyService
    policy: PolicyService
    operations: OperationService
    preservation: PreservationService
    lifecycle: LifecycleService
    backup_recovery: BackupRecoveryService
    key_rotation: KeyRotationService
    admission: AdmissionController
    scene: SceneService
    spatial_data: SpatialDataService
    scene_runtime: SceneRuntimeService
    providers: ProviderRegistry
    representations: RepresentationService
    hybrid: HybridControlService
    publisher: RepresentationPublisher
    models: ModelRegistry
    construction: ConstructionService
    liveforever: LiveForeverService
    search: SearchService
    collaboration: CollaborationService
    notifications: NotificationService
    agents: AgentService
    security_ops: SecurityOperationsService
    operations_intelligence: OperationsIntelligenceService
    deployment: DeploymentService

    @classmethod
    def create(cls, settings: Settings | None = None, *, create_schema: bool | None = None) -> "PlatformContext":
        settings = settings or Settings.from_env()
        if create_schema is None:
            create_schema = settings.environment in {"development", "test"} and settings.database_url.startswith("sqlite")
        database = Database(settings.database_url, create=create_schema)
        cipher = EnvelopeCipher(settings.master_key, settings.master_key_id)
        if settings.object_store_backend == "local":
            store: ContentAddressedStore = LocalContentAddressedStore(settings.object_store_root, cipher)
        else:
            import boto3

            client = boto3.client(
                "s3",
                region_name=settings.s3_region,
                endpoint_url=settings.s3_endpoint_url,
            )
            store = S3ContentAddressedStore(
                bucket=settings.s3_bucket or "",
                prefix=settings.s3_prefix,
                cipher=cipher,
                client=client,
                kms_key_id=settings.s3_kms_key_id,
            )
        audit = AuditService(database, settings.signing_key)
        token_codec = SignedTokenCodec(settings.signing_key)
        assets = AssetService(database, store, audit, token_codec, multipart_root=settings.multipart_root)
        preservation = PreservationService(database, assets)
        policy = PolicyService(database, audit)
        search = SearchService(database, audit)
        models = ModelRegistry(database, settings.signing_key)
        operations = OperationService(database, audit)
        admission = AdmissionController(database, audit)
        providers = ProviderRegistry(database, audit, settings.signing_key)
        representations = RepresentationService(database, audit)
        hybrid = HybridControlService(
            database,
            audit,
            operations,
            providers,
            representations,
            models,
            admission,
            token_codec,
            policy,
            environment=settings.environment,
        )
        scene_service = SceneService(database, audit)
        scene_runtime = SceneRuntimeService(database, audit, policy, hybrid, scene_service)
        security_ops = SecurityOperationsService(
            database,
            audit,
            token_codec,
            settings.signing_key,
            environment=settings.environment,
            local_only=settings.object_store_backend == "local",
        )
        operations_intelligence = OperationsIntelligenceService(
            database,
            audit,
            bundle_root=settings.object_store_root.parent / "support-bundles",
            release="1.1.0-progress09",
            environment=settings.environment,
        )
        deployment = DeploymentService(
            database,
            audit,
            settings.signing_key,
            root=Path(__file__).resolve().parents[2],
            environment=settings.environment,
            security_ops=security_ops,
        )
        assets.set_deployment_service(deployment)
        operations.set_deployment_service(deployment)
        return cls(
            settings=settings,
            database=database,
            store=store,
            audit=audit,
            assets=assets,
            tenancy=TenancyService(database, audit),
            policy=policy,
            operations=operations,
            preservation=preservation,
            lifecycle=LifecycleService(database, assets, audit),
            backup_recovery=BackupRecoveryService(database, preservation, assets, audit),
            key_rotation=KeyRotationService(database, assets, audit),
            admission=admission,
            scene=scene_service,
            spatial_data=SpatialDataService(database, audit, policy, models),
            scene_runtime=scene_runtime,
            providers=providers,
            representations=representations,
            hybrid=hybrid,
            publisher=RepresentationPublisher(database, audit, providers),
            models=models,
            construction=ConstructionService(database, audit),
            liveforever=LiveForeverService(database, audit),
            search=search,
            collaboration=CollaborationService(database),
            notifications=NotificationService(database),
            agents=AgentService(database, policy, search, audit),
            security_ops=security_ops,
            operations_intelligence=operations_intelligence,
            deployment=deployment,
        )


def temporary_settings(root: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite:///{root / 'sip.sqlite3'}",
        object_store_backend="local",
        object_store_root=root / "objects",
        multipart_root=root / "multipart",
        s3_bucket=None,
        s3_prefix="sip-test",
        s3_region=None,
        s3_endpoint_url=None,
        s3_kms_key_id=None,
        master_key=b"m" * 32,
        master_key_id="test-master-v1",
        signing_key=b"a" * 32,
        allow_development_auth=True,
    )
