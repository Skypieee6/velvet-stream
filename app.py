import threading, requests, json, os, hashlib, time
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template_string, jsonify, Response, request, session, redirect, url_for
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'velvet_secret_key_2024_xK9mP3qR')

# --- CONFIGURATION ---
data_lock = threading.Lock()
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# In-memory user store (use a real DB in production)
users_db = {}
favorites_db = {}  # username -> list of video dicts
history_db = {}    # username -> list of video dicts

# --- BACKEND ---
def fetch_single_page(query, page_num, order='latest', per_page=24):
    try:
        url = (
            f'https://www.eporner.com/api/v2/video/search/'
            f'?query={requests.utils.quote(query)}'
            f'&per_page={per_page}'
            f'&page={page_num}'
            f'&order={order}'
            f'&format=json'
            f'&thumbsize=big'
        )
        r = requests.get(url, headers=HEADERS, timeout=6)
        if r.status_code == 200:
            data = r.json()
            return data.get('videos', []), data.get('total_count', 0)
    except Exception as e:
        print(f"Fetch error: {e}")
    return [], 0

def format_video(v):
    try:
        thumbs = v.get('thumbs', [])
        poster = thumbs[4]['src'] if len(thumbs) > 4 else v.get('default_thumb', {}).get('src', '')
        big_thumb = thumbs[-1]['src'] if thumbs else poster
        
        return {
            "id": v.get('id', ''),
            "title": v.get('title', 'Untitled'),
            "poster": poster,
            "big_thumb": big_thumb,
            "rating": round(float(v.get('rate', 0)), 1),
            "views": v.get('views', 0),
            "categories": [k.strip() for k in v.get('keywords', '').split(',')][:4],
            "duration": v.get('length_min', '0'),
            "embed_url": v.get('embed', ''),
            "video_url": v.get('url', ''),
            "added": v.get('added', ''),
            "is_vr": v.get('is_vr', False)
        }
    except Exception as e:
        print(f"Format error: {e}")
        return None

def load_content(query="korean", page=1, order='latest', per_page=24):
    videos, total = fetch_single_page(query, page, order, per_page)
    result = []
    for v in videos:
        fmt = format_video(v)
        if fmt and fmt['embed_url']:
            result.append(fmt)
    return result, total

def load_multi_page(query="korean", pages=3, order='latest'):
    all_videos = []
    total = 0
    with ThreadPoolExecutor(max_workers=pages) as executor:
        futures = list(executor.map(lambda p: fetch_single_page(query, p, order, 24), range(1, pages + 1)))
    for videos, t in futures:
        if t > total:
            total = t
        for v in videos:
            fmt = format_video(v)
            if fmt and fmt['embed_url']:
                all_videos.append(fmt)
    return all_videos, total

# --- ROUTES ---
@app.route('/api/data')
def get_data():
    query = request.args.get('q', 'korean')
    page = int(request.args.get('page', 1))
    order = request.args.get('order', 'latest')
    per_page = int(request.args.get('per_page', 24))
    videos, total = load_content(query, page, order, per_page)
    return jsonify({"videos": videos, "total": total, "page": page})

@app.route('/api/trending')
def get_trending():
    videos, total = load_content('sex', 1, 'top-weekly', 12)
    return jsonify({"videos": videos})

@app.route('/api/related')
def get_related():
    query = request.args.get('q', 'sex')
    page = int(request.args.get('page', 1))
    videos, _ = load_content(query, page, 'top-rated', 12)
    return jsonify({"videos": videos})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    email = data.get('email', '').strip().lower()
    if not username or not password or not email:
        return jsonify({"error": "All fields required"}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if username in users_db:
        return jsonify({"error": "Username already taken"}), 409
    hashed = hashlib.sha256(password.encode()).hexdigest()
    users_db[username] = {"email": email, "password": hashed, "created": time.time(), "avatar": username[0].upper()}
    favorites_db[username] = []
    history_db[username] = []
    session['user'] = username
    return jsonify({"success": True, "username": username})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    user = users_db.get(username)
    if not user:
        return jsonify({"error": "Invalid username or password"}), 401
    hashed = hashlib.sha256(password.encode()).hexdigest()
    if user['password'] != hashed:
        return jsonify({"error": "Invalid username or password"}), 401
    session['user'] = username
    return jsonify({"success": True, "username": username, "avatar": user['avatar']})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({"success": True})

@app.route('/api/me')
def me():
    user = session.get('user')
    if not user or user not in users_db:
        return jsonify({"logged_in": False})
    u = users_db[user]
    return jsonify({
        "logged_in": True,
        "username": user,
        "avatar": u.get('avatar', user[0].upper()),
        "email": u.get('email', ''),
        "favorites_count": len(favorites_db.get(user, [])),
        "history_count": len(history_db.get(user, []))
    })

@app.route('/api/favorites', methods=['GET'])
def get_favorites():
    user = session.get('user')
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"videos": favorites_db.get(user, [])})

@app.route('/api/favorites', methods=['POST'])
def toggle_favorite():
    user = session.get('user')
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json()
    video = data.get('video')
    if not video:
        return jsonify({"error": "No video data"}), 400
    favs = favorites_db.setdefault(user, [])
    existing = next((i for i, f in enumerate(favs) if f['id'] == video['id']), None)
    if existing is not None:
        favs.pop(existing)
        return jsonify({"favorited": False})
    else:
        favs.insert(0, video)
        return jsonify({"favorited": True})

@app.route('/api/history', methods=['GET'])
def get_history():
    user = session.get('user')
    if not user:
        return jsonify({"videos": []})
    return jsonify({"videos": history_db.get(user, [])[:50]})

@app.route('/api/history', methods=['POST'])
def add_history():
    user = session.get('user')
    data = request.get_json()
    video = data.get('video')
    if not video:
        return jsonify({"error": "No video"}), 400
    if user and user in users_db:
        hist = history_db.setdefault(user, [])
        hist = [h for h in hist if h['id'] != video['id']]
        hist.insert(0, video)
        history_db[user] = hist[:100]
    return jsonify({"success": True})

@app.route('/api/is_favorite')
def is_favorite():
    user = session.get('user')
    vid_id = request.args.get('id')
    if not user or not vid_id:
        return jsonify({"favorited": False})
    favs = favorites_db.get(user, [])
    return jsonify({"favorited": any(f['id'] == vid_id for f in favs)})

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

# --- FRONTEND TEMPLATE ---
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#0a0a0a">
    <title>VELVET — Premium Streaming</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <style>
        :root {
            --bg: #080808;
            --surface: #111111;
            --surface2: #181818;
            --border: rgba(255,255,255,0.07);
            --pink: #e91e8c;
            --pink-dark: #b5166d;
            --pink-glow: rgba(233, 30, 140, 0.3);
            --text: #f0e6f0;
            --text-muted: #776677;
            --text-dim: #3d2d3d;
            --gold: #d4af37;
            --radius: 10px;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
        html { scroll-behavior: smooth; }
        body {
            background: var(--bg);
            color: var(--text);
            font-family: 'DM Sans', sans-serif;
            font-size: 14px;
            overflow-x: hidden;
            padding-bottom: 80px;
            min-height: 100vh;
        }
        /* Block ALL content visibility until age is verified */
        body.age-locked { overflow: hidden; }
        body.age-locked header,
        body.age-locked #section-main,
        body.age-locked #section-favorites,
        body.age-locked #section-history,
        body.age-locked .bottom-nav,
        body.age-locked .fab,
        body.age-locked #progress-bar,
        body.age-locked #toast { visibility: hidden !important; pointer-events: none !important; }
        body::before {
            content: '';
            position: fixed;
            inset: 0;
            background: radial-gradient(ellipse 80% 60% at 50% -20%, rgba(233,30,140,0.08) 0%, transparent 70%);
            pointer-events: none;
            z-index: 0;
        }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: var(--bg); }
        ::-webkit-scrollbar-thumb { background: var(--pink); border-radius: 2px; }
        .hidden { display: none !important; }

        /* ---- AGE GATE ---- */
        #age-gate {
            position: fixed; inset: 0; background: #000; z-index: 99999;
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            text-align: center; padding: 30px;
        }
        .age-logo { font-family: 'Playfair Display', serif; font-size: 52px; font-weight: 900; color: var(--pink); letter-spacing: -2px; margin-bottom: 8px; text-shadow: 0 0 40px var(--pink-glow); }
        .age-subtitle { color: var(--text-muted); font-size: 11px; letter-spacing: 4px; text-transform: uppercase; margin-bottom: 40px; }
        .age-warning { width: 70px; height: 70px; border-radius: 50%; background: rgba(233,30,140,0.1); border: 2px solid var(--pink); display: flex; align-items: center; justify-content: center; margin: 0 auto 24px; }
        .age-warning i { font-size: 28px; color: var(--pink); }
        .age-gate h2 { font-size: 22px; font-weight: 700; color: #fff; margin-bottom: 10px; }
        .age-gate p { color: var(--text-muted); font-size: 13px; max-width: 300px; margin: 0 auto 32px; line-height: 1.6; }
        .age-btns { display: flex; gap: 12px; }
        .btn-enter { background: linear-gradient(135deg, var(--pink), var(--pink-dark)); color: white; padding: 14px 36px; border-radius: 50px; font-weight: 600; font-size: 15px; cursor: pointer; border: none; box-shadow: 0 0 30px var(--pink-glow); transition: all 0.2s; letter-spacing: 0.5px; }
        .btn-enter:hover { transform: translateY(-1px); box-shadow: 0 0 40px var(--pink-glow); }
        .btn-leave { background: transparent; color: var(--text-muted); padding: 14px 28px; border-radius: 50px; font-weight: 500; font-size: 15px; cursor: pointer; border: 1px solid var(--border); transition: all 0.2s; }
        .btn-leave:hover { border-color: var(--text-muted); color: var(--text); }
        .age-disclaimer { margin-top: 28px; color: var(--text-dim); font-size: 11px; max-width: 320px; line-height: 1.5; }

        /* ---- HEADER ---- */
        header {
            position: sticky; top: 0; background: rgba(8,8,8,0.95); z-index: 200;
            border-bottom: 1px solid var(--border); backdrop-filter: blur(20px);
        }
        .header-top { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; gap: 12px; }
        .logo { font-family: 'Playfair Display', serif; font-size: 26px; font-weight: 900; color: var(--pink); letter-spacing: -1px; cursor: pointer; text-shadow: 0 0 20px var(--pink-glow); flex-shrink: 0; }
        .logo span { color: var(--text); }
        .search-wrap { flex: 1; position: relative; max-width: 400px; }
        .search-wrap i { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: var(--text-muted); font-size: 13px; pointer-events: none; }
        .search-input { width: 100%; background: var(--surface2); border: 1px solid var(--border); border-radius: 50px; padding: 9px 16px 9px 36px; color: var(--text); font-size: 13px; font-family: 'DM Sans', sans-serif; outline: none; transition: all 0.2s; }
        .search-input:focus { border-color: var(--pink); background: var(--surface); box-shadow: 0 0 0 3px var(--pink-glow); }
        .search-input::placeholder { color: var(--text-dim); }
        .header-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
        .icon-btn { background: var(--surface2); border: 1px solid var(--border); color: var(--text-muted); width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; font-size: 14px; }
        .icon-btn:hover { color: var(--pink); border-color: var(--pink); }
        .login-btn { background: linear-gradient(135deg, var(--pink), var(--pink-dark)); color: white; border: none; padding: 8px 18px; border-radius: 50px; font-size: 12px; font-weight: 600; cursor: pointer; font-family: 'DM Sans', sans-serif; white-space: nowrap; transition: all 0.2s; }
        .login-btn:hover { box-shadow: 0 0 20px var(--pink-glow); }
        .user-avatar { width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg, var(--pink), var(--pink-dark)); color: white; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; cursor: pointer; border: 2px solid transparent; transition: all 0.2s; }
        .user-avatar:hover { border-color: var(--pink); }

        /* ---- CATEGORIES BAR ---- */
        .cat-bar { display: flex; gap: 4px; overflow-x: auto; padding: 0 12px 12px; scrollbar-width: none; }
        .cat-bar::-webkit-scrollbar { display: none; }
        .cat-pill { padding: 6px 14px; border-radius: 50px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; cursor: pointer; border: 1px solid var(--border); color: var(--text-muted); background: transparent; white-space: nowrap; transition: all 0.2s; }
        .cat-pill:hover { color: var(--text); border-color: rgba(255,255,255,0.2); }
        .cat-pill.active { background: var(--pink); color: white; border-color: var(--pink); box-shadow: 0 0 15px var(--pink-glow); }

        /* ---- SORT BAR ---- */
        .sort-bar { display: flex; align-items: center; gap: 8px; padding: 8px 16px; border-bottom: 1px solid var(--border); overflow-x: auto; scrollbar-width: none; }
        .sort-bar::-webkit-scrollbar { display: none; }
        .sort-label { color: var(--text-muted); font-size: 11px; text-transform: uppercase; letter-spacing: 1px; flex-shrink: 0; }
        .sort-btn { padding: 5px 12px; border-radius: 6px; font-size: 11px; font-weight: 500; cursor: pointer; border: 1px solid var(--border); color: var(--text-muted); background: transparent; white-space: nowrap; transition: all 0.15s; }
        .sort-btn.active, .sort-btn:hover { background: var(--surface2); color: var(--text); border-color: rgba(255,255,255,0.2); }
        .sort-btn.active { color: var(--pink); border-color: var(--pink); }
        .results-count { margin-left: auto; color: var(--text-muted); font-size: 11px; flex-shrink: 0; white-space: nowrap; }

        /* ---- HERO / TRENDING STRIP ---- */
        .section-title { display: flex; align-items: center; gap: 8px; padding: 20px 16px 12px; }
        .section-title h2 { font-family: 'Playfair Display', serif; font-size: 18px; font-weight: 700; color: var(--text); }
        .section-title .badge { background: var(--pink); color: white; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
        .trending-scroll { display: flex; gap: 10px; overflow-x: auto; padding: 0 16px 16px; scrollbar-width: none; }
        .trending-scroll::-webkit-scrollbar { display: none; }
        .trending-card { flex-shrink: 0; width: 150px; cursor: pointer; }
        .trending-card img { width: 100%; aspect-ratio: 16/9; object-fit: cover; border-radius: 8px; background: var(--surface2); transition: transform 0.2s; }
        .trending-card:hover img { transform: scale(1.03); }
        .trending-card .tc-title { font-size: 12px; font-weight: 500; color: var(--text); margin-top: 6px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; line-height: 1.3; }
        .trending-card .tc-meta { font-size: 10px; color: var(--text-muted); margin-top: 3px; }
        .trending-card .tc-duration { position: absolute; bottom: 5px; right: 5px; background: rgba(0,0,0,0.8); color: white; font-size: 10px; font-weight: 600; padding: 2px 5px; border-radius: 4px; }
        .tc-thumb { position: relative; }

        /* ---- MAIN GRID ---- */
        .main-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; padding: 12px 12px; }
        @media(min-width: 480px) { .main-grid { grid-template-columns: repeat(3, 1fr); } }
        @media(min-width: 768px) { .main-grid { grid-template-columns: repeat(4, 1fr); } }
        @media(min-width: 1024px) { .main-grid { grid-template-columns: repeat(5, 1fr); } }

        .video-card { cursor: pointer; position: relative; animation: fadeIn 0.3s ease both; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        .video-card .thumb-wrap { position: relative; border-radius: var(--radius); overflow: hidden; aspect-ratio: 16/9; background: var(--surface2); }
        .video-card img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.3s; display: block; }
        .video-card:hover img { transform: scale(1.05); }
        .video-card .overlay { position: absolute; inset: 0; background: linear-gradient(to top, rgba(0,0,0,0.8) 0%, transparent 50%); opacity: 0; transition: opacity 0.2s; display: flex; align-items: center; justify-content: center; }
        .video-card:hover .overlay { opacity: 1; }
        .play-icon { width: 44px; height: 44px; background: var(--pink); border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 20px var(--pink-glow); }
        .play-icon i { font-size: 16px; color: white; margin-left: 3px; }
        .video-card .duration-badge { position: absolute; bottom: 6px; right: 6px; background: rgba(0,0,0,0.85); color: white; font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; }
        .video-card .vr-badge { position: absolute; top: 6px; left: 6px; background: var(--gold); color: #000; font-size: 9px; font-weight: 700; padding: 2px 5px; border-radius: 3px; letter-spacing: 0.5px; }
        .video-card .fav-btn { position: absolute; top: 6px; right: 6px; width: 28px; height: 28px; background: rgba(0,0,0,0.7); border: none; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; color: white; font-size: 12px; opacity: 0; transition: opacity 0.2s; }
        .video-card:hover .fav-btn { opacity: 1; }
        .fav-btn.favorited { opacity: 1 !important; color: var(--pink) !important; }
        .video-card .card-info { padding: 7px 2px 2px; }
        .video-card .card-title { font-size: 12px; font-weight: 500; color: var(--text); overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; line-height: 1.4; }
        .video-card .card-meta { display: flex; align-items: center; gap: 6px; margin-top: 4px; }
        .card-rating { color: var(--gold); font-size: 10px; font-weight: 600; }
        .card-views { color: var(--text-muted); font-size: 10px; }
        .card-cat { background: var(--surface2); color: var(--text-muted); font-size: 9px; padding: 2px 6px; border-radius: 3px; text-transform: uppercase; letter-spacing: 0.5px; }

        /* ---- LOAD MORE ---- */
        .load-more-wrap { display: flex; justify-content: center; padding: 24px; }
        .load-more-btn { background: var(--surface2); border: 1px solid var(--border); color: var(--text); padding: 12px 36px; border-radius: 50px; font-size: 13px; font-weight: 600; cursor: pointer; font-family: 'DM Sans', sans-serif; transition: all 0.2s; }
        .load-more-btn:hover { border-color: var(--pink); color: var(--pink); }

        /* ---- SPINNER ---- */
        .spinner-wrap { display: flex; justify-content: center; align-items: center; padding: 60px; }
        .spinner { width: 36px; height: 36px; border: 3px solid var(--surface2); border-top-color: var(--pink); border-radius: 50%; animation: spin 0.7s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* ---- FAB ---- */
        .fab { position: fixed; bottom: 90px; right: 16px; width: 48px; height: 48px; background: linear-gradient(135deg, var(--pink), var(--pink-dark)); border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 20px var(--pink-glow); z-index: 300; cursor: pointer; transition: all 0.2s; }
        .fab:active { transform: scale(0.9); }
        .fab i { color: white; font-size: 18px; transition: transform 0.3s; }
        .fab.spinning i { animation: spin 0.5s linear; }

        /* ---- PLAYER MODAL ---- */
        #player-modal { position: fixed; inset: 0; background: #000; z-index: 600; overflow-y: auto; display: none; padding-bottom: 80px; }
        .player-header { position: sticky; top: 0; background: rgba(0,0,0,0.95); z-index: 10; padding: 12px 16px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid var(--border); backdrop-filter: blur(10px); }
        .back-btn { width: 36px; height: 36px; background: var(--surface2); border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text); flex-shrink: 0; }
        .player-header-title { font-weight: 600; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
        .player-fav-btn { background: var(--surface2); border: 1px solid var(--border); color: var(--text-muted); width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; transition: all 0.2s; font-size: 14px; }
        .player-fav-btn.fav-active { color: var(--pink); border-color: var(--pink); background: rgba(233,30,140,0.1); }
        .video-frame-wrap { width: 100%; aspect-ratio: 16/9; background: #000; position: relative; }
        #main-iframe { width: 100%; height: 100%; border: none; display: block; }
        .player-body { padding: 16px; }
        .player-title { font-family: 'Playfair Display', serif; font-size: 18px; font-weight: 700; line-height: 1.3; margin-bottom: 10px; }
        .player-meta { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px; }
        .meta-chip { display: flex; align-items: center; gap: 5px; background: var(--surface2); padding: 6px 12px; border-radius: 50px; font-size: 12px; color: var(--text-muted); }
        .meta-chip i { color: var(--pink); font-size: 11px; }
        .tags-wrap { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 20px; }
        .tag { padding: 4px 10px; background: var(--surface2); border: 1px solid var(--border); border-radius: 4px; font-size: 11px; color: var(--text-muted); cursor: pointer; transition: all 0.15s; }
        .tag:hover { color: var(--pink); border-color: var(--pink); }
        .section-divider { border: none; border-top: 1px solid var(--border); margin: 20px 0; }
        .related-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
        @media(min-width: 480px) { .related-grid { grid-template-columns: repeat(3, 1fr); } }

        /* ---- AUTH MODAL ---- */
        .modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.85); z-index: 800; display: flex; align-items: center; justify-content: center; padding: 20px; backdrop-filter: blur(8px); }
        .modal-box { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; width: 100%; max-width: 380px; padding: 28px; position: relative; }
        .modal-box h2 { font-family: 'Playfair Display', serif; font-size: 22px; font-weight: 700; margin-bottom: 6px; }
        .modal-box .sub { color: var(--text-muted); font-size: 13px; margin-bottom: 24px; }
        .modal-close { position: absolute; top: 16px; right: 16px; width: 30px; height: 30px; background: var(--surface2); border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text-muted); font-size: 13px; }
        .form-group { margin-bottom: 14px; }
        .form-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; color: var(--text-muted); display: block; margin-bottom: 6px; }
        .form-input { width: 100%; background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 11px 14px; color: var(--text); font-size: 14px; font-family: 'DM Sans', sans-serif; outline: none; transition: all 0.2s; }
        .form-input:focus { border-color: var(--pink); box-shadow: 0 0 0 3px var(--pink-glow); }
        .form-submit { width: 100%; background: linear-gradient(135deg, var(--pink), var(--pink-dark)); color: white; border: none; padding: 13px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; font-family: 'DM Sans', sans-serif; margin-top: 6px; transition: all 0.2s; }
        .form-submit:hover { box-shadow: 0 0 25px var(--pink-glow); }
        .form-error { color: #ff4466; font-size: 12px; margin-top: 6px; display: none; }
        .form-switch { text-align: center; margin-top: 16px; font-size: 13px; color: var(--text-muted); }
        .form-switch a { color: var(--pink); cursor: pointer; font-weight: 500; }

        /* ---- USER MENU ---- */
        .user-menu { position: fixed; top: 60px; right: 12px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; width: 220px; z-index: 500; overflow: hidden; box-shadow: 0 8px 30px rgba(0,0,0,0.5); }
        .user-menu-header { padding: 16px; border-bottom: 1px solid var(--border); }
        .user-menu-name { font-weight: 700; font-size: 15px; color: var(--text); }
        .user-menu-email { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
        .menu-item { padding: 12px 16px; display: flex; align-items: center; gap: 10px; cursor: pointer; color: var(--text-muted); font-size: 13px; transition: all 0.15s; }
        .menu-item:hover { background: var(--surface2); color: var(--text); }
        .menu-item i { width: 16px; text-align: center; color: var(--pink); font-size: 13px; }
        .menu-item.danger { color: #ff4466; }
        .menu-item.danger i { color: #ff4466; }

        /* ---- TOAST ---- */
        #toast { position: fixed; bottom: 90px; left: 50%; transform: translateX(-50%) translateY(20px); background: var(--surface2); border: 1px solid var(--border); color: var(--text); padding: 10px 20px; border-radius: 50px; font-size: 13px; font-weight: 500; z-index: 9999; opacity: 0; transition: all 0.3s; pointer-events: none; white-space: nowrap; box-shadow: 0 4px 20px rgba(0,0,0,0.4); }
        #toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
        #toast.success i { color: #22c55e; }
        #toast.error i { color: #ff4466; }

        /* ---- EMPTY STATE ---- */
        .empty-state { text-align: center; padding: 60px 20px; }
        .empty-state i { font-size: 48px; color: var(--text-dim); margin-bottom: 16px; }
        .empty-state h3 { font-size: 18px; font-weight: 700; color: var(--text-muted); margin-bottom: 8px; }
        .empty-state p { font-size: 13px; color: var(--text-dim); }

        /* ---- SKELETON SHIMMER ---- */
        @keyframes shimmer { 0% { background-position: -400px 0; } 100% { background-position: 400px 0; } }
        .thumb-wrap img { background: var(--surface2); }
        .thumb-wrap img.loading-img {
            background: linear-gradient(90deg, var(--surface2) 25%, #222 50%, var(--surface2) 75%);
            background-size: 400px 100%;
            animation: shimmer 1.4s ease infinite;
        }

        /* ---- INFINITE SCROLL SENTINEL ---- */
        #scroll-sentinel { height: 1px; width: 100%; }
        .infinite-spinner { display: flex; justify-content: center; align-items: center; padding: 30px; }
        .infinite-spinner .spinner { width: 28px; height: 28px; border-width: 2px; }

        /* ---- PROGRESS BAR ---- */
        #progress-bar { position: fixed; top: 0; left: 0; height: 2px; background: linear-gradient(90deg, var(--pink), #ff6bb0); z-index: 99999; width: 0; transition: width 0.3s; }

        /* ---- BOTTOM NAV ---- */
        .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; background: rgba(8,8,8,0.97); border-top: 1px solid var(--border); display: flex; z-index: 400; backdrop-filter: blur(20px); }
        .nav-item { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 10px 4px 12px; cursor: pointer; color: var(--text-muted); font-size: 10px; gap: 4px; transition: color 0.2s; }
        .nav-item i { font-size: 18px; }
        .nav-item.active { color: var(--pink); }
        .nav-item span { font-weight: 500; }

        /* ---- TABS ---- */
        #section-main, #section-favorites, #section-history { display: none; }
        #section-main.active-section, #section-favorites.active-section, #section-history.active-section { display: block; }

        /* ---- NO RESULTS ---- */
        .no-results { text-align: center; padding: 80px 20px; }
        .no-results i { font-size: 40px; color: var(--text-dim); margin-bottom: 16px; display: block; }
        .no-results p { color: var(--text-muted); font-size: 14px; }
    </style>
</head>
<body>

<div id="progress-bar"></div>
<div id="toast"><i class="fa fa-check-circle me-2"></i> <span id="toast-msg"></span></div>

<!-- AGE GATE -->
<div id="age-gate">
    <div class="age-logo">VELVET</div>
    <div class="age-subtitle">Premium Streaming</div>
    <div class="age-warning"><i class="fa fa-shield-halved"></i></div>
    <h2>Age Verification Required</h2>
    <p>This website contains explicit adult content intended only for viewers 18 years of age or older.</p>
    <div class="age-btns">
        <button class="btn-enter" onclick="enterSite()">I'm 18 or Older</button>
        <button class="btn-leave" onclick="window.location.href='https://www.google.com'">Exit</button>
    </div>
    <div class="age-disclaimer">By entering, you confirm you are at least 18 years old and consent to viewing explicit adult content. This site uses cookies.</div>
</div>

<!-- HEADER -->
<header>
    <div class="header-top">
        <div class="logo" onclick="goHome()">VELVET<span>+</span></div>
        <div class="search-wrap">
            <i class="fa fa-magnifying-glass"></i>
            <input type="text" class="search-input" id="search-input" placeholder="Search videos..." autocomplete="off" oninput="debounceSearch(this.value)">
        </div>
        <div class="header-actions">
            <div class="icon-btn" onclick="toggleTheme()" title="Toggle theme"><i class="fa fa-circle-half-stroke"></i></div>
            <div id="auth-area">
                <button class="login-btn" onclick="showAuthModal('login')"><i class="fa fa-user"></i> Login</button>
            </div>
        </div>
    </div>
    <div class="cat-bar" id="cat-bar">
        <div class="cat-pill active" onclick="setCategory('korean', this)">Korean</div>
        <div class="cat-pill" onclick="setCategory('japanese', this)">Japanese</div>
        <div class="cat-pill" onclick="setCategory('amateur', this)">Amateur</div>
        <div class="cat-pill" onclick="setCategory('hentai', this)">Hentai</div>
        <div class="cat-pill" onclick="setCategory('milf', this)">MILF</div>
        <div class="cat-pill" onclick="setCategory('asian', this)">Asian</div>
        <div class="cat-pill" onclick="setCategory('vr', this)">VR</div>
        <div class="cat-pill" onclick="setCategory('blonde', this)">Blonde</div>
        <div class="cat-pill" onclick="setCategory('latina', this)">Latina</div>
        <div class="cat-pill" onclick="setCategory('pov', this)">POV</div>
        <div class="cat-pill" onclick="setCategory('teen', this)">Teen 18+</div>
        <div class="cat-pill" onclick="setCategory('threesome', this)">Threesome</div>
        <div class="cat-pill" onclick="setCategory('lesbian', this)">Lesbian</div>
        <div class="cat-pill" onclick="setCategory('bdsm', this)">BDSM</div>
        <div class="cat-pill" onclick="setCategory('creampie', this)">Creampie</div>
        <div class="cat-pill" onclick="setCategory('step sister nun strapon', this)">The Nun</div>
        <div class="cat-pill" onclick="setCategory('Adriana chechik', this)">Adriana</div>
        <div class="cat-pill" onclick="setCategory('step brother', this)">Step Bro</div>
        <div class="cat-pill" onclick="setCategory('Vina sky', this)">Vina Sky</div>
        <div class="cat-pill" onclick="setCategory('Aria alexander', this)">Aria Alexander</div>
        <div class="cat-pill" onclick="setCategory('Melayu gangbang', this)">Melayu</div>
        <div class="cat-pill" onclick="setCategory('Kitty meana wolf', this)">Meana Wolf</div>
        <div class="cat-pill" onclick="setCategory('mom son taboo', this)">Mom</div>
        <div class="cat-pill" onclick="setCategory('Nurul', this)">Nurul</div>
        <div class="cat-pill" onclick="setCategory('Kurashina kana', this)">Kana</div>
        <div class="cat-pill" onclick="setCategory('korean movie', this)">Korean Movie</div>
        <div class="cat-pill" onclick="setCategory('married couple', this)">Married</div>
        <div class="cat-pill" onclick="setCategory('british mom', this)">British Mom</div>
        <div class="cat-pill" onclick="setCategory('Ava adams', this)">Ava Adams</div>
        <div class="cat-pill" onclick="setCategory('gangbang', this)">Gangbang</div>
        <div class="cat-pill" onclick="setCategory('anal', this)">Anal</div>
        <div class="cat-pill" onclick="setCategory('squirt', this)">Squirt</div>
        <div class="cat-pill" onclick="setCategory('massage', this)">Massage</div>
    </div>
    <div class="sort-bar">
        <span class="sort-label">Sort:</span>
        <button class="sort-btn active" onclick="setSort('latest', this)">Latest</button>
        <button class="sort-btn" onclick="setSort('top-weekly', this)">Hot</button>
        <button class="sort-btn" onclick="setSort('top-monthly', this)">Monthly</button>
        <button class="sort-btn" onclick="setSort('top-rated', this)">Top Rated</button>
        <button class="sort-btn" onclick="setSort('most-popular', this)">Most Viewed</button>
        <div class="results-count" id="results-count"></div>
    </div>
</header>

<!-- MAIN SECTION -->
<div id="section-main" class="active-section">
    <!-- TRENDING -->
    <div id="trending-section">
        <div class="section-title">
            <h2>🔥 Trending Now</h2>
            <span class="badge">Live</span>
        </div>
        <div class="trending-scroll" id="trending-scroll">
            <div class="spinner-wrap"><div class="spinner"></div></div>
        </div>
    </div>
    <div class="section-title">
        <h2 id="grid-title">Latest Videos</h2>
    </div>
    <div class="main-grid" id="main-grid"></div>
    <div class="spinner-wrap hidden" id="loading-spinner"><div class="spinner"></div></div>
    <div id="infinite-spinner" class="infinite-spinner hidden"><div class="spinner"></div></div>
    <div id="scroll-sentinel"></div>
</div>

<!-- FAVORITES SECTION -->
<div id="section-favorites">
    <div class="section-title"><h2>❤️ My Favorites</h2></div>
    <div class="main-grid" id="fav-grid"></div>
    <div class="empty-state hidden" id="fav-empty">
        <i class="fa fa-heart"></i>
        <h3>No favorites yet</h3>
        <p>Tap the heart icon on any video to save it here.</p>
    </div>
</div>

<!-- HISTORY SECTION -->
<div id="section-history">
    <div class="section-title"><h2>🕐 Watch History</h2></div>
    <div class="main-grid" id="hist-grid"></div>
    <div class="empty-state hidden" id="hist-empty">
        <i class="fa fa-clock"></i>
        <h3>No history yet</h3>
        <p>Videos you watch will appear here.</p>
    </div>
</div>

<!-- FAB -->
<div class="fab" onclick="scrollToTop()" id="fab"><i class="fa fa-arrow-up"></i></div>

<!-- PLAYER MODAL -->
<div id="player-modal">
    <div class="player-header">
        <div class="back-btn" onclick="closePlayer()"><i class="fa fa-chevron-left"></i></div>
        <div class="player-header-title" id="player-header-title">Now Playing</div>
        <div class="player-fav-btn" id="player-fav-btn" onclick="togglePlayerFav()"><i class="fa fa-heart"></i></div>
    </div>
    <div class="video-frame-wrap">
        <iframe id="main-iframe" allowfullscreen allow="autoplay; fullscreen; encrypted-media; picture-in-picture" src="about:blank"></iframe>
    </div>
    <div class="player-body">
        <h1 class="player-title" id="player-title"></h1>
        <div class="player-meta" id="player-meta"></div>
        <div class="tags-wrap" id="player-tags"></div>
        <hr class="section-divider">
        <div class="section-title" style="padding: 0 0 12px;"><h2>Related Videos</h2></div>
        <div class="related-grid" id="related-grid">
            <div class="spinner-wrap" style="grid-column: 1/-1;"><div class="spinner"></div></div>
        </div>
    </div>
</div>

<!-- AUTH MODAL -->
<div class="modal-backdrop hidden" id="auth-modal" onclick="closeAuthModal(event)">
    <div class="modal-box">
        <div class="modal-close" onclick="hideAuthModal()"><i class="fa fa-xmark"></i></div>
        <!-- LOGIN -->
        <div id="login-form-wrap">
            <h2>Welcome back</h2>
            <p class="sub">Sign in to access your favorites and history.</p>
            <div class="form-group">
                <label class="form-label">Username</label>
                <input type="text" class="form-input" id="login-user" placeholder="your_username" autocomplete="username">
            </div>
            <div class="form-group">
                <label class="form-label">Password</label>
                <input type="password" class="form-input" id="login-pass" placeholder="••••••••" autocomplete="current-password" onkeydown="if(event.key==='Enter')doLogin()">
            </div>
            <div class="form-error" id="login-error"></div>
            <button class="form-submit" onclick="doLogin()">Sign In</button>
            <div class="form-switch">Don't have an account? <a onclick="showAuthModal('register')">Create one</a></div>
        </div>
        <!-- REGISTER -->
        <div id="register-form-wrap" class="hidden">
            <h2>Create account</h2>
            <p class="sub">Join for free and save your favorites.</p>
            <div class="form-group">
                <label class="form-label">Username</label>
                <input type="text" class="form-input" id="reg-user" placeholder="your_username" autocomplete="username">
            </div>
            <div class="form-group">
                <label class="form-label">Email</label>
                <input type="email" class="form-input" id="reg-email" placeholder="you@example.com" autocomplete="email">
            </div>
            <div class="form-group">
                <label class="form-label">Password</label>
                <input type="password" class="form-input" id="reg-pass" placeholder="Min. 6 characters" autocomplete="new-password" onkeydown="if(event.key==='Enter')doRegister()">
            </div>
            <div class="form-error" id="reg-error"></div>
            <button class="form-submit" onclick="doRegister()">Create Account</button>
            <div class="form-switch">Already have an account? <a onclick="showAuthModal('login')">Sign in</a></div>
        </div>
    </div>
</div>

<!-- USER MENU -->
<div class="user-menu hidden" id="user-menu">
    <div class="user-menu-header">
        <div class="user-menu-name" id="menu-name">Username</div>
        <div class="user-menu-email" id="menu-email">email</div>
    </div>
    <div class="menu-item" onclick="showSection('favorites'); hideUserMenu()"><i class="fa fa-heart"></i> My Favorites <span id="fav-count-badge" style="margin-left:auto;font-size:11px;color:var(--text-dim)"></span></div>
    <div class="menu-item" onclick="showSection('history'); hideUserMenu()"><i class="fa fa-clock-rotate-left"></i> Watch History</div>
    <div class="menu-item danger" onclick="doLogout()"><i class="fa fa-right-from-bracket"></i> Sign Out</div>
</div>

<!-- BOTTOM NAV -->
<nav class="bottom-nav">
    <div class="nav-item active" id="nav-home" onclick="showSection('main')">
        <i class="fa fa-house"></i><span>Home</span>
    </div>
    <div class="nav-item" id="nav-favorites" onclick="requireLogin(()=>showSection('favorites'))">
        <i class="fa fa-heart"></i><span>Favorites</span>
    </div>
    <div class="nav-item" id="nav-history" onclick="requireLogin(()=>showSection('history'))">
        <i class="fa fa-clock"></i><span>History</span>
    </div>
    <div class="nav-item" id="nav-search" onclick="focusSearch()">
        <i class="fa fa-magnifying-glass"></i><span>Search</span>
    </div>
</nav>

<script>
// ===== STATE =====
let state = {
    currentCategory: 'korean',
    currentOrder: 'latest',
    currentPage: 1,
    totalVideos: 0,
    allVideos: [],
    currentVideo: null,
    user: null,
    favorites: new Set(),
    isLoading: false,
    hasMore: true,
    searchTimeout: null
};

// ===== PROGRESS BAR =====
function startProgress() {
    const bar = document.getElementById('progress-bar');
    bar.style.width = '0';
    bar.style.transition = 'width 0.3s';
    setTimeout(() => bar.style.width = '70%', 50);
}
function endProgress() {
    const bar = document.getElementById('progress-bar');
    bar.style.width = '100%';
    setTimeout(() => { bar.style.width = '0'; bar.style.transition = 'none'; }, 500);
}

// ===== TOAST =====
function showToast(msg, type='success') {
    const t = document.getElementById('toast');
    document.getElementById('toast-msg').textContent = msg;
    t.className = 'show ' + type;
    clearTimeout(t._timeout);
    t._timeout = setTimeout(() => t.className = '', 2500);
}

// ===== AGE GATE =====
function checkAge() {
    if (sessionStorage.getItem('velvet_age_v3') === 'true') {
        document.getElementById('age-gate').style.display = 'none';
        document.body.classList.remove('age-locked');
    } else {
        // Lock everything until verified
        document.body.classList.add('age-locked');
    }
}
function enterSite() {
    sessionStorage.setItem('velvet_age_v3', 'true');
    document.getElementById('age-gate').style.display = 'none';
    document.body.classList.remove('age-locked');
}

// ===== INIT =====
async function init() {
    checkAge();
    await checkSession();
    fetchTrending();
    fetchVideos(true);
    setupInfiniteScroll();
    window.addEventListener('scroll', onScroll);
    window.addEventListener('hashchange', onHashChange);
    window.addEventListener('click', onDocClick);
    if (location.hash === '#watch') history.replaceState(null, null, ' ');
}

function onScroll() {
    const fab = document.getElementById('fab');
    if (window.scrollY > 400) fab.style.opacity = '1';
    else fab.style.opacity = '0.3';
}

function onDocClick(e) {
    if (!e.target.closest('#user-menu') && !e.target.closest('#auth-area')) {
        hideUserMenu();
    }
}

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ===== SESSION =====
async function checkSession() {
    try {
        const r = await fetch('/api/me');
        const data = await r.json();
        if (data.logged_in) {
            state.user = data;
            renderAuthArea(data);
            await loadFavoriteIds();
        }
    } catch(e) {}
}

async function loadFavoriteIds() {
    try {
        const r = await fetch('/api/favorites');
        const data = await r.json();
        state.favorites = new Set((data.videos || []).map(v => v.id));
    } catch(e) {}
}

function renderAuthArea(user) {
    const area = document.getElementById('auth-area');
    area.innerHTML = `<div class="user-avatar" onclick="toggleUserMenu()">${user.avatar || user.username[0].toUpperCase()}</div>`;
    document.getElementById('menu-name').textContent = user.username;
    document.getElementById('menu-email').textContent = user.email || '';
    document.getElementById('fav-count-badge').textContent = user.favorites_count ? `(${user.favorites_count})` : '';
}

// ===== AUTH MODAL =====
function showAuthModal(tab = 'login') {
    document.getElementById('auth-modal').classList.remove('hidden');
    document.getElementById('login-form-wrap').classList.toggle('hidden', tab !== 'login');
    document.getElementById('register-form-wrap').classList.toggle('hidden', tab !== 'register');
    document.getElementById('login-error').style.display = 'none';
    document.getElementById('reg-error').style.display = 'none';
    if (tab === 'login') setTimeout(() => document.getElementById('login-user').focus(), 100);
    else setTimeout(() => document.getElementById('reg-user').focus(), 100);
}
function hideAuthModal() { document.getElementById('auth-modal').classList.add('hidden'); }
function closeAuthModal(e) { if (e.target === document.getElementById('auth-modal')) hideAuthModal(); }

async function doLogin() {
    const user = document.getElementById('login-user').value.trim();
    const pass = document.getElementById('login-pass').value;
    const errEl = document.getElementById('login-error');
    errEl.style.display = 'none';
    if (!user || !pass) { errEl.textContent = 'Please fill all fields.'; errEl.style.display = 'block'; return; }
    try {
        const r = await fetch('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: user, password: pass }) });
        const data = await r.json();
        if (data.error) { errEl.textContent = data.error; errEl.style.display = 'block'; return; }
        state.user = data;
        renderAuthArea(data);
        await loadFavoriteIds();
        hideAuthModal();
        showToast(`Signed in as ${data.username} ✓`);
    } catch(e) { errEl.textContent = 'Server error. Try again.'; errEl.style.display = 'block'; }
}

async function doRegister() {
    const user = document.getElementById('reg-user').value.trim();
    const email = document.getElementById('reg-email').value.trim();
    const pass = document.getElementById('reg-pass').value;
    const errEl = document.getElementById('reg-error');
    errEl.style.display = 'none';
    if (!user || !email || !pass) { errEl.textContent = 'Please fill all fields.'; errEl.style.display = 'block'; return; }
    try {
        const r = await fetch('/api/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: user, email, password: pass }) });
        const data = await r.json();
        if (data.error) { errEl.textContent = data.error; errEl.style.display = 'block'; return; }
        state.user = data;
        renderAuthArea(data);
        hideAuthModal();
        showToast(`Account created! Welcome, ${data.username}! 🎊`);
    } catch(e) { errEl.textContent = 'Server error. Try again.'; errEl.style.display = 'block'; }
}

async function doLogout() {
    await fetch('/api/logout', { method: 'POST' });
    state.user = null;
    state.favorites = new Set();
    document.getElementById('auth-area').innerHTML = `<button class="login-btn" onclick="showAuthModal('login')"><i class="fa fa-user"></i> Login</button>`;
    hideUserMenu();
    showToast('Signed out successfully.');
    showSection('main');
    renderGrid(state.allVideos, false);
}

function toggleUserMenu() {
    document.getElementById('user-menu').classList.toggle('hidden');
}
function hideUserMenu() {
    document.getElementById('user-menu').classList.add('hidden');
}

function requireLogin(cb) {
    if (!state.user) { showToast('Please sign in first.', 'error'); showAuthModal('login'); return; }
    cb();
}

// ===== SECTIONS =====
function showSection(name) {
    ['main', 'favorites', 'history'].forEach(s => {
        document.getElementById(`section-${s}`).classList.remove('active-section');
        document.getElementById(`nav-${s === 'main' ? 'home' : s}`).classList.remove('active');
    });
    document.getElementById(`section-${name}`).classList.add('active-section');
    document.getElementById(`nav-${name === 'main' ? 'home' : name}`).classList.add('active');
    if (name === 'favorites') loadFavoritesPage();
    if (name === 'history') loadHistoryPage();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function goHome() {
    showSection('main');
}

function focusSearch() {
    showSection('main');
    setTimeout(() => document.getElementById('search-input').focus(), 100);
}

// ===== FETCH VIDEOS =====
async function fetchVideos(reset = false) {
    if (state.isLoading) return;
    state.isLoading = true;
    if (reset) {
        state.currentPage = 1;
        state.allVideos = [];
        document.getElementById('main-grid').innerHTML = '';
        document.getElementById('trending-section').style.display = 'none';
    }
    startProgress();
    const spinner = document.getElementById(reset ? 'loading-spinner' : 'infinite-spinner');
    spinner.classList.remove('hidden');
    try {
        const r = await fetch(`/api/data?q=${encodeURIComponent(state.currentCategory)}&page=${state.currentPage}&order=${state.currentOrder}&per_page=24`);
        const data = await r.json();
        state.totalVideos = data.total || 0;
        const videos = data.videos || [];
        state.allVideos = reset ? videos : [...state.allVideos, ...videos];
        document.getElementById('results-count').textContent = state.totalVideos ? `${formatNum(state.totalVideos)} videos` : '';
        const titleMap = { latest: 'Latest Videos', 'top-weekly': 'Hot This Week', 'top-monthly': 'Hot This Month', 'top-rated': 'Top Rated', 'most-popular': 'Most Popular' };
        document.getElementById('grid-title').textContent = `${state.currentCategory.charAt(0).toUpperCase() + state.currentCategory.slice(1)} — ${titleMap[state.currentOrder] || 'Videos'}`;
        renderGrid(videos, !reset);
        // Update hasMore flag for infinite scroll
        state.hasMore = state.allVideos.length < state.totalVideos;
    } catch(e) { console.error(e); showToast('Failed to load videos.', 'error'); }
    spinner.classList.add('hidden');
    endProgress();
    state.isLoading = false;
}

async function fetchTrending() {
    try {
        const r = await fetch('/api/trending');
        const data = await r.json();
        renderTrending(data.videos || []);
    } catch(e) {
        document.getElementById('trending-section').style.display = 'none';
    }
}

// Infinite scroll - called by IntersectionObserver
function loadMoreInfinite() {
    if (!state.hasMore || state.isLoading) return;
    state.currentPage++;
    fetchVideos(false);
    document.getElementById('trending-section').style.display = 'none';
}

// Setup IntersectionObserver for infinite scroll
function setupInfiniteScroll() {
    const sentinel = document.getElementById('scroll-sentinel');
    if (!sentinel) return;
    const observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) loadMoreInfinite();
    }, { rootMargin: '200px' }); // trigger 200px before sentinel is visible
    observer.observe(sentinel);
}

// ===== RENDER =====
function renderGrid(videos, append = false) {
    const grid = document.getElementById('main-grid');
    if (!append) grid.innerHTML = '';
    if (!videos.length && !append) {
        grid.innerHTML = `<div style="grid-column:1/-1" class="no-results"><i class="fa fa-video-slash"></i><p>No videos found. Try a different search.</p></div>`;
        return;
    }
    videos.forEach((v, i) => {
        const isFav = state.favorites.has(v.id);
        const card = document.createElement('div');
        card.className = 'video-card';
        card.style.animationDelay = `${(i % 12) * 30}ms`;
        const safeV = JSON.stringify(v).replace(/\\/g,'\\\\').replace(/'/g,"\\'");
        card.innerHTML = `
            <div class="thumb-wrap">
                <img
                    src="${v.poster}"
                    alt=""
                    class="loading-img"
                    loading="lazy"
                    onload="this.classList.remove('loading-img')"
                    onerror="this.classList.remove('loading-img'); this.src='data:image/svg+xml,%3Csvg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'320\\' height=\\'180\\'%3E%3Crect width=\\'320\\' height=\\'180\\' fill=\\'%23181818\\'/%3E%3Ctext x=\\'50%25\\' y=\\'50%25\\' fill=\\'%23333\\' text-anchor=\\'middle\\' dy=\\'.3em\\' font-size=\\'12\\'%3ENo Image%3C/text%3E%3C/svg%3E'">
                <div class="overlay"><div class="play-icon"><i class="fa fa-play"></i></div></div>
                <div class="duration-badge">${v.duration} min</div>
                ${v.is_vr ? '<div class="vr-badge">VR</div>' : ''}
                <button class="fav-btn ${isFav ? 'favorited' : ''}" onclick="event.stopPropagation(); quickFav(event, '${v.id}')" title="Favorite">
                    <i class="fa${isFav ? '-solid' : '-regular'} fa-heart"></i>
                </button>
            </div>
            <div class="card-info">
                <div class="card-title">${escHtml(v.title)}</div>
                <div class="card-meta">
                    <span class="card-rating">★ ${v.rating}</span>
                    <span class="card-views">${formatNum(v.views)} views</span>
                    ${v.categories[0] ? `<span class="card-cat">${escHtml(v.categories[0])}</span>` : ''}
                </div>
            </div>
        `;
        card.onclick = () => openPlayer(v);
        grid.appendChild(card);
    });
}

function renderTrending(videos) {
    const scroll = document.getElementById('trending-scroll');
    if (!videos.length) { document.getElementById('trending-section').style.display = 'none'; return; }
    scroll.innerHTML = videos.slice(0, 12).map(v => `
        <div class="trending-card" onclick="openPlayer(${JSON.stringify(v).replace(/'/g,"&apos;")})">
            <div class="tc-thumb">
                <img src="${v.poster}" alt="${escHtml(v.title)}" loading="lazy">
                <div class="tc-duration">${v.duration}m</div>
            </div>
            <div class="tc-title">${escHtml(v.title)}</div>
            <div class="tc-meta">★ ${v.rating} · ${formatNum(v.views)} views</div>
        </div>
    `).join('');
    document.getElementById('trending-section').style.display = '';
}

// ===== PLAYER =====
function openPlayer(video) {
    state.currentVideo = video;
    document.getElementById('player-header-title').textContent = video.title;
    document.getElementById('player-title').textContent = video.title;
    document.getElementById('main-iframe').src = video.embed_url;
    
    // Meta
    document.getElementById('player-meta').innerHTML = `
        <div class="meta-chip"><i class="fa fa-star"></i>${video.rating} Rating</div>
        <div class="meta-chip"><i class="fa fa-eye"></i>${formatNum(video.views)} Views</div>
        <div class="meta-chip"><i class="fa fa-clock"></i>${video.duration} min</div>
        ${video.is_vr ? '<div class="meta-chip"><i class="fa fa-vr-cardboard"></i>VR</div>' : ''}
    `;
    
    // Tags
    document.getElementById('player-tags').innerHTML = (video.categories || []).filter(Boolean).map(c =>
        `<span class="tag" onclick="setCategory('${escHtml(c.trim())}', null); closePlayer()">${escHtml(c.trim())}</span>`
    ).join('');
    
    // Fav state
    const favBtn = document.getElementById('player-fav-btn');
    favBtn.className = 'player-fav-btn' + (state.favorites.has(video.id) ? ' fav-active' : '');
    
    // Show
    const modal = document.getElementById('player-modal');
    modal.style.display = 'block';
    modal.scrollTop = 0;
    window.location.hash = 'watch';
    
    // History
    addHistory(video);
    
    // Related
    fetchRelated(video.categories[0] || state.currentCategory);
}

async function fetchRelated(query) {
    const grid = document.getElementById('related-grid');
    grid.innerHTML = '<div class="spinner-wrap" style="grid-column:1/-1"><div class="spinner"></div></div>';
    try {
        // Fetch two pages of related in parallel for more variety
        const [r1, r2] = await Promise.all([
            fetch(`/api/related?q=${encodeURIComponent(query)}&page=1`),
            fetch(`/api/related?q=${encodeURIComponent(query)}&page=2`)
        ]);
        const [d1, d2] = await Promise.all([r1.json(), r2.json()]);
        const currentId = (state.currentVideo || {}).id;
        const seen = new Set([currentId]);
        const combined = [...(d1.videos || []), ...(d2.videos || [])].filter(v => {
            if (seen.has(v.id)) return false;
            seen.add(v.id);
            return true;
        }).slice(0, 18);
        if (!combined.length) {
            grid.innerHTML = '<p style="color:var(--text-muted);grid-column:1/-1;padding:20px;text-align:center">No related videos found.</p>';
            return;
        }
        grid.innerHTML = combined.map(v => `
            <div class="video-card" onclick="openRelated(${JSON.stringify(v).replace(/"/g,'&quot;')})">
                <div class="thumb-wrap">
                    <img src="${v.poster}" class="loading-img" loading="lazy" onload="this.classList.remove('loading-img')" onerror="this.classList.remove('loading-img')">
                    <div class="overlay"><div class="play-icon"><i class="fa fa-play"></i></div></div>
                    <div class="duration-badge">${v.duration}m</div>
                </div>
                <div class="card-info">
                    <div class="card-title">${escHtml(v.title)}</div>
                    <div class="card-meta"><span class="card-rating">★ ${v.rating}</span><span class="card-views">${formatNum(v.views)}v</span></div>
                </div>
            </div>
        `).join('');
    } catch(e) { grid.innerHTML = '<p style="color:var(--text-muted);grid-column:1/-1;padding:20px;text-align:center">Could not load related.</p>'; }
}

function openRelated(video) {
    // Open related video - scroll player back to top
    openPlayer(video);
    document.getElementById('player-modal').scrollTop = 0;
}

function closePlayer() {
    document.getElementById('player-modal').style.display = 'none';
    document.getElementById('main-iframe').src = 'about:blank';
    state.currentVideo = null;
    if (location.hash === '#watch') history.back();
}

function onHashChange() {
    if (location.hash !== '#watch') {
        if (document.getElementById('player-modal').style.display !== 'none') {
            document.getElementById('player-modal').style.display = 'none';
            document.getElementById('main-iframe').src = 'about:blank';
        }
    }
}

// ===== FAVORITES =====
async function quickFav(e, videoId) {
    if (!state.user) { showToast('Sign in to save favorites.', 'error'); showAuthModal('login'); return; }
    const video = state.allVideos.find(v => v.id == videoId) || state.currentVideo;
    if (!video) return;
    try {
        const r = await fetch('/api/favorites', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video })
        });
        const data = await r.json();
        const btn = e.target.closest('.fav-btn');
        if (data.favorited) {
            state.favorites.add(videoId);
            if (btn) { btn.classList.add('favorited'); btn.querySelector('i').className = 'fa-solid fa-heart'; }
            showToast('Added to favorites ❤️');
        } else {
            state.favorites.delete(videoId);
            if (btn) { btn.classList.remove('favorited'); btn.querySelector('i').className = 'fa-regular fa-heart'; }
            showToast('Removed from favorites');
        }
    } catch(e) { showToast('Error updating favorites.', 'error'); }
}

async function togglePlayerFav() {
    if (!state.user) { showToast('Sign in to save favorites.', 'error'); showAuthModal('login'); return; }
    if (!state.currentVideo) return;
    const video = state.currentVideo;
    try {
        const r = await fetch('/api/favorites', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video })
        });
        const data = await r.json();
        const btn = document.getElementById('player-fav-btn');
        if (data.favorited) {
            state.favorites.add(video.id);
            btn.className = 'player-fav-btn fav-active';
            showToast('Added to favorites ❤️');
        } else {
            state.favorites.delete(video.id);
            btn.className = 'player-fav-btn';
            showToast('Removed from favorites');
        }
    } catch(e) { showToast('Error.', 'error'); }
}

async function loadFavoritesPage() {
    const grid = document.getElementById('fav-grid');
    const empty = document.getElementById('fav-empty');
    if (!state.user) { grid.innerHTML = ''; empty.classList.remove('hidden'); return; }
    try {
        const r = await fetch('/api/favorites');
        const data = await r.json();
        const favs = data.videos || [];
        if (!favs.length) { grid.innerHTML = ''; empty.classList.remove('hidden'); return; }
        empty.classList.add('hidden');
        grid.innerHTML = favs.map(v => `
            <div class="video-card" onclick="openPlayer(${JSON.stringify(v).replace(/'/g,"&apos;").replace(/"/g,'&quot;')})">
                <div class="thumb-wrap">
                    <img src="${v.poster}" loading="lazy">
                    <div class="overlay"><div class="play-icon"><i class="fa fa-play"></i></div></div>
                    <div class="duration-badge">${v.duration}m</div>
                </div>
                <div class="card-info">
                    <div class="card-title">${escHtml(v.title)}</div>
                    <div class="card-meta"><span class="card-rating">★ ${v.rating}</span><span class="card-views">${formatNum(v.views)}v</span></div>
                </div>
            </div>
        `).join('');
    } catch(e) { console.error(e); }
}

async function loadHistoryPage() {
    const grid = document.getElementById('hist-grid');
    const empty = document.getElementById('hist-empty');
    try {
        const r = await fetch('/api/history');
        const data = await r.json();
        const hist = data.videos || [];
        if (!hist.length) { grid.innerHTML = ''; empty.classList.remove('hidden'); return; }
        empty.classList.add('hidden');
        grid.innerHTML = hist.map(v => `
            <div class="video-card" onclick="openPlayer(${JSON.stringify(v).replace(/'/g,"&apos;").replace(/"/g,'&quot;')})">
                <div class="thumb-wrap">
                    <img src="${v.poster}" loading="lazy">
                    <div class="overlay"><div class="play-icon"><i class="fa fa-play"></i></div></div>
                    <div class="duration-badge">${v.duration}m</div>
                </div>
                <div class="card-info">
                    <div class="card-title">${escHtml(v.title)}</div>
                    <div class="card-meta"><span class="card-rating">★ ${v.rating}</span><span class="card-views">${formatNum(v.views)}v</span></div>
                </div>
            </div>
        `).join('');
    } catch(e) { console.error(e); }
}

async function addHistory(video) {
    try {
        await fetch('/api/history', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video })
        });
    } catch(e) {}
}

// ===== CATEGORY / SORT / SEARCH =====
function setCategory(cat, btn) {
    state.currentCategory = cat;
    document.querySelectorAll('.cat-pill').forEach(p => p.classList.remove('active'));
    if (btn) btn.classList.add('active');
    document.getElementById('search-input').value = '';
    document.getElementById('trending-section').style.display = cat === state.currentCategory ? '' : 'none';
    fetchVideos(true);
    showSection('main');
}

function setSort(order, btn) {
    state.currentOrder = order;
    document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    fetchVideos(true);
}

function debounceSearch(val) {
    clearTimeout(state.searchTimeout);
    if (val.length < 2) return;
    state.searchTimeout = setTimeout(() => {
        state.currentCategory = val;
        document.querySelectorAll('.cat-pill').forEach(p => p.classList.remove('active'));
        document.getElementById('trending-section').style.display = 'none';
        fetchVideos(true);
    }, 500);
}

// ===== UTILS =====
function formatNum(n) {
    if (!n) return '0';
    n = parseInt(n);
    if (n >= 1000000) return (n/1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n/1000).toFixed(1) + 'K';
    return n.toString();
}
function escHtml(s) {
    if (!s) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#x27;');
}

function toggleTheme() {
    // Simple dark theme toggle (already dark by default)
    showToast('Dark theme is on by default for the best experience.');
}

// ===== START =====
window.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>
"""

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, threaded=True)
