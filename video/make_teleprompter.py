#!/usr/bin/env python3
"""Write teleprompter.html from the narration text, one page per shot, so the prompter can never
drift from the script.  Usage: RD_VARIANT=hackaday python3 make_teleprompter.py"""
import html, os, re
if os.environ.get("RD_VARIANT") == "hackaday":
    from narration_hackaday import SHOTS
else:
    from narration import SHOTS
HEAD = """<!doctype html><html><head><meta charset="utf-8"><title>RD-03D narration teleprompter</title>
<style>
body{background:#111;color:#eee;font-family:Georgia,serif;margin:0}
section{display:none;max-width:1100px;margin:0 auto;padding:40px 48px 120px}
section.on{display:block}
h2{font-size:22px;font-weight:bold;color:#9ad;margin:0 0 28px;letter-spacing:.02em}
p{font-size:34px;line-height:1.55;margin:0 0 22px}
.nav{position:fixed;bottom:0;left:0;right:0;background:#1b1b1b;color:#999;font:18px Helvetica,Arial;padding:14px 48px;display:flex;gap:28px;align-items:center}
.nav b{color:#eee}
.hint{color:#777}
</style></head><body>
"""
TAIL = """<div class="nav"><span id="pos"></span><span class="hint">&larr; &rarr; arrow keys or space to move between shots &middot; read at a conversational pace &middot; if you fluff a line, pause two seconds and read that sentence again</span></div>
<script>
const s=[...document.querySelectorAll('section')];let i=0;
function show(n){i=Math.max(0,Math.min(s.length-1,n));s.forEach((e,k)=>e.classList.toggle('on',k===i));document.getElementById('pos').innerHTML='Shot <b>'+(i+1)+'</b> of '+s.length;window.scrollTo(0,0);}
addEventListener('keydown',e=>{if(e.key==='ArrowRight'||e.key===' ')show(i+1);if(e.key==='ArrowLeft')show(i-1);});
const h=location.hash.match(/s(\\d+)/);show(h?+h[1]-1:0);
</script></body></html>
"""
out = [HEAD]
for n, (key, title, text) in enumerate(SHOTS, 1):
    sents = re.split(r"(?<=[.!?:])\s+", text.strip())
    out.append('<section id="s%d"><h2>%d of %d &middot; %s</h2>' % (n, n, len(SHOTS), html.escape(title)))
    out.extend("<p>%s</p>" % html.escape(s) for s in sents)
    out.append("</section>\n")
out.append(TAIL)
open("teleprompter.html", "w", encoding="utf-8").write("".join(out))
print("teleprompter.html: %d shots" % len(SHOTS))
