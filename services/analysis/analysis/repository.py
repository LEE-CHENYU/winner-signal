"""Bounded public GitHub reads only. Submitted code is never executed."""

import hashlib
import re
from urllib.parse import quote
import httpx
from fastapi import HTTPException


async def snapshot(url):
    match = re.fullmatch(
        r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?", url
    )
    if not match:
        raise HTTPException(400, "Use a public https://github.com/owner/repository URL")
    repo = "/".join(match.groups())
    async with httpx.AsyncClient(
        timeout=20, follow_redirects=False, headers={"Accept": "application/vnd.github+json"}
    ) as client:

        async def get(path):
            r = await client.get("https://api.github.com/repos/" + repo + path)
            if r.status_code != 200:
                raise HTTPException(
                    422, "Public repository unavailable or GitHub rate limited; retry later"
                )
            if len(r.content) > 8_000_000:
                raise HTTPException(422, "Repository listing too large")
            return r.json()

        commit = (await get("/commits/HEAD"))["sha"]
        if not re.fullmatch(r"[a-f0-9]{40}", commit):
            raise HTTPException(422, "Invalid repository revision")
        tree = await get("/git/trees/" + commit + "?recursive=1")
        files = {}
        total = 0
        candidates = [
            r
            for r in tree.get("tree", [])
            if r.get("type") == "blob"
            and r.get("mode") == "100644"
            and r.get("size", 0) <= 30000
            and re.search(r"\.(py|tsx?|jsx?|md|sql)$", r["path"])
            and not any(
                part.startswith(".") or part in ("node_modules", "vendor", "session-history")
                for part in r["path"].split("/")
            )
        ]
        candidates.sort(key=lambda r: (r["path"].lower().endswith(".md"), r["path"]))
        for row in candidates[:16]:
            path = row["path"]
            if ".." in path.split("/"):
                continue
            r = await client.get(
                f"https://raw.githubusercontent.com/{repo}/{commit}/{quote(path, safe='/')}"
            )
            if r.status_code != 200 or len(r.content) > 30000:
                continue
            try:
                text = r.content.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if total + len(r.content) > 160000:
                break
            files[path] = {"text": text, "sha256": hashlib.sha256(r.content).hexdigest()}
            total += len(r.content)
    return {
        "repository_url": "https://github.com/" + repo,
        "commit_sha": commit,
        "files": files,
        "coverage": f"{len(files)} source files; bounded snapshot, not full repository",
        "tree_truncated": bool(tree.get("truncated")),
    }
