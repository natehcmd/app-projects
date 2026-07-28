import SwiftUI
import AppKit

/// NSTextView-backed conversation view. Lets the user drag-select across every
/// message in the transcript and copy with ⌘C, which SwiftUI's per-Text
/// `.textSelection(.enabled)` can't do.
struct SelectableConversation: NSViewRepresentable {
    let messages: [Message]

    func makeNSView(context: Context) -> NSScrollView {
        let scrollView = NSTextView.scrollableTextView()
        scrollView.borderType = .noBorder
        scrollView.drawsBackground = false
        scrollView.hasVerticalScroller = true
        scrollView.autohidesScrollers = true
        scrollView.scrollerStyle = .overlay

        guard let textView = scrollView.documentView as? NSTextView else {
            return scrollView
        }
        textView.isEditable = false
        textView.isSelectable = true
        textView.drawsBackground = false
        textView.textContainerInset = NSSize(width: 14, height: 12)
        textView.textColor = .labelColor
        textView.font = NSFont.systemFont(ofSize: 13, weight: .regular)
        textView.usesFontPanel = false
        textView.allowsUndo = false
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false
        textView.autoresizingMask = [.width]
        textView.textContainer?.widthTracksTextView = true

        update(textView: textView)
        return scrollView
    }

    func updateNSView(_ scrollView: NSScrollView, context: Context) {
        guard let textView = scrollView.documentView as? NSTextView else { return }
        update(textView: textView)
        // Scroll to bottom on update.
        DispatchQueue.main.async {
            textView.scrollToEndOfDocument(nil)
        }
    }

    private func update(textView: NSTextView) {
        let attributed = NSMutableAttributedString()
        for (i, m) in messages.enumerated() {
            let prefix = m.role == .user ? "You" : "Hands"
            let header = NSAttributedString(
                string: "\(prefix)\n",
                attributes: [
                    .font: NSFont.systemFont(ofSize: 10, weight: .semibold),
                    .foregroundColor: m.role == .user
                        ? NSColor(calibratedRed: 0.55, green: 0.72, blue: 0.95, alpha: 1)
                        : NSColor.secondaryLabelColor,
                ]
            )
            let body = NSAttributedString(
                string: m.text,
                attributes: [
                    .font: NSFont.systemFont(ofSize: 13, weight: .regular),
                    .foregroundColor: NSColor.labelColor,
                ]
            )
            attributed.append(header)
            attributed.append(body)
            if i < messages.count - 1 {
                attributed.append(NSAttributedString(string: "\n\n"))
            }
        }
        textView.textStorage?.setAttributedString(attributed)
    }
}
