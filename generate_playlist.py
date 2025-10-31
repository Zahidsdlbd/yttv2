import os
import sys
import requests
from datetime import datetime
import yt_dlp

print("🚀 YouTube HLS Playlist Generator (yt-dlp + redirect resolver)")

def resolve_live_redirect(url):
    try:
        resp = requests.get(url, allow_redirects=True, timeout=10)
        final_url = resp.url
        if "watch?v=" in final_url:
            print(f"[DEBUG] Resolved live URL → {final_url}")
            return final_url
        return url
    except Exception as e:
        print(f"[WARN] Could not resolve redirect for {url}: {e}")
        return url

def normalize_to_watch_url(token: str) -> str:
    token = token.strip()
    if not token:
        return None
    if token.startswith("@"):
        return f"https://www.youtube.com/{token}/live"
    if token.startswith("http://") or token.startswith("https://"):
        return token
    return f"https://www.youtube.com/watch?v={token}"

def extract_hls_url(url: str) -> str | None:
    ydl_opts = {
        "quiet": False,
        "no_warnings": True,
        "skip_download": True,
        "format": "bestvideo+bestaudio/best",
        "geo_bypass": True,
        "source_address": "0.0.0.0",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            print(f"[DEBUG] Extracted info for {url}: {info.get('title')}")
    except yt_dlp.utils.DownloadError as e:
        print(f"[WARN] yt-dlp could not extract from {url}: {e}")
        return None
    except Exception as e:
        print(f"[WARN] Unexpected error for {url}: {e}")
        return None

    formats = info.get("formats", []) or []
    hls_candidates = []
    for f in formats:
        proto = f.get("protocol") or ""
        link = f.get("url")
        if not link:
            continue
        if "m3u8" in proto or (".m3u8" in link):
            hls_candidates.append((f.get("tbr", 0) or 0, link))

    if hls_candidates:
        hls_candidates.sort(key=lambda x: x[0])
        return hls_candidates[-1][1]

    if isinstance(info.get("url"), str) and ".m3u8" in info["url"]:
        return info["url"]
    return None

def generate_m3u8_playlist(input_file="links.txt", output_file="playlist.m3u8"):
    if not os.path.exists(input_file):
        print(f"[FATAL] Missing {input_file}.")
        sys.exit(1)

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = ["#EXTM3U", f"# Generated on {now}", "#EXT-X-VERSION:3"]
    total = 0
    added = 0
    seen = set()

    with open(input_file, "r", encoding="utf-8") as fh:
        for line in fh:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            parts = [p.strip() for p in raw.split("|")]
            if len(parts) != 2:
                print(f"[SKIP] Malformed line: {raw}")
                continue

            name, token = parts
            if token in seen:
                continue
            seen.add(token)
            total += 1

            url = normalize_to_watch_url(token)
            url = resolve_live_redirect(url)

            print(f"[INFO] Processing {name} ({url})...")
            hls = extract_hls_url(url)
            if hls:
                lines.append(f"#EXTINF:-1,{name}")
                lines.append("#EXT-X-PROGRAM-ID:1")
                lines.append(hls)
                added += 1
                print(f"[OK] Added HLS for {name}")
            else:
                lines.append(f"#EXTINF:-1,{name} (offline)")
                print(f"[INFO] No HLS for {name} (not live or restricted).")

    with open(output_file, "w", encoding="utf-8") as out:
        out.write("\n".join(lines) + "\n")

    print(f"[DONE] {added}/{total} entries produced HLS. Wrote '{output_file}'.")

if __name__ == "__main__":
    generate_m3u8_playlist()
