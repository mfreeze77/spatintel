import Foundation

public struct JournalRecord: Codable, Sendable, Equatable {
    public let sequence: UInt64
    public let timestampNanoseconds: UInt64
    public let event: String
    public let payload: [String: String]
    public let previousHash: String
    public let recordHash: String

    private struct Unsigned: Codable {
        let sequence: UInt64
        let timestampNanoseconds: UInt64
        let event: String
        let payload: [String: String]
        let previousHash: String
    }

    public static func make(sequence: UInt64, timestampNanoseconds: UInt64, event: String, payload: [String: String], previousHash: String) throws -> JournalRecord {
        let unsigned = Unsigned(sequence: sequence, timestampNanoseconds: timestampNanoseconds, event: event, payload: payload, previousHash: previousHash)
        return JournalRecord(sequence: sequence, timestampNanoseconds: timestampNanoseconds, event: event, payload: payload, previousHash: previousHash, recordHash: try CanonicalJSON.hash(unsigned))
    }

    public func verify() throws {
        let unsigned = Unsigned(sequence: sequence, timestampNanoseconds: timestampNanoseconds, event: event, payload: payload, previousHash: previousHash)
        guard try CanonicalJSON.hash(unsigned) == recordHash else { throw CaptureCoreError.journalCorrupt("journal record hash mismatch at sequence \(sequence)") }
    }
}

public actor AppendOnlyJournal {
    public let url: URL
    private var lastSequence: UInt64
    private var lastHash: String
    private let fsyncInterval: Int
    private var unflushedCount = 0

    public init(url: URL, fsyncInterval: Int = 1) throws {
        guard fsyncInterval > 0 else { throw CaptureCoreError.journalCorrupt("fsync interval must be positive") }
        self.url = url
        self.fsyncInterval = fsyncInterval
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        if !FileManager.default.fileExists(atPath: url.path) { guard FileManager.default.createFile(atPath: url.path, contents: nil) else { throw CaptureCoreError.journalCorrupt("unable to create journal file") } }
        let records = try Self.readAndVerify(url: url)
        self.lastSequence = records.last?.sequence ?? 0
        self.lastHash = records.last?.recordHash ?? String(repeating: "0", count: 64)
    }

    @discardableResult
    public func append(event: String, payload: [String: String] = [:], timestampNanoseconds: UInt64) throws -> JournalRecord {
        let record = try JournalRecord.make(sequence: lastSequence + 1, timestampNanoseconds: timestampNanoseconds, event: event, payload: payload, previousHash: lastHash)
        var encoded = try CanonicalJSON.data(record)
        encoded.append(0x0a)
        let handle = try FileHandle(forWritingTo: url)
        defer { try? handle.close() }
        try handle.seekToEnd()
        try handle.write(contentsOf: encoded)
        unflushedCount += 1
        if unflushedCount >= fsyncInterval {
            try handle.synchronize()
            unflushedCount = 0
        }
        lastSequence = record.sequence
        lastHash = record.recordHash
        return record
    }

    public func synchronize() throws {
        let handle = try FileHandle(forWritingTo: url)
        defer { try? handle.close() }
        try handle.synchronize()
        unflushedCount = 0
    }

    public func records() throws -> [JournalRecord] { try Self.readAndVerify(url: url) }
    public func rootHash() -> String { lastHash }

    public nonisolated static func readAndVerify(url: URL) throws -> [JournalRecord] {
        guard FileManager.default.fileExists(atPath: url.path) else { return [] }
        let data = try Data(contentsOf: url)
        let lines = data.split(separator: 0x0a, omittingEmptySubsequences: true)
        let decoder = JSONDecoder()
        var records: [JournalRecord] = []
        var expectedPrevious = String(repeating: "0", count: 64)
        for (index, line) in lines.enumerated() {
            let record = try decoder.decode(JournalRecord.self, from: Data(line))
            guard record.sequence == UInt64(index + 1) else { throw CaptureCoreError.journalCorrupt("non-contiguous journal sequence") }
            guard record.previousHash == expectedPrevious else { throw CaptureCoreError.journalCorrupt("journal hash-chain mismatch") }
            try record.verify()
            records.append(record)
            expectedPrevious = record.recordHash
        }
        return records
    }
}
