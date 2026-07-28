// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "SIPCapture",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "CaptureCore", targets: ["CaptureCore"]),
        .library(name: "CaptureSensors", targets: ["CaptureSensors"]),
        .library(name: "CaptureTransfer", targets: ["CaptureTransfer"]),
        .executable(name: "sip-capture", targets: ["SIPCaptureApp"])
    ],
    targets: [
        .target(name: "CaptureCore"),
        .target(name: "CaptureSensors", dependencies: ["CaptureCore"]),
        .target(name: "CaptureTransfer", dependencies: ["CaptureCore"]),
        .executableTarget(name: "SIPCaptureApp", dependencies: ["CaptureCore", "CaptureSensors", "CaptureTransfer"]),
        .testTarget(name: "CaptureCoreTests", dependencies: ["CaptureCore", "CaptureSensors"]),
        .testTarget(name: "CaptureTransferTests", dependencies: ["CaptureCore", "CaptureTransfer"])
    ],
    swiftLanguageModes: [.v6]
)
