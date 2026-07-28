import Foundation

public enum CanonicalJSON {
    public static func encoder() -> JSONEncoder {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        return encoder
    }
    public static func data<T: Encodable>(_ value: T) throws -> Data { try encoder().encode(value) }
    public static func hash<T: Encodable>(_ value: T) throws -> String { SHA256Digest.hex(try data(value)) }
}
