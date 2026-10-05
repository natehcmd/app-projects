import Foundation

/// Finds the first supported reel/video URL in shared text and cleans it up.
public enum LinkExtractor {
    public static let allowedHosts: Set<String> = [
        "instagram.com", "www.instagram.com",
        "tiktok.com", "www.tiktok.com", "vm.tiktok.com",
        "youtube.com", "youtu.be",
    ]

    /// First supported URL found in `text` (a bare URL or prose containing one).
    public static func extract(from text: String) -> URL? {
        var candidates: [String] = []
        if let det = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue) {
            let ns = text as NSString
            for m in det.matches(in: text, range: NSRange(location: 0, length: ns.length)) {
                if let u = m.url { candidates.append(u.absoluteString) }
            }
        }
        candidates.append(contentsOf: text.split(whereSeparator: { $0.isWhitespace }).map(String.init))
        for c in candidates {
            if let u = normalize(c) { return u }
        }
        return nil
    }

    /// Returns a cleaned https URL, or nil if the host isn't supported.
    public static func normalize(_ raw: String) -> URL? {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines.union(CharacterSet(charactersIn: "<>\"'")))
        guard var comps = URLComponents(string: trimmed),
              let scheme = comps.scheme?.lowercased(), scheme == "http" || scheme == "https",
              let host = comps.host?.lowercased(), allowedHosts.contains(host) else { return nil }
        comps.scheme = "https"
        comps.host = host
        comps.fragment = nil
        comps.port = nil
        comps.user = nil
        comps.password = nil
        // Drop tracking params (igsh, utm_*, si, ...). Only YouTube's `v` is meaningful.
        if host == "youtube.com" {
            comps.queryItems = comps.queryItems?.filter { $0.name == "v" }
        } else {
            comps.queryItems = nil
        }
        if comps.queryItems?.isEmpty == true { comps.queryItems = nil }
        guard !comps.path.isEmpty, comps.path != "/" || comps.queryItems != nil else { return nil }
        return comps.url
    }
}
