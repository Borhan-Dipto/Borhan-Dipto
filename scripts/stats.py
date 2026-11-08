"""Render assets/stats.svg from live GitHub data (run daily by .github/workflows/stats.yml).

Needs GITHUB_TOKEN in the environment. `python3 scripts/stats.py --sample` renders
made-up numbers for a local design preview without calling the API.
"""
import datetime as dt
import json
import os
import sys
import urllib.request

from theme import AMBER, DIM, INK, PAPER, ROSE, RULE, TEAL, e, prompt, window, write

LOGIN = os.environ.get("PROFILE_LOGIN", "Borhan-Dipto")
LANG_COLORS = [AMBER, TEAL, ROSE, "#7fb2ff", "#c7a8ff", DIM]

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date } }
      }
    }
    pullRequests { totalCount }
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def fetch():
    token = os.environ["GITHUB_TOKEN"]
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if body.get("errors"):
        raise SystemExit(f"GitHub API error: {body['errors']}")
    u = body["data"]["user"]
    cc = u["contributionsCollection"]
    weeks = [sum(d["contributionCount"] for d in w["contributionDays"])
             for w in cc["contributionCalendar"]["weeks"]]
    first_day = cc["contributionCalendar"]["weeks"][0]["contributionDays"][0]["date"]
    langs = {}
    stars = 0
    for repo in u["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        for edge in repo["languages"]["edges"]:
            langs[edge["node"]["name"]] = langs.get(edge["node"]["name"], 0) + edge["size"]
    return dict(
        contributions=cc["contributionCalendar"]["totalContributions"],
        commits=cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        prs=u["pullRequests"]["totalCount"],
        repos=u["repositories"]["totalCount"],
        stars=stars, weeks=weeks, first_day=first_day, langs=langs,
    )


def sample():
    import random
    random.seed(7)
    weeks = [max(0, int(random.gauss(18, 14))) if i > 30 else random.randint(0, 6) for i in range(53)]
    start = (dt.date.today() - dt.timedelta(weeks=52)).isoformat()
    return dict(contributions=sum(weeks), commits=612, prs=12, repos=6, stars=3, weeks=weeks,
                first_day=start,
                langs={"TypeScript": 900, "JavaScript": 800, "PHP": 500, "Blade": 200, "PLpgSQL": 90, "CSS": 60})


def render(s):
    W, H, X = 900, 400, 40
    b = [prompt(X, 74, f"git log --author={LOGIN} --since=1.year --stats")[0]]

    # headline numbers
    nums = [(f"{s['contributions']:,}", "contributions in the last year"),
            (f"{s['commits']:,}", "commits"),
            (f"{s['prs']:,}", "pull requests"),
            (f"{s['repos']:,}", "public repositories")]
    x = X
    for i, (n, label) in enumerate(nums):
        size = 34 if i == 0 else 24
        b.append(f'<text class="d" x="{x}" y="126" font-size="{size}" font-weight="800" fill="{AMBER if i == 0 else PAPER}">{e(n)}</text>')
        b.append(f'<text x="{x}" y="150" font-size="13" fill="{DIM}">{e(label)}</text>')
        x += 300 if i == 0 else 175

    # weekly contribution histogram
    top, base = 178, 282
    weeks = s["weeks"][-53:]
    peak = max(weeks) or 1
    bw = (W - 2 * X) / len(weeks)
    for i, c in enumerate(weeks):
        h = max(2, (base - top) * c / peak) if c else 2
        col = AMBER if c else RULE
        b.append(f'<rect x="{X + i * bw:.1f}" y="{base - h:.1f}" width="{bw - 3:.1f}" height="{h:.1f}" rx="1.5" fill="{col}"/>')
    b.append(f'<rect x="{X}" y="{base + 3}" width="{W - 2 * X}" height="1" fill="{RULE}"/>')
    start = dt.date.fromisoformat(s["first_day"])
    seen = set()
    for i in range(len(weeks)):
        d = start + dt.timedelta(weeks=i)
        if d.day <= 7 and (d.year, d.month) not in seen and i % 1 == 0:
            seen.add((d.year, d.month))
            if len(seen) % 2:
                b.append(f'<text x="{X + i * bw:.1f}" y="{base + 21}" font-size="12" fill="{DIM}">{d.strftime("%b").lower()}</text>')

    # languages across public repos
    total = sum(s["langs"].values()) or 1
    ranked = sorted(s["langs"].items(), key=lambda kv: -kv[1])
    top_langs = ranked[:5]
    rest = total - sum(v for _, v in top_langs)
    if rest > 0:
        top_langs.append(("other", rest))
    y, x = 330, X
    for i, (name, v) in enumerate(top_langs):
        w = (W - 2 * X) * v / total
        b.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w - 3, 2):.1f}" height="10" rx="2" fill="{LANG_COLORS[i]}"/>')
        x += w
    lx = X
    for i, (name, v) in enumerate(top_langs):
        label = f"{name.lower()} {v / total * 100:.0f}%"
        b.append(f'<rect x="{lx}" y="{y + 25}" width="9" height="9" rx="2" fill="{LANG_COLORS[i]}"/>'
                 f'<text x="{lx + 15}" y="{y + 34}" font-size="13" fill="{PAPER}">{e(label)}</text>')
        lx += 15 + len(label) * 13 * 0.6 + 26
    updated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    b.append(f'<text x="{W - 20}" y="27" text-anchor="end" font-size="12" font-style="italic" fill="{DIM}">updated {updated}</text>')
    return window(W, H, "git log", "".join(b),
                  label=f"{s['contributions']} contributions in the last year, {s['commits']} commits, "
                        f"{s['prs']} pull requests, {s['repos']} public repositories")


def pending():
    """Shown only until the first workflow run replaces it with real numbers."""
    W, H, X = 900, 170, 40
    b = [prompt(X, 74, f"git log --author={LOGIN} --since=1.year --stats")[0],
         f'<text x="{X}" y="112" font-size="16" fill="{PAPER}">collecting stats from GitHub...</text>',
         f'<text x="{X}" y="138" font-size="13" fill="{DIM}">this card refreshes itself every day</text>']
    return window(W, H, "git log", "".join(b), label="GitHub stats are being generated")


if __name__ == "__main__":
    if "--pending" in sys.argv:
        write("stats.svg", pending())
        raise SystemExit
    data = sample() if "--sample" in sys.argv else fetch()
    write("stats.svg", render(data))
    print("stats.svg written")
