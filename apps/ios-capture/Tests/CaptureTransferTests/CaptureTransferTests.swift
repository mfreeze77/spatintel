import Foundation
import Testing
@testable import CaptureCore
@testable import CaptureTransfer

actor InterruptingTransport: UploadTransport {
    let destination: URL
    var chunks: [Int: UploadChunk] = [:]
    var failOnIndex: Int?
    init(destination: URL, failOnIndex: Int?) { self.destination = destination; self.failOnIndex = failOnIndex }
    func put(_ chunk: UploadChunk) async throws {
        if chunk.index == failOnIndex { failOnIndex = nil; throw CaptureCoreError.packageInvalid("synthetic interruption") }
        chunks[chunk.index] = chunk
    }
    func finalize(uploadID: String, sourceHash: String, byteCount: Int64) async throws -> VerifiedReceipt {
        var data = Data(); for index in chunks.keys.sorted() { data.append(chunks[index]!.data) }
        guard SHA256Digest.hex(data) == sourceHash else { throw CaptureCoreError.packageInvalid("assembly mismatch") }
        try data.write(to: destination, options: [.atomic])
        return .init(uploadID: uploadID, destination: destination.path, sourceHash: sourceHash, byteCount: byteCount, verifiedAtNanoseconds: 1, signature: "fixture-signature")
    }
}

@Test("CAPIOS-006 resumable transfer persists chunk checkpoints and verifies destination receipt")
func resumableUpload() async throws {
    let root = FileManager.default.temporaryDirectory.appendingPathComponent("sip-transfer-\(UUID().uuidString)")
    try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    let source = root.appendingPathComponent("source.bin")
    let checkpoint = root.appendingPathComponent("checkpoint.json")
    let destination = root.appendingPathComponent("received.bin")
    let data = Data((0..<4096).map { UInt8($0 % 251) })
    try data.write(to: source)
    let transport = InterruptingTransport(destination: destination, failOnIndex: 1)
    let uploader = try ResumableUploader(sourceURL: source, checkpointURL: checkpoint, uploadID: "upload-1", chunkSize: 1024, transport: transport)
    await #expect(throws: CaptureCoreError.self) { try await uploader.upload() }
    #expect(FileManager.default.fileExists(atPath: checkpoint.path))
    let receipt = try await uploader.upload()
    #expect(receipt.sourceHash == SHA256Digest.hex(data))
    #expect(try Data(contentsOf: destination) == data)
}
