import Foundation
import CaptureCore

public enum SensorAdapterEvent: Sendable, Equatable {
    case frame(FrameObservation)
    case trackingChanged(state: TrackingState, reason: LimitedTrackingReason?)
    case relocalizationStarted
    case relocalizationCompleted
    case worldOriginChanged(transform: [Double])
    case sessionInterrupted
    case sessionResumed
    case meshChanged(MeshObservation)
    case dropped(DroppedObservation)
}

public protocol SpatialSensorAdapter: Sendable {
    var adapterID: String { get }
    var availableSensors: Set<SensorKind> { get }
    func start(policy: CapturePolicyBundle, profile: CaptureProfile) async throws
    func stop() async
    func nextEvent() async -> SensorAdapterEvent?
}

public actor FixtureSensorAdapter: SpatialSensorAdapter {
    public let adapterID = "fixture-sensor-v1"
    public let availableSensors: Set<SensorKind>
    private var events: [SensorAdapterEvent]
    private var started = false
    public init(events: [SensorAdapterEvent], availableSensors: Set<SensorKind> = [.rgb, .lidarDepth, .confidence, .mesh, .motion]) {
        self.events = events; self.availableSensors = availableSensors
    }
    public func start(policy: CapturePolicyBundle, profile: CaptureProfile) async throws {
        guard profile.requiredSensors.isSubset(of: availableSensors) else { throw CaptureCoreError.packageInvalid("fixture lacks a required sensor") }
        guard profile.requiredSensors.isSubset(of: policy.permittedSensors) else { throw CaptureCoreError.packageInvalid("project policy disables a required sensor") }
        started = true
    }
    public func stop() async { started = false }
    public func nextEvent() async -> SensorAdapterEvent? {
        guard started, !events.isEmpty else { return nil }
        return events.removeFirst()
    }
}
