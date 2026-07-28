import Foundation

public enum RecoveryAction: String, Codable, Sendable, CaseIterable { case resume, finalizePartial, exportForRepair, discardWithConfirmation }
public struct RecoveryAssessment: Codable, Sendable, Equatable {
    public let packageRevision: String
    public let journalRecords: Int
    public let recentHashesValid: Bool
    public let availableActions: [RecoveryAction]
    public let failure: String?
}

public enum CaptureRecovery {
    public static func assess(journalURL: URL, packageRevision: String) -> RecoveryAssessment {
        do {
            let records = try AppendOnlyJournal.readAndVerify(url: journalURL)
            return .init(packageRevision: packageRevision, journalRecords: records.count, recentHashesValid: true, availableActions: [.resume, .finalizePartial, .exportForRepair, .discardWithConfirmation], failure: nil)
        } catch {
            return .init(packageRevision: packageRevision, journalRecords: 0, recentHashesValid: false, availableActions: [.exportForRepair, .discardWithConfirmation], failure: String(describing: error))
        }
    }

    public static func repairRevision(originalSessionID: String, originalRootHash: String, reason: String) -> [String: String] {
        ["lineage.originalSessionID": originalSessionID, "lineage.originalRootHash": originalRootHash, "lineage.repairReason": reason, "lineage.revision": UUID().uuidString.lowercased()]
    }
}

public struct PreflightInput: Sendable, Equatable {
    public let projectSelected: Bool
    public let permissionsGranted: Bool
    public let availableStorageBytes: Int64
    public let requiredStorageBytes: Int64
    public let calibrationSatisfied: Bool
    public let safetyAcknowledged: Bool
    public let consentSatisfied: Bool
    public let profileSensors: Set<SensorKind>
    public let deviceSensors: Set<SensorKind>
}
public enum FieldSOP {
    public static func preflightFailures(_ input: PreflightInput) -> [String] {
        var failures: [String] = []
        if !input.projectSelected { failures.append("project_not_selected") }
        if !input.permissionsGranted { failures.append("permissions_missing") }
        if input.availableStorageBytes < input.requiredStorageBytes { failures.append("storage_insufficient") }
        if !input.calibrationSatisfied { failures.append("calibration_required") }
        if !input.safetyAcknowledged { failures.append("safety_not_acknowledged") }
        if !input.consentSatisfied { failures.append("consent_not_satisfied") }
        if !input.profileSensors.isSubset(of: input.deviceSensors) { failures.append("required_sensor_unavailable") }
        return failures
    }
    public static func closeoutChecklist(trackingReviewed: Bool, coverageReviewed: Bool, detailsReviewed: Bool, privacyReviewed: Bool, notesReviewed: Bool, packageFinalized: Bool) -> [String] {
        [trackingReviewed ? nil : "tracking", coverageReviewed ? nil : "coverage", detailsReviewed ? nil : "details", privacyReviewed ? nil : "privacy", notesReviewed ? nil : "notes", packageFinalized ? nil : "package_finalization"].compactMap { $0 }
    }
    public static let safetyGuidance = "Do not view the screen while walking through hazards; avoid ladders, restricted zones, active work, crowds, mirrors, glass, darkness, and moving machinery without a site-specific safe method."
}
