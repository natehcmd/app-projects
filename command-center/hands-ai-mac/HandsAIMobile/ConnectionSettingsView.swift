import SwiftUI

/// One-time (and reachable-again-later via the gear icon) setup: the Mac's
/// Tailscale IP, port, and token — all three shown together in the Mac's own
/// Settings → Remote tab, meant to be typed in here once.
struct ConnectionSettingsView: View {
    @EnvironmentObject var remote: RemoteAgentClient
    @Environment(\.dismiss) private var dismiss

    @State private var host: String = ""
    @State private var port: String = "8787"
    @State private var token: String = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("Connect to your Mac") {
                    TextField("Tailscale IP, e.g. 100.91.36.127", text: $host)
                        .keyboardType(.numbersAndPunctuation)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    TextField("Port", text: $port)
                        .keyboardType(.numberPad)
                    SecureField("Token (from Mac Settings → Remote)", text: $token)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }
                Section {
                    Text("On the Mac: Settings → Remote → turn on \"Let the Hands AI Remote app connect\", then copy the IP/port/token shown there.")
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                }
                Section {
                    Button("Save & Connect") {
                        remote.host = host.trimmingCharacters(in: .whitespaces)
                        remote.port = Int(port) ?? 8787
                        remote.token = token.trimmingCharacters(in: .whitespaces)
                        remote.connect()
                        dismiss()
                    }
                    .disabled(host.trimmingCharacters(in: .whitespaces).isEmpty || token.isEmpty)
                }
            }
            .navigationTitle("Connection")
            .onAppear {
                host = remote.host
                port = String(remote.port)
                token = remote.token
            }
        }
    }
}
