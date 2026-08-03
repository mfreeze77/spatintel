import Foundation

/// Thread-safe, content-addressed storage used by the sensor callback boundary.
/// Files are complete before an asset reference is returned.
public final class CaptureAssetStore: @unchecked Sendable {
    public let rootURL: URL
    private let lock = NSLock()
    private var recordsByID: [String: AssetReference] = [:]

    public init(rootURL: URL) throws {
        self.rootURL = rootURL.standardizedFileURL
        try FileManager.default.createDirectory(at: self.rootURL, withIntermediateDirectories: true)
    }

    @discardableResult
    public func write(
        _ data: Data,
        relativePath: String,
        mediaType: String,
        creationSource: String,
        retentionClass: String = "evidence"
    ) throws -> AssetReference {
        let normalized = try Self.safeRelativePath(relativePath)
        let digest = SHA256Digest.hex(data)
        let assetID = "asset-\(digest.prefix(24))"
        let destination = rootURL.appendingPathComponent(normalized).standardizedFileURL
        guard destination.path.hasPrefix(rootURL.path + "/") else {
            throw CaptureCoreError.packageInvalid("asset path escapes capture directory")
        }
        lock.lock()
        defer { lock.unlock() }
        if let existing = recordsByID[assetID] {
            guard existing.sha256 == digest, existing.byteCount == data.count else {
                throw CaptureCoreError.packageInvalid("content-addressed asset identifier conflict")
            }
            return existing
        }
        try FileManager.default.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
        #if os(iOS)
        try data.write(to: destination, options: [.atomic, .completeFileProtection])
        #else
        try data.write(to: destination, options: [.atomic])
        #endif
        let record = AssetReference(
            assetID: assetID,
            relativePath: normalized,
            mediaType: mediaType,
            byteCount: data.count,
            sha256: digest,
            creationSource: creationSource,
            encrypted: true,
            retentionClass: retentionClass
        )
        recordsByID[assetID] = record
        return record
    }

    public func assets() -> [AssetReference] {
        lock.lock()
        defer { lock.unlock() }
        return recordsByID.values.sorted { $0.relativePath < $1.relativePath }
    }

    private static func safeRelativePath(_ value: String) throws -> String {
        let normalized = value.replacingOccurrences(of: "\\", with: "/")
        let parts = normalized.split(separator: "/", omittingEmptySubsequences: false)
        guard !normalized.hasPrefix("/"), !parts.isEmpty,
              parts.allSatisfy({ !$0.isEmpty && $0 != "." && $0 != ".." }) else {
            throw CaptureCoreError.packageInvalid("asset path is not a safe relative path")
        }
        return parts.joined(separator: "/")
    }
}

public enum MeshAnchorBinary {
    public static let mediaType = "application/vnd.sip.mesh-anchor-v1"
    public static let encoding = "sip_mesh_anchor_v1_little_endian"
    private static let magic = Data([0x53, 0x49, 0x50, 0x4d, 0x53, 0x48, 0x31, 0x00])

    public static func encode(
        vertices: [SIMD3<Float>],
        normals: [SIMD3<Float>],
        faces: [SIMD3<UInt32>],
        classifications: [UInt8]
    ) throws -> Data {
        guard normals.count == vertices.count, classifications.count == faces.count else {
            throw CaptureCoreError.packageInvalid("mesh-anchor arrays are not aligned")
        }
        var data = magic
        data.appendLittleEndian(UInt32(vertices.count))
        data.appendLittleEndian(UInt32(faces.count))
        for value in vertices { data.appendFloat3(value) }
        for value in normals { data.appendFloat3(value) }
        for value in faces {
            data.appendLittleEndian(value.x); data.appendLittleEndian(value.y); data.appendLittleEndian(value.z)
        }
        data.append(contentsOf: classifications)
        return data
    }
}

private extension Data {
    mutating func appendLittleEndian<T: FixedWidthInteger>(_ value: T) {
        var encoded = value.littleEndian
        Swift.withUnsafeBytes(of: &encoded) { append(contentsOf: $0) }
    }

    mutating func appendFloat3(_ value: SIMD3<Float>) {
        for component in [value.x, value.y, value.z] {
            var bits = component.bitPattern.littleEndian
            Swift.withUnsafeBytes(of: &bits) { append(contentsOf: $0) }
        }
    }
}
