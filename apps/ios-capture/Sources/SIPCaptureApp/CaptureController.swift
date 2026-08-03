#if os(iOS) && canImport(SwiftUI) && canImport(ARKit)
import ARKit
import Foundation
import SwiftUI
import UIKit
import CaptureCore
import CaptureSensors

@MainActor
final class CaptureController: ObservableObject {
    @Published private(set) var state: CaptureState = .setup
    @Published private(set) var frameCount = 0
    @Published private(set) var droppedCount = 0
    @Published private(set) var message = "Ready to configure a local capture."
    @Published private(set) var finalizedDirectory: URL?

    private var machine = CaptureStateMachine()
    private var coordinator: AppleSpatialCaptureCoordinator?
    private var store: CaptureAssetStore?
    private var journal: AppendOnlyJournal?
    private var eventTask: Task<Void, Never>?
    private var frames: [FrameObservation] = []
    private var meshObservations: [MeshObservation] = []
    private var events: [CaptureEventRecord] = []
    private var sessionID = ""
    private var startedAt: UInt64 = 0
    private var policy: CapturePolicyBundle?

    var canStart: Bool { state == .setup || state == .ready }
    var canFinalize: Bool { state == .capturing || state == .paused || state == .trackingRecovery }

    func start() async {
        guard canStart else { return }
        do {
            machine = CaptureStateMachine()
            try machine.apply(.beginCalibration)
            try machine.apply(.calibrationPassed)
            try machine.apply(.beginCapture)
            state = machine.state
            sessionID = UUID().uuidString.lowercased()
            startedAt = nowNanoseconds()
            frames = []; meshObservations = []; events = []; frameCount = 0; droppedCount = 0
            let base = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first
                ?? FileManager.default.temporaryDirectory
            let directory = base.appendingPathComponent("SpatintelCaptures", isDirectory: true)
                .appendingPathComponent(sessionID, isDirectory: true)
            let assetStore = try CaptureAssetStore(rootURL: directory)
            let capture = try AppleSpatialCaptureCoordinator(assetStore: assetStore)
            let capturePolicy = CapturePolicyBundle(
                projectID: "local-internal",
                permittedSensors: [.rgb, .lidarDepth, .confidence, .mesh, .motion],
                cloudTransferAllowed: false,
                cableExportAllowed: true,
                purgeAfterVerifiedReceiptAllowed: false,
                consentContext: "Private local capture; operator controls export."
            )
            let required: Set<SensorKind> = capture.availableSensors.contains(.lidarDepth) ? [.rgb, .lidarDepth] : [.rgb]
            let profile = try CaptureProfile(
                profileID: "iphone-local-quality",
                requiredSensors: required,
                imageResolution: .init(width: 1920, height: 1440),
                targetFrameRate: 30,
                operatorPattern: "slow overlapping loops with oblique detail passes",
                expectedRangeMeters: 0.25...5.0,
                blurMaximum: 0.35,
                minimumDepthCoverage: 0.4,
                storageBudgetBytes: 20_000_000_000
            )
            let captureJournal = try AppendOnlyJournal(url: directory.appendingPathComponent("events/capture.journal.jsonl"))
            _ = try await captureJournal.append(event: "session_started", payload: ["session_id": sessionID], timestampNanoseconds: startedAt)
            coordinator = capture; store = assetStore; journal = captureJournal; policy = capturePolicy
            try await capture.start(policy: capturePolicy, profile: profile)
            eventTask = Task { [weak self, capture] in
                while !Task.isCancelled, let event = await capture.nextEvent() {
                    await self?.record(event)
                }
            }
            message = required.contains(.lidarDepth)
                ? "Capturing RGB, LiDAR depth/confidence, pose, motion, and mesh locally."
                : "Capturing RGB/pose locally. This device did not expose LiDAR depth."
        } catch {
            state = .failedRecoverable
            message = "Capture start failed: \(error)"
        }
    }

    func finalize() async {
        guard canFinalize, let coordinator, let store, let journal, let policy else { return }
        do {
            await coordinator.stop()
            await eventTask?.value
            eventTask = nil
            let endedAt = nowNanoseconds()
            if machine.state == .capturing { try machine.apply(.finalizeSegment) }
            else {
                if machine.state == .trackingRecovery { try machine.apply(.trackingRecovered) }
                if machine.state == .capturing { try machine.apply(.pause) }
                try machine.apply(.finalizeSession)
            }
            if machine.state == .segmentFinalization {
                try machine.apply(.segmentFinalized)
                try machine.apply(.finalizeSession)
            }
            state = machine.state
            _ = try await journal.append(event: "session_finalized", payload: ["frames": String(frames.count)], timestampNanoseconds: endedAt)
            try await journal.synchronize()
            let journalData = try Data(contentsOf: journal.url)
            _ = try store.write(
                journalData,
                relativePath: "events/capture.journal.jsonl",
                mediaType: "application/x-ndjson",
                creationSource: "AppendOnlyJournal"
            )
            let rootHash = await journal.rootHash()
            let sortedFrames = frames.sorted { $0.timestampNanoseconds < $1.timestampNanoseconds }
            guard let first = sortedFrames.first, let last = sortedFrames.last else {
                throw CaptureCoreError.packageInvalid("cannot finalize a capture without accepted frames")
            }
            let manifest = try CapturePackageManifest.finalized(
                sessionID: sessionID,
                tenantID: nil,
                projectID: policy.projectID,
                sourceAdapter: coordinator.adapterID,
                device: DeviceManifest(
                    model: UIDevice.current.model,
                    operatingSystem: "iOS \(UIDevice.current.systemVersion)",
                    appBuild: Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "development",
                    availableSensors: coordinator.availableSensors,
                    calibrationCameraIdentity: "arkit-back-camera-lidar"
                ),
                startTimeNanoseconds: min(startedAt, first.timestampNanoseconds),
                endTimeNanoseconds: max(endedAt, last.timestampNanoseconds),
                coordinateFrames: [
                    .init(frameID: "arkit-world", parentFrameID: nil, convention: "right_handed_y_up_minus_z_initial_view", units: "meter", transformToParent: nil)
                ],
                segments: [
                    .init(segmentID: "segment-1", startedAtNanoseconds: first.timestampNanoseconds, endedAtNanoseconds: last.timestampNanoseconds, frameIDs: sortedFrames.map(\.frameID), overlapControl: "operator-guided overlapping pass")
                ],
                assets: store.assets(),
                frames: sortedFrames,
                journalRootHash: rootHash,
                signatureStatus: "device_file_protection_unsigned",
                policy: policy,
                unknownOptionalFields: ["desktop_import": "sip import-iphone-capture"],
                meshObservations: meshObservations,
                events: events
            )
            try CapturePackageWriter.write(manifest, to: store.rootURL)
            try machine.apply(.packageFinalized)
            state = machine.state
            finalizedDirectory = store.rootURL
            message = "Capture finalized and verified locally. Copy this directory to the workstation; originals remain on the phone."
        } catch {
            state = .failedRecoverable
            message = "Finalization failed without deleting source assets: \(error)"
        }
    }

    private func record(_ event: SensorAdapterEvent) async {
        let timestamp = nowNanoseconds()
        switch event {
        case let .frame(frame):
            frames.append(frame); frameCount = frames.count
            await appendJournal("frame_finalized", ["frame_id": frame.frameID], frame.timestampNanoseconds)
        case let .meshChanged(mesh):
            meshObservations.append(mesh)
            await appendJournal("mesh_\(mesh.change.rawValue)", ["anchor_id": mesh.anchorID], timestamp)
        case let .dropped(drop):
            droppedCount += 1
            await appendEvent("observation_dropped", ["frame_id": drop.frameID, "cause": drop.cause], drop.timestampNanoseconds)
        case let .trackingChanged(tracking, reason):
            await appendEvent("tracking_changed", ["state": tracking.rawValue, "reason": reason?.rawValue ?? "none"], timestamp)
        case .relocalizationStarted: await appendEvent("relocalization_started", [:], timestamp)
        case .relocalizationCompleted: await appendEvent("relocalization_completed", [:], timestamp)
        case let .worldOriginChanged(transform): await appendEvent("world_origin_changed", ["transform": transform.map { String($0) }.joined(separator: ",")], timestamp)
        case .sessionInterrupted: await appendEvent("session_interrupted", [:], timestamp)
        case .sessionResumed: await appendEvent("session_resumed", [:], timestamp)
        }
    }

    private func appendEvent(_ name: String, _ details: [String: String], _ timestamp: UInt64) async {
        events.append(.init(timestampNanoseconds: timestamp, event: name, details: details))
        await appendJournal(name, details, timestamp)
    }

    private func appendJournal(_ event: String, _ payload: [String: String], _ timestamp: UInt64) async {
        do { _ = try await journal?.append(event: event, payload: payload, timestampNanoseconds: timestamp) }
        catch { message = "Journal write failed; stop and finalize: \(error)" }
    }

    private func nowNanoseconds() -> UInt64 {
        UInt64(ProcessInfo.processInfo.systemUptime * 1_000_000_000)
    }
}
#endif
