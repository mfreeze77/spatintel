import Foundation
import Testing
@testable import CaptureCore
@testable import CaptureSensors

private func temporaryDirectory(_ name: String = UUID().uuidString) throws -> URL {
    let url = FileManager.default.temporaryDirectory.appendingPathComponent("sip-capture-tests").appendingPathComponent(name)
    try? FileManager.default.removeItem(at: url)
    try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    return url
}

private func policy() -> CapturePolicyBundle {
    .init(projectID: "project-1", permittedSensors: [.rgb, .lidarDepth, .confidence, .mesh, .motion], cloudTransferAllowed: false, cableExportAllowed: true, purgeAfterVerifiedReceiptAllowed: false, consentContext: "Synthetic fixture consent")
}

private func profile() throws -> CaptureProfile {
    try .init(profileID: "building-reference", requiredSensors: [.rgb, .lidarDepth], imageResolution: .init(width: 1920, height: 1440), targetFrameRate: 30, operatorPattern: "slow overlapping loops", expectedRangeMeters: 0.3...5.0, blurMaximum: 0.35, minimumDepthCoverage: 0.45, storageBudgetBytes: 4_000_000_000)
}

private func frame(id: String = "frame-1", timestamp: UInt64 = 1, tracking: TrackingState = .normal) throws -> FrameObservation {
    try .init(frameID: id, timestampNanoseconds: timestamp, imageAssetID: "rgb-\(id)", depthAssetID: "depth-\(id)", confidenceAssetID: "confidence-\(id)", cameraTransform: [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1], intrinsics: [1000,0,960, 0,1000,720, 0,0,1], resolution: .init(width: 1920, height: 1440), trackingState: tracking, limitedTrackingReason: tracking == .normal ? nil : .insufficientFeatures, exposure: .init(durationSeconds: 0.01, iso: 100, exposureTargetOffset: 0), orientation: .landscapeRight, invalidDepthPreserved: true)
}

@Test("CAPIOS-001 state machine covers required persisted states and rejects invalid transitions")
func stateMachineTransitions() throws {
    var machine = CaptureStateMachine()
    try machine.apply(.beginCalibration); #expect(machine.state == .calibrationCheck)
    try machine.apply(.calibrationPassed); #expect(machine.state == .ready)
    try machine.apply(.beginCapture); #expect(machine.state == .capturing)
    try machine.apply(.trackingLost); #expect(machine.state == .trackingRecovery)
    try machine.apply(.trackingRecovered); #expect(machine.state == .capturing)
    try machine.apply(.pause); #expect(machine.state == .paused)
    try machine.apply(.resume); #expect(machine.state == .capturing)
    try machine.apply(.finalizeSegment); #expect(machine.state == .segmentFinalization)
    try machine.apply(.segmentFinalized); #expect(machine.state == .ready)
    try machine.apply(.finalizeSession); #expect(machine.state == .sessionFinalization)
    try machine.apply(.packageFinalized); #expect(machine.state == .upload)
    try machine.apply(.receiptVerified); #expect(machine.state == .verified)
    #expect(throws: CaptureCoreError.self) { try machine.apply(.beginCapture) }
}

@Test("CAPIOS-003 CAPREC-001 append-only journal recovers and detects tampering")
func journalRecoveryAndTamper() async throws {
    let root = try temporaryDirectory()
    let url = root.appendingPathComponent("capture.journal.jsonl")
    let journal = try AppendOnlyJournal(url: url, fsyncInterval: 1)
    let first = try await journal.append(event: "session_started", timestampNanoseconds: 1)
    let second = try await journal.append(event: "frame_finalized", payload: ["frame": "1"], timestampNanoseconds: 2)
    #expect(second.previousHash == first.recordHash)
    #expect(try AppendOnlyJournal.readAndVerify(url: url).count == 2)
    var data = try Data(contentsOf: url)
    let index = data.firstIndex(of: Character("f").asciiValue!)!
    data[index] = Character("x").asciiValue!
    try data.write(to: url)
    #expect(throws: Error.self) { try AppendOnlyJournal.readAndVerify(url: url) }
}

@Test("CAPSENS-001 CAPSENS-002 frame metadata preserves invalid depth semantics")
func frameMetadata() throws {
    let observation = try frame()
    #expect(observation.cameraTransform.count == 16)
    #expect(observation.intrinsics.count == 9)
    #expect(observation.depthAssetID != nil)
    #expect(observation.confidenceAssetID != nil)
    #expect(observation.invalidDepthPreserved)
}

@Test("CAPSENS-003 CAPSENS-005 fixture adapter emits explicit tracking events and bounded drops")
func adapterAndBoundedBuffer() async throws {
    let observation = try frame()
    let adapter = FixtureSensorAdapter(events: [.trackingChanged(state: .limited, reason: .relocalizing), .relocalizationStarted, .frame(observation)])
    try await adapter.start(policy: policy(), profile: profile())
    #expect(await adapter.nextEvent() == .trackingChanged(state: .limited, reason: .relocalizing))
    #expect(await adapter.nextEvent() == .relocalizationStarted)
    let buffer = try BoundedObservationBuffer(capacity: 1)
    #expect(await buffer.enqueue(observation))
    #expect(!(await buffer.enqueue(try frame(id: "frame-2", timestamp: 2))))
    #expect(await buffer.droppedObservations().first?.cause == "bounded_queue_full")
}

@Test("CAPQUAL-001 CAPQUAL-003 quality warnings state cause consequence and corrective action")
func qualityWarnings() throws {
    let signals = QualitySignals(blur: 0.8, exposureClippingFraction: 0.2, angularVelocityRadiansPerSecond: 2, trackingState: .limited, depthCoverage: 0.1, viewpointDiversity: 0.05, weakSurfaceFraction: 0.8)
    let warnings = QualityEvaluator.warnings(signals: signals, profile: try profile())
    #expect(warnings.count >= 5)
    #expect(warnings.allSatisfy { !$0.cause.isEmpty && !$0.consequence.isEmpty && !$0.correctiveAction.isEmpty })
}

@Test("CAPIOS-004 CAPREC-004 resource pressure degrades safely before filesystem exhaustion")
func resourcePressure() {
    #expect(ResourceController.decision(.init(thermalState: .critical, availableStorageBytes: 1_000_000_000, batteryFraction: 0.5, memoryPressure: false), reserveBytes: 100_000_000).0 == .pausePreservingPackage)
    #expect(ResourceController.decision(.init(thermalState: .nominal, availableStorageBytes: 1, batteryFraction: 0.9, memoryPressure: false), reserveBytes: 100).0 == .pausePreservingPackage)
    #expect(ResourceController.decision(.init(thermalState: .serious, availableStorageBytes: 1_000, batteryFraction: 0.9, memoryPressure: false), reserveBytes: 100).0 == .disableOptionalSensors)
}

@Test("CAPIOS-005 CAPIOS-006 policy disables sensors and purge fails closed")
func policyAndPurge() throws {
    #expect(!policy().permits(.audio))
    #expect(throws: CaptureCoreError.self) { try PurgePolicy.authorize(.init(packageIntegrityVerified: true, destinationReceiptVerified: false, userAuthorized: true, policy: policy())) }
    try PurgePolicy.authorize(.init(packageIntegrityVerified: true, destinationReceiptVerified: true, userAuthorized: true, policy: policy()))
}

@Test("CAPPRIV-002 CAPPRIV-003 CAPPRIV-005 detector suggestions remain reviewable and broad export fails closed")
func privacyGate() throws {
    let suggested = RestrictedRegion(regionID: "r1", kind: .screen, origin: .detectorSuggestion, state: .suggested, frameID: "frame-1", normalizedBounds: [0.1,0.1,0.2,0.2], spatialAnchorID: nil, reason: "screen detector")
    #expect(throws: CaptureCoreError.self) { try PrivacyExportGate.validate(regions: [suggested], operations: [], broadShare: true) }
    var redacted = suggested; redacted.state = .redacted
    let operation = RedactionOperation(operationID: "op1", sourceAssetID: "rgb", derivedAssetID: "rgb-redacted", regionID: "r1", operation: "blur", parameters: ["radius": "20"])
    try PrivacyExportGate.validate(regions: [redacted], operations: [operation], broadShare: true)
}

@Test("CAPSTRAT-003 CAPSTRAT-004 profiles cannot claim accuracy without validation evidence")
func profileClaims() throws {
    #expect(throws: CaptureCoreError.self) {
        try CaptureProfile(profileID: "invalid", requiredSensors: [.rgb], imageResolution: .init(width: 100, height: 100), targetFrameRate: 30, operatorPattern: "loop", expectedRangeMeters: 0.2...3, blurMaximum: 1, minimumDepthCoverage: 0.2, storageBudgetBytes: 1000, claimedAccuracyMeters: 0.01)
    }
    let valid = try CaptureProfile(profileID: "validated", requiredSensors: [.rgb], imageResolution: .init(width: 100, height: 100), targetFrameRate: 30, operatorPattern: "loop", expectedRangeMeters: 0.2...3, blurMaximum: 1, minimumDepthCoverage: 0.2, storageBudgetBytes: 1000, claimedAccuracyMeters: 0.01, validationEvidenceIDs: ["cal-1", "field-1"])
    #expect(valid.claimedAccuracyMeters == 0.01)
}

@Test("CAPREC-002 CAPREC-005 recovery offers safe actions and explicit repair lineage")
func recoveryAssessment() async throws {
    let root = try temporaryDirectory()
    let journalURL = root.appendingPathComponent("journal")
    let journal = try AppendOnlyJournal(url: journalURL)
    _ = try await journal.append(event: "started", timestampNanoseconds: 1)
    let assessment = CaptureRecovery.assess(journalURL: journalURL, packageRevision: "r1")
    #expect(assessment.recentHashesValid)
    #expect(assessment.availableActions.contains(.resume))
    let lineage = CaptureRecovery.repairRevision(originalSessionID: "s1", originalRootHash: String(repeating: "a", count: 64), reason: "recovered")
    #expect(lineage["lineage.originalSessionID"] == "s1")
}

@Test("CAPSOP-001 CAPSOP-004 field SOP preflight and closeout fail visibly")
func fieldSOP() {
    let failures = FieldSOP.preflightFailures(.init(projectSelected: false, permissionsGranted: false, availableStorageBytes: 1, requiredStorageBytes: 2, calibrationSatisfied: false, safetyAcknowledged: false, consentSatisfied: false, profileSensors: [.rgb, .lidarDepth], deviceSensors: [.rgb]))
    #expect(failures.count == 7)
    #expect(FieldSOP.closeoutChecklist(trackingReviewed: true, coverageReviewed: false, detailsReviewed: true, privacyReviewed: false, notesReviewed: true, packageFinalized: false) == ["coverage", "privacy", "package_finalization"])
}

@Test("CAPCSCP-001 through CAPCSCP-005 package hashing is deterministic and validation rejects corruption")
func packageValidation() throws {
    let root = try temporaryDirectory()
    let rgbData = Data("rgb".utf8), depthData = Data("depth".utf8), confidenceData = Data("confidence".utf8)
    for (name, data) in [("rgb.bin",rgbData),("depth.bin",depthData),("confidence.bin",confidenceData)] { try data.write(to: root.appendingPathComponent(name)) }
    let assets = [
        AssetReference(assetID: "rgb-frame-1", relativePath: "rgb.bin", mediaType: "application/octet-stream", byteCount: rgbData.count, sha256: SHA256Digest.hex(rgbData), creationSource: "fixture", encrypted: true, retentionClass: "evidence"),
        AssetReference(assetID: "depth-frame-1", relativePath: "depth.bin", mediaType: "application/octet-stream", byteCount: depthData.count, sha256: SHA256Digest.hex(depthData), creationSource: "fixture", encrypted: true, retentionClass: "evidence"),
        AssetReference(assetID: "confidence-frame-1", relativePath: "confidence.bin", mediaType: "application/octet-stream", byteCount: confidenceData.count, sha256: SHA256Digest.hex(confidenceData), creationSource: "fixture", encrypted: true, retentionClass: "evidence")
    ]
    let observation = try FrameObservation(frameID: "frame-1", timestampNanoseconds: 1, imageAssetID: "rgb-frame-1", depthAssetID: "depth-frame-1", confidenceAssetID: "confidence-frame-1", cameraTransform: [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1], intrinsics: [1,0,0,0,1,0,0,0,1], resolution: .init(width: 2, height: 2), trackingState: .normal, limitedTrackingReason: nil, exposure: .init(durationSeconds: 0.01, iso: 100, exposureTargetOffset: 0), orientation: .portrait)
    let input = (sessionID: "session-1", tenantID: Optional("tenant-1"), projectID: Optional("project-1"), sourceAdapter: "first-party-arkit-v1", device: DeviceManifest(model: "fixture", operatingSystem: "fixture", appBuild: "1", availableSensors: [.rgb,.lidarDepth,.confidence], calibrationCameraIdentity: "fixture-camera"), start: UInt64(1), end: UInt64(2), frames: [observation])
    let manifest = try CapturePackageManifest.finalized(sessionID: input.sessionID, tenantID: input.tenantID, projectID: input.projectID, sourceAdapter: input.sourceAdapter, device: input.device, startTimeNanoseconds: input.start, endTimeNanoseconds: input.end, coordinateFrames: [.init(frameID: "world", parentFrameID: nil, convention: "right_handed_y_up_meters", units: "meter", transformToParent: nil)], segments: [.init(segmentID: "segment-1", startedAtNanoseconds: 1, endedAtNanoseconds: 2, frameIDs: ["frame-1"], overlapControl: "known fiducial")], assets: assets, frames: input.frames, journalRootHash: String(repeating: "0", count: 64), signatureStatus: "unsigned_fixture", policy: policy(), unknownOptionalFields: ["future.compatible": "retained"])
    let again = try CapturePackageManifest.finalized(sessionID: input.sessionID, tenantID: input.tenantID, projectID: input.projectID, sourceAdapter: input.sourceAdapter, device: input.device, startTimeNanoseconds: input.start, endTimeNanoseconds: input.end, coordinateFrames: manifest.coordinateFrames, segments: manifest.segments, assets: assets, frames: input.frames, journalRootHash: manifest.journalRootHash, signatureStatus: manifest.signatureStatus, policy: policy(), unknownOptionalFields: manifest.unknownOptionalFields)
    #expect(manifest.rootHash == again.rootHash)
    try CapturePackageValidator.validate(manifest, packageDirectory: root)
    try Data("corrupt".utf8).write(to: root.appendingPathComponent("rgb.bin"))
    #expect(throws: CaptureCoreError.self) { try CapturePackageValidator.validate(manifest, packageDirectory: root) }
}
