import XCTest

final class LinkExtractorTests: XCTestCase {
    func testInstagramReelStripsIgsh() {
        let u = LinkExtractor.extract(from: "https://www.instagram.com/reel/DW4Gc3PDibh/?igsh=MXRzbjA5dmx2eg==")
        XCTAssertEqual(u?.absoluteString, "https://www.instagram.com/reel/DW4Gc3PDibh/")
    }
    func testInstagramPostWithUtm() {
        let u = LinkExtractor.extract(from: "https://instagram.com/p/ABC123/?utm_source=ig_web_copy_link&igsh=zzz")
        XCTAssertEqual(u?.absoluteString, "https://instagram.com/p/ABC123/")
    }
    func testURLInsideProse() {
        let u = LinkExtractor.extract(from: "Check this out! https://www.instagram.com/reel/XyZ/?igsh=1 so good")
        XCTAssertEqual(u?.absoluteString, "https://www.instagram.com/reel/XyZ/")
    }
    func testTikTok() {
        XCTAssertEqual(LinkExtractor.extract(from: "https://vm.tiktok.com/ZMabc123/")?.absoluteString, "https://vm.tiktok.com/ZMabc123/")
        XCTAssertEqual(LinkExtractor.extract(from: "https://www.tiktok.com/@u/video/123?_t=8&_r=1")?.absoluteString, "https://www.tiktok.com/@u/video/123")
    }
    func testYouTube() {
        XCTAssertEqual(LinkExtractor.extract(from: "https://youtu.be/dQw4w9WgXcQ?si=track")?.absoluteString, "https://youtu.be/dQw4w9WgXcQ")
        XCTAssertEqual(LinkExtractor.extract(from: "https://youtube.com/watch?v=dQw4w9WgXcQ&si=x&feature=share")?.absoluteString, "https://youtube.com/watch?v=dQw4w9WgXcQ")
    }
    func testRejectsOtherHosts() {
        XCTAssertNil(LinkExtractor.extract(from: "https://example.com/reel/1"))
        XCTAssertNil(LinkExtractor.extract(from: "https://evilinstagram.com/reel/1"))
        XCTAssertNil(LinkExtractor.extract(from: "https://instagram.com.evil.com/reel/1"))
        XCTAssertNil(LinkExtractor.extract(from: "no links here"))
    }
    func testSkipsUnsupportedThenFindsSupported() {
        let u = LinkExtractor.extract(from: "https://example.com/a https://youtu.be/abc")
        XCTAssertEqual(u?.absoluteString, "https://youtu.be/abc")
    }
}

final class SaveQueueTests: XCTestCase {
    private func tmp() -> URL { FileManager.default.temporaryDirectory.appendingPathComponent("q-\(UUID().uuidString).json") }

    func testAppendUpdatePersistRoundTrip() {
        let f = tmp(); defer { try? FileManager.default.removeItem(at: f) }
        let q = SaveQueue(fileURL: f)
        XCTAssertTrue(q.load().isEmpty)
        let a = q.append(url: "https://www.instagram.com/reel/A/")
        let b = q.append(url: "https://youtu.be/B", note: "n")
        q.update(a.id, status: .sent)
        q.update(b.id, status: .failed, error: "boom")

        let q2 = SaveQueue(fileURL: f)   // fresh instance reads from disk
        let items = q2.load()
        XCTAssertEqual(items.count, 2)
        XCTAssertEqual(items.first { $0.id == a.id }?.status, .sent)
        let bb = items.first { $0.id == b.id }
        XCTAssertEqual(bb?.status, .failed); XCTAssertEqual(bb?.lastError, "boom"); XCTAssertEqual(bb?.note, "n")
        XCTAssertEqual(q2.pending().map(\.id), [b.id])
    }

    func testDelete() {
        let f = tmp(); defer { try? FileManager.default.removeItem(at: f) }
        let q = SaveQueue(fileURL: f)
        let a = q.append(url: "https://youtu.be/A"); q.append(url: "https://youtu.be/B")
        q.delete(a.id)
        XCTAssertEqual(q.load().map(\.url), ["https://youtu.be/B"])
    }
}

final class SenderTests: XCTestCase {
    func testBaseURL() {
        XCTAssertEqual(Sender.baseURL("192.168.1.5:8787")?.absoluteString, "http://192.168.1.5:8787")
        XCTAssertEqual(Sender.baseURL(" http://100.1.2.3:8787/ ")?.absoluteString, "http://100.1.2.3:8787")
        XCTAssertNil(Sender.baseURL("  "))
    }
}
