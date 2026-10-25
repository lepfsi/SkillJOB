"""Vérification des liens du référentiel de formation (§19).

Contrôle que chaque ressource pointe vers une page vivante, et distingue :

- ``ok``      : la page répond (2xx) ;
- ``deplace`` : redirection permanente (l'URL finale est signalée) ;
- ``protege`` : le fournisseur bloque les robots (401/403/405/429) : le lien
  n'est pas cassé pour autant, mais demande une vérification manuelle ;
- ``mort``    : 404/410 ou erreur réseau : le lien doit être corrigé.

Usage :
    python scripts/check_learning_links.py            # rapport lisible
    python scripts/check_learning_links.py --json out.json
    python scripts/check_learning_links.py --only mort,deplace

Le code de sortie vaut 1 dès qu'un lien mort subsiste : utilisable en
vérification automatisée.
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.services.learning import load_resources  # noqa: E402
from app.services.learning_tracking import infer_link_kind  # noqa: E402

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def classify(status: int | None) -> str:
    if status is None:
        return "mort"
    if 200 <= status < 300:
        return "ok"
    if status in (301, 302, 303, 307, 308):
        return "deplace"
    if status in (401, 403, 405, 406, 429):
        return "protege"
    return "mort"


def check(url: str, timeout: float = 20.0) -> dict:
    import urllib.error
    import urllib.request

    request = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "fr,en;q=0.8",
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            final = response.url
    except urllib.error.HTTPError as exc:
        status = exc.code
        final = getattr(exc, "url", url) or url
    except Exception as exc:  # réseau, TLS, DNS…
        return {"url": url, "status": None, "state": "mort", "error": str(exc)[:200]}
    return {
        "url": url,
        "status": status,
        "state": classify(status),
        "final_url": final if final != url else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--only", help="états à détailler, séparés par des virgules")
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()

    resources = load_resources()
    unique: dict[str, list[str]] = {}
    for skill, items in resources.items():
        for r in items:
            url = r.get("url")
            if not url:
                continue
            unique.setdefault(url, []).append(f"{skill} · {r['title']}")

    print(f"{len(unique)} liens uniques dans {len(resources)} compétences\n")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(check, unique))

    order = {"mort": 0, "deplace": 1, "protege": 2, "ok": 3}
    results.sort(key=lambda r: (order.get(r["state"], 9), r["url"]))
    counts: dict[str, int] = {}
    for r in results:
        counts[r["state"]] = counts.get(r["state"], 0) + 1

    wanted = set(args.only.split(",")) if args.only else {"mort", "deplace", "protege"}
    for r in results:
        if r["state"] not in wanted:
            continue
        who = "; ".join(unique[r["url"]][:3])
        print(f"[{r['state']:8s}] {r['status'] or '-'} {r['url']}")
        if r.get("final_url"):
            print(f"           -> {r['final_url']}")
        if r.get("error"):
            print(f"           {r['error']}")
        print(f"           {who}")

    print("\nRésumé :", ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))

    # Nature des liens déclarée vs déduite (cohérence du référentiel).
    declared = {r["link_kind"] for items in resources.values() for r in items}
    print("Types de lien utilisés :", ", ".join(sorted(declared)))

    if args.json_path:
        Path(args.json_path).write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Rapport écrit dans {args.json_path}")

    return 1 if counts.get("mort") else 0


if __name__ == "__main__":
    raise SystemExit(main())
