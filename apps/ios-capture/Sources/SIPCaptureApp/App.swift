import Foundation
import CaptureCore
import CaptureSensors
import CaptureTransfer

#if os(iOS) && canImport(SwiftUI)
import SwiftUI

@main
struct SIPCaptureApplication: App {
    @StateObject private var capture = CaptureController()
    var body: some Scene {
        WindowGroup {
            NavigationStack {
                VStack(spacing: 20) {
                    Text("SIP Capture").font(.largeTitle.bold())
                    Text("State: \(capture.state.rawValue)").accessibilityLabel("Capture state \(capture.state.rawValue)")
                    Text("Frames: \(capture.frameCount) · Dropped: \(capture.droppedCount)")
                    Text(capture.message).multilineTextAlignment(.center)
                    HStack {
                        Button("Start local capture") { Task { await capture.start() } }
                            .disabled(!capture.canStart)
                        Button("Finalize package") { Task { await capture.finalize() } }
                            .disabled(!capture.canFinalize)
                    }
                    if let directory = capture.finalizedDirectory {
                        Text(directory.lastPathComponent).font(.caption.monospaced())
                        Text("Use Files or a cable connection to copy the complete SpatintelCaptures session directory.")
                            .font(.caption)
                    }
                    Text("Originals remain encrypted on this device until package integrity and destination receipt are verified.")
                    Text("Do not look at the screen while moving through hazards.").foregroundStyle(.orange)
                }
                .padding()
                .navigationTitle("Spatial Capture")
            }
        }
    }
}
#else
@main
struct SIPCaptureFixtureExecutable {
    static func main() {
        print("SIPCapture fixture build: ARKit/SwiftUI acquisition requires a supported Apple platform; core package is available.")
    }
}
#endif
