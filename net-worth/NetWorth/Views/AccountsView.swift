import SwiftUI

struct AccountsView: View {
    @EnvironmentObject var store: Store
    @State private var editing: Account?
    @State private var showSheet = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack(alignment: .top) {
                    ScreenHeader(title: "Accounts", subtitle: "Assets and liabilities that make up your net worth.")
                    Spacer()
                    Button {
                        editing = nil; showSheet = true
                    } label: {
                        Label("Add", systemImage: "plus")
                            .font(.system(size: 13, weight: .semibold))
                            .padding(.horizontal, 14).padding(.vertical, 9)
                            .background(RoundedRectangle(cornerRadius: 11, style: .continuous).fill(Theme.lav))
                            .foregroundStyle(Theme.bg)
                    }
                    .buttonStyle(.plain)
                }

                section("Assets", store.assets, Theme.mint)
                section("Liabilities", store.liabilities, Theme.rose)
            }
            .padding(28)
            .frame(maxWidth: 900, alignment: .leading)
            .frame(maxWidth: .infinity)
        }
        .sheet(isPresented: $showSheet) {
            AccountEditor(existing: editing) { acct in
                if editing == nil { store.addAccount(acct) } else { store.updateAccount(acct) }
            }
        }
    }

    private func section(_ title: String, _ accounts: [Account], _ color: Color) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(title).font(.system(size: 15, weight: .semibold)).foregroundStyle(Theme.ink)
                Spacer()
                Text(accounts.reduce(0) { $0 + $1.balance }.asCurrency)
                    .font(.system(size: 15, weight: .bold)).foregroundStyle(color)
            }
            if accounts.isEmpty {
                Text("Nothing here yet.").font(.system(size: 13)).foregroundStyle(Theme.inkFaint)
            } else {
                VStack(spacing: 8) {
                    ForEach(accounts) { a in row(a, color) }
                }
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .glassCard(radius: 16)
    }

    private func row(_ a: Account, _ color: Color) -> some View {
        HStack(spacing: 14) {
            RoundedRectangle(cornerRadius: 9, style: .continuous)
                .fill(color.opacity(0.16))
                .frame(width: 38, height: 38)
                .overlay(Image(systemName: iconFor(a.type)).font(.system(size: 15, weight: .semibold)).foregroundStyle(color))
            VStack(alignment: .leading, spacing: 2) {
                Text(a.name).font(.system(size: 14, weight: .semibold)).foregroundStyle(Theme.ink)
                Text(a.type).font(.system(size: 12)).foregroundStyle(Theme.inkDim)
            }
            Spacer()
            Text(a.balance.asCurrency).font(.system(size: 15, weight: .semibold)).foregroundStyle(Theme.ink)
            Menu {
                Button("Edit") { editing = a; showSheet = true }
                Button("Delete", role: .destructive) { store.deleteAccount(a) }
            } label: {
                Image(systemName: "ellipsis").font(.system(size: 14, weight: .bold)).foregroundStyle(Theme.inkDim)
                    .frame(width: 28, height: 28)
            }
            .menuStyle(.borderlessButton).frame(width: 28)
        }
        .padding(.vertical, 8).padding(.horizontal, 12)
        .background(RoundedRectangle(cornerRadius: 12, style: .continuous).fill(Color.white.opacity(0.02)))
    }

    private func iconFor(_ type: String) -> String {
        switch type.lowercased() {
        case "bank": return "banknote"
        case "investment", "brokerage": return "chart.pie"
        case "retirement": return "figure.walk"
        case "vehicle": return "car"
        case "card": return "creditcard"
        case "loan": return "doc.text"
        default: return "dollarsign.circle"
        }
    }
}

// MARK: - Editor sheet

struct AccountEditor: View {
    @Environment(\.dismiss) private var dismiss
    let existing: Account?
    let onSave: (Account) -> Void

    @State private var name = ""
    @State private var type = "Bank"
    @State private var kind: AccountKind = .asset
    @State private var balance = ""

    private let types = ["Bank", "Investment", "Retirement", "Vehicle", "Real Estate", "Card", "Loan", "Other"]

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(existing == nil ? "Add Account" : "Edit Account")
                .font(.system(size: 18, weight: .bold)).foregroundStyle(Theme.ink)

            field("Name") { TextField("e.g. Checking", text: $name).textFieldStyle(.roundedBorder) }

            field("Kind") {
                Picker("", selection: $kind) {
                    ForEach(AccountKind.allCases) { Text($0.rawValue).tag($0) }
                }.pickerStyle(.segmented).labelsHidden()
            }

            field("Type") {
                Picker("", selection: $type) {
                    ForEach(types, id: \.self) { Text($0).tag($0) }
                }.labelsHidden()
            }

            field("Balance") {
                TextField("0", text: $balance).textFieldStyle(.roundedBorder)
            }

            HStack {
                Button("Cancel") { dismiss() }.keyboardShortcut(.cancelAction)
                Spacer()
                Button("Save") {
                    let bal = Double(balance.replacingOccurrences(of: ",", with: "")) ?? 0
                    var a = existing ?? Account(name: "", type: type, kind: kind, balance: 0)
                    a.name = name.isEmpty ? "Untitled" : name
                    a.type = type; a.kind = kind; a.balance = bal
                    onSave(a); dismiss()
                }
                .keyboardShortcut(.defaultAction)
                .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding(24)
        .frame(width: 360)
        .background(Theme.bg2)
        .onAppear {
            if let e = existing {
                name = e.name; type = e.type; kind = e.kind; balance = String(e.balance)
            }
        }
    }

    private func field<Content: View>(_ label: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label.uppercased()).font(.system(size: 10, weight: .bold)).tracking(1).foregroundStyle(Theme.inkDim)
            content()
        }
    }
}
