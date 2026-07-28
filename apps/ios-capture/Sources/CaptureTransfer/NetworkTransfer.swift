import Foundation
import CaptureCore

#if canImport(Network)
import Network

/// Network.framework transport boundary. The production implementation uses the same chunk hashes and checkpoint contract as `ResumableUploader`.
public actor NetworkFrameworkTransport: UploadTransport {
    private let host: NWEndpoint.Host
    private let port: NWEndpoint.Port
    private let tls: NWProtocolTLS.Options
    public init(host: String, port: UInt16, tls: NWProtocolTLS.Options = .init()) throws {
        guard let endpointPort = NWEndpoint.Port(rawValue: port) else { throw CaptureCoreError.packageInvalid("invalid upload port") }
        self.host = NWEndpoint.Host(host); self.port = endpointPort; self.tls = tls
    }
    public func put(_ chunk: UploadChunk) async throws {
        // Chunk framing is intentionally explicit; production server acknowledgement must bind upload ID, index, offset, hash, and length.
        let connection = NWConnection(host: host, port: port, using: NWParameters(tls: tls))
        connection.start(queue: .global(qos: .utility))
        defer { connection.cancel() }
        let header = try CanonicalJSON.data(["upload_id": chunk.uploadID, "index": String(chunk.index), "offset": String(chunk.offset), "sha256": chunk.sha256, "length": String(chunk.data.count)])
        var message = Data(); message.append(UInt32(header.count).bigEndianData); message.append(header); message.append(chunk.data)
        try await connection.sendAsync(message)
    }
    public func finalize(uploadID: String, sourceHash: String, byteCount: Int64) async throws -> VerifiedReceipt {
        throw CaptureCoreError.packageInvalid("receipt finalization requires the paired SIP server endpoint and is not emulated on-device")
    }
}

private extension UInt32 { var bigEndianData: Data { withUnsafeBytes(of: bigEndian) { Data($0) } } }
private extension NWConnection {
    func sendAsync(_ data: Data) async throws {
        try await withCheckedThrowingContinuation { continuation in
            send(content: data, completion: .contentProcessed { error in error == nil ? continuation.resume() : continuation.resume(throwing: error!) })
        }
    }
}
#endif
