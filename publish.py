"""
Publish the prototype's current build to the public test site
(https://timtrew.github.io/supbristol-test/).

Copies ../SUP Bristol Prototype/dist/supbristol.html in as index.html,
adds tags asking search engines and AI crawlers not to index it, hides
the reviewer toolbar, adds Microsoft Clarity (with the prototype's
tracked actions as Clarity events), brings across only the image and
video files the page actually uses, blurs every face it can find in the
photos (videos are left as they are), then commits and pushes.

Face blurring uses OpenCV's YuNet model in tools/ (not published) and
caches each blurred photo in .blurcache/, so only new photos are redone.

Usage (after running build.py and extract_images.py in the prototype):
  py -3 publish.py "what changed"
  py -3 publish.py --dry          build the files here without pushing
"""
import hashlib, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "..", "SUP Bristol Prototype", "dist")
MODEL = os.path.join(HERE, "tools", "face_detection_yunet_2023mar.onnx")
CACHE = os.path.join(HERE, ".blurcache")
BLUR_VERSION = "1"   # bump to redo every photo after changing the blur


def blur_faces(src, dst):
    """Copy src to dst with every detected face blurred; returns the count."""
    import cv2, numpy as np
    data = open(src, "rb").read()
    ext = os.path.splitext(src)[1].lower()
    key = hashlib.sha1(data + BLUR_VERSION.encode()).hexdigest()
    cached = os.path.join(CACHE, key + ext)
    if os.path.exists(cached):
        shutil.copy2(cached, dst)
        return -1
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None or img.ndim < 3:
        shutil.copy2(src, dst); return 0
    rgb = img[:, :, :3]
    h, w = rgb.shape[:2]
    det = cv2.FaceDetectorYN.create(MODEL, "", (320, 320), 0.5, 0.3, 5000)
    boxes = []
    # a second pass enlarged, for the small faces in group photos
    for scale in (1.0, 2.0):
        s = min(scale, 2400 / max(w, h))
        im = cv2.resize(rgb, (int(w * s), int(h * s))) if s != 1 else np.ascontiguousarray(rgb)
        det.setInputSize((im.shape[1], im.shape[0]))
        _, found = det.detect(im)
        if found is not None:
            boxes += [(r[0] / s, r[1] / s, r[2] / s, r[3] / s) for r in found]
    for x, y, bw, bh in boxes:
        # widen for hair and ears; blur hard inside an oval
        cx, cy = x + bw / 2, y + bh / 2
        rw, rh = bw * 0.75, bh * 0.85
        x0, y0 = max(0, int(cx - rw)), max(0, int(cy - rh))
        x1, y1 = min(w, int(cx + rw)), min(h, int(cy + rh))
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        roi = img[y0:y1, x0:x1]
        k = max(15, (min(x1 - x0, y1 - y0) // 2) | 1)
        blurred = cv2.GaussianBlur(cv2.GaussianBlur(roi, (k, k), 0), (k, k), 0)
        mask = np.zeros(roi.shape[:2], np.uint8)
        cv2.ellipse(mask, ((roi.shape[1] // 2, roi.shape[0] // 2), (roi.shape[1], roi.shape[0]), 0), 255, -1)
        roi[mask > 0] = blurred[mask > 0]
    if not boxes:
        shutil.copy2(src, dst)
    else:
        params = [cv2.IMWRITE_JPEG_QUALITY, 86] if ext in (".jpg", ".jpeg") else []
        ok, buf = cv2.imencode(ext, img, params)
        open(dst, "wb").write(buf.tobytes())
    os.makedirs(CACHE, exist_ok=True)
    shutil.copy2(dst, cached)
    return len(boxes)

NOINDEX = ('<meta name="robots" content="noindex, nofollow, noarchive, nosnippet, noimageindex, noai, noimageai">\n'
           '<meta name="googlebot" content="noindex, nofollow">\n')

# test copy only: the reviewer toolbar hidden, and Microsoft Clarity recording
TEST_HEAD = """<style>#dev-bar{display:none!important}</style>
<script type="text/javascript">
    (function(c,l,a,r,i,t,y){
        c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
        t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
        y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
    })(window, document, "clarity", "script", "yncgjw8udz");
</script>
"""

# after the prototype's own scripts: every tracked action becomes a Clarity
# event, and each page (the prototype is one URL with #/ routes) a tag
TEST_TAIL = """
<script>
(function(){
  if(typeof window.track === "function"){
    var own = window.track;
    window.track = function(name, params){
      try{ window.clarity("event", String(name)); }catch(e){}
      return own.apply(this, arguments);
    };
  }
  function page(){
    var r = (location.hash || "#/").split("?")[0];
    try{ window.clarity("set", "page", r); }catch(e){}
  }
  window.addEventListener("hashchange", page);
  page();
})();
</script>
"""

ROBOTS = """# Test copy of the SUP Bristol prototype: not for search engines or AI.
User-agent: *
Disallow: /
""" + "".join(f"\nUser-agent: {bot}\nDisallow: /\n" for bot in [
    "Googlebot", "Google-Extended", "Bingbot", "GPTBot", "ChatGPT-User", "OAI-SearchBot",
    "ClaudeBot", "Claude-Web", "anthropic-ai", "CCBot", "PerplexityBot", "Bytespider",
    "Applebot-Extended", "Meta-ExternalAgent", "Amazonbot", "cohere-ai"])


def main():
    args = [a for a in sys.argv[1:] if a != "--dry"]
    msg = args[0] if args else "Update test site"
    page = open(os.path.join(DIST, "supbristol.html"), encoding="utf-8").read()
    assert page.startswith('<meta charset="utf-8">'), "unexpected start of supbristol.html"
    page = page.replace('<meta charset="utf-8">\n', '<meta charset="utf-8">\n' + NOINDEX + TEST_HEAD, 1)
    page = page.rstrip() + "\n" + TEST_TAIL

    used = sorted(set(re.findall(r'(img/[0-9a-f]+\.[a-z0-9]+|hero\.mp4)', page)))

    # drop media the page no longer uses; files only, as OneDrive can hold
    # a folder open and refuse to remove it
    keep = set(os.path.normpath(u) for u in used)
    for root, _, files in os.walk(HERE):
        if ".git" in os.path.relpath(root, HERE).split(os.sep):
            continue
        for f in files:
            rel = os.path.normpath(os.path.relpath(os.path.join(root, f), HERE))
            if rel.startswith("img" + os.sep) and rel not in keep:
                os.remove(os.path.join(HERE, rel))

    open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(page)
    open(os.path.join(HERE, "robots.txt"), "w", encoding="utf-8").write(ROBOTS)
    open(os.path.join(HERE, ".nojekyll"), "w").close()

    blurred = 0
    for rel in used:
        src = os.path.join(DIST, rel)
        dst = os.path.join(HERE, rel)
        os.makedirs(os.path.dirname(dst) or HERE, exist_ok=True)
        if rel.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            n = blur_faces(src, dst)
            blurred += max(n, 0)
        else:
            shutil.copy2(src, dst)
    print(f"index.html + {len(used)} media files ({blurred} faces blurred in new photos)")
    if "--dry" in sys.argv:
        print("dry run: files written, nothing committed or pushed")
        return

    git = lambda *a: subprocess.run(["git", *a], cwd=HERE, check=True)
    git("add", "-A")
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=HERE).returncode == 0:
        print("nothing changed")
        return
    git("commit", "-q", "-m", msg)
    git("push", "-q", "origin", "main")
    print("pushed; the site updates in a minute or two")


if __name__ == "__main__":
    main()
