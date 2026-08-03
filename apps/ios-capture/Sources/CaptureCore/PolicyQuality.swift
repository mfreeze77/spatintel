import Foundation

public enum SensorKind: String, Codable, Sendable, CaseIterable { case rgb, lidarDepth, confidence, mesh, motion, audio, location }

public struct CapturePolicyBundle: Codable, Sendable, Equatable {
    public let projectID: String
    public let permittedSensors: Set<SensorKind>
    public let cloudTransferAllowed: Bool
    public let cableExportAllowed: Bool
    public let purgeAfterVerifiedReceiptAllowed: Bool
    public let consentContext: String
    private enum CodingKeys: String, CodingKey { case projectID, permittedSensors, cloudTransferAllowed, cableExportAllowed, purgeAfterVerifiedReceiptAllowed, consentContext }
    public init(projectID: String, permittedSensors: Set<SensorKind>, cloudTransferAllowed: Bool, cableExportAllowed: Bool, purgeAfterVerifiedReceiptAllowed: Bool, consentContext: String) {
        self.projectID = projectID; self.permittedSensors = permittedSensors; self.cloudTransferAllowed = cloudTransferAllowed; self.cableExportAllowed = cableExportAllowed; self.purgeAfterVerifiedReceiptAllowed = purgeAfterVerifiedReceiptAllowed; self.consentContext = consentContext
    }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        projectID = try container.decode(String.self, forKey: .projectID)
        permittedSensors = Set(try container.decode([SensorKind].self, forKey: .permittedSensors))
        cloudTransferAllowed = try container.decode(Bool.self, forKey: .cloudTransferAllowed)
        cableExportAllowed = try container.decode(Bool.self, forKey: .cableExportAllowed)
        purgeAfterVerifiedReceiptAllowed = try container.decode(Bool.self, forKey: .purgeAfterVerifiedReceiptAllowed)
        consentContext = try container.decode(String.self, forKey: .consentContext)
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(projectID, forKey: .projectID)
        try container.encode(permittedSensors.sorted { $0.rawValue < $1.rawValue }, forKey: .permittedSensors)
        try container.encode(cloudTransferAllowed, forKey: .cloudTransferAllowed)
        try container.encode(cableExportAllowed, forKey: .cableExportAllowed)
        try container.encode(purgeAfterVerifiedReceiptAllowed, forKey: .purgeAfterVerifiedReceiptAllowed)
        try container.encode(consentContext, forKey: .consentContext)
    }
    public func permits(_ sensor: SensorKind) -> Bool { permittedSensors.contains(sensor) }
}

public struct CaptureProfile: Codable, Sendable, Equatable {
    public let profileID: String
    public let requiredSensors: Set<SensorKind>
    public let imageResolution: ImageResolution
    public let targetFrameRate: Int
    public let operatorPattern: String
    public let expectedRangeMeters: ClosedRange<Double>
    public let blurMaximum: Double
    public let minimumDepthCoverage: Double
    public let storageBudgetBytes: Int64
    public let claimedAccuracyMeters: Double?
    public let validationEvidenceIDs: [String]
    private enum CodingKeys: String, CodingKey { case profileID, requiredSensors, imageResolution, targetFrameRate, operatorPattern, expectedRangeLowerMeters, expectedRangeUpperMeters, blurMaximum, minimumDepthCoverage, storageBudgetBytes, claimedAccuracyMeters, validationEvidenceIDs }
    public init(profileID: String, requiredSensors: Set<SensorKind>, imageResolution: ImageResolution, targetFrameRate: Int, operatorPattern: String, expectedRangeMeters: ClosedRange<Double>, blurMaximum: Double, minimumDepthCoverage: Double, storageBudgetBytes: Int64, claimedAccuracyMeters: Double? = nil, validationEvidenceIDs: [String] = []) throws {
        guard targetFrameRate > 0, storageBudgetBytes > 0, expectedRangeMeters.lowerBound >= 0, expectedRangeMeters.upperBound > expectedRangeMeters.lowerBound else { throw CaptureCoreError.packageInvalid("invalid capture profile") }
        if claimedAccuracyMeters != nil && validationEvidenceIDs.isEmpty { throw CaptureCoreError.packageInvalid("accuracy claims require calibration and field-validation evidence") }
        self.profileID = profileID; self.requiredSensors = requiredSensors; self.imageResolution = imageResolution; self.targetFrameRate = targetFrameRate; self.operatorPattern = operatorPattern; self.expectedRangeMeters = expectedRangeMeters; self.blurMaximum = blurMaximum; self.minimumDepthCoverage = minimumDepthCoverage; self.storageBudgetBytes = storageBudgetBytes; self.claimedAccuracyMeters = claimedAccuracyMeters; self.validationEvidenceIDs = validationEvidenceIDs
    }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let lower = try container.decode(Double.self, forKey: .expectedRangeLowerMeters)
        let upper = try container.decode(Double.self, forKey: .expectedRangeUpperMeters)
        try self.init(profileID: container.decode(String.self, forKey: .profileID), requiredSensors: Set(container.decode([SensorKind].self, forKey: .requiredSensors)), imageResolution: container.decode(ImageResolution.self, forKey: .imageResolution), targetFrameRate: container.decode(Int.self, forKey: .targetFrameRate), operatorPattern: container.decode(String.self, forKey: .operatorPattern), expectedRangeMeters: lower...upper, blurMaximum: container.decode(Double.self, forKey: .blurMaximum), minimumDepthCoverage: container.decode(Double.self, forKey: .minimumDepthCoverage), storageBudgetBytes: container.decode(Int64.self, forKey: .storageBudgetBytes), claimedAccuracyMeters: container.decodeIfPresent(Double.self, forKey: .claimedAccuracyMeters), validationEvidenceIDs: container.decode([String].self, forKey: .validationEvidenceIDs))
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(profileID, forKey: .profileID)
        try container.encode(requiredSensors.sorted { $0.rawValue < $1.rawValue }, forKey: .requiredSensors)
        try container.encode(imageResolution, forKey: .imageResolution)
        try container.encode(targetFrameRate, forKey: .targetFrameRate)
        try container.encode(operatorPattern, forKey: .operatorPattern)
        try container.encode(expectedRangeMeters.lowerBound, forKey: .expectedRangeLowerMeters)
        try container.encode(expectedRangeMeters.upperBound, forKey: .expectedRangeUpperMeters)
        try container.encode(blurMaximum, forKey: .blurMaximum)
        try container.encode(minimumDepthCoverage, forKey: .minimumDepthCoverage)
        try container.encode(storageBudgetBytes, forKey: .storageBudgetBytes)
        try container.encodeIfPresent(claimedAccuracyMeters, forKey: .claimedAccuracyMeters)
        try container.encode(validationEvidenceIDs, forKey: .validationEvidenceIDs)
    }
}

public struct QualitySignals: Codable, Sendable, Equatable {
    public let blur: Double
    public let exposureClippingFraction: Double
    public let angularVelocityRadiansPerSecond: Double
    public let trackingState: TrackingState
    public let depthCoverage: Double
    public let viewpointDiversity: Double
    public let weakSurfaceFraction: Double
    public let calculationVersion: String
    public let knownBlindSpots: [String]
    public init(blur: Double, exposureClippingFraction: Double, angularVelocityRadiansPerSecond: Double, trackingState: TrackingState, depthCoverage: Double, viewpointDiversity: Double, weakSurfaceFraction: Double, calculationVersion: String = "sip.iphone-frame-quality/v1", knownBlindSpots: [String] = ["viewpoint diversity requires session-level aggregation", "frame score does not establish metric accuracy"]) {
        self.blur = blur; self.exposureClippingFraction = exposureClippingFraction; self.angularVelocityRadiansPerSecond = angularVelocityRadiansPerSecond; self.trackingState = trackingState; self.depthCoverage = depthCoverage; self.viewpointDiversity = viewpointDiversity; self.weakSurfaceFraction = weakSurfaceFraction; self.calculationVersion = calculationVersion; self.knownBlindSpots = knownBlindSpots
    }
}

public struct QualityWarning: Codable, Sendable, Equatable {
    public let code: String
    public let cause: String
    public let consequence: String
    public let correctiveAction: String
    public let severity: String
}

public enum QualityEvaluator {
    public static func warnings(signals: QualitySignals, profile: CaptureProfile) -> [QualityWarning] {
        var result: [QualityWarning] = []
        if signals.blur > profile.blurMaximum { result.append(.init(code: "BLUR_HIGH", cause: "Camera motion or focus produced excessive blur.", consequence: "Image features and texture may not register reliably.", correctiveAction: "Slow down, hold the device steady, and improve lighting.", severity: "warning")) }
        if signals.exposureClippingFraction > 0.08 { result.append(.init(code: "EXPOSURE_CLIPPED", cause: "Highlights or shadows are clipped.", consequence: "Surface appearance and feature matching may be lost.", correctiveAction: "Change viewpoint or lighting and recapture the area.", severity: "warning")) }
        if signals.angularVelocityRadiansPerSecond > 1.2 { result.append(.init(code: "MOTION_HIGH", cause: "The device is rotating too quickly.", consequence: "Pose and depth alignment may degrade.", correctiveAction: "Move in slow arcs and avoid abrupt turns.", severity: "warning")) }
        if signals.trackingState != .normal { result.append(.init(code: "TRACKING_LIMITED", cause: "World tracking is limited or unavailable.", consequence: "New poses cannot be treated as valid world observations.", correctiveAction: "Pause and return to a previously observed textured area.", severity: "critical")) }
        if signals.depthCoverage < profile.minimumDepthCoverage { result.append(.init(code: "DEPTH_COVERAGE_LOW", cause: "Too little of the frame has reliable depth.", consequence: "Metric fusion will have gaps or high uncertainty.", correctiveAction: "Move closer and rescan reflective or distant surfaces from another angle.", severity: "warning")) }
        if signals.viewpointDiversity < 0.2 || signals.weakSurfaceFraction > 0.35 { result.append(.init(code: "COVERAGE_WEAK", cause: "Surfaces are unvisited or observed from too few viewpoints.", consequence: "Reconstruction may contain holes and unstable surfaces.", correctiveAction: "Add overlapping passes and oblique viewpoints around weak surfaces.", severity: "warning")) }
        return result
    }
}

public enum ThermalState: String, Codable, Sendable { case nominal, fair, serious, critical }
public struct ResourceSnapshot: Codable, Sendable, Equatable {
    public let thermalState: ThermalState
    public let availableStorageBytes: Int64
    public let batteryFraction: Double
    public let memoryPressure: Bool
}
public enum ResourceDecision: String, Codable, Sendable { case continueNormally, reduceFrameRate, disableOptionalSensors, pausePreservingPackage }
public enum ResourceController {
    public static func decision(_ snapshot: ResourceSnapshot, reserveBytes: Int64) -> (ResourceDecision, String) {
        if snapshot.availableStorageBytes <= reserveBytes { return (.pausePreservingPackage, "Capture paused before storage exhaustion; finalize or export the current package.") }
        if snapshot.thermalState == .critical || snapshot.batteryFraction <= 0.03 { return (.pausePreservingPackage, "Capture paused to preserve device and package integrity.") }
        if snapshot.thermalState == .serious || snapshot.memoryPressure { return (.disableOptionalSensors, "Optional sensors disabled due to thermal or memory pressure.") }
        if snapshot.thermalState == .fair || snapshot.batteryFraction <= 0.12 { return (.reduceFrameRate, "Frame rate reduced due to resource pressure.") }
        return (.continueNormally, "Resources are within the capture profile budget.")
    }
}

public struct PurgeContext: Sendable, Equatable {
    public let packageIntegrityVerified: Bool
    public let destinationReceiptVerified: Bool
    public let userAuthorized: Bool
    public let policy: CapturePolicyBundle
}
public enum PurgePolicy {
    public static func authorize(_ context: PurgeContext) throws {
        guard context.packageIntegrityVerified else { throw CaptureCoreError.purgeDenied("local originals cannot be purged before package integrity is verified") }
        guard context.destinationReceiptVerified else { throw CaptureCoreError.purgeDenied("local originals cannot be purged before destination receipt is verified") }
        guard context.userAuthorized || context.policy.purgeAfterVerifiedReceiptAllowed else { throw CaptureCoreError.purgeDenied("local purge requires user or project-policy authorization") }
    }
}
