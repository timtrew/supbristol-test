"""
Publish the prototype's current build to the public test site
(https://timtrew.github.io/supbristol-test/).

Copies ../SUP Bristol Prototype/dist/supbristol.html in as index.html,
adds tags asking search engines and AI crawlers not to index it, brings
across only the image and video files the page actually uses, then
commits and pushes.

Usage (after running build.py and extract_images.py in the prototype):
  py -3 publish.py "what changed"
"""
import os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "..", "SUP Bristol Prototype", "dist")

NOINDEX = ('<meta name="robots" content="noindex, nofollow, noarchive, nosnippet, noimageindex, noai, noimageai">\n'
           '<meta name="googlebot" content="noindex, nofollow">\n')

ROBOTS = """# Test copy of the SUP Bristol prototype: not for search engines or AI.
User-agent: *
Disallow: /
""" + "".join(f"\nUser-agent: {bot}\nDisallow: /\n" for bot in [
    "Googlebot", "Google-Extended", "Bingbot", "GPTBot", "ChatGPT-User", "OAI-SearchBot",
    "ClaudeBot", "Claude-Web", "anthropic-ai", "CCBot", "PerplexityBot", "Bytespider",
    "Applebot-Extended", "Meta-ExternalAgent", "Amazonbot", "cohere-ai"])


def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else "Update test site"
    page = open(os.path.join(DIST, "supbristol.html"), encoding="utf-8").read()
    assert page.startswith('<meta charset="utf-8">'), "unexpected start of supbristol.html"
    page = page.replace('<meta charset="utf-8">\n', '<meta charset="utf-8">\n' + NOINDEX, 1)

    # start clean so files the page no longer uses are dropped
    for name in os.listdir(HERE):
        if name in (".git", "publish.py"):
            continue
        path = os.path.join(HERE, name)
        shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)

    open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(page)
    open(os.path.join(HERE, "robots.txt"), "w", encoding="utf-8").write(ROBOTS)
    open(os.path.join(HERE, ".nojekyll"), "w").close()

    used = sorted(set(re.findall(r'(img/[0-9a-f]+\.[a-z0-9]+|hero\.mp4)', page)))
    for rel in used:
        src = os.path.join(DIST, rel)
        dst = os.path.join(HERE, rel)
        os.makedirs(os.path.dirname(dst) or HERE, exist_ok=True)
        shutil.copy2(src, dst)
    print(f"index.html + {len(used)} media files")

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
