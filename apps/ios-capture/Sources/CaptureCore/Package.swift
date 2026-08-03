import Foundation

public struct DeviceManifest: Codable, Sendable, Equatable {
    public let model: String
    public let operatingSystem: String
    public let appBuild: String
    public let availableSensors: Set<SensorKind>
    public let calibrationCameraIdentity: String
    private enum CodingKeys: String, CodingKey { case model, operatingSystem, appBuild, availableSensors, calibrationCameraIdentity }
    public init(model: String, operatingSystem: String, appBuild: String, availableSensors: Set<SensorKind>, calibrationCameraIdentity: String) {
        self.model = model; self.operatingSystem = operatingSystem; self.appBuild = appBuild; self.availableSensors = availableSensors; self.calibrationCameraIdentity = calibrationCameraIdentity
    }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        model = try container.decode(String.self, forKey: .model)
        operatingSystem = try container.decode(String.self, forKey: .operatingSystem)
        appBuild = try container.decode(String.self, forKey: .appBuild)
        availableSensors = Set(try container.decode([SensorKind].self, forKey: .availableSensors))
        calibrationCameraIdentity = try container.decode(String.self, forKey: .calibrationCameraIdentity)
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(model, forKey: .model)
        try container.encode(operatingSystem, forKey: .operatingSystem)
        try container.encode(appBuild, forKey: .appBuild)
        try container.encode(availableSensors.sorted { $0.rawValue < $1.rawValue }, forKey: .availableSensors)
        try container.encode(calibrationCameraIdentity, forKey: .calibrationCameraIdentity)
    }
}

public struct CoordinateFrameManifest: Codable, Sendable, Equatable {
    public let frameID: String
    public let parentFrameID: String?
    public let convention: String
    public let units: String
    public let transformToParent: [Double]?
}

public struct SegmentManifest: Codable, Sendable, Equatable {
    public let segmentID: String
    public let startedAtNanoseconds: UInt64
    public let endedAtNanoseconds: UInt64
    public let frameIDs: [String]
    public let overlapControl: String
}

public struct CaptureEventRecord: Codable, Sendable, Equatable {
    public let timestampNanoseconds: UInt64
    public let event: String
    public let details: [String: String]
    public init(timestampNanoseconds: UInt64, event: String, details: [String: String] = [:]) {
        self.timestampNanoseconds = timestampNanoseconds; self.event = event; self.details = details
    }
}

public struct CapturePackageManifest: Codable, Sendable, Equatable {
    public let schema: String
    public let schemaVersion: String
    public let sessionID: String
    public let tenantID: String?
    public let projectID: String?
    public let sourceAdapter: String
    public let device: DeviceManifest
    public let startTimeNanoseconds: UInt64
    public let endTimeNanoseconds: UInt64
    public let coordinateFrames: [CoordinateFrameManifest]
    public let segments: [SegmentManifest]
    public let assets: [AssetReference]
    public let frames: [FrameObservation]
    public let meshObservations: [MeshObservation]
    public let events: [CaptureEventRecord]
    public let journalRootHash: String
    public let signatureStatus: String
    public let policy: CapturePolicyBundle
    public let unknownOptionalFields: [String: String]
    public let rootHash: String

    private struct Rootless: Codable {
        let schema: String; let schemaVersion: String; let sessionID: String; let tenantID: String?; let projectID: String?
        let sourceAdapter: String; let device: DeviceManifest; let startTimeNanoseconds: UInt64; let endTimeNanoseconds: UInt64
        let coordinateFrames: [CoordinateFrameManifest]; let segments: [SegmentManifest]; let assets: [AssetReference]
        let frames: [FrameObservation]; let meshObservations: [MeshObservation]; let events: [CaptureEventRecord]
        let journalRootHash: String; let signatureStatus: String; let policy: CapturePolicyBundle
        let unknownOptionalFields: [String: String]
    }

    public static func finalized(sessionID: String, tenantID: String?, projectID: String?, sourceAdapter: String, device: DeviceManifest, startTimeNanoseconds: UInt64, endTimeNanoseconds: UInt64, coordinateFrames: [CoordinateFrameManifest], segments: [SegmentManifest], assets: [AssetReference], frames: [FrameObservation], journalRootHash: String, signatureStatus: String, policy: CapturePolicyBundle, unknownOptionalFields: [String: String] = [:], meshObservations: [MeshObservation] = [], events: [CaptureEventRecord] = []) throws -> CapturePackageManifest {
        let rootless = Rootless(schema: "sip.cscp", schemaVersion: "1.1.0", sessionID: sessionID, tenantID: tenantID, projectID: projectID, sourceAdapter: sourceAdapter, device: device, startTimeNanoseconds: startTimeNanoseconds, endTimeNanoseconds: endTimeNanoseconds, coordinateFrames: coordinateFrames, segments: segments, assets: assets, frames: frames, meshObservations: meshObservations, events: events, journalRootHash: journalRootHash, signatureStatus: signatureStatus, policy: policy, unknownOptionalFields: unknownOptionalFields)
        return CapturePackageManifest(schema: rootless.schema, schemaVersion: rootless.schemaVersion, sessionID: rootless.sessionID, tenantID: rootless.tenantID, projectID: rootless.projectID, sourceAdapter: rootless.sourceAdapter, device: rootless.device, startTimeNanoseconds: rootless.startTimeNanoseconds, endTimeNanoseconds: rootless.endTimeNanoseconds, coordinateFrames: rootless.coordinateFrames, segments: rootless.segments, assets: rootless.assets, frames: rootless.frames, meshObservations: rootless.meshObservations, events: rootless.events, journalRootHash: rootless.journalRootHash, signatureStatus: rootless.signatureStatus, policy: rootless.policy, unknownOptionalFields: rootless.unknownOptionalFields, rootHash: try CanonicalJSON.hash(rootless))
    }

    public func verifyRootHash() throws {
        let expected = try Self.finalized(sessionID: sessionID, tenantID: tenantID, projectID: projectID, sourceAdapter: sourceAdapter, device: device, startTimeNanoseconds: startTimeNanoseconds, endTimeNanoseconds: endTimeNanoseconds, coordinateFrames: coordinateFrames, segments: segments, assets: assets, frames: frames, journalRootHash: journalRootHash, signatureStatus: signatureStatus, policy: policy, unknownOptionalFields: unknownOptionalFields, meshObservations: meshObservations, events: events).rootHash
        guard expected == rootHash else { throw CaptureCoreError.packageInvalid("capture package root hash mismatch") }
    }
}

public enum CapturePackageWriter {
    public static func write(_ manifest: CapturePackageManifest, to directory: URL) throws {
        try CapturePackageValidator.validate(manifest, packageDirectory: directory)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let data = try CanonicalJSON.data(manifest)
        let temporary = directory.appendingPathComponent("manifest.json.tmp")
        let final = directory.appendingPathComponent("manifest.json")
        try data.write(to: temporary, options: [.atomic])
        if FileManager.default.fileExists(atPath: final.path) { try FileManager.default.removeItem(at: final) }
        try FileManager.default.moveItem(at: temporary, to: final)
        let handle = try FileHandle(forReadingFrom: final)
        try handle.synchronize()
        try handle.close()
    }
}

public enum CapturePackageValidator {
    public static func validate(_ manifest: CapturePackageManifest, packageDirectory: URL? = nil) throws {
        guard manifest.schema == "sip.cscp" else { throw CaptureCoreError.packageInvalid("unsupported package schema") }
        guard manifest.schemaVersion.split(separator: ".").first == "1" else { throw CaptureCoreError.packageInvalid("unsupported major package version") }
        try manifest.verifyRootHash()
        guard manifest.startTimeNanoseconds <= manifest.endTimeNanoseconds else { throw CaptureCoreError.packageInvalid("package time range is reversed") }
        let assetIDs = manifest.assets.map(\.assetID)
        guard Set(assetIDs).count == assetIDs.count else { throw CaptureCoreError.packageInvalid("duplicate asset identifiers") }
        let frameIDs = manifest.frames.map(\.frameID)
        guard Set(frameIDs).count == frameIDs.count else { throw CaptureCoreError.packageInvalid("duplicate frame identifiers") }
        let timestamps = manifest.frames.map(\.timestampNanoseconds)
        guard timestamps == timestamps.sorted(), Set(timestamps).count == timestamps.count else { throw CaptureCoreError.packageInvalid("frame timestamps must be strictly monotonic") }
        let knownAssets = Set(assetIDs)
        for frame in manifest.frames {
            guard knownAssets.contains(frame.imageAssetID) else { throw CaptureCoreError.packageInvalid("frame references a missing image asset") }
            for optional in [frame.depthAssetID, frame.confidenceAssetID].compactMap({ $0 }) where !knownAssets.contains(optional) {
                throw CaptureCoreError.packageInvalid("frame references a missing optional asset")
            }
            for mesh in frame.meshObservations where mesh.geometryAssetID != nil && !knownAssets.contains(mesh.geometryAssetID!) {
                throw CaptureCoreError.packageInvalid("frame mesh observation references a missing geometry asset")
            }
            if frame.trackingState != .normal && frame.cameraTransform != Array(repeating: 0, count: 16) {
                // Transform is retained for forensics, but downstream validity is controlled by tracking state.
            }
        }
        for mesh in manifest.meshObservations where mesh.geometryAssetID != nil && !knownAssets.contains(mesh.geometryAssetID!) {
            throw CaptureCoreError.packageInvalid("mesh observation references a missing geometry asset")
        }
        let frameSet = Set(frameIDs)
        for segment in manifest.segments {
            guard segment.startedAtNanoseconds <= segment.endedAtNanoseconds else { throw CaptureCoreError.packageInvalid("segment time range is reversed") }
            guard Set(segment.frameIDs).isSubset(of: frameSet) else { throw CaptureCoreError.packageInvalid("segment references missing frames") }
            guard !segment.overlapControl.isEmpty else { throw CaptureCoreError.packageInvalid("segment overlap or explicit control is required") }
        }
        if let directory = packageDirectory {
            for asset in manifest.assets {
                let url = directory.appendingPathComponent(asset.relativePath).standardizedFileURL
                guard url.path.hasPrefix(directory.standardizedFileURL.path + "/") else { throw CaptureCoreError.packageInvalid("asset path escapes package directory") }
                guard FileManager.default.fileExists(atPath: url.path) else { throw CaptureCoreError.packageInvalid("asset file is missing: \(asset.relativePath)") }
                let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
                guard (attributes[.size] as? NSNumber)?.intValue == asset.byteCount else { throw CaptureCoreError.packageInvalid("asset byte count mismatch") }
                guard try SHA256Digest.file(url) == asset.sha256 else { throw CaptureCoreError.packageInvalid("asset hash mismatch") }
            }
        }
    }
}
