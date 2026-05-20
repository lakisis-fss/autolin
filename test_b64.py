import base64
import os

html = '<html><body>'
for f in ['docs/cv_debug/hp_detect.png', 'docs/cv_debug/mp_detect.png', 'docs/cv_debug/weight_detect.png']:
    if os.path.exists(f):
        with open(f, 'rb') as img:
            b64 = base64.b64encode(img.read()).decode('utf-8')
            html += f'<h3>{f}</h3><img src="data:image/png;base64,{b64}"/>'
html += '</body></html>'
with open('debug_imgs.html', 'w', encoding='utf-8') as out:
    out.write(html)
