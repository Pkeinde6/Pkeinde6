"""Genere les images « terminal » du profil GitHub (contributions, whoami).

Lit le calendrier de contributions par l'API GraphQL de GitHub et l'avatar du compte,
puis ecrit assets/contributions.svg et assets/whoami.svg. Lance chaque jour par
.github/workflows/profil.yml ; en local : GITHUB_TOKEN=$(gh auth token) python scripts/generer.py
"""
import datetime as dt
import io
import json
import os
import urllib.request
from collections import Counter

from PIL import Image, ImageOps

LOGIN = os.environ.get('PROFIL_LOGIN', 'Pkeinde6')
INVITE = 'pape@github'
SORTIE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
VERTS = ['#161b22', '#0e4429', '#006d32', '#26a641', '#39d353']
FOND, BORD, TEXTE, GRIS = '#0d1117', '#30363d', '#e6edf3', '#7d8590'
POLICE = "ui-monospace,SFMono-Regular,'JetBrains Mono',Menlo,Consolas,monospace"


def graphql(requete, variables):
    corps = json.dumps({'query': requete, 'variables': variables}).encode()
    req = urllib.request.Request('https://api.github.com/graphql', corps, {
        'Authorization': 'bearer ' + os.environ['GITHUB_TOKEN'], 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as r:
        return json.load(r)['data']


def calendrier():
    d = graphql('''query($l:String!){user(login:$l){avatarUrl(size:400)
      contributionsCollection{contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}''', {'l': LOGIN})
    u = d['user']
    semaines = [[(j['date'], j['contributionCount']) for j in s['contributionDays']]
                for s in u['contributionsCollection']['contributionCalendar']['weeks']]
    return u['avatarUrl'], semaines, u['contributionsCollection']['contributionCalendar']['totalContributions']


def niveau(n, maxi):
    if n == 0:
        return 0
    return min(4, 1 + int(3 * n / max(1, maxi)))


def statistiques(jours):
    serie = actuelle = meilleure = 0
    for _, n in jours:
        serie = serie + 1 if n else 0
        meilleure = max(meilleure, serie)
    # la serie en cours tolere un aujourd'hui encore vide
    for i, (_, n) in enumerate(reversed(jours)):
        if n:
            actuelle += 1
        elif i > 0:
            break
    actifs = [n for _, n in jours if n]
    return {
        'actuelle': actuelle, 'meilleure': meilleure, 'total': sum(n for _, n in jours),
        'actifs': len(actifs), 'record': max(actifs or [0]),
        'moyenne': round(sum(actifs) / len(actifs), 1) if actifs else 0,
    }


def en_tete(largeur, commande):
    return (f'<rect width="{largeur}" height="100%" rx="12" fill="{FOND}" stroke="{BORD}"/>'
            f'<circle cx="22" cy="22" r="6" fill="#ff5f57"/><circle cx="42" cy="22" r="6" fill="#febc2e"/><circle cx="62" cy="22" r="6" fill="#28c840"/>'
            f'<text x="{largeur / 2}" y="27" text-anchor="middle" class="t">{INVITE} <tspan fill="{GRIS}">~ $</tspan> {commande}<tspan class="curseur">▍</tspan></text>')


STYLE = f'''<style>
text{{font-family:{POLICE};font-size:13px;fill:{TEXTE}}}
.p{{fill:{GRIS};font-size:11px}} .g{{font-size:26px;font-weight:700;fill:#39d353}} .b{{font-size:26px;font-weight:700}}
.curseur{{animation:clignote 1s steps(1) infinite}} @keyframes clignote{{50%{{opacity:0}}}}
.c{{opacity:0;animation:apparait .4s ease-out forwards}} @keyframes apparait{{to{{opacity:1}}}}
.barre{{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);animation:monte .8s cubic-bezier(.22,1,.36,1) forwards}}
@keyframes monte{{to{{transform:scaleY(1)}}}}
@media (prefers-reduced-motion:reduce){{.c,.barre{{animation:none;opacity:1;transform:none}}}}
</style>'''


def svg_contributions(semaines, total):
    case, pas, x0, y0 = 13, 16, 60, 86
    largeur = x0 + len(semaines) * pas + 30
    maxi = max(n for s in semaines for _, n in s) or 1
    morceaux, mois_vus = [], set()
    for i, s in enumerate(semaines):
        d = dt.date.fromisoformat(s[0][0])
        if d.day <= 7 and d.month not in mois_vus:
            mois_vus.add(d.month)
            morceaux.append(f'<text x="{x0 + i * pas}" y="{y0 - 12}" class="p">{d.strftime("%b")}</text>')
        for date, n in s:
            j = (dt.date.fromisoformat(date).weekday() + 1) % 7
            morceaux.append(f'<rect class="c" style="animation-delay:{i * 30}ms" x="{x0 + i * pas}" y="{y0 + j * pas}" width="{case}" height="{case}" rx="3" fill="{VERTS[niveau(n, maxi)]}"><title>{date} : {n}</title></rect>')
    for j, nom in ((1, 'Lun'), (3, 'Mer'), (5, 'Ven')):
        morceaux.append(f'<text x="18" y="{y0 + j * pas + 11}" class="p">{nom}</text>')
    hauteur = y0 + 7 * pas + 44
    legende = ''.join(f'<rect x="{largeur - 150 + k * 18}" y="{hauteur - 34}" width="13" height="13" rx="3" fill="{c}"/>' for k, c in enumerate(VERTS))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{largeur}" height="{hauteur}" viewBox="0 0 {largeur} {hauteur}">{STYLE}'
            + en_tete(largeur, './contributions.sh') + ''.join(morceaux)
            + f'<text x="{x0}" y="{hauteur - 23}" class="p">{total:,} contributions sur la dernière année</text>'.replace(',', ' ')
            + f'<text x="{largeur - 190}" y="{hauteur - 23}" class="p">Moins</text>{legende}<text x="{largeur - 56}" y="{hauteur - 23}" class="p">Plus</text></svg>')


def ascii_portrait(url, colonnes=56, lignes=30):
    with urllib.request.urlopen(url) as r:
        img = Image.open(io.BytesIO(r.read())).convert('L')
    img = ImageOps.autocontrast(img).resize((colonnes, lignes))
    rampe = '@%#*+=-:. '  # sombre = dense : le trait du visage ressort sur le fond noir
    return [''.join(rampe[int(p / 256 * len(rampe))] for p in (img.getpixel((x, y)) for x in range(colonnes))) for y in range(lignes)]


def svg_whoami(avatar, jours):
    st = statistiques(jours)
    largeur, hauteur = 900, 440
    portrait = ascii_portrait(avatar)
    lignes = ''.join(
        f'<text class="c" style="animation-delay:{k * 35}ms;font-size:10px;fill:#c9d1d9" x="36" y="{78 + k * 11.2}" xml:space="preserve">{l.replace("&", "&amp;").replace("<", "&lt;")}</text>'
        for k, l in enumerate(portrait))
    cartes = [('série en cours', f"{st['actuelle']}", 'jours', True), ('meilleure série', f"{st['meilleure']}", 'jours', False),
              ('contributions', f"{st['total']:,}".replace(',', ' '), 'sur 1 an', True), ('jours actifs', f"{st['actifs']}", 'sur 365', False),
              ('meilleur jour', f"{st['record']}", 'contributions', False), ('moyenne', f"{st['moyenne']}", 'par jour actif', False)]
    xc, yc = 440, 66
    blocs = []
    for k, (lib, val, sous, vert) in enumerate(cartes):
        x, y = xc + (k % 2) * 220, yc + (k // 2) * 78
        blocs.append(f'<g class="c" style="animation-delay:{300 + k * 90}ms"><rect x="{x}" y="{y}" width="206" height="66" rx="8" fill="#161b22" stroke="{BORD}"/>'
                     f'<text x="{x + 14}" y="{y + 20}" class="p">$ {lib}</text><text x="{x + 14}" y="{y + 50}" class="{"g" if vert else "b"}">{val}</text>'
                     f'<text x="{x + 14 + len(val) * 16 + 8}" y="{y + 50}" class="p">{sous}</text></g>')
    # contributions par mois, en barres
    parmois = Counter()
    for date, n in jours:
        parmois[date[:7]] += n
    mois = sorted(parmois)[-12:]
    mx = max(parmois[m] for m in mois) or 1
    barres = []
    for k, m in enumerate(mois):
        h = max(2, 84 * parmois[m] / mx)
        x = xc + k * 36
        barres.append(f'<rect class="barre" style="animation-delay:{900 + k * 60}ms" x="{x}" y="{404 - h}" width="24" height="{h}" rx="3" fill="{VERTS[4] if parmois[m] == mx else VERTS[3]}"><title>{m} : {parmois[m]}</title></rect>'
                      f'<text x="{x + 12}" y="{422}" text-anchor="middle" class="p">{dt.date.fromisoformat(m + "-01").strftime("%b")[0]}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{largeur}" height="{hauteur + 10}" viewBox="0 0 {largeur} {hauteur + 10}">{STYLE}'
            + en_tete(largeur, 'whoami') + lignes + ''.join(blocs)
            + f'<text x="{xc}" y="{yc + 3 * 78 + 16}" class="p">$ contributions / mois</text>' + ''.join(barres) + '</svg>')


def main():
    avatar, semaines, total = calendrier()
    jours = [j for s in semaines for j in s if j[0] <= dt.date.today().isoformat()]
    os.makedirs(SORTIE, exist_ok=True)
    open(os.path.join(SORTIE, 'contributions.svg'), 'w', encoding='utf-8').write(svg_contributions(semaines, total))
    open(os.path.join(SORTIE, 'whoami.svg'), 'w', encoding='utf-8').write(svg_whoami(avatar, jours))
    print(f'{total} contributions, images écrites dans {SORTIE}')


if __name__ == '__main__':
    main()
