import Foundation

public enum RestrictedRegionKind: String, Codable, Sendable { case face, screen, document, licensePlate, securityEquipment, room, arbitrary }
public enum RestrictionOrigin: String, Codable, Sendable { case operatorMarked, detectorSuggestion }
public enum RestrictionState: String, Codable, Sendable { case suggested, confirmed, rejected, redacted, unresolved }

public struct RestrictedRegion: Codable, Sendable, Equatable {
    public let regionID: String
    public let kind: RestrictedRegionKind
    public let origin: RestrictionOrigin
    public var state: RestrictionState
    public let frameID: String?
    public let normalizedBounds: [Double]?
    public let spatialAnchorID: String?
    public let reason: String
}

public struct RedactionOperation: Codable, Sendable, Equatable {
    public let operationID: String
    public let sourceAssetID: String
    public let derivedAssetID: String
    public let regionID: String
    public let operation: String
    public let parameters: [String: String]
}

public enum PrivacyExportGate {
    public static func validate(regions: [RestrictedRegion], operations: [RedactionOperation], broadShare: Bool) throws {
        guard broadShare else { return }
        let unresolved = regions.filter { $0.state == .suggested || $0.state == .unresolved || $0.state == .confirmed }
        guard unresolved.isEmpty else { throw CaptureCoreError.exportDenied("broad-share export denied while required redactions are unresolved") }
        let redactedIDs = Set(operations.map(\.regionID))
        let missing = regions.filter { $0.state == .redacted && !redactedIDs.contains($0.regionID) }
        guard missing.isEmpty else { throw CaptureCoreError.exportDenied("redacted regions require source-linked redaction operations") }
    }
}
