import UIKit
import SwiftUI
import UniformTypeIdentifiers

@MainActor
final class ShareModel: ObservableObject {
    enum Phase { case saving, sent, queued, unsupported }
    @Published var phase: Phase = .saving
}

struct ShareStatusView: View {
    @ObservedObject var model: ShareModel
    var body: some View {
        VStack(spacing: 14) {
            switch model.phase {
            case .saving:
                ProgressView(); Text("Saving...")
            case .sent:
                Image(systemName: "checkmark.circle.fill").font(.system(size: 44)).foregroundStyle(.green)
                Text("Saved to AgentDrop ✓").font(.headline)
            case .queued:
                Image(systemName: "clock.fill").font(.system(size: 44)).foregroundStyle(.orange)
                Text("Saved — will send when your Mac is reachable").font(.headline).multilineTextAlignment(.center)
            case .unsupported:
                Image(systemName: "xmark.circle.fill").font(.system(size: 44)).foregroundStyle(.red)
                Text("Only Instagram, TikTok and YouTube links for now").font(.headline).multilineTextAlignment(.center)
            }
        }
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(.regularMaterial)
    }
}

final class ShareViewController: UIViewController {
    private let model = ShareModel()

    override func viewDidLoad() {
        super.viewDidLoad()
        let host = UIHostingController(rootView: ShareStatusView(model: model))
        addChild(host)
        host.view.frame = view.bounds
        host.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.addSubview(host.view)
        host.didMove(toParent: self)
        Task { await run() }
    }

    private func run() async {
        let texts = await collectStrings()
        var found: URL?
        for t in texts { if let u = LinkExtractor.extract(from: t) { found = u; break } }
        guard let url = found else {
            model.phase = .unsupported
            await finish(after: 1.8)
            return
        }
        let queue = SaveQueue.shared()
        let item = queue.append(url: url.absoluteString)
        switch await Sender.send(url: url.absoluteString, address: ConnectionStore.address, token: ConnectionStore.token) {
        case .sent:
            queue.update(item.id, status: .sent); model.phase = .sent
        case .unreachable(let m):
            queue.update(item.id, status: .queued, error: m); model.phase = .queued
        case .rejected(let m):
            queue.update(item.id, status: .failed, error: m); model.phase = .queued
        }
        await finish(after: 1.2)
    }

    private func finish(after s: TimeInterval) async {
        try? await Task.sleep(nanoseconds: UInt64(s * 1_000_000_000))
        extensionContext?.completeRequest(returningItems: nil)
    }

    private func collectStrings() async -> [String] {
        var out: [String] = []
        let items = (extensionContext?.inputItems as? [NSExtensionItem]) ?? []
        for item in items {
            if let t = item.attributedContentText?.string, !t.isEmpty { out.append(t) }
            for p in item.attachments ?? [] {
                if p.hasItemConformingToTypeIdentifier(UTType.url.identifier),
                   let v = try? await p.loadItem(forTypeIdentifier: UTType.url.identifier) {
                    if let u = v as? URL { out.append(u.absoluteString) }
                    else if let s = v as? String { out.append(s) }
                }
                if p.hasItemConformingToTypeIdentifier(UTType.plainText.identifier),
                   let v = try? await p.loadItem(forTypeIdentifier: UTType.plainText.identifier) {
                    if let s = v as? String { out.append(s) }
                    else if let u = v as? URL { out.append(u.absoluteString) }
                }
            }
        }
        return out
    }
}
