import Foundation
import CaptureCore

#if os(iOS) && canImport(ARKit) && canImport(AVFoundation) && canImport(CoreMotion) && canImport(Metal) && canImport(Network) && canImport(BackgroundTasks)
@preconcurrency import ARKit
import AVFoundation
import CoreMotion
import CoreImage
import CoreVideo
import Metal
import Network
import BackgroundTasks
#if canImport(UIKit)
import UIKit
#endif
#if canImport(RealityKit)
import RealityKit
#endif
#if canImport(RoomPlan)
import RoomPlan
#endif

/// Apple-platform acquisition boundary. Heavy image/depth serialization is dispatched away from ARSession's callback queue.
public final class AppleSpatialCaptureCoordinator: NSObject, SpatialSensorAdapter, @unchecked Sendable {
    public let adapterID = "first-party-arkit-v1"
    public let availableSensors: Set<SensorKind>
    private let session = ARSession()
    private let motionManager = CMMotionManager()
    private let processingQueue = DispatchQueue(label: "sip.capture.processing", qos: .userInitiated)
    private let eventContinuation: AsyncStream<SensorAdapterEvent>.Continuation
    private let eventStream: AsyncStream<SensorAdapterEvent>
    public let assetStore: CaptureAssetStore
    private let imageContext = CIContext(options: [.cacheIntermediates: false])
    private var policy: CapturePolicyBundle?
    private var frameSequence: UInt64 = 0
    private var pendingMeshChanges: [MeshObservation] = []
    private var lastTracking: (TrackingState, LimitedTrackingReason?)?

    public override convenience init() {
        let base = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first
            ?? FileManager.default.temporaryDirectory
        let directory = base.appendingPathComponent("SpatintelCaptures", isDirectory: true)
            .appendingPathComponent(UUID().uuidString.lowercased(), isDirectory: true)
        try! self.init(assetStore: CaptureAssetStore(rootURL: directory))
    }

    public init(assetStore: CaptureAssetStore) throws {
        self.assetStore = assetStore
        var continuation: AsyncStream<SensorAdapterEvent>.Continuation!
        self.eventStream = AsyncStream(bufferingPolicy: .bufferingNewest(12)) { continuation = $0 }
        self.eventContinuation = continuation
        self.availableSensors = [.rgb, .motion]
            .union(ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth) ? [.lidarDepth, .confidence] : [])
            .union(ARWorldTrackingConfiguration.supportsSceneReconstruction(.mesh) ? [.mesh] : [])
        super.init()
        session.delegate = self
    }

    public func start(policy: CapturePolicyBundle, profile: CaptureProfile) async throws {
        guard profile.requiredSensors.isSubset(of: availableSensors) else { throw CaptureCoreError.packageInvalid("device lacks required capture sensors") }
        guard profile.requiredSensors.isSubset(of: policy.permittedSensors) else { throw CaptureCoreError.packageInvalid("policy denies required capture sensors") }
        self.policy = policy
        let configuration = ARWorldTrackingConfiguration()
        configuration.worldAlignment = .gravity
        if policy.permits(.lidarDepth), ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth) { configuration.frameSemantics.insert(.sceneDepth) }
        if policy.permits(.mesh), ARWorldTrackingConfiguration.supportsSceneReconstruction(.mesh) { configuration.sceneReconstruction = .mesh }
        session.run(configuration, options: [])
        if policy.permits(.motion), motionManager.isDeviceMotionAvailable {
            motionManager.deviceMotionUpdateInterval = 1.0 / 100.0
            motionManager.startDeviceMotionUpdates()
        }
    }

    public func stop() async {
        session.pause()
        motionManager.stopDeviceMotionUpdates()
        await flush()
        eventContinuation.finish()
    }

    public func flush() async {
        await withCheckedContinuation { continuation in
            processingQueue.async { continuation.resume() }
        }
    }

    public func nextEvent() async -> SensorAdapterEvent? {
        var iterator = eventStream.makeAsyncIterator()
        return await iterator.next()
    }

    public func setWorldOrigin(relativeTransform: simd_float4x4) {
        session.setWorldOrigin(relativeTransform: relativeTransform)
        eventContinuation.yield(.worldOriginChanged(transform: flatten(relativeTransform)))
    }

    private func tracking(_ state: ARCamera.TrackingState) -> (TrackingState, LimitedTrackingReason?) {
        switch state {
        case .normal: return (.normal, nil)
        case .notAvailable: return (.notAvailable, nil)
        case let .limited(reason):
            let mapped: LimitedTrackingReason = switch reason {
            case .initializing: .initializing
            case .excessiveMotion: .excessiveMotion
            case .insufficientFeatures: .insufficientFeatures
            case .relocalizing: .relocalizing
            @unknown default: .unknown
            }
            return (.limited, mapped)
        }
    }

    private func flatten(_ matrix: simd_float4x4) -> [Double] {
        (0..<4).flatMap { column in (0..<4).map { row in Double(matrix[column][row]) } }
    }

    private func flatten(_ matrix: simd_float3x3) -> [Double] {
        (0..<3).flatMap { column in (0..<3).map { row in Double(matrix[column][row]) } }
    }

    private func packedBytes(_ pixelBuffer: CVPixelBuffer, bytesPerPixel: Int) throws -> Data {
        CVPixelBufferLockBaseAddress(pixelBuffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(pixelBuffer, .readOnly) }
        guard !CVPixelBufferIsPlanar(pixelBuffer), let base = CVPixelBufferGetBaseAddress(pixelBuffer) else {
            throw CaptureCoreError.packageInvalid("pixel buffer is not a packed single-plane image")
        }
        let width = CVPixelBufferGetWidth(pixelBuffer)
        let height = CVPixelBufferGetHeight(pixelBuffer)
        let sourceStride = CVPixelBufferGetBytesPerRow(pixelBuffer)
        let rowBytes = width * bytesPerPixel
        guard sourceStride >= rowBytes else { throw CaptureCoreError.packageInvalid("pixel buffer row stride is invalid") }
        var result = Data(count: rowBytes * height)
        result.withUnsafeMutableBytes { output in
            guard let destination = output.baseAddress else { return }
            for row in 0..<height {
                memcpy(destination.advanced(by: row * rowBytes), base.advanced(by: row * sourceStride), rowBytes)
            }
        }
        return result
    }

    private func rgbBytes(_ source: CVPixelBuffer) throws -> (Data, ImageResolution) {
        let width = CVPixelBufferGetWidth(source), height = CVPixelBufferGetHeight(source)
        var converted: CVPixelBuffer?
        let attributes = [kCVPixelBufferIOSurfacePropertiesKey: [:]] as CFDictionary
        let status = CVPixelBufferCreate(
            kCFAllocatorDefault, width, height, kCVPixelFormatType_32BGRA, attributes, &converted
        )
        guard status == kCVReturnSuccess, let converted else {
            throw CaptureCoreError.packageInvalid("unable to allocate the BGRA capture buffer")
        }
        imageContext.render(CIImage(cvPixelBuffer: source), to: converted)
        return (try packedBytes(converted, bytesPerPixel: 4), .init(width: width, height: height))
    }

    private func currentMotionSample() -> MotionSample? {
        guard let motion = motionManager.deviceMotion else { return nil }
        return try? MotionSample(
            timestampNanoseconds: UInt64(max(motion.timestamp, 0) * 1_000_000_000),
            acceleration: [motion.userAcceleration.x, motion.userAcceleration.y, motion.userAcceleration.z],
            rotationRate: [motion.rotationRate.x, motion.rotationRate.y, motion.rotationRate.z],
            attitudeQuaternion: [motion.attitude.quaternion.x, motion.attitude.quaternion.y, motion.attitude.quaternion.z, motion.attitude.quaternion.w]
        )
    }

    private func orientation() -> InterfaceOrientation {
        #if canImport(UIKit)
        switch UIDevice.current.orientation {
        case .portrait: return .portrait
        case .portraitUpsideDown: return .portraitUpsideDown
        case .landscapeLeft: return .landscapeLeft
        case .landscapeRight: return .landscapeRight
        default: return .unknown
        }
        #else
        return .unknown
        #endif
    }

    private func frameQuality(rgb: Data, depth: Data?, confidence: Data?, tracking: TrackingState, motion: MotionSample?) -> QualitySignals {
        let pixelCount = rgb.count / 4
        var clipped = 0, sampled = 0
        var gradientSum = 0.0, gradientSquared = 0.0, prior: Double?
        rgb.withUnsafeBytes { raw in
            let bytes = raw.bindMemory(to: UInt8.self)
            for pixel in stride(from: 0, to: pixelCount, by: 16) {
                let offset = pixel * 4
                let luminance = 0.0722 * Double(bytes[offset]) + 0.7152 * Double(bytes[offset + 1]) + 0.2126 * Double(bytes[offset + 2])
                if luminance <= 4 || luminance >= 251 { clipped += 1 }
                if let prior {
                    let gradient = abs(luminance - prior)
                    gradientSum += gradient; gradientSquared += gradient * gradient
                }
                prior = luminance; sampled += 1
            }
        }
        let gradients = max(sampled - 1, 1)
        let mean = gradientSum / Double(gradients)
        let variance = max(gradientSquared / Double(gradients) - mean * mean, 0)
        let blur = 1.0 / (1.0 + variance / 400.0)
        var validDepth = 0, totalDepth = 0
        if let depth {
            totalDepth = depth.count / 4
            depth.withUnsafeBytes { raw in
                let bytes = raw.bindMemory(to: UInt8.self)
                for index in 0..<totalDepth {
                    let offset = index * 4
                    let bits = UInt32(bytes[offset])
                        | (UInt32(bytes[offset + 1]) << 8)
                        | (UInt32(bytes[offset + 2]) << 16)
                        | (UInt32(bytes[offset + 3]) << 24)
                    let value = Float(bitPattern: bits)
                    let confidenceValid = confidence.map { Int($0[index]) >= 1 } ?? true
                    if value.isFinite && value > 0 && confidenceValid { validDepth += 1 }
                }
            }
        }
        let angular = motion.map { sqrt($0.rotationRate.reduce(0) { $0 + $1 * $1 }) } ?? 0
        let coverage = Double(validDepth) / Double(max(totalDepth, 1))
        return QualitySignals(
            blur: blur,
            exposureClippingFraction: Double(clipped) / Double(max(sampled, 1)),
            angularVelocityRadiansPerSecond: angular,
            trackingState: tracking,
            depthCoverage: coverage,
            viewpointDiversity: 0,
            weakSurfaceFraction: 1 - coverage
        )
    }
}

extension AppleSpatialCaptureCoordinator: ARSessionDelegate {
    public func session(_ session: ARSession, didUpdate frame: ARFrame) {
        frameSequence &+= 1
        let sequence = frameSequence
        let tracking = tracking(frame.camera.trackingState)
        if lastTracking?.0 != tracking.0 || lastTracking?.1 != tracking.1 {
            eventContinuation.yield(.trackingChanged(state: tracking.0, reason: tracking.1))
            if lastTracking?.1 == .relocalizing, tracking.0 == .normal {
                eventContinuation.yield(.relocalizationCompleted)
            }
            lastTracking = tracking
        }
        let timestampNs = UInt64(max(frame.timestamp, 0) * 1_000_000_000)
        processingQueue.async { [weak self] in
            guard let self else { return }
            do {
                let prefix = String(format: "frames/%06llu", sequence)
                let (rgbData, imageResolution) = try self.rgbBytes(frame.capturedImage)
                let rgb = try self.assetStore.write(
                    rgbData,
                    relativePath: "\(prefix)/rgb.bgra8",
                    mediaType: "application/vnd.sip.image-bgra8",
                    creationSource: "ARFrame.capturedImage"
                )
                var depthData: Data?, confidenceData: Data?, depthResolution: ImageResolution?
                var depthAssetID: String?, confidenceAssetID: String?
                if let sceneDepth = frame.sceneDepth {
                    let width = CVPixelBufferGetWidth(sceneDepth.depthMap)
                    let height = CVPixelBufferGetHeight(sceneDepth.depthMap)
                    depthResolution = .init(width: width, height: height)
                    let bytes = try self.packedBytes(sceneDepth.depthMap, bytesPerPixel: 4)
                    depthData = bytes
                    depthAssetID = try self.assetStore.write(
                        bytes,
                        relativePath: "\(prefix)/depth.f32",
                        mediaType: "application/vnd.sip.depth-f32",
                        creationSource: "ARDepthData.depthMap"
                    ).assetID
                    if let confidenceMap = sceneDepth.confidenceMap {
                        let confidenceBytes = try self.packedBytes(confidenceMap, bytesPerPixel: 1)
                        confidenceData = confidenceBytes
                        confidenceAssetID = try self.assetStore.write(
                            confidenceBytes,
                            relativePath: "\(prefix)/confidence.u8",
                            mediaType: "application/vnd.sip.confidence-u8",
                            creationSource: "ARDepthData.confidenceMap"
                        ).assetID
                    }
                }
                let motion = self.currentMotionSample()
                let exposure = ExposureMetadata(
                    durationSeconds: frame.camera.exposureDuration,
                    iso: Double(AVCaptureDevice.default(for: .video)?.iso ?? 0),
                    exposureTargetOffset: frame.camera.exposureOffset
                )
                let meshChanges = self.pendingMeshChanges
                self.pendingMeshChanges.removeAll(keepingCapacity: true)
                let quality = self.frameQuality(
                    rgb: rgbData,
                    depth: depthData,
                    confidence: confidenceData,
                    tracking: tracking.0,
                    motion: motion
                )
                let observation = try FrameObservation(
                    frameID: "frame-\(sequence)", timestampNanoseconds: timestampNs,
                    imageAssetID: rgb.assetID,
                    depthAssetID: depthAssetID,
                    confidenceAssetID: confidenceAssetID,
                    cameraTransform: self.flatten(frame.camera.transform), intrinsics: self.flatten(frame.camera.intrinsics),
                    resolution: imageResolution,
                    trackingState: tracking.0, limitedTrackingReason: tracking.1, exposure: exposure,
                    orientation: self.orientation(), motionSamples: motion.map { [$0] } ?? [], meshObservations: meshChanges,
                    privacyRegionIDs: [], invalidDepthPreserved: true, imageEncoding: "bgra8",
                    depthResolution: depthResolution, depthEncoding: depthAssetID == nil ? nil : "float32_little_endian_meters",
                    confidenceEncoding: confidenceAssetID == nil ? nil : "arkit_0_low_1_medium_2_high",
                    qualitySignals: quality
                )
                if case .dropped = self.eventContinuation.yield(.frame(observation)) {
                    self.eventContinuation.yield(.dropped(.init(frameID: observation.frameID, timestampNanoseconds: observation.timestampNanoseconds, cause: "bounded_queue_full")))
                }
            } catch {
                self.eventContinuation.yield(.dropped(.init(frameID: "frame-\(sequence)", timestampNanoseconds: timestampNs, cause: "asset_serialization_failed:\(type(of: error))")))
            }
        }
    }

    public func sessionWasInterrupted(_ session: ARSession) { eventContinuation.yield(.sessionInterrupted) }
    public func sessionInterruptionEnded(_ session: ARSession) {
        eventContinuation.yield(.sessionResumed)
        eventContinuation.yield(.relocalizationStarted)
    }
    public func sessionShouldAttemptRelocalization(_ session: ARSession) -> Bool { eventContinuation.yield(.relocalizationStarted); return true }
    public func session(_ session: ARSession, didChange geoTrackingStatus: ARGeoTrackingStatus) { /* location capture remains policy-disabled unless explicitly enabled */ }
    public func session(_ session: ARSession, didAdd anchors: [ARAnchor]) { journalMesh(anchors, change: .added) }
    public func session(_ session: ARSession, didUpdate anchors: [ARAnchor]) { journalMesh(anchors, change: .updated) }
    public func session(_ session: ARSession, didRemove anchors: [ARAnchor]) { journalMesh(anchors, change: .removed) }

    private func journalMesh(_ anchors: [ARAnchor], change: MeshObservation.Change) {
        guard policy?.permits(.mesh) == true else { return }
        let timestampNs = UInt64(ProcessInfo.processInfo.systemUptime * 1_000_000_000)
        for anchor in anchors.compactMap({ $0 as? ARMeshAnchor }) {
            processingQueue.async { [weak self] in
                guard let self else { return }
                do {
                    let anchorID = anchor.identifier.uuidString.lowercased()
                    var geometryAssetID: String?
                    if change != .removed {
                        let encoded = try self.meshBytes(anchor.geometry)
                        geometryAssetID = try self.assetStore.write(
                            encoded,
                            relativePath: "meshes/\(anchorID)/\(timestampNs)-\(change.rawValue).sipmesh",
                            mediaType: MeshAnchorBinary.mediaType,
                            creationSource: "ARMeshAnchor.geometry"
                        ).assetID
                    }
                    let observation = try MeshObservation(
                        anchorID: anchorID,
                        timestampNanoseconds: timestampNs,
                        change: change,
                        transform: self.flatten(anchor.transform),
                        geometryAssetID: geometryAssetID
                    )
                    self.pendingMeshChanges.append(observation)
                    self.eventContinuation.yield(.meshChanged(observation))
                } catch {
                    self.eventContinuation.yield(.dropped(.init(frameID: "mesh-\(anchor.identifier.uuidString.lowercased())", timestampNanoseconds: timestampNs, cause: "mesh_serialization_failed:\(type(of: error))")))
                }
            }
        }
    }

    private func meshBytes(_ geometry: ARMeshGeometry) throws -> Data {
        func vector(_ source: ARGeometrySource, _ index: Int) -> SIMD3<Float> {
            var value = SIMD3<Float>.zero
            memcpy(
                &value,
                source.buffer.contents().advanced(by: source.offset + source.stride * index),
                MemoryLayout<SIMD3<Float>>.size
            )
            return value
        }
        let vertices = (0..<geometry.vertices.count).map { vector(geometry.vertices, $0) }
        let normals = (0..<geometry.normals.count).map { vector(geometry.normals, $0) }
        let element = geometry.faces
        guard element.indexCountPerPrimitive == 3, element.bytesPerIndex == 2 || element.bytesPerIndex == 4 else {
            throw CaptureCoreError.packageInvalid("ARKit mesh faces use an unsupported index layout")
        }
        var faces: [SIMD3<UInt32>] = []
        var classifications: [UInt8] = []
        for faceIndex in 0..<element.count {
            var indices = SIMD3<UInt32>.zero
            for corner in 0..<3 {
                let offset = (faceIndex * 3 + corner) * element.bytesPerIndex
                let pointer = element.buffer.contents().advanced(by: offset)
                let value: UInt32
                if element.bytesPerIndex == 2 {
                    var raw: UInt16 = 0; memcpy(&raw, pointer, 2); value = UInt32(UInt16(littleEndian: raw))
                } else {
                    var raw: UInt32 = 0; memcpy(&raw, pointer, 4); value = UInt32(littleEndian: raw)
                }
                indices[corner] = value
            }
            faces.append(indices)
            classifications.append(UInt8(clamping: geometry.classificationOf(faceWithIndex: faceIndex).rawValue))
        }
        return try MeshAnchorBinary.encode(vertices: vertices, normals: normals, faces: faces, classifications: classifications)
    }
}

#else
public actor AppleSpatialCaptureCoordinator: SpatialSensorAdapter {
    public let adapterID = "first-party-arkit-v1-unavailable"
    public let availableSensors: Set<SensorKind> = []
    public init() {}
    public func start(policy: CapturePolicyBundle, profile: CaptureProfile) async throws {
        throw CaptureCoreError.packageInvalid("ARKit capture is available only on a supported Apple device")
    }
    public func stop() async {}
    public func nextEvent() async -> SensorAdapterEvent? { nil }
}
#endif
