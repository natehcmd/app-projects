import SwiftUI
import WebKit

extension Notification.Name {
    static let commandCenterReload = Notification.Name("commandCenterReload")
}

/// Embeds the mission-control web dashboard (served locally on :8450) in a
/// real app window — no address bar, no browser chrome. Retries a few times
/// while the server finishes booting (CommandCenterLauncher just started it).
/// There's no browser chrome for a manual reload button, so Cmd+R (wired in
/// CommandCenterApp's Commands) posts .commandCenterReload instead — without
/// this, static file changes (new tabs, JS fixes) need a full quit/relaunch
/// to show up, since the page itself is never re-fetched otherwise.
struct CommandCenterWebView: NSViewRepresentable {
    let url: URL

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeNSView(context: Context) -> WKWebView {
        let web = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        web.navigationDelegate = context.coordinator
        web.setValue(false, forKey: "drawsBackground") // let our dark bg show through while loading
        // This dashboard is under active local development — WKWebView's
        // persistent disk cache otherwise keeps serving yesterday's os.js
        // even across a full quit/relaunch, since 127.0.0.1 responses cache
        // like any other HTTP response. Always fetch fresh from the server.
        var request = URLRequest(url: url)
        request.cachePolicy = .reloadIgnoringLocalAndRemoteCacheData
        web.load(request)
        context.coordinator.web = web
        context.coordinator.url = url
        NotificationCenter.default.addObserver(forName: .commandCenterReload, object: nil, queue: .main) { [weak web] _ in
            web?.reloadFromOrigin()
        }
        return web
    }

    func updateNSView(_ web: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate {
        weak var web: WKWebView?
        var url: URL?
        private var retries = 0

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            retry()
        }
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            retry()
        }

        private func retry() {
            guard retries < 10, let url else { return }
            retries += 1
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [weak self] in
                var request = URLRequest(url: url)
                request.cachePolicy = .reloadIgnoringLocalAndRemoteCacheData
                self?.web?.load(request)
            }
        }
    }
}
