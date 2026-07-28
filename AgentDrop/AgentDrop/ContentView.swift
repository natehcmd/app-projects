import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @StateObject private var runner = AgentRunner()
    @State private var instruction = ""
    @State private var files: [URL] = []
    @State private var isDropTargeted = false

    var body: some View {
        VStack(spacing: 12) {
            dropZone
            instructionBar
            outputView
            statusBar
        }
        .padding(16)
        .onPasteCommand(of: [.fileURL, .url, .plainText]) { providers in
            addFiles(from: providers)
        }
    }

    private var dropZone: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 14)
                .strokeBorder(style: StrokeStyle(lineWidth: 2, dash: [8]))
                .foregroundStyle(isDropTargeted ? Color.accentColor : Color.secondary.opacity(0.5))
                .background(
                    RoundedRectangle(cornerRadius: 14)
                        .fill(isDropTargeted ? Color.accentColor.opacity(0.12) : Color.secondary.opacity(0.05))
                )

            if files.isEmpty {
                VStack(spacing: 6) {
                    Image(systemName: "film.stack")
                        .font(.system(size: 34))
                        .foregroundStyle(.secondary)
                    Text("Drop or paste a video or link here")
                        .font(.headline)
                    Text("(files or web links — YouTube, articles, anything)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .padding()
            } else {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(files, id: \.self) { url in
                        HStack {
                            Image(systemName: url.isFileURL ? "doc.fill" : "link")
                                .foregroundStyle(.tint)
                            Text(url.isFileURL ? url.lastPathComponent : url.absoluteString)
                                .lineLimit(1)
                                .truncationMode(.middle)
                            Spacer()
                            Button {
                                files.removeAll { $0 == url }
                            } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .foregroundStyle(.secondary)
                            }
                            .buttonStyle(.plain)
                        }
                        .padding(.horizontal, 12)
                    }
                }
                .padding(.vertical, 10)
            }
        }
        .frame(height: max(90, CGFloat(files.count) * 28 + 40))
        .onDrop(of: [.fileURL, .url, .plainText], isTargeted: $isDropTargeted) { providers in
            addFiles(from: providers)
            return true
        }
        .animation(.easeInOut(duration: 0.15), value: isDropTargeted)
    }

    private var instructionBar: some View {
        HStack(spacing: 8) {
            TextField("What do you want done? e.g. \"what happens in this video?\", \"convert to GIF\", \"research this for me\"",
                      text: $instruction, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .lineLimit(1...4)
                .onSubmit(runIt)
                .disabled(runner.isRunning)

            if runner.isRunning {
                Button(role: .destructive, action: runner.stop) {
                    Label("Stop", systemImage: "stop.fill")
                }
            } else {
                Button(action: runIt) {
                    Label("Do it", systemImage: "sparkles")
                }
                .keyboardShortcut(.return, modifiers: .command)
                .buttonStyle(.borderedProminent)
                .disabled(instruction.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
    }

    private var outputView: some View {
        ScrollViewReader { proxy in
            ScrollView {
                Text(runner.output.isEmpty ? "Agent output will appear here…" : runner.output)
                    .font(.system(.body, design: .monospaced))
                    .foregroundStyle(runner.output.isEmpty ? .secondary : .primary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
                    .padding(10)
                    .id("bottom")
            }
            .background(Color(nsColor: .textBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Color.secondary.opacity(0.25)))
            .onChange(of: runner.output) {
                proxy.scrollTo("bottom", anchor: .bottom)
            }
        }
    }

    private var statusBar: some View {
        HStack {
            if runner.isRunning {
                ProgressView().controlSize(.small)
            }
            Text(runner.statusMessage)
                .font(.callout)
                .foregroundStyle(.secondary)
            Spacer()
            Button("Open Workspace") {
                NSWorkspace.shared.open(runner.workspace)
            }
            .controlSize(.small)
        }
    }

    private func runIt() {
        let text = instruction.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !runner.isRunning else { return }
        runner.run(instruction: text, files: files)
    }

    private func addFiles(from providers: [NSItemProvider]) {
        for provider in providers {
            if provider.canLoadObject(ofClass: URL.self) {
                _ = provider.loadObject(ofClass: URL.self) { url, _ in
                    guard let url else { return }
                    DispatchQueue.main.async { addURL(url) }
                }
            } else if provider.canLoadObject(ofClass: NSString.self) {
                _ = provider.loadObject(ofClass: NSString.self) { string, _ in
                    guard let text = string as? String else { return }
                    DispatchQueue.main.async { addLinks(fromText: text) }
                }
            }
        }
    }

    private func addURL(_ url: URL) {
        if !files.contains(url) { files.append(url) }
    }

    /// Pulls http(s) links out of pasted/dropped plain text.
    private func addLinks(fromText text: String) {
        let detector = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue)
        let range = NSRange(text.startIndex..., in: text)
        let matches = detector?.matches(in: text, options: [], range: range) ?? []
        for match in matches {
            if let url = match.url, url.scheme == "http" || url.scheme == "https" {
                addURL(url)
            }
        }
    }
}
