import SwiftUI

@main
struct FileGraphApp: App {
    @StateObject private var store = GraphStore()

    var body: some Scene {
        WindowGroup("File Graph") {
            ContentView(store: store)
                .task { await store.start() }
                .frame(minWidth: 980, minHeight: 640)
        }
        .windowStyle(.automatic)
    }
}

struct ContentView: View {
    @ObservedObject var store: GraphStore
    @State private var query = ""
    @State private var semantic = true
    @State private var showResults = false

    var body: some View {
        HSplitView {
            ZStack(alignment: .topLeading) {
                switch store.mode {
                case .twoD:    Graph2DView(store: store)
                case .threeD:  Graph3DView(store: store)
                case .mindMap: MindMapView(store: store)
                }
                if showResults && !store.searchResults.isEmpty {
                    resultsOverlay
                }
            }
            .frame(minWidth: 600)
            InspectorView(store: store)
        }
        .background(Palette.background)
        .toolbar {
            ToolbarItemGroup {
                Picker("Mode", selection: $store.mode) {
                    ForEach(GraphMode.allCases, id: \.self) { Text($0.rawValue) }
                }
                .pickerStyle(.segmented)

                Button("Expand All") { store.expandAll() }
                Button("Minimize All") { store.minimizeAll() }

                Picker("Search mode", selection: $semantic) {
                    Text("Meaning").tag(true)
                    Text("Name").tag(false)
                }
                .pickerStyle(.menu)

                TextField("Search your files…", text: $query)
                    .textFieldStyle(.roundedBorder)
                    .frame(width: 220)
                    .onSubmit {
                        Task {
                            await store.search(query, semantic: semantic)
                            showResults = true
                        }
                    }

                Button { store.rescan() } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .help("Rescan home directory")

                Text(store.statusText)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var resultsOverlay: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text("\(store.searchResults.count) results")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(.secondary)
                Spacer()
                Button {
                    showResults = false
                } label: { Image(systemName: "xmark").font(.system(size: 9)) }
                    .buttonStyle(.plain)
            }
            .padding(.bottom, 4)
            ScrollView {
                VStack(alignment: .leading, spacing: 1) {
                    ForEach(store.searchResults.prefix(20)) { item in
                        Button {
                            Task { await store.reveal(item.path) }
                        } label: {
                            HStack(spacing: 6) {
                                Circle().fill(Palette.color(for: item.kind))
                                    .frame(width: 7, height: 7)
                                Text(item.name).font(.system(size: 12)).lineLimit(1)
                                if item.allowed == false {
                                    Image(systemName: "lock.fill")
                                        .font(.system(size: 8))
                                        .foregroundStyle(Palette.blocked)
                                }
                                Spacer()
                                if let score = item.score {
                                    Text("\(Int(score * 100))%")
                                        .font(.system(size: 10))
                                        .foregroundStyle(.secondary)
                                }
                            }
                            .padding(.vertical, 3).padding(.horizontal, 6)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .frame(maxHeight: 320)
        }
        .padding(10)
        .frame(width: 320)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
        .padding(12)
    }
}
