import Foundation

public enum CaptureState: String, Codable, Sendable, CaseIterable {
    case setup, calibrationCheck, ready, capturing, paused, trackingRecovery
    case segmentFinalization, sessionFinalization, upload, verified, failedRecoverable
}

public enum CaptureAction: String, Codable, Sendable {
    case beginCalibration, calibrationPassed, beginCapture, pause, resume, trackingLost, trackingRecovered
    case finalizeSegment, segmentFinalized, finalizeSession, packageFinalized, beginUpload, receiptVerified, recoverableFailure, retry
}

public struct CaptureStateMachine: Codable, Sendable, Equatable {
    public private(set) var state: CaptureState
    public init(state: CaptureState = .setup) { self.state = state }
    public mutating func apply(_ action: CaptureAction) throws {
        let next: CaptureState? = switch (state, action) {
        case (.setup, .beginCalibration): .calibrationCheck
        case (.calibrationCheck, .calibrationPassed): .ready
        case (.ready, .beginCapture), (.paused, .resume), (.trackingRecovery, .trackingRecovered): .capturing
        case (.capturing, .pause): .paused
        case (.capturing, .trackingLost): .trackingRecovery
        case (.capturing, .finalizeSegment): .segmentFinalization
        case (.segmentFinalization, .segmentFinalized): .ready
        case (.ready, .finalizeSession), (.paused, .finalizeSession): .sessionFinalization
        case (.sessionFinalization, .packageFinalized): .upload
        case (.upload, .beginUpload): .upload
        case (.upload, .receiptVerified): .verified
        case (_, .recoverableFailure): .failedRecoverable
        case (.failedRecoverable, .retry): .setup
        default: nil
        }
        guard let next else { throw CaptureCoreError.invalidTransition(state: state, action: action) }
        state = next
    }
}

public enum TrackingState: String, Codable, Sendable { case normal, limited, notAvailable }
public enum LimitedTrackingReason: String, Codable, Sendable { case initializing, excessiveMotion, insufficientFeatures, relocalizing, unknown }
public enum InterfaceOrientation: String, Codable, Sendable { case portrait, portraitUpsideDown, landscapeLeft, landscapeRight, unknown }

public struct ImageResolution: Codable, Sendable, Equatable {
    public let width: Int
    public let height: Int
    public init(width: Int, height: Int) { self.width = width; self.height = height }
}

public struct ExposureMetadata: Codable, Sendable, Equatable {
    public let durationSeconds: Double
    public let iso: Double
    public let exposureTargetOffset: Double
    public init(durationSeconds: Double, iso: Double, exposureTargetOffset: Double) {
        self.durationSeconds = durationSeconds; self.iso = iso; self.exposureTargetOffset = exposureTargetOffset
    }
}

public struct AssetReference: Codable, Sendable, Hashable {
    public let assetID: String
    public let relativePath: String
    public let mediaType: String
    public let byteCount: Int
    public let sha256: String
    public let creationSource: String
    public let encrypted: Bool
    public let retentionClass: String
    public init(assetID: String, relativePath: String, mediaType: String, byteCount: Int, sha256: String, creationSource: String, encrypted: Bool, retentionClass: String) {
        self.assetID = assetID; self.relativePath = relativePath; self.mediaType = mediaType; self.byteCount = byteCount; self.sha256 = sha256; self.creationSource = creationSource; self.encrypted = encrypted; self.retentionClass = retentionClass
    }
}

public struct MotionSample: Codable, Sendable, Equatable {
    public let timestampNanoseconds: UInt64
    public let acceleration: [Double]
    public let rotationRate: [Double]
    public let attitudeQuaternion: [Double]
}

public struct MeshObservation: Codable, Sendable, Equatable {
    public enum Change: String, Codable, Sendable { case added, updated, removed }
    public let anchorID: String
    public let change: Change
    public let transform: [Double]
    public let geometryAssetID: String?
}

public struct FrameObservation: Codable, Sendable, Equatable {
    public let frameID: String
    public let timestampNanoseconds: UInt64
    public let imageAssetID: String
    public let depthAssetID: String?
    public let confidenceAssetID: String?
    public let cameraTransform: [Double]
    public let intrinsics: [Double]
    public let resolution: ImageResolution
    public let trackingState: TrackingState
    public let limitedTrackingReason: LimitedTrackingReason?
    public let exposure: ExposureMetadata
    public let orientation: InterfaceOrientation
    public let motionSamples: [MotionSample]
    public let meshObservations: [MeshObservation]
    public let privacyRegionIDs: [String]
    public let invalidDepthPreserved: Bool
    public init(frameID: String, timestampNanoseconds: UInt64, imageAssetID: String, depthAssetID: String?, confidenceAssetID: String?, cameraTransform: [Double], intrinsics: [Double], resolution: ImageResolution, trackingState: TrackingState, limitedTrackingReason: LimitedTrackingReason?, exposure: ExposureMetadata, orientation: InterfaceOrientation, motionSamples: [MotionSample] = [], meshObservations: [MeshObservation] = [], privacyRegionIDs: [String] = [], invalidDepthPreserved: Bool = true) throws {
        guard cameraTransform.count == 16 else { throw CaptureCoreError.invalidMatrix("cameraTransform must contain 16 values") }
        guard intrinsics.count == 9 else { throw CaptureCoreError.invalidMatrix("intrinsics must contain 9 values") }
        guard resolution.width > 0, resolution.height > 0 else { throw CaptureCoreError.invalidDimensions }
        if trackingState == .normal, limitedTrackingReason != nil { throw CaptureCoreError.invalidTrackingState }
        self.frameID = frameID; self.timestampNanoseconds = timestampNanoseconds; self.imageAssetID = imageAssetID; self.depthAssetID = depthAssetID; self.confidenceAssetID = confidenceAssetID; self.cameraTransform = cameraTransform; self.intrinsics = intrinsics; self.resolution = resolution; self.trackingState = trackingState; self.limitedTrackingReason = limitedTrackingReason; self.exposure = exposure; self.orientation = orientation; self.motionSamples = motionSamples; self.meshObservations = meshObservations; self.privacyRegionIDs = privacyRegionIDs; self.invalidDepthPreserved = invalidDepthPreserved
    }
}

public enum CaptureCoreError: Error, Equatable, CustomStringConvertible {
    case invalidTransition(state: CaptureState, action: CaptureAction)
    case invalidMatrix(String), invalidDimensions, invalidTrackingState
    case journalCorrupt(String), packageInvalid(String), exportDenied(String), purgeDenied(String)
    public var description: String { switch self {
    case let .invalidTransition(state, action): "invalid transition from \(state.rawValue) using \(action.rawValue)"
    case let .invalidMatrix(message), let .journalCorrupt(message), let .packageInvalid(message), let .exportDenied(message), let .purgeDenied(message): message
    case .invalidDimensions: "image dimensions must be positive"
    case .invalidTrackingState: "normal tracking cannot have a limited-tracking reason"
    } }
}
