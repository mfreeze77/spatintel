import Foundation
import CaptureCore

public struct UploadChunk: Sendable, Equatable {
    public let uploadID: String
    public let index: Int
    public let offset: Int64
    public let data: Data
    public let sha256: String
    public init(uploadID: String, index: Int, offset: Int64, data: Data) {
        self.uploadID = uploadID; self.index = index; self.offset = offset; self.data = data; self.sha256 = SHA256Digest.hex(data)
    }
}

public struct UploadCheckpoint: Codable, Sendable, Equatable {
    public let uploadID: String
    public let sourceHash: String
    public let byteCount: Int64
    public let chunkSize: Int
    public var uploadedChunkIndices: Set<Int>
}

public struct VerifiedReceipt: Codable, Sendable, Equatable {
    public let uploadID: String
    public let destination: String
    public let sourceHash: String
    public let byteCount: Int64
    public let verifiedAtNanoseconds: UInt64
    public let signature: String
}

public protocol UploadTransport: Sendable {
    func put(_ chunk: UploadChunk) async throws
    func finalize(uploadID: String, sourceHash: String, byteCount: Int64) async throws -> VerifiedReceipt
}

public actor ResumableUploader {
    public let sourceURL: URL
    public let checkpointURL: URL
    public let uploadID: String
    public let chunkSize: Int
    private let transport: any UploadTransport

    public init(sourceURL: URL, checkpointURL: URL, uploadID: String, chunkSize: Int = 1_048_576, transport: any UploadTransport) throws {
        guard chunkSize > 0 else { throw CaptureCoreError.packageInvalid("upload chunk size must be positive") }
        self.sourceURL = sourceURL; self.checkpointURL = checkpointURL; self.uploadID = uploadID; self.chunkSize = chunkSize; self.transport = transport
    }

    public func upload() async throws -> VerifiedReceipt {
        let sourceData = try Data(contentsOf: sourceURL, options: [.mappedIfSafe])
        let sourceHash = SHA256Digest.hex(sourceData)
        var checkpoint = try loadOrCreateCheckpoint(sourceHash: sourceHash, byteCount: Int64(sourceData.count))
        let count = max(1, Int(ceil(Double(sourceData.count) / Double(chunkSize))))
        for index in 0..<count where !checkpoint.uploadedChunkIndices.contains(index) {
            let start = min(index * chunkSize, sourceData.count)
            let end = min(start + chunkSize, sourceData.count)
            let chunk = UploadChunk(uploadID: uploadID, index: index, offset: Int64(start), data: sourceData.subdata(in: start..<end))
            try await transport.put(chunk)
            checkpoint.uploadedChunkIndices.insert(index)
            try save(checkpoint)
        }
        let receipt = try await transport.finalize(uploadID: uploadID, sourceHash: sourceHash, byteCount: Int64(sourceData.count))
        guard receipt.uploadID == uploadID, receipt.sourceHash == sourceHash, receipt.byteCount == Int64(sourceData.count), !receipt.signature.isEmpty else {
            throw CaptureCoreError.packageInvalid("destination receipt did not verify the uploaded source")
        }
        return receipt
    }

    private func loadOrCreateCheckpoint(sourceHash: String, byteCount: Int64) throws -> UploadCheckpoint {
        if FileManager.default.fileExists(atPath: checkpointURL.path) {
            let existing = try JSONDecoder().decode(UploadCheckpoint.self, from: Data(contentsOf: checkpointURL))
            guard existing.uploadID == uploadID, existing.sourceHash == sourceHash, existing.byteCount == byteCount, existing.chunkSize == chunkSize else {
                throw CaptureCoreError.packageInvalid("upload checkpoint does not match source")
            }
            return existing
        }
        return UploadCheckpoint(uploadID: uploadID, sourceHash: sourceHash, byteCount: byteCount, chunkSize: chunkSize, uploadedChunkIndices: [])
    }

    private func save(_ checkpoint: UploadCheckpoint) throws {
        try FileManager.default.createDirectory(at: checkpointURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        try CanonicalJSON.data(checkpoint).write(to: checkpointURL, options: [.atomic])
    }
}

public actor LocalDirectoryTransport: UploadTransport {
    private let destination: URL
    private var chunks: [Int: UploadChunk] = [:]
    public init(destination: URL) { self.destination = destination }
    public func put(_ chunk: UploadChunk) async throws {
        guard SHA256Digest.hex(chunk.data) == chunk.sha256 else { throw CaptureCoreError.packageInvalid("upload chunk hash mismatch") }
        if let existing = chunks[chunk.index], existing.sha256 != chunk.sha256 { throw CaptureCoreError.packageInvalid("idempotent upload chunk conflict") }
        chunks[chunk.index] = chunk
    }
    public func finalize(uploadID: String, sourceHash: String, byteCount: Int64) async throws -> VerifiedReceipt {
        let ordered = chunks.keys.sorted().compactMap { chunks[$0]?.data }
        var data = Data(); for chunk in ordered { data.append(chunk) }
        guard data.count == Int(byteCount), SHA256Digest.hex(data) == sourceHash else { throw CaptureCoreError.packageInvalid("assembled upload does not match source") }
        try FileManager.default.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: destination, options: [.atomic])
        return .init(uploadID: uploadID, destination: destination.path, sourceHash: sourceHash, byteCount: byteCount, verifiedAtNanoseconds: UInt64(Date().timeIntervalSince1970 * 1_000_000_000), signature: SHA256Digest.hex("\(uploadID):\(sourceHash):\(byteCount)"))
    }
}
