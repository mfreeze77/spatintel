import Foundation

public struct DroppedObservation: Codable, Sendable, Equatable {
    public let frameID: String
    public let timestampNanoseconds: UInt64
    public let cause: String
}

public actor BoundedObservationBuffer {
    private let capacity: Int
    private var observations: [FrameObservation] = []
    private var drops: [DroppedObservation] = []
    public init(capacity: Int) throws {
        guard capacity > 0 else { throw CaptureCoreError.packageInvalid("buffer capacity must be positive") }
        self.capacity = capacity
    }
    @discardableResult
    public func enqueue(_ observation: FrameObservation) -> Bool {
        guard observations.count < capacity else {
            drops.append(.init(frameID: observation.frameID, timestampNanoseconds: observation.timestampNanoseconds, cause: "bounded_queue_full"))
            return false
        }
        observations.append(observation)
        return true
    }
    public func dequeue() -> FrameObservation? { observations.isEmpty ? nil : observations.removeFirst() }
    public func droppedObservations() -> [DroppedObservation] { drops }
    public func count() -> Int { observations.count }
}
