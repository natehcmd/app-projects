import Foundation

struct SystemStats: Equatable {
    var cpuPercent: Double = 0
    var perCore: [Double] = []
    var ramUsedGB: Double = 0
    var ramTotalGB: Double = 0
    var ramPressure: Double = 0
    var swapUsedGB: Double = 0
    var diskFreeGB: Double = 0
    var diskTotalGB: Double = 0
    var diskReadKBps: Double = 0
    var diskWriteKBps: Double = 0
    var netDownKBps: Double = 0
    var netUpKBps: Double = 0
    var uptimeSeconds: TimeInterval = 0
    var thermalLevel: String = "Nominal"
    var batteryPercent: Double? = nil
    var batteryCharging: Bool = false
    var topProcesses: [ProcessRow] = []
    var hostName: String = Host.current().localizedName ?? "Mac"
    var osVersion: String = ProcessInfo.processInfo.operatingSystemVersionString

    var ramUsedFraction: Double {
        guard ramTotalGB > 0 else { return 0 }
        return min(1.0, ramUsedGB / ramTotalGB)
    }

    var diskUsedFraction: Double {
        guard diskTotalGB > 0 else { return 0 }
        return min(1.0, (diskTotalGB - diskFreeGB) / diskTotalGB)
    }
}

struct ProcessRow: Identifiable, Equatable {
    let id = UUID()
    let pid: Int32
    let name: String
    let cpu: Double
    let memMB: Double
}
