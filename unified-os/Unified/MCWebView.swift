import SwiftUI
import WebKit

/// Embeds the Mission Control web app (served locally on :8450). Retries a few
/// times while the launchd-managed server finishes booting.
struct MCWebView: NSViewRepresentable {
    let url: URL

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        let web = WKWebView(frame: .zero, configuration: config)
        web.navigationDelegate = context.coordinator
        web.setValue(false, forKey: "drawsBackground")   // let our dark bg show through while loading
        web.load(URLRequest(url: url))
        context.coordinator.web = web
        context.coordinator.url = url
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
                self?.web?.load(URLRequest(url: url))
            }
        }
    }
}
