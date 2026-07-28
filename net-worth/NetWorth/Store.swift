import Foundation
import SwiftUI

// MARK: - Models

enum AccountKind: String, Codable, CaseIterable, Identifiable {
    case asset      = "Asset"
    case liability  = "Liability"
    var id: String { rawValue }
}

struct Account: Identifiable, Codable, Hashable {
    var id = UUID()
    var name: String
    var type: String          // e.g. Checking, Investment, Mortgage, Card
    var kind: AccountKind
    var balance: Double
}

struct Snapshot: Identifiable, Codable, Hashable {
    var id = UUID()
    var date: Date
    var netWorth: Double
}

struct Txn: Identifiable, Codable, Hashable {
    var id = UUID()
    var date: Date
    var desc: String
    var amount: Double         // negative = spend, positive = income
    var category: String
}

/// Everything persisted to disk in one JSON file.
struct DB: Codable {
    var accounts: [Account] = []
    var snapshots: [Snapshot] = []
    var txns: [Txn] = []
    var budgets: [String: Double] = [:]   // category -> monthly limit
}

// MARK: - Store

final class Store: ObservableObject {
    @Published var db = DB()

    private let url: URL

    init() {
        let dir = FileManager.default
            .urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("NetWorth", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        url = dir.appendingPathComponent("data.json")

        if let data = try? Data(contentsOf: url),
           let decoded = try? JSONDecoder.iso.decode(DB.self, from: data) {
            db = decoded
        } else {
            db = Self.seed()
            save()
        }
    }

    // MARK: Derived

    var assets: [Account]      { db.accounts.filter { $0.kind == .asset } }
    var liabilities: [Account] { db.accounts.filter { $0.kind == .liability } }
    var totalAssets: Double     { assets.reduce(0) { $0 + $1.balance } }
    var totalLiabilities: Double { liabilities.reduce(0) { $0 + $1.balance } }
    var netWorth: Double        { totalAssets - totalLiabilities }

    /// Spending (positive numbers) by category for the current month.
    func spendingThisMonth() -> [(category: String, amount: Double)] {
        let cal = Calendar.current
        let now = Date()
        var totals: [String: Double] = [:]
        for t in db.txns where t.amount < 0 {
            if cal.isDate(t.date, equalTo: now, toGranularity: .month) {
                totals[t.category, default: 0] += -t.amount
            }
        }
        return totals.map { ($0.key, $0.value) }.sorted { $0.amount > $1.amount }
    }

    var categories: [String] {
        Array(Set(db.txns.map { $0.category }).union(db.budgets.keys)).sorted()
    }

    // MARK: Mutations

    func addAccount(_ a: Account) { db.accounts.append(a); save() }
    func updateAccount(_ a: Account) {
        if let i = db.accounts.firstIndex(where: { $0.id == a.id }) { db.accounts[i] = a; save() }
    }
    func deleteAccount(_ a: Account) { db.accounts.removeAll { $0.id == a.id }; save() }

    func recordSnapshot() {
        let cal = Calendar.current
        let today = cal.startOfDay(for: Date())
        // Replace any existing snapshot from today.
        db.snapshots.removeAll { cal.isDate($0.date, inSameDayAs: today) }
        db.snapshots.append(Snapshot(date: today, netWorth: netWorth))
        db.snapshots.sort { $0.date < $1.date }
        save()
    }

    func setBudget(_ category: String, _ amount: Double) {
        if amount <= 0 { db.budgets.removeValue(forKey: category) }
        else { db.budgets[category] = amount }
        save()
    }

    /// Import a bank CSV. Expected header contains date, description, amount, category (order-flexible).
    /// Returns count imported or throws with a readable message.
    ///
    /// The file read + parse (the part that scales with row count) runs off the main
    /// thread via `Self.parseCSV`, so a large statement export doesn't freeze the UI.
    /// Only the final array append + save (already O(n) but fast) touches `db` on @MainActor.
    @discardableResult
    func importCSV(from fileURL: URL) async throws -> Int {
        let raw = try String(contentsOf: fileURL, encoding: .utf8)
        let imported = try await Task.detached(priority: .userInitiated) {
            try Self.parseCSV(raw)
        }.value
        db.txns.append(contentsOf: imported)
        db.txns.sort { $0.date > $1.date }
        save()
        return imported.count
    }

    /// Pure CSV -> [Txn] parsing, safe to run off the main actor.
    nonisolated static func parseCSV(_ raw: String) throws -> [Txn] {
        var lines = raw.split(whereSeparator: \.isNewline).map(String.init)
        guard !lines.isEmpty else { return [] }

        let header = parseCSVLine(lines.removeFirst()).map { $0.lowercased().trimmingCharacters(in: .whitespaces) }
        func col(_ names: [String]) -> Int? {
            for n in names { if let i = header.firstIndex(of: n) { return i } }
            return nil
        }
        let iDate = col(["date", "transaction date", "posted date"])
        let iDesc = col(["description", "desc", "name", "memo", "payee"])
        let iAmt  = col(["amount", "amt", "value"])
        let iCat  = col(["category", "cat"])
        guard let iDate, let iAmt else {
            throw ImportError.badHeader
        }

        var imported: [Txn] = []
        for line in lines {
            let f = parseCSVLine(line)
            guard f.count > iDate, f.count > iAmt else { continue }
            guard let date = Date.parseFlexible(f[iDate]) else { continue }
            let amtStr = f[iAmt].replacingOccurrences(of: "$", with: "")
                .replacingOccurrences(of: ",", with: "")
                .trimmingCharacters(in: .whitespaces)
            guard let amt = Double(amtStr) else { continue }
            let desc = (iDesc != nil && f.count > iDesc!) ? f[iDesc!] : ""
            let cat  = (iCat != nil && f.count > iCat!) ? f[iCat!].trimmingCharacters(in: .whitespaces) : ""
            imported.append(Txn(date: date, desc: desc, amount: amt,
                                category: cat.isEmpty ? "Uncategorized" : cat))
        }
        return imported
    }

    enum ImportError: LocalizedError {
        case badHeader
        var errorDescription: String? {
            "CSV needs at least a 'Date' and 'Amount' column (Description and Category are optional)."
        }
    }

    // MARK: Persistence

    func save() {
        if let data = try? JSONEncoder.iso.encode(db) {
            try? data.write(to: url, options: .atomic)
        }
    }

    // MARK: Seed

    static func seed() -> DB {
        let cal = Calendar.current
        let today = cal.startOfDay(for: Date())
        func daysAgo(_ n: Int) -> Date { cal.date(byAdding: .day, value: -n, to: today)! }

        var db = DB()
        db.accounts = [
            Account(name: "Checking",     type: "Bank",       kind: .asset,     balance: 8_400),
            Account(name: "Savings",      type: "Bank",       kind: .asset,     balance: 22_500),
            Account(name: "Brokerage",    type: "Investment", kind: .asset,     balance: 61_200),
            Account(name: "401(k)",       type: "Retirement", kind: .asset,     balance: 74_000),
            Account(name: "Car",          type: "Vehicle",    kind: .asset,     balance: 18_000),
            Account(name: "Credit Card",  type: "Card",       kind: .liability, balance: 2_150),
            Account(name: "Auto Loan",    type: "Loan",       kind: .liability, balance: 11_300),
            Account(name: "Student Loan", type: "Loan",       kind: .liability, balance: 14_600),
        ]

        // A rising net-worth trend over the last ~5 months.
        let base = db.accounts.filter { $0.kind == .asset }.reduce(0) { $0 + $1.balance }
                 - db.accounts.filter { $0.kind == .liability }.reduce(0) { $0 + $1.balance }
        let steps: [(Int, Double)] = [(150, 0.90), (120, 0.93), (90, 0.95), (60, 0.97), (30, 0.99), (0, 1.0)]
        db.snapshots = steps.map { Snapshot(date: daysAgo($0.0), netWorth: (base * $0.1).rounded()) }

        db.budgets = [
            "Groceries": 600, "Dining": 300, "Transport": 200,
            "Shopping": 250, "Utilities": 350, "Entertainment": 150,
        ]

        // Sample transactions this month.
        let samples: [(Int, String, Double, String)] = [
            (1, "Whole Foods",        -86.40,  "Groceries"),
            (2, "Shell Gas",          -52.10,  "Transport"),
            (3, "Netflix",            -15.49,  "Entertainment"),
            (4, "Chipotle",           -12.75,  "Dining"),
            (5, "Paycheck",          3200.00,  "Income"),
            (6, "Trader Joe's",       -64.20,  "Groceries"),
            (7, "Electric Bill",     -128.00,  "Utilities"),
            (8, "Amazon",             -47.99,  "Shopping"),
            (9, "Uber",               -21.30,  "Transport"),
            (10, "Thai Kitchen",      -38.50,  "Dining"),
            (12, "Water Bill",        -44.00,  "Utilities"),
            (14, "Costco",           -152.80,  "Groceries"),
            (16, "Movie Tickets",     -32.00,  "Entertainment"),
            (18, "Target",            -74.15,  "Shopping"),
        ]
        db.txns = samples.map { Txn(date: daysAgo($0.0), desc: $0.1, amount: $0.2, category: $0.3) }
        return db
    }
}

// MARK: - CSV / Date helpers

/// Minimal CSV field splitter that honors double-quoted fields.
func parseCSVLine(_ line: String) -> [String] {
    var fields: [String] = []
    var cur = ""
    var inQuotes = false
    var i = line.startIndex
    while i < line.endIndex {
        let c = line[i]
        if c == "\"" {
            if inQuotes, line.index(after: i) < line.endIndex, line[line.index(after: i)] == "\"" {
                cur.append("\""); i = line.index(after: i)
            } else { inQuotes.toggle() }
        } else if c == "," && !inQuotes {
            fields.append(cur); cur = ""
        } else {
            cur.append(c)
        }
        i = line.index(after: i)
    }
    fields.append(cur)
    return fields.map { $0.trimmingCharacters(in: .whitespaces) }
}

extension Date {
    static func parseFlexible(_ s: String) -> Date? {
        let str = s.trimmingCharacters(in: .whitespaces)
        let formats = ["yyyy-MM-dd", "MM/dd/yyyy", "M/d/yyyy", "MM/dd/yy", "yyyy/MM/dd", "dd-MM-yyyy"]
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        for fmt in formats {
            f.dateFormat = fmt
            if let d = f.date(from: str) { return d }
        }
        return ISO8601DateFormatter().date(from: str)
    }
}

extension JSONEncoder {
    static var iso: JSONEncoder {
        let e = JSONEncoder(); e.dateEncodingStrategy = .iso8601; e.outputFormatting = .prettyPrinted; return e
    }
}
extension JSONDecoder {
    static var iso: JSONDecoder {
        let d = JSONDecoder(); d.dateDecodingStrategy = .iso8601; return d
    }
}
