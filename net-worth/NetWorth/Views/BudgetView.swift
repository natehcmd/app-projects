import SwiftUI
import Charts
import UniformTypeIdentifiers

struct BudgetView: View {
    @EnvironmentObject var store: Store
    @State private var importMessage: String?
    @State private var importOK = true

    private var spending: [(category: String, amount: Double)] { store.spendingThisMonth() }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack(alignment: .top) {
                    ScreenHeader(title: "Budget", subtitle: "Spending by category vs. your monthly limits.")
                    Spacer()
                    Button(action: importCSV) {
                        Label("Import CSV", systemImage: "square.and.arrow.down")
                            .font(.system(size: 13, weight: .semibold))
                            .padding(.horizontal, 14).padding(.vertical, 9)
                            .background(RoundedRectangle(cornerRadius: 11, style: .continuous).fill(Theme.peach))
                            .foregroundStyle(Theme.bg)
                    }
                    .buttonStyle(.plain)
                }

                if let m = importMessage {
                    Text(m).font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(importOK ? Theme.mint : Theme.rose)
                        .padding(.horizontal, 14).padding(.vertical, 9)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(RoundedRectangle(cornerRadius: 10).fill(Color.white.opacity(0.03)))
                }

                if spending.isEmpty {
                    emptyState
                } else {
                    donutCard
                    budgetVsActualCard
                }
            }
            .padding(28)
            .frame(maxWidth: 900, alignment: .leading)
            .frame(maxWidth: .infinity)
        }
    }

    private var emptyState: some View {
        VStack(spacing: 10) {
            Image(systemName: "tray").font(.system(size: 30)).foregroundStyle(Theme.inkFaint)
            Text("No spending this month yet.").font(.system(size: 14, weight: .semibold)).foregroundStyle(Theme.inkDim)
            Text("Import a bank CSV (date, description, amount, category) to get started.")
                .font(.system(size: 12)).foregroundStyle(Theme.inkFaint)
        }
        .frame(maxWidth: .infinity, minHeight: 220)
        .glassCard(radius: 18)
    }

    private var totalSpent: Double { spending.reduce(0) { $0 + $1.amount } }

    private var donutCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("This Month's Spending").font(.system(size: 15, weight: .semibold)).foregroundStyle(Theme.ink)
            HStack(alignment: .center, spacing: 24) {
                Chart(spending, id: \.category) { item in
                    SectorMark(angle: .value("Amount", item.amount), innerRadius: .ratio(0.62), angularInset: 2)
                        .cornerRadius(4)
                        .foregroundStyle(Theme.color(for: item.category))
                }
                .frame(width: 180, height: 180)
                .overlay(
                    VStack(spacing: 2) {
                        Text("Spent").font(.system(size: 11)).foregroundStyle(Theme.inkDim)
                        Text(totalSpent.asCurrency).font(.system(size: 20, weight: .bold)).foregroundStyle(Theme.ink)
                    }
                )

                VStack(alignment: .leading, spacing: 9) {
                    ForEach(spending, id: \.category) { item in
                        HStack(spacing: 9) {
                            Circle().fill(Theme.color(for: item.category)).frame(width: 9, height: 9)
                            Text(item.category).font(.system(size: 13)).foregroundStyle(Theme.ink)
                            Spacer(minLength: 20)
                            Text(item.amount.asCurrency).font(.system(size: 13, weight: .semibold)).foregroundStyle(Theme.inkDim)
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(22)
        .frame(maxWidth: .infinity, alignment: .leading)
        .glassCard(radius: 18)
    }

    private var budgetVsActualCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Budget vs. Actual").font(.system(size: 15, weight: .semibold)).foregroundStyle(Theme.ink)
            let cats = Array(Set(spending.map { $0.category }).union(store.db.budgets.keys)).sorted()
            ForEach(cats, id: \.self) { cat in
                BudgetRow(category: cat,
                          spent: spending.first(where: { $0.category == cat })?.amount ?? 0,
                          budget: store.db.budgets[cat] ?? 0)
            }
        }
        .padding(22)
        .frame(maxWidth: .infinity, alignment: .leading)
        .glassCard(radius: 18)
    }

    private func importCSV() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.commaSeparatedText, .plainText]
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        Task {
            do {
                let n = try await store.importCSV(from: url)
                importOK = true
                importMessage = "Imported \(n) transaction\(n == 1 ? "" : "s")."
            } catch {
                importOK = false
                importMessage = error.localizedDescription
            }
        }
    }
}

// MARK: - Budget row with editable limit

struct BudgetRow: View {
    @EnvironmentObject var store: Store
    let category: String
    let spent: Double
    let budget: Double
    @State private var editing = false
    @State private var draft = ""

    private var color: Color { Theme.color(for: category) }
    private var pct: Double { budget > 0 ? min(spent / budget, 1.3) : 0 }
    private var over: Bool { budget > 0 && spent > budget }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(category).font(.system(size: 13, weight: .semibold)).foregroundStyle(Theme.ink)
                Spacer()
                if editing {
                    TextField("Limit", text: $draft)
                        .frame(width: 70).textFieldStyle(.roundedBorder)
                        .onSubmit(commit)
                    Button("Set", action: commit).font(.system(size: 12))
                } else {
                    Text(budget > 0 ? "\(spent.asCurrency) / \(budget.asCurrency)" : "\(spent.asCurrency) · no budget")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(over ? Theme.rose : Theme.inkDim)
                    Button {
                        draft = budget > 0 ? String(Int(budget)) : ""
                        editing = true
                    } label: {
                        Image(systemName: "pencil").font(.system(size: 11)).foregroundStyle(Theme.inkDim)
                    }.buttonStyle(.plain)
                }
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color.white.opacity(0.06)).frame(height: 8)
                    Capsule()
                        .fill(over ? Theme.rose : color)
                        .frame(width: max(6, geo.size.width * (budget > 0 ? pct : (spent > 0 ? 0.04 : 0))), height: 8)
                }
            }
            .frame(height: 8)
        }
        .padding(.vertical, 4)
    }

    private func commit() {
        let v = Double(draft.replacingOccurrences(of: ",", with: "")) ?? 0
        store.setBudget(category, v)
        editing = false
    }
}
