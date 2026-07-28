---
spec_id: APP-DIAG
title: "Architecture and Workflow Diagrams"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: appendix
normative: false
---
# Architecture and Workflow Diagrams

## System landscape

```mermaid
flowchart LR
    subgraph Capture
      IOS[iOS Capture]
      POLY[Polycam Raw Export]
      OTHER[Video / 360 / External LiDAR / BIM]
    end
    subgraph ControlPlane[Control Plane]
      API[Control API]
      IAM[Identity and Policy]
      WF[Workflow Orchestration]
      AUD[Audit and Governance]
    end
    subgraph DataPlane[Data Plane]
      PG[(PostgreSQL / PostGIS)]
      OBJ[(Content-addressed Object Storage)]
      IDX[(Search / Vector Index)]
      Q[(Queue / Event Bus)]
    end
    subgraph Compute[Compute Plane]
      VAL[Normalize / Validate]
      LING[LingBot Adapter]
      OPT[Pose Optimizer]
      FUS[Depth / TSDF Fusion]
      SPLAT[Splat / Visual]
      SEM[Semantic / Media]
    end
    subgraph Experience
      WEB[Web Viewer]
      DESK[Desktop Review]
      CON[Construction]
      LF[LiveForever]
      AG[Spatial Agent]
    end

    IOS --> API
    POLY --> API
    OTHER --> API
    API --> IAM
    API --> PG
    API --> OBJ
    API --> WF
    WF --> Q
    Q --> VAL
    VAL --> LING
    VAL --> OPT
    LING --> OPT
    OPT --> FUS
    OPT --> SPLAT
    VAL --> SEM
    FUS --> OBJ
    SPLAT --> OBJ
    SEM --> PG
    WF --> AUD
    WEB --> API
    DESK --> API
    CON --> API
    LF --> API
    AG --> API
    PG --> IDX
```

## Capture state machine

```mermaid
stateDiagram-v2
    [*] --> Setup
    Setup --> CalibrationCheck
    CalibrationCheck --> Ready: pass or permitted warning
    CalibrationCheck --> Setup: fail
    Ready --> Capturing
    Capturing --> Paused: operator pause
    Capturing --> TrackingRecovery: tracking limited/lost
    TrackingRecovery --> Capturing: relocalized
    TrackingRecovery --> SegmentFinalize: start new local frame
    Paused --> Capturing
    Paused --> SegmentFinalize
    Capturing --> SegmentFinalize: room/area complete
    SegmentFinalize --> Ready: next segment
    SegmentFinalize --> SessionFinalize: capture complete
    SessionFinalize --> LocalVerified
    LocalVerified --> Uploading: cloud/hybrid allowed
    LocalVerified --> Complete: local-only
    Uploading --> UploadPaused: offline/error
    UploadPaused --> Uploading
    Uploading --> ServerVerified
    ServerVerified --> Complete
    Setup --> Recovering: restored journal
    Recovering --> Paused
    Recovering --> SessionFinalize
    Complete --> [*]
```

## Reconstruction workflow

```mermaid
sequenceDiagram
    participant C as Capture Service
    participant W as Workflow
    participant V as Validator
    participant L as LingBot Worker
    participant M as Metric Worker
    participant O as Optimizer
    participant F as Fusion
    participant S as Scene Service
    participant R as Reviewer

    C->>W: CaptureSessionFinalized
    W->>V: validate(package manifest)
    V-->>W: normalized observations + quality
    par Learned lane
      W->>L: execute approved profile
      L-->>W: poses/depth/confidence + manifest
    and Metric lane
      W->>M: normalize ARKit/LiDAR/control
      M-->>W: metric observations
    end
    W->>O: align and optimize observations
    O-->>W: pose solution + residual report
    W->>F: fuse accepted depth observations
    F-->>W: metric volume/mesh + quality
    W->>S: create review commit
    S-->>R: review task
    R->>S: accept with limitations / reject / recapture
    S-->>W: SceneCommitPublished
```

## Truth and authority model

```mermaid
flowchart TB
    SRC[Source class] --> OBS[Observed / measured / recalled / documented / inferred / generated]
    CONF[Confidence] --> NUM[Calibrated uncertainty or model confidence]
    COR[Corroboration] --> EVD[Supporting / contradicting evidence]
    AUTH[Authority] --> STA[Draft / preview / accepted reference / verified authoritative]
    OBS --> ASSERT[Assertion or geometry region]
    NUM --> ASSERT
    EVD --> ASSERT
    STA --> ASSERT
    ASSERT --> UI[Viewer and Reports expose all dimensions]
```

## Spatial Git

```mermaid
gitGraph
   commit id: "initial-place"
   branch design
   checkout design
   commit id: "IFC-design-r1"
   checkout main
   branch field-observation
   checkout field-observation
   commit id: "visit-2026-07-26"
   commit id: "device-mapping-review"
   checkout main
   merge field-observation id: "accepted-reference"
   branch verified-as-built
   checkout verified-as-built
   commit id: "field-dimensions-verified"
   checkout main
   merge verified-as-built id: "verified-release"
```

## Construction authority hierarchy

```mermaid
flowchart TB
    V1[Verified survey/control] --> A[Permitted authoritative use]
    V2[Accountable field measurement] --> A
    D[Accepted design record] --> DI[Design intent only]
    C[Calibrated sensor observation] --> R[Reference use by policy]
    S[Unverified scan estimate] --> I[Informational / estimating with warning]
    L[Learned inference] --> H[Hypothesis / proposed review]
    G[Generated placeholder] --> P[Presentation only]
```

## LiveForever evidence-backed experience

```mermaid
flowchart LR
    INT[Interview source] --> MEM[Memory graph]
    PHOTO[Photos / video / letters] --> MEM
    SCAN[Current place/object scan] --> PLACE[Spatial scene]
    HIST[Historical media / maps] --> RECON[Historical reconstruction]
    MEM --> ANCH[Spatial anchors]
    PLACE --> ANCH
    RECON --> ANCH
    CONS[Consent and audience] --> EXP[Experience edition]
    ANCH --> EXP
    MEM --> EXP
    EXP --> VIEW[Guided / explore / timeline / evidence view]
```

## Permission evaluation

```mermaid
flowchart LR
    U[Authenticated principal] --> P[Policy engine]
    R[Requested action/resource] --> P
    T[Tenant/project role] --> P
    C[Data classification] --> P
    S[Spatial volume/entity restriction] --> P
    K[Consent/purpose/audience] --> P
    TIME[Time/expiry/legal hold] --> P
    P -->|allow with obligations| O[Filter/redact/watermark/audit]
    P -->|deny| D[Non-disclosing denial]
```

## Deployment profiles

```mermaid
flowchart TB
    subgraph Local[Local-only]
      LP[Local PostgreSQL/object store]
      LG[Local GPU]
      LV[Local viewer]
    end
    subgraph Hybrid[Hybrid]
      EDGE[Encrypted edge cache/raw store]
      CLOUD[Cloud control and approved compute]
    end
    subgraph Cloud[Cloud]
      CP[Regional control plane]
      DP[Managed data plane]
      GP[Elastic GPU pools]
    end
    PHONE[iPhone] --> LP
    PHONE --> EDGE
    PHONE --> CP
    EDGE --> CLOUD
    CP --> DP
    CP --> GP
```

## Version 1.1 diagrams

The diagram set shall include provider admission and trust boundaries, conversion/quarantine/publication state machine, hybrid runtime capability resolution, support-map anchor remapping, construction role composition, LiveForever branch/evidence composition, provider revocation, and v1.0-to-v1.1 migration.
