import SwiftUI

@main
struct MyAppsApp: App {
    var body: some Scene {
        WindowGroup("My Apps") {
            ContentView()
                .frame(minWidth: 920, minHeight: 600)
        }
    }
}

struct ContentView: View {
    @State private var apps: [MadeApp] = []
    @State private var query = ""
    @State private var category: Category?
    @State private var selected: MadeApp?

    private var filtered: [MadeApp] {
        apps.filter { app in
            (category == nil || app.category == category)
            && (query.isEmpty
                || app.name.localizedCaseInsensitiveContains(query)
                || app.summary.localizedCaseInsensitiveContains(query))
        }
    }

    private var featured: [MadeApp] {
        Array(apps.sorted { $0.modified > $1.modified }.prefix(4))
    }

    var body: some View {
        NavigationSplitView {
            sidebar
        } detail: {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    if category == nil && query.isEmpty {
                        featuredRow
                    }
                    sectionedGrid
                }
                .padding(.bottom, 24)
            }
            .background(OrbBackground())
            .searchable(text: $query, placement: .toolbar, prompt: "Search your apps")
            .navigationTitle(category?.rawValue ?? "Discover")
            .toolbar {
                ToolbarItem {
                    Button { rescan() } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .help("Rescan")
                }
            }
        }
        .sheet(item: $selected) { app in
            AppDetailSheet(app: app) { selected = nil }
        }
        .onAppear { rescan() }
    }

    /// Scanning walks the home directory + Projects tree synchronously (directory
    /// listings, README reads, icon lookups) — real I/O that would otherwise hitch
    /// the UI if run directly on .onAppear/button-tap on the main thread.
    private func rescan() {
        DispatchQueue.global(qos: .userInitiated).async {
            let result = AppScanner.scan()
            DispatchQueue.main.async { apps = result }
        }
    }

    private var sidebar: some View {
        List(selection: $category) {
            Section("Store") {
                Label("Discover", systemImage: "sparkles")
                    .tag(Category?.none)
                    .foregroundStyle(category == nil ? Theme.ink : Theme.inkDim)
            }
            Section("Categories") {
                ForEach(Category.allCases, id: \.self) { cat in
                    let count = apps.filter { $0.category == cat }.count
                    Label {
                        HStack {
                            Text(cat.rawValue)
                            Spacer()
                            Text("\(count)")
                                .font(.caption2)
                                .foregroundStyle(Theme.inkFaint)
                        }
                    } icon: {
                        Image(systemName: cat.sidebarIcon)
                    }
                    .tag(Category?.some(cat))
                }
            }
        }
        .navigationSplitViewColumnWidth(min: 180, ideal: 200)
    }

    private var featuredRow: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Recently Updated")
                .font(.system(size: 15, weight: .bold))
                .foregroundStyle(Theme.ink)
                .padding(.horizontal, 20)
                .padding(.top, 18)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 14) {
                    ForEach(featured) { app in
                        FeaturedCard(app: app) { selected = app }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 4)
            }
        }
        .padding(.bottom, 8)
    }

    private var sectionedGrid: some View {
        Group {
            if category == nil {
                ForEach(Category.allCases, id: \.self) { cat in
                    let items = filtered.filter { $0.category == cat }
                    if !items.isEmpty {
                        sectionHeader(cat.rawValue, count: items.count)
                        grid(items)
                    }
                }
            } else {
                grid(filtered).padding(.top, 8)
            }
        }
    }

    private func sectionHeader(_ title: String, count: Int) -> some View {
        HStack {
            Text(title)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(Theme.inkDim)
            Text("\(count)")
                .font(.system(size: 10, weight: .medium))
                .padding(.horizontal, 6).padding(.vertical, 1)
                .background(Theme.glass, in: Capsule())
                .foregroundStyle(Theme.inkDim)
            Spacer()
        }
        .padding(.horizontal, 20)
        .padding(.top, 16)
        .padding(.bottom, 6)
    }

    private func grid(_ items: [MadeApp]) -> some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 300), spacing: 14)],
                  spacing: 14) {
            ForEach(items) { app in
                AppCard(app: app) { selected = app }
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 6)
    }
}

// MARK: - Featured (hero) card

struct FeaturedCard: View {
    let app: MadeApp
    let onTap: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            AppIconView(app: app, size: 56)
            VStack(alignment: .leading, spacing: 3) {
                Text(app.name)
                    .font(.system(size: 15, weight: .bold))
                    .foregroundStyle(Theme.ink)
                    .lineLimit(1)
                Text(app.summary)
                    .font(.system(size: 11.5))
                    .foregroundStyle(Theme.inkDim)
                    .lineLimit(3, reservesSpace: true)
            }
            Spacer(minLength: 0)
            HStack {
                CategoryPill(category: app.category, kind: app.kind, appName: app.name)
                Spacer()
                Text(app.modified, format: .relative(presentation: .named))
                    .font(.system(size: 9.5))
                    .foregroundStyle(Theme.inkFaint)
            }
        }
        .padding(14)
        .frame(width: 220, height: 168, alignment: .topLeading)
        .glassCard(radius: 16)
        .contentShape(Rectangle())
        .onTapGesture(perform: onTap)
    }
}

// MARK: - Grid card (App Store style)

struct AppCard: View {
    let app: MadeApp
    let onTap: () -> Void
    @State private var hovering = false

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            AppIconView(app: app, size: 48)

            VStack(alignment: .leading, spacing: 4) {
                Text(app.name)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(Theme.ink)
                    .lineLimit(1)
                Text(app.summary)
                    .font(.system(size: 11.5))
                    .foregroundStyle(Theme.inkDim)
                    .lineLimit(2, reservesSpace: true)
                HStack(spacing: 6) {
                    CategoryPill(category: app.category, kind: app.kind, appName: app.name)
                    Spacer()
                    Button(app.category.openVerb) { AppScanner.open(app) }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.small)
                        .tint(app.kind.color.opacity(0.35))
                }
                .padding(.top, 2)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .glassCard(radius: 14)
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .fill(Color.white.opacity(hovering ? 0.03 : 0))
                .allowsHitTesting(false)
        )
        .contentShape(Rectangle())
        .onTapGesture(perform: onTap)
        .onHover { h in withAnimation(.easeOut(duration: 0.12)) { hovering = h } }
    }
}

// MARK: - Detail sheet (App Store product page)

struct AppDetailSheet: View {
    let app: MadeApp
    let dismiss: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Spacer()
                Button("Done", action: dismiss)
                    .keyboardShortcut(.escape, modifiers: [])
            }
            .padding([.top, .horizontal], 14)

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    HStack(alignment: .top, spacing: 16) {
                        AppIconView(app: app, size: 88)
                        VStack(alignment: .leading, spacing: 6) {
                            Text(app.name)
                                .font(.system(size: 22, weight: .bold))
                                .foregroundStyle(Theme.ink)
                            CategoryPill(category: app.category, kind: app.kind, appName: app.name)
                            Button(app.category.openVerb) { AppScanner.open(app) }
                                .buttonStyle(.borderedProminent)
                                .tint(app.kind.color.opacity(0.4))
                                .padding(.top, 4)
                        }
                        Spacer()
                    }

                    VStack(alignment: .leading, spacing: 6) {
                        Text("About")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(Theme.inkDim)
                        Text(app.summary)
                            .font(.system(size: 13))
                            .foregroundStyle(Theme.ink)
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    VStack(alignment: .leading, spacing: 6) {
                        Text("Details")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(Theme.inkDim)
                        detailRow("Type", app.kind.rawValue)
                        detailRow("Location", app.path.replacingOccurrences(of: NSHomeDirectory(), with: "~"))
                        detailRow("Last updated", app.modified.formatted(date: .abbreviated, time: .shortened))
                        if let bundle = app.appBundle {
                            detailRow("App bundle", bundle.replacingOccurrences(of: NSHomeDirectory(), with: "~"))
                        }
                    }

                    HStack(spacing: 8) {
                        Button {
                            NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: app.path)])
                        } label: { Label("Show in Finder", systemImage: "folder") }
                        .buttonStyle(.bordered)

                        if app.category != .app && app.category != .inspo {
                            Button {
                                AppScanner.openWith("Visual Studio Code", app.path)
                            } label: { Label("Open in VS Code", systemImage: "chevron.left.forwardslash.chevron.right") }
                            .buttonStyle(.bordered)

                            Button {
                                AppScanner.openWith("Terminal", app.path)
                            } label: { Label("Open in Terminal", systemImage: "terminal") }
                            .buttonStyle(.bordered)
                        }
                    }
                    .controlSize(.small)
                }
                .padding(20)
            }
        }
        .frame(width: 480, height: 460)
        .background(Theme.bg)
    }

    private func detailRow(_ label: String, _ value: String) -> some View {
        HStack(alignment: .top) {
            Text(label)
                .font(.system(size: 11.5))
                .foregroundStyle(Theme.inkFaint)
                .frame(width: 100, alignment: .leading)
            Text(value)
                .font(.system(size: 11.5, design: .monospaced))
                .foregroundStyle(Theme.inkDim)
                .textSelection(.enabled)
        }
    }
}

// MARK: - Shared pieces

struct AppIconView: View {
    let app: MadeApp
    let size: CGFloat

    var body: some View {
        Group {
            if let icon = app.realIcon {
                Image(nsImage: icon)
                    .resizable()
                    .interpolation(.high)
                    .aspectRatio(contentMode: .fit)
            } else {
                ZStack {
                    RoundedRectangle(cornerRadius: size * 0.24, style: .continuous)
                        .fill(Theme.gradient(for: app.name))
                    Image(systemName: Theme.icon(for: app))
                        .font(.system(size: size * 0.42, weight: .semibold))
                        .foregroundStyle(Theme.color(for: app.name))
                }
            }
        }
        .frame(width: size, height: size)
        .clipShape(RoundedRectangle(cornerRadius: size * 0.24, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: size * 0.24, style: .continuous)
                .strokeBorder(Theme.color(for: app.name).opacity(0.3), lineWidth: 1)
        )
    }
}

struct CategoryPill: View {
    let category: Category
    let kind: AppKind
    var appName: String = ""

    var body: some View {
        let appColor = appName.isEmpty ? kind.color : Theme.color(for: appName)
        Text(kind.rawValue)
            .font(.system(size: 9.5, weight: .medium))
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(appColor.opacity(0.18), in: Capsule())
            .foregroundStyle(appColor)
    }
}
