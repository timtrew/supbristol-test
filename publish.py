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

# test copy only: the reviewer toolbar hidden, and Microsoft Clarity, which
# loads only once a visitor has agreed in the privacy notice below
TEST_HEAD = """<style>#dev-bar{display:none!important}
.tc-scrim{position:fixed;inset:0;z-index:2000;background:rgba(5,24,34,.6);display:flex;align-items:center;justify-content:center;padding:16px}
.tc-scrim[hidden]{display:none}
.tc-box{background:#fff;color:var(--ink,#152b3b);max-width:480px;width:100%;max-height:calc(100vh - 32px);overflow:auto;border-radius:12px;padding:24px;box-shadow:0 20px 50px rgba(5,24,34,.35);font-family:"Poppins","Helvetica Neue",Arial,sans-serif}
.tc-box h2{font-family:"Rift Soft Bold","Barlow Condensed","Arial Narrow",sans-serif;text-transform:uppercase;font-size:1.6rem;line-height:1.05;margin:0 0 12px}
.tc-box p{margin:0 0 10px;font-size:.9375rem;line-height:1.55;color:var(--ink-2,#3b4b57)}
.tc-box a{color:var(--sup-deep,#1f6d95)}
.tc-tick{display:flex;gap:10px;align-items:flex-start;margin:16px 0;font-size:.9375rem;line-height:1.45;color:var(--ink,#152b3b);cursor:pointer}
.tc-tick input{width:20px;height:20px;margin:1px 0 0;flex:none;accent-color:var(--sup-deep,#1f6d95)}
.tc-go{display:block;width:100%;min-height:50px;border:0;border-radius:999px;background:var(--sup,#29abe2);color:#fff;font:700 1rem "Poppins","Helvetica Neue",Arial,sans-serif;cursor:pointer}
.tc-go:disabled{opacity:.45;cursor:not-allowed}
</style>
<script>
  window.startClarity = function(){
    if(window.clarityStarted) return; window.clarityStarted = true;
    (function(c,l,a,r,i,t,y){
        c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
        t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
        y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
    })(window, document, "clarity", "script", "yncgjw8udz");
  };
  try{ if(localStorage.getItem("sup-test-consent") === "yes") window.startClarity(); }catch(e){}
</script>
"""

# the privacy notice, shown once on a visitor's first opening of the site
CONSENT = """
<div class="tc-scrim" id="tc" role="dialog" aria-modal="true" aria-labelledby="tc-title" hidden>
  <div class="tc-box">
    <h2 id="tc-title">Help us test our new website</h2>
    <p>This is a test version of the new SUP Bristol website. Bookings made here are not real and no payment is taken.</p>
    <p>To see how people use it, we record visits with <a href="https://clarity.microsoft.com/terms" target="_blank" rel="noopener">Microsoft Clarity</a>: the pages you view and where you tap, click and scroll. It does not record what you type into forms. Clarity uses cookies, and Microsoft keeps recordings for up to 30 days. We only use them to improve the website.</p>
    <p>Questions? Email <a href="mailto:hello@supbristol.com">hello@supbristol.com</a>.</p>
    <label class="tc-tick"><input type="checkbox" id="tc-ok"> <span>I understand my visit will be recorded to help improve the website</span></label>
    <button class="tc-go" id="tc-go" disabled>Continue</button>
  </div>
</div>
<script>
(function(){
  var seen = null;
  try{ seen = localStorage.getItem("sup-test-consent"); }catch(e){}
  if(seen) return;
  var box = document.getElementById("tc"), ok = document.getElementById("tc-ok"), go = document.getElementById("tc-go");
  box.hidden = false;
  document.body.style.overflow = "hidden";
  function done(choice){
    try{ localStorage.setItem("sup-test-consent", choice); }catch(e){}
    box.hidden = true; document.body.style.overflow = "";
    if(choice === "yes"){
      window.startClarity();
      try{ window.clarity("set", "page", (location.hash || "#/").split("?")[0]); }catch(e){}
    }
  }
  ok.addEventListener("change", function(){ go.disabled = !ok.checked; });
  go.addEventListener("click", function(){ if(ok.checked) done("yes"); });
  ok.focus();
})();
</script>
"""

# after the prototype's own scripts: every tracked action becomes a Clarity
# event, and each page (the prototype is one URL with #/ routes) a tag.
# Nothing is sent unless Clarity has been started with consent.
TEST_TAIL = CONSENT + """
<script>
(function(){
  if(typeof window.track === "function"){
    var own = window.track;
    window.track = function(name, params){
      try{ if(window.clarityStarted) window.clarity("event", String(name)); }catch(e){}
      return own.apply(this, arguments);
    };
  }
  function page(){
    var r = (location.hash || "#/").split("?")[0];
    try{ if(window.clarityStarted) window.clarity("set", "page", r); }catch(e){}
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
