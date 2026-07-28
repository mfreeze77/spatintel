import Foundation
import CaptureCore
import CaptureSensors
import CaptureTransfer

#if os(iOS) && canImport(SwiftUI)
import SwiftUI

@main
struct SIPCaptureApplication: App {
    @State private var state = CaptureState.setup
    var body: some Scene {
        WindowGroup {
            NavigationStack {
                VStack(spacing: 20) {
                    Text("SIP Capture").font(.largeTitle.bold())
                    Text("State: \(state.rawValue)").accessibilityLabel("Capture state \(state.rawValue)")
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
