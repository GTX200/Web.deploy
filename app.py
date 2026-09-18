import base64
import io
import re
import threading
import zipfile
from pathlib import Path, PurePosixPath

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

GITHUB_API = "https://api.github.com"
API_VERSION = "2026-03-10"

state = {"running": False, "message": "Siap.", "url": ""}
ALLOWED_EXTENSIONS = {".html", ".htm", ".css", ".js", ".json", ".xml", ".txt", ".md", ".svg", ".ico", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".woff", ".woff2", ".ttf", ".otf", ".map", ".webmanifest", ".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"}


def set_state(message, running=None, url=None):
    state["message"] = message
    if running is not None:
        state["running"] = running
    if url is not None:
        state["url"] = url


def gh_headers(token):
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "Termux-Website-Deployer/1.0",
    }


def validate_name(value, label):
    if not value or not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
        raise ValueError(f"{label} tidak valid.")
    return value


def safe_zip_files(zip_bytes):
    result = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            raw = info.filename.replace("\\", "/")
            path = PurePosixPath(raw)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("ZIP mengandung path yang tidak aman.")
            if raw.startswith("./") or not raw:
                continue
            if Path(raw).suffix.lower() not in ALLOWED_EXTENSIONS:
                raise ValueError(f"File tidak didukung: {raw}")
            result.append((raw, zf.read(info)))
    if not result:
        raise ValueError("ZIP tidak berisi file.")
    names = {p.lower() for p, _ in result}
    if "index.html" not in names and "index.htm" not in names:
        raise ValueError("ZIP harus memiliki index.html atau index.htm di folder utama.")
    if not any(p.lower() in ("index.html", "index.htm") for p, _ in result):
        raise ValueError("index.html/index.htm harus berada di folder utama ZIP.")
    return result


def gh_error(resp):
    try:
        return resp.json().get("message") or f"GitHub HTTP {resp.status_code}"
    except Exception:
        return f"GitHub HTTP {resp.status_code}"


def get_repo(token, owner, repo):
    r = requests.get(f"{GITHUB_API}/repos/{owner}/{repo}", headers=gh_headers(token), timeout=30)
    if not r.ok:
        raise RuntimeError(gh_error(r))
    return r.json()


def get_existing_sha(token, owner, repo, path, branch):
    r = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
        params={"ref": branch}, headers=gh_headers(token), timeout=30,
    )
    if r.status_code == 404:
        return None
    if not r.ok:
        raise RuntimeError(gh_error(r))
    return r.json().get("sha")


def put_file(token, owner, repo, branch, path, data):
    sha = get_existing_sha(token, owner, repo, path, branch)
    payload = {
        "message": f"Deploy website: {path}",
        "content": base64.b64encode(data).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(
        f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
        headers=gh_headers(token), json=payload, timeout=60,
    )
    if not r.ok:
        raise RuntimeError(f"{path}: {gh_error(r)}")


def configure_pages(token, owner, repo, branch):
    payload = {"source": {"branch": branch, "path": "/"}, "build_type": "legacy", "https_enforced": True}
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pages"
    r = requests.post(url, headers=gh_headers(token), json=payload, timeout=30)
    if r.status_code == 409:
        r = requests.put(url, headers=gh_headers(token), json=payload, timeout=30)
    if not r.ok:
        raise RuntimeError(gh_error(r))
    return r.json() if r.content else {}


def deploy_job(form, zip_bytes):
    token = form["token"].strip()
    owner = validate_name(form["owner"].strip(), "Owner")
    repo = validate_name(form["repo"].strip(), "Repository")
    requested_branch = form.get("branch", "").strip()

    set_state("Memeriksa repository...", True, "")
    info = get_repo(token, owner, repo)
    branch = requested_branch or info.get("default_branch") or "main"

    set_state("Membaca ZIP...", True, "")
    files = safe_zip_files(zip_bytes)

    for i, (path, data) in enumerate(files, 1):
        set_state(f"Upload {i}/{len(files)}: {path}", True, "")
        put_file(token, owner, repo, branch, path, data)

    set_state("Mengaktifkan GitHub Pages...", True, "")
    try:
        pages = configure_pages(token, owner, repo, branch)
    except RuntimeError as exc:
        raise RuntimeError(f"File sudah ter-upload, tetapi GitHub Pages belum bisa diaktifkan: {exc}")

    site_url = pages.get("html_url") if pages else None
    if not site_url:
        site_url = f"https://{owner}.github.io/{repo}/"
    set_state("Deployment selesai. GitHub Pages mungkin membutuhkan beberapa saat untuk build.", False, site_url)


def _safe_job(form, zip_bytes):
    try:
        deploy_job(form, zip_bytes)
    except Exception as exc:
        set_state(f"Deployment gagal: {exc}", False, "")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/status")
def status():
    return jsonify(state)


@app.route("/preview", methods=["POST"])
def preview():
    upload = request.files.get("site_zip")
    if not upload or not upload.filename.lower().endswith(".zip"):
        return jsonify({"ok": False, "message": "Pilih file ZIP website."}), 400
    try:
        files = safe_zip_files(upload.read())
        return jsonify({"ok": True, "message": f"ZIP valid. {len(files)} file siap di-deploy.", "files": [p for p, _ in files][:100]})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400


@app.route("/deploy", methods=["POST"])
def deploy():
    if state["running"]:
        return jsonify({"ok": False, "message": "Deployment masih berjalan."}), 409
    token = request.form.get("token", "").strip()
    owner = request.form.get("owner", "").strip()
    repo = request.form.get("repo", "").strip()
    branch = request.form.get("branch", "").strip()
    upload = request.files.get("site_zip")
    if not token:
        return jsonify({"ok": False, "message": "GitHub token wajib diisi."}), 400
    if not owner or not repo:
        return jsonify({"ok": False, "message": "Owner dan repository wajib diisi."}), 400
    if not upload or not upload.filename.lower().endswith(".zip"):
        return jsonify({"ok": False, "message": "Pilih file ZIP website."}), 400
    try:
        zip_bytes = upload.read()
        if len(zip_bytes) > 50 * 1024 * 1024:
            raise ValueError("ZIP terlalu besar (maksimal 50 MB).")
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    state["url"] = ""
    threading.Thread(target=_safe_job, args=({"token": token, "owner": owner, "repo": repo, "branch": branch}, zip_bytes), daemon=True).start()
    return jsonify({"ok": True, "message": "Deployment dimulai."})


@app.post("/reset")
def reset():
    if state["running"]:
        return jsonify({"ok": False, "message": "Deployment masih berjalan."}), 409
    set_state("Siap.", False, "")
    return jsonify({"ok": True, "message": "Status direset."})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
