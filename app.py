#!/usr/bin/env python3
"""RcloneGUI - Interface graphique web pour rclone"""

import subprocess, json, os, threading, time, logging, tempfile, mimetypes
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)
active_jobs = {}
job_counter = 0
job_lock = threading.Lock()

def run_rclone(args, timeout=30):
    try:
        r = subprocess.run(["rclone"] + args, capture_output=True, text=True, timeout=timeout)
        return {"success": r.returncode == 0, "stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode}
    except subprocess.TimeoutExpired:
        return {"success": False, "stderr": "Timeout", "stdout": "", "returncode": -1}
    except FileNotFoundError:
        return {"success": False, "stderr": "rclone introuvable.", "stdout": "", "returncode": -1}

def run_rclone_stream(args, job_id):
    cmd = ["rclone"] + args + ["--use-json-log", "--log-level", "INFO", "--stats", "2s", "--stats-one-line"]
    with job_lock:
        active_jobs[job_id] = {"status": "running", "cmd": "rclone " + " ".join(args), "output": [], "process": None, "start_time": time.time()}
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        with job_lock:
            active_jobs[job_id]["process"] = proc
        def read_stream(stream):
            for raw in stream:
                line = raw.rstrip()
                if not line: continue
                try:
                    obj = json.loads(line)
                    msg = obj.get("msg", line)
                    if obj.get("level") == "error": msg = "❌ " + msg
                    elif "Copied" in msg or "copied" in msg: msg = "✓ " + msg
                except Exception:
                    msg = line
                with job_lock:
                    active_jobs[job_id]["output"].append(msg)
        t1 = threading.Thread(target=read_stream, args=(proc.stdout,), daemon=True)
        t2 = threading.Thread(target=read_stream, args=(proc.stderr,), daemon=True)
        t1.start(); t2.start(); t1.join(); t2.join()
        proc.wait()
        with job_lock:
            rc = proc.returncode
            active_jobs[job_id]["returncode"] = rc
            active_jobs[job_id]["status"] = "done" if rc == 0 else "error"
            active_jobs[job_id]["output"].append("✅ Terminé avec succès" if rc == 0 else "❌ Erreur (code {})".format(rc))
    except Exception as e:
        with job_lock:
            active_jobs[job_id]["status"] = "error"
            active_jobs[job_id]["output"].append("❌ " + str(e))

@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/check_rclone")
def check_rclone():
    r = run_rclone(["version"])
    return jsonify({"installed": r["success"], "version": r["stdout"].splitlines()[0] if r["success"] else None, "error": r["stderr"] if not r["success"] else None})

@app.route("/api/remotes")
def list_remotes():
    r = run_rclone(["listremotes"])
    remotes = [x.strip() for x in r["stdout"].splitlines() if x.strip()] if r["success"] else []
    return jsonify({"remotes": remotes, "error": r.get("stderr") if not r["success"] else None})

@app.route("/api/ls")
def list_files():
    path = request.args.get("path", "")
    if not path: return jsonify({"error": "Chemin manquant"}), 400
    r = run_rclone(["lsjson", path, "--max-depth=1"])
    if r["success"]:
        try: return jsonify({"files": json.loads(r["stdout"])})
        except: return jsonify({"files": []})
    return jsonify({"files": [], "error": r["stderr"]})

def make_job(args):
    global job_counter
    with job_lock:
        job_counter += 1
        jid = str(job_counter)
    t = threading.Thread(target=run_rclone_stream, args=(args, jid), daemon=True)
    t.start()
    return jsonify({"job_id": jid})

@app.route("/api/copy", methods=["POST"])
def copy_files():
    d = request.json
    return make_job(["copy", d.get("src",""), d.get("dst","")])

@app.route("/api/sync", methods=["POST"])
def sync_files():
    d = request.json
    return make_job(["sync", d.get("src",""), d.get("dst","")])

@app.route("/api/move", methods=["POST"])
def move_files():
    d = request.json
    return make_job(["move", d.get("src",""), d.get("dst","")])

@app.route("/api/delete", methods=["POST"])
def delete_file():
    d = request.json
    path = d.get("path","")
    if not path: return jsonify({"error": "Chemin manquant"}), 400
    return jsonify(run_rclone(["purge" if d.get("is_dir") else "deletefile", path]))

@app.route("/api/mkdir", methods=["POST"])
def mkdir():
    path = request.json.get("path","")
    if not path: return jsonify({"error": "Chemin manquant"}), 400
    r = run_rclone(["mkdir", path])
    if r["success"]: return jsonify(r)
    # S3/object storage : créer un .keep
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name
    try:
        r2 = run_rclone(["copyto", tmp_path, path.rstrip('/') + '/.keep'])
        return jsonify(r2)
    finally:
        os.unlink(tmp_path)

@app.route("/api/upload", methods=["POST"])
def upload_file():
    remote_path = request.form.get("path","")
    if not remote_path: return jsonify({"error": "Chemin manquant"}), 400
    files = request.files.getlist("files")
    if not files: return jsonify({"error": "Aucun fichier"}), 400
    results = []
    tmp_dir = tempfile.mkdtemp()
    try:
        for f in files:
            if not f.filename: continue
            tmp_path = os.path.join(tmp_dir, f.filename)
            f.save(tmp_path)
            r = run_rclone(["copyto", tmp_path, remote_path.rstrip("/") + "/" + f.filename], timeout=300)
            results.append({"file": f.filename, "success": r["success"], "error": r["stderr"] if not r["success"] else None})
            os.unlink(tmp_path)
    finally:
        try: os.rmdir(tmp_dir)
        except: pass
    return jsonify({"results": results, "success": all(r["success"] for r in results)})

@app.route("/api/download")
def download_file():
    path = request.args.get("path","")
    if not path: return jsonify({"error": "Chemin manquant"}), 400
    filename = path.split("/")[-1].split(":")[-1]
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, filename)
    r = run_rclone(["copyto", path, tmp_path], timeout=300)
    if not r["success"] or not os.path.exists(tmp_path):
        return jsonify({"error": r["stderr"]}), 500
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return send_file(tmp_path, as_attachment=True, download_name=filename, mimetype=mime)

@app.route("/api/job/<job_id>")
def job_status(job_id):
    with job_lock:
        job = active_jobs.get(job_id)
    if not job: return jsonify({"error": "Introuvable"}), 404
    return jsonify({"status": job["status"], "output": job["output"][-50:], "cmd": job["cmd"], "elapsed": round(time.time() - job["start_time"], 1)})

@app.route("/api/job/<job_id>/cancel", methods=["POST"])
def cancel_job(job_id):
    with job_lock:
        job = active_jobs.get(job_id)
        if job and job.get("process"):
            job["process"].terminate()
            job["status"] = "cancelled"
    return jsonify({"ok": True})

@app.route("/api/jobs")
def list_jobs():
    with job_lock:
        jobs = {jid: {"status": j["status"], "cmd": j["cmd"], "elapsed": round(time.time() - j["start_time"], 1)} for jid, j in active_jobs.items()}
    return jsonify(jobs)

@app.route("/api/config/create", methods=["POST"])
def create_config():
    d = request.json
    args = ["config", "create", d.get("name",""), d.get("type","")]
    for k, v in d.get("params", {}).items():
        if v: args += [k, v]
    return jsonify(run_rclone(args))

@app.route("/api/config/delete", methods=["POST"])
def delete_config():
    return jsonify(run_rclone(["config", "delete", request.json.get("name","")]))

if __name__ == "__main__":
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    print("\n" + "="*50)
    print("  🚀 RcloneGUI démarré !")
    print("  Ouvrez : http://localhost:7458")
    print("  Ctrl+C pour arrêter")
    print("="*50 + "\n")
    app.run(host="127.0.0.1", port=7458, debug=False)
