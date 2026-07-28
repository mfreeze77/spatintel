import Foundation
import CaptureCore

#if os(iOS) && canImport(ARKit) && canImport(AVFoundation) && canImport(CoreMotion) && canImport(Metal) && canImport(Network) && canImport(BackgroundTasks)
import ARKit
import AVFoundation
import CoreMotion
import Metal
import Network
import BackgroundTasks
#if canImport(RealityKit)
import RealityKit
#endif
#if canImport(RoomPlan)
import RoomPlan
#endif

/// Apple-platform acquisition boundary. Heavy image/depth serialization is dispatched away from ARSession's callback queue.
public final class AppleSpatialCaptureCoordinator: NSObject, SpatialSensorAdapter, @unchecked Sendable {
    public let adapterID = "first-party-arkit-v1"
    public let availableSensors: Set<SensorKind>
    private let session = ARSession()
    private let motionManager = CMMotionManager()
    private let processingQueue = DispatchQueue(label: "sip.capture.processing", qos: .userInitiated)
    private let eventContinuation: AsyncStream<SensorAdapterEvent>.Continuation
    private let eventStream: AsyncStream<SensorAdapterEvent>
    private let buffer: BoundedObservationBuffer
    private var policy: CapturePolicyBundle?
    private var frameSequence: UInt64 = 0
    private var pendingMeshChanges: [MeshObservation] = []

    public override init() {
        var continuation: AsyncStream<SensorAdapterEvent>.Continuation!
        self.eventStream = AsyncStream(bufferingPolicy: .bufferingNewest(256)) { continuation = $0 }
        self.eventContinuation = continuation
        self.availableSensors = [.rgb, .motion]
            .union(ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth) ? [.lidarDepth, .confidence] : [])
            .union(ARWorldTrackingConfiguration.supportsSceneReconstruction(.mesh) ? [.mesh] : [])
        self.buffer = try! BoundedObservationBuffer(capacity: 12)
        super.init()
        session.delegate = self
    }

    public func start(policy: CapturePolicyBundle, profile: CaptureProfile) async throws {
        guard profile.requiredSensors.isSubset(of: availableSensors) else { throw CaptureCoreError.packageInvalid("device lacks required capture sensors") }
        guard profile.requiredSensors.isSubset(of: policy.permittedSensors) else { throw CaptureCoreError.packageInvalid("policy denies required capture sensors") }
        self.policy = policy
        let configuration = ARWorldTrackingConfiguration()
        configuration.worldAlignment = .gravity
        if policy.permits(.lidarDepth), ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth) { configuration.frameSemantics.insert(.sceneDepth) }
        if policy.permits(.mesh), ARWorldTrackingConfiguration.supportsSceneReconstruction(.mesh) { configuration.sceneReconstruction = .mesh }
        session.run(configuration, options: [])
        if policy.permits(.motion), motionManager.isDeviceMotionAvailable {
            motionManager.deviceMotionUpdateInterval = 1.0 / 100.0
            motionManager.startDeviceMotionUpdates()
        }
    }

    public func stop() async {
        session.pause()
        motionManager.stopDeviceMotionUpdates()
        eventContinuation.finish()
    }

    public func nextEvent() async -> SensorAdapterEvent? {
        var iterator = eventStream.makeAsyncIterator()
        return await iterator.next()
    }

    private func tracking(_ state: ARCamera.TrackingState) -> (TrackingState, LimitedTrackingReason?) {
        switch state {
        case .normal: return (.normal, nil)
        case .notAvailable: return (.notAvailable, nil)
        case let .limited(reason):
            let mapped: LimitedTrackingReason = switch reason {
            case .initializing: .initializing
            case .excessiveMotion: .excessiveMotion
            case .insufficientFeatures: .insufficientFeatures
            case .relocalizing: .relocalizing
            @unknown default: .unknown
            }
            return (.limited, mapped)
        }
    }

    private func flatten(_ matrix: simd_float4x4) -> [Double] {
        (0..<4).flatMap { column in (0..<4).map { row in Double(matrix[column][row]) } }
    }

    private func flatten(_ matrix: simd_float3x3) -> [Double] {
        (0..<3).flatMap { column in (0..<3).map { row in Double(matrix[column][row]) } }
    }
}

extension AppleSpatialCaptureCoordinator: ARSessionDelegate {
    public func session(_ session: ARSession, didUpdate frame: ARFrame) {
        frameSequence &+= 1
        let sequence = frameSequence
        let tracking = tracking(frame.camera.trackingState)
        let timestampNs = UInt64(max(frame.timestamp, 0) * 1_000_000_000)
        let meshChanges = pendingMeshChanges
        pendingMeshChanges.removeAll(keepingCapacity: true)
        processingQueue.async { [weak self] in
            guard let self else { return }
            // Production writer converts CVPixelBuffer and ARDepthData to encrypted files before emitting asset references.
            // Invalid depth/confidence values are serialized verbatim; they are never coerced to zero-distance geometry.
            let exposure = ExposureMetadata(durationSeconds: frame.camera.exposureDuration, iso: frame.camera.exposureOffset, exposureTargetOffset: frame.camera.exposureOffset)
            let observation = try? FrameObservation(
                frameID: "frame-\(sequence)", timestampNanoseconds: timestampNs,
                imageAssetID: "pending-rgb-\(sequence)",
                depthAssetID: frame.sceneDepth == nil ? nil : "pending-depth-\(sequence)",
                confidenceAssetID: frame.sceneDepth?.confidenceMap == nil ? nil : "pending-confidence-\(sequence)",
                cameraTransform: self.flatten(frame.camera.transform), intrinsics: self.flatten(frame.camera.intrinsics),
                resolution: .init(width: Int(frame.camera.imageResolution.width), height: Int(frame.camera.imageResolution.height)),
                trackingState: tracking.0, limitedTrackingReason: tracking.1, exposure: exposure,
                orientation: .unknown, motionSamples: [], meshObservations: meshChanges, privacyRegionIDs: [], invalidDepthPreserved: true
            )
            guard let observation else { return }
            Task {
                if await self.buffer.enqueue(observation) { self.eventContinuation.yield(.frame(observation)) }
                else { self.eventContinuation.yield(.dropped(.init(frameID: observation.frameID, timestampNanoseconds: observation.timestampNanoseconds, cause: "bounded_queue_full"))) }
            }
        }
    }

    public func sessionWasInterrupted(_ session: ARSession) { eventContinuation.yield(.sessionInterrupted) }
    public func sessionInterruptionEnded(_ session: ARSession) { eventContinuation.yield(.sessionResumed) }
    public func sessionShouldAttemptRelocalization(_ session: ARSession) -> Bool { eventContinuation.yield(.relocalizationStarted); return true }
    public func session(_ session: ARSession, didChange geoTrackingStatus: ARGeoTrackingStatus) { /* location capture remains policy-disabled unless explicitly enabled */ }
    public func session(_ session: ARSession, didAdd anchors: [ARAnchor]) { journalMesh(anchors, change: .added) }
    public func session(_ session: ARSession, didUpdate anchors: [ARAnchor]) { journalMesh(anchors, change: .updated) }
    public func session(_ session: ARSession, didRemove anchors: [ARAnchor]) { journalMesh(anchors, change: .removed) }

    private func journalMesh(_ anchors: [ARAnchor], change: MeshObservation.Change) {
        guard policy?.permits(.mesh) == true else { return }
        for anchor in anchors.compactMap({ $0 as? ARMeshAnchor }) {
            pendingMeshChanges.append(.init(anchorID: anchor.identifier.uuidString.lowercased(), change: change, transform: flatten(anchor.transform), geometryAssetID: change == .removed ? nil : "pending-mesh-\(anchor.identifier.uuidString.lowercased())"))
        }
    }
}

#else
public actor AppleSpatialCaptureCoordinator: SpatialSensorAdapter {
    public let adapterID = "first-party-arkit-v1-unavailable"
    public let availableSensors: Set<SensorKind> = []
    public init() {}
    public func start(policy: CapturePolicyBundle, profile: CaptureProfile) async throws {
        throw CaptureCoreError.packageInvalid("ARKit capture is available only on a supported Apple device")
    }
    public func stop() async {}
    public func nextEvent() async -> SensorAdapterEvent? { nil }
}
#endif
