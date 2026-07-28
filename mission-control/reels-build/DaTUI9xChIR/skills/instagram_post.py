"""
instagram_post.py
------------------

Publishes a video to an Instagram Business/Creator account using Meta's
official **Instagram Graph API**. This is the same API Meta documents for
third-party scheduling tools (Buffer, Later, etc.) — it requires:

  * A Facebook App with the "Instagram Graph API" product added.
  * An Instagram Business or Creator account linked to a Facebook Page.
  * A long-lived Page/User access token with the `instagram_content_publish`
    permission, granted by the account owner through Meta's normal OAuth
    consent screen.
  * The video hosted at a **public HTTPS URL** (Graph API pulls the video
    from a URL you give it — it does not accept raw file uploads for Reels).

No browser automation, no scraping, no credential harvesting. If you don't
have Graph API credentials configured, this module refuses to do anything
except print what it *would* do (use --dry-run, or just don't set the env
vars — dry-run is auto-enabled when config is missing).

Environment variables (see README.md):
    IG_USER_ID            Instagram Business Account ID (numeric string)
    IG_ACCESS_TOKEN        Long-lived access token with publish permission
    IG_GRAPH_API_VERSION    Optional, defaults to "v19.0"
"""

from __future__ import annotations

import os
import time
import urllib.parse

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


class InstagramConfigError(Exception):
    pass


GRAPH_HOST = "https://graph.facebook.com"


def _graph_version() -> str:
    return os.environ.get("IG_GRAPH_API_VERSION", "v19.0")


def _require_public_url(video_path: str) -> str:
    """The Graph API needs a public URL, not a local path.

    If the caller already passed a URL, use it. Otherwise raise a clear
    error explaining that the file needs to be hosted somewhere first
    (e.g. S3, Cloudflare R2, a CDN) — we deliberately do NOT attempt to
    stand up any tunneling/hosting ourselves.
    """
    parsed = urllib.parse.urlparse(video_path)
    if parsed.scheme in ("http", "https"):
        return video_path
    raise InstagramConfigError(
        f"'{video_path}' looks like a local file path, but the Instagram "
        "Graph API requires a public HTTPS URL to fetch the video from. "
        "Upload it to any storage/CDN you control first, then pass that "
        "URL as the video argument."
    )


def post_video_to_instagram(video_path: str, caption: str, dry_run: bool = False) -> str:
    ig_user_id = os.environ.get("IG_USER_ID")
    access_token = os.environ.get("IG_ACCESS_TOKEN")

    if dry_run or not ig_user_id or not access_token:
        reason = "requested" if dry_run else "no IG_USER_ID/IG_ACCESS_TOKEN set"
        return (
            f"[DRY RUN, {reason}] Would publish '{video_path}' to Instagram "
            f"(IG Business Account) with caption: {caption!r}"
        )

    if requests is None:
        raise InstagramConfigError(
            "The 'requests' package is required for real (non-dry-run) posting. "
            "Install it with: pip install requests"
        )

    video_url = _require_public_url(video_path)
    version = _graph_version()

    # Step 1: create a media container (use media_type=REELS for short-form video)
    create_url = f"{GRAPH_HOST}/{version}/{ig_user_id}/media"
    create_resp = requests.post(create_url, data={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": access_token,
    })
    create_resp.raise_for_status()
    container_id = create_resp.json()["id"]

    # Step 2: poll the container until Meta finishes processing the video
    status_url = f"{GRAPH_HOST}/{version}/{container_id}"
    for _ in range(30):
        status_resp = requests.get(status_url, params={
            "fields": "status_code",
            "access_token": access_token,
        })
        status_resp.raise_for_status()
        status_code = status_resp.json().get("status_code")
        if status_code == "FINISHED":
            break
        if status_code == "ERROR":
            raise InstagramConfigError("Instagram failed to process the video container.")
        time.sleep(5)
    else:
        raise InstagramConfigError("Timed out waiting for Instagram to process the video.")

    # Step 3: publish the container
    publish_url = f"{GRAPH_HOST}/{version}/{ig_user_id}/media_publish"
    publish_resp = requests.post(publish_url, data={
        "creation_id": container_id,
        "access_token": access_token,
    })
    publish_resp.raise_for_status()
    media_id = publish_resp.json()["id"]

    return f"Published to Instagram. Media ID: {media_id}"
