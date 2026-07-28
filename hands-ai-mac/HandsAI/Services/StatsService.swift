import Foundation
import SwiftUI
import Darwin
import Darwin.Mach

@MainActor
final class StatsService: ObservableObject {
    @Published var stats = SystemStats()
    @Published var cpuHistory: [Double] = []
    @Published var ramHistory: [Double] = []
    @Published var netDownHistory: [Double] = []
    @Published var netUpHistory: [Double] = []
    private let historyCap = 60

    private var timer: Timer?
    private var prevCPUTicks: (user: UInt64, system: UInt64, idle: UInt64, nice: UInt64)?
    private var prevPerCoreTicks: [(UInt64, UInt64, UInt64, UInt64)] = []
    private var prevNet: (rx: UInt64, tx: UInt64, t: Date)?
    private var prevDisk: (read: UInt64, write: UInt64, t: Date)?

    func start() {
        sample()
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.sample() }
        }
    }

    func stop() {
        timer?.invalidate()
        timer = nil
    }

    private func sample() {
        var s = stats
        s.cpuPercent = sampleCPU(into: &s)
        sampleMemory(into: &s)
        sampleDisk(into: &s)
        sampleNetwork(into: &s)
        s.uptimeSeconds = sampleUptime()
        s.thermalLevel = sampleThermal()
        s.topProcesses = sampleTopProcesses()
        s.batteryPercent = sampleBattery(charging: &s.batteryCharging)
        self.stats = s

        cpuHistory.append(s.cpuPercent)
        if cpuHistory.count > historyCap { cpuHistory.removeFirst(cpuHistory.count - historyCap) }
        ramHistory.append(s.ramUsedFraction * 100)
        if ramHistory.count > historyCap { ramHistory.removeFirst(ramHistory.count - historyCap) }
        netDownHistory.append(s.netDownKBps)
        if netDownHistory.count > historyCap { netDownHistory.removeFirst(netDownHistory.count - historyCap) }
        netUpHistory.append(s.netUpKBps)
        if netUpHistory.count > historyCap { netUpHistory.removeFirst(netUpHistory.count - historyCap) }
    }

    // MARK: - CPU

    private func sampleCPU(into s: inout SystemStats) -> Double {
        var count = mach_msg_type_number_t(MemoryLayout<host_cpu_load_info_data_t>.size / MemoryLayout<integer_t>.size)
        var info = host_cpu_load_info_data_t()
        let result = withUnsafeMutablePointer(to: &info) { ptr -> kern_return_t in
            ptr.withMemoryRebound(to: integer_t.self, capacity: Int(count)) { intPtr in
                host_statistics(mach_host_self(), HOST_CPU_LOAD_INFO, intPtr, &count)
            }
        }
        guard result == KERN_SUCCESS else { return s.cpuPercent }

        let user   = UInt64(info.cpu_ticks.0)
        let system = UInt64(info.cpu_ticks.1)
        let idle   = UInt64(info.cpu_ticks.2)
        let nice   = UInt64(info.cpu_ticks.3)

        defer { prevCPUTicks = (user, system, idle, nice) }
        guard let prev = prevCPUTicks else { return 0 }
        let du = user - prev.user
        let ds = system - prev.system
        let di = idle - prev.idle
        let dn = nice - prev.nice
        let total = du + ds + di + dn
        guard total > 0 else { return s.cpuPercent }
        let active = du + ds + dn
        let percent = (Double(active) / Double(total)) * 100.0

        s.perCore = samplePerCore()
        return percent
    }

    private func samplePerCore() -> [Double] {
        var numCPUs: natural_t = 0
        var info: processor_info_array_t!
        var infoCount: mach_msg_type_number_t = 0
        let result = host_processor_info(mach_host_self(), PROCESSOR_CPU_LOAD_INFO,
                                         &numCPUs, &info, &infoCount)
        guard result == KERN_SUCCESS else { return [] }
        defer {
            vm_deallocate(mach_task_self_,
                          vm_address_t(bitPattern: info),
                          vm_size_t(infoCount) * vm_size_t(MemoryLayout<integer_t>.stride))
        }

        var out: [Double] = []
        var newTicks: [(UInt64, UInt64, UInt64, UInt64)] = []
        for i in 0..<Int(numCPUs) {
            let base = i * Int(CPU_STATE_MAX)
            let user   = UInt64(info[base + Int(CPU_STATE_USER)])
            let system = UInt64(info[base + Int(CPU_STATE_SYSTEM)])
            let idle   = UInt64(info[base + Int(CPU_STATE_IDLE)])
            let nice   = UInt64(info[base + Int(CPU_STATE_NICE)])
            newTicks.append((user, system, idle, nice))

            if i < prevPerCoreTicks.count {
                let p = prevPerCoreTicks[i]
                let du = user - p.0, ds = system - p.1, di = idle - p.2, dn = nice - p.3
                let total = du + ds + di + dn
                let active = du + ds + dn
                if total > 0 {
                    out.append(Double(active) / Double(total) * 100.0)
                } else {
                    out.append(0)
                }
            } else {
                out.append(0)
            }
        }
        prevPerCoreTicks = newTicks
        return out
    }

    // MARK: - Memory

    private func sampleMemory(into s: inout SystemStats) {
        var totalBytes: UInt64 = 0
        var size = MemoryLayout<UInt64>.size
        sysctlbyname("hw.memsize", &totalBytes, &size, nil, 0)
        s.ramTotalGB = Double(totalBytes) / 1_073_741_824.0

        var info = vm_statistics64_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<vm_statistics64_data_t>.size / MemoryLayout<integer_t>.size)
        let result = withUnsafeMutablePointer(to: &info) { ptr -> kern_return_t in
            ptr.withMemoryRebound(to: integer_t.self, capacity: Int(count)) { intPtr in
                host_statistics64(mach_host_self(), HOST_VM_INFO64, intPtr, &count)
            }
        }
        guard result == KERN_SUCCESS else { return }
        let pageSize = UInt64(vm_kernel_page_size)
        let active   = UInt64(info.active_count)   * pageSize
        let wired    = UInt64(info.wire_count)     * pageSize
        let compressed = UInt64(info.compressor_page_count) * pageSize
        let used = active + wired + compressed
        s.ramUsedGB = Double(used) / 1_073_741_824.0
        s.ramPressure = s.ramUsedFraction

        var xsw = xsw_usage()
        var xswSize = MemoryLayout<xsw_usage>.size
        if sysctlbyname("vm.swapusage", &xsw, &xswSize, nil, 0) == 0 {
            s.swapUsedGB = Double(xsw.xsu_used) / 1_073_741_824.0
        }
    }

    // MARK: - Disk

    private func sampleDisk(into s: inout SystemStats) {
        if let attrs = try? FileManager.default.attributesOfFileSystem(forPath: "/") {
            if let total = attrs[.systemSize] as? NSNumber {
                s.diskTotalGB = total.doubleValue / 1_073_741_824.0
            }
            if let free = attrs[.systemFreeSize] as? NSNumber {
                s.diskFreeGB = free.doubleValue / 1_073_741_824.0
            }
        }
    }

    // MARK: - Network

    private func sampleNetwork(into s: inout SystemStats) {
        var ifaddrPtr: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&ifaddrPtr) == 0, let first = ifaddrPtr else { return }
        defer { freeifaddrs(ifaddrPtr) }

        var rx: UInt64 = 0, tx: UInt64 = 0
        var ptr: UnsafeMutablePointer<ifaddrs>? = first
        while let p = ptr {
            let name = String(cString: p.pointee.ifa_name)
            let isLoopback = (Int32(p.pointee.ifa_flags) & IFF_LOOPBACK) != 0
            if !isLoopback,
               (name.hasPrefix("en") || name.hasPrefix("utun") || name.hasPrefix("awdl") || name.hasPrefix("bridge")),
               let data = p.pointee.ifa_data?.assumingMemoryBound(to: if_data.self) {
                rx &+= UInt64(data.pointee.ifi_ibytes)
                tx &+= UInt64(data.pointee.ifi_obytes)
            }
            ptr = p.pointee.ifa_next
        }

        let now = Date()
        if let prev = prevNet {
            let dt = now.timeIntervalSince(prev.t)
            if dt > 0 {
                s.netDownKBps = Double(rx &- prev.rx) / 1024.0 / dt
                s.netUpKBps   = Double(tx &- prev.tx) / 1024.0 / dt
            }
        }
        prevNet = (rx, tx, now)
    }

    // MARK: - Uptime / Thermal / Battery

    private func sampleUptime() -> TimeInterval {
        var bootTime = timeval()
        var size = MemoryLayout<timeval>.size
        var mib: [Int32] = [CTL_KERN, KERN_BOOTTIME]
        if sysctl(&mib, 2, &bootTime, &size, nil, 0) == 0 {
            return Date().timeIntervalSince1970 - Double(bootTime.tv_sec)
        }
        return 0
    }

    private func sampleThermal() -> String {
        switch ProcessInfo.processInfo.thermalState {
        case .nominal:  return "Nominal"
        case .fair:     return "Fair"
        case .serious:  return "Serious"
        case .critical: return "Critical"
        @unknown default: return "Unknown"
        }
    }

    private func sampleBattery(charging: inout Bool) -> Double? {
        // Use pmset for portability; private IOKit calls are private API.
        let p = Process()
        p.launchPath = "/usr/bin/pmset"
        p.arguments = ["-g", "batt"]
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = Pipe()
        do {
            try p.run()
            p.waitUntilExit()
        } catch {
            return nil
        }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard let out = String(data: data, encoding: .utf8) else { return nil }
        guard out.contains("InternalBattery") else { return nil }
        if let range = out.range(of: #"\d+%"#, options: .regularExpression) {
            let pctStr = out[range].dropLast()
            charging = out.contains("charging") || out.contains("AC Power")
            return Double(pctStr)
        }
        return nil
    }

    // MARK: - Top processes

    private func sampleTopProcesses() -> [ProcessRow] {
        let p = Process()
        p.launchPath = "/bin/ps"
        p.arguments = ["-Aceo", "pid,pcpu,rss,comm"]
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = Pipe()
        do {
            try p.run()
            p.waitUntilExit()
        } catch {
            return []
        }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard let out = String(data: data, encoding: .utf8) else { return [] }
        var rows: [ProcessRow] = []
        for line in out.split(separator: "\n").dropFirst() {
            let cols = line.split(separator: " ", omittingEmptySubsequences: true)
            guard cols.count >= 4,
                  let pid = Int32(cols[0]),
                  let cpu = Double(cols[1]),
                  let rss = Double(cols[2]) else { continue }
            let name = cols[3...].joined(separator: " ")
            rows.append(ProcessRow(pid: pid, name: name, cpu: cpu, memMB: rss / 1024.0))
        }
        return Array(rows.sorted { $0.cpu > $1.cpu }.prefix(10))
    }
}
