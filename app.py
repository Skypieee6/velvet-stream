import threading, requests, json, os, random
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template_string, jsonify, Response, request

app = Flask(__name__)

# --- CONFIGURATION ---
data_lock = threading.Lock()
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- BACKEND ---
def fetch_single_page(query, page_num):
    try:
        # Fetching 100 videos per page
        url = f'https://www.eporner.com/api/v2/video/search/?query={query}&per_page=100&page={page_num}&format=json'
        r = requests.get(url, headers=HEADERS, timeout=5)
        if r.status_code == 200:
            return r.json().get('videos', [])
    except:
        pass
    return []

def load_content(query="korean"):
    all_videos = []
    # Fetch 5 pages (500 videos) in parallel for speed
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = executor.map(lambda p: fetch_single_page(query, p), range(1, 6))
        for video_list in futures:
            if video_list:
                for v in video_list:
                    all_videos.append({
                        "id": v['id'],
                        "title": v['title'],
                        "poster": v['default_thumb']['src'], 
                        "rating": v['rate'],
                        "categories": v['keywords'].split(',')[:2], 
                        "overview": f"{v['length_min']} min",
                        "embed_url": v['embed'] 
                    })
    # Shuffle the list so every refresh looks "New"
    random.shuffle(all_videos)
    return all_videos

# --- FRONTEND TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#000000">
    <title>Velvet | Premium Streaming</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    
    <script src="https://pl28556403.effectivegatecpm.com/4c/f8/8e/4cf88e1f5990dbbeafba4a2cbe51afeb.js"></script>
    <style>
        * { -webkit-tap-highlight-color: transparent; }
        body { background: #000; color: #fce7f3; font-family: -apple-system, BlinkMacSystemFont, Roboto, sans-serif; overflow-x: hidden; user-select: none; padding-bottom: 80px; }
        ::-webkit-scrollbar { display: none; }
        .hidden { display: none !important; }
        .nav-active { color: #db2777; border-bottom: 2px solid #db2777; }
        .spinner { border: 3px solid rgba(255, 255, 255, 0.1); border-left-color: #db2777; border-radius: 50%; width: 30px; height: 30px; animation: spin 0.6s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .refresh-btn { position: fixed; bottom: 85px; right: 20px; background: #db2777; color: white; width: 55px; height: 55px; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 15px rgba(219, 39, 119, 0.5); z-index: 900; cursor: pointer; border: 2px solid rgba(255,255,255,0.2); transition: transform 0.2s; }
        .refresh-btn:active { transform: scale(0.9) rotate(90deg); }
        #age-gate { position: fixed; inset: 0; background: #000; z-index: 99999; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 20px; }
        .enter-btn { background: #db2777; color: white; padding: 15px 40px; border-radius: 50px; font-weight: bold; font-size: 18px; text-transform: uppercase; margin-top: 20px; box-shadow: 0 0 20px rgba(219, 39, 119, 0.6); }
    </style>
</head>
<body>

    <div id="age-gate">
        <div class="text-pink-600 text-6xl mb-4"><i class="fa fa-exclamation-triangle"></i></div>
        <h1 class="text-3xl font-black text-white mb-2">AGE VERIFICATION</h1>
        <p class="text-zinc-400 text-sm max-w-xs mb-8">Strictly 18+ content only.</p>
        <button onclick="enterSite()" class="enter-btn">I am 18+</button>
    </div>

    <div onclick="manualRefresh()" class="refresh-btn">
        <i class="fa fa-sync-alt text-xl"></i>
    </div>

    <div class="w-full h-[50px] flex items-center justify-center bg-zinc-900/50">
        <script type="text/javascript">
            atOptions = {'key' : 'cfe6cbc6aec619a6b7586f34fd279feb','format' : 'iframe','height' : 50,'width' : 320,'params' : {}};
        </script>
        <script type="text/javascript" src="https://www.highperformanceformat.com/cfe6cbc6aec619a6b7586f34fd279feb/invoke.js"></script>
    </div>

    <header class="sticky top-0 bg-black/95 z-[100] border-b border-white/10 backdrop-blur-md">
        <div class="flex items-center justify-between p-4">
            <div class="flex items-center gap-2"><i class="fa fa-fire text-pink-600 text-xl"></i><h1 class="font-black text-xl tracking-tighter text-white">VELVET</h1></div>
            <div class="relative w-1/2">
                <i class="fa fa-search absolute left-3 top-2.5 text-pink-600/50 text-xs"></i>
                <input type="text" id="search-input" onchange="searchCustom()" placeholder="Search..." class="w-full bg-zinc-900 rounded-full py-2 pl-9 pr-4 text-xs text-white outline-none focus:ring-1 focus:ring-pink-600">
            </div>
        </div>
        <div id="cat-bar" class="flex space-x-4 overflow-x-auto text-[11px] font-bold text-zinc-500 whitespace-nowrap uppercase tracking-wide px-4 pb-3">
            <span onclick="setTab('korean', this)" class="cursor-pointer nav-active text-pink-500">Korean</span>
            <span onclick="setTab('japanese', this)" class="cursor-pointer">Japanese</span>
            <span onclick="setTab('trending', this)" class="cursor-pointer">Trending</span>
            <span onclick="setTab('amateur', this)" class="cursor-pointer">Amateur</span>
            <span onclick="setTab('hentai', this)" class="cursor-pointer">Hentai</span>
            <span onclick="setTab('milf', this)" class="cursor-pointer">MILF</span>
            <span onclick="setTab('vr', this)" class="cursor-pointer">VR</span>
        </div>
    </header>

    <div id="section-home" class="min-h-screen">
        <div id="grid-home" class="p-4 grid grid-cols-2 gap-3"></div>
        <div id="loading-spinner" class="flex justify-center p-10 hidden"><div class="spinner"></div></div>
    </div>

    <div class="fixed bottom-0 w-full h-[60px] bg-black border-t border-zinc-800 z-[200] flex justify-center items-center">
        <script type="text/javascript">
            atOptions = {'key' : 'cfe6cbc6aec619a6b7586f34fd279feb','format' : 'iframe','height' : 50,'width' : 320,'params' : {}};
        </script>
        <script type="text/javascript" src="https://www.highperformanceformat.com/cfe6cbc6aec619a6b7586f34fd279feb/invoke.js"></script>
    </div>

    <div id="section-player" class="hidden fixed inset-0 bg-black z-[500] overflow-y-auto pb-20">
        <div class="relative w-full aspect-video bg-black sticky top-0 z-50">
            <iframe id="v-frame" class="w-full h-full border-0" allow="autoplay; fullscreen" allowfullscreen></iframe>
            <div onclick="closePlayer()" class="absolute top-4 left-4 bg-black/60 text-white p-2 w-8 h-8 flex items-center justify-center rounded-full z-[60]"><i class="fa fa-chevron-left text-xs"></i></div>
        </div>
        <div class="p-5">
            <h1 id="play-title" class="text-lg font-bold text-white leading-tight mb-2"></h1>
            <p id="play-desc" class="text-xs text-zinc-400"></p>
            <div class="w-full h-[250px] mt-6 flex justify-center items-center bg-zinc-900/30 rounded-lg">
                <script type="text/javascript">
                    atOptions = {'key' : '0c49e0fbba461d3918166ddb70fd0ba8','format' : 'iframe','height' : 250,'width' : 300,'params' : {}};
                </script>
                <script type="text/javascript" src="https://www.highperformanceformat.com/0c49e0fbba461d3918166ddb70fd0ba8/invoke.js"></script>
            </div>
        </div>
    </div>

    <script>
        let allData = [];
        let currentCategory = 'korean';

        function enterSite() {
            sessionStorage.setItem('velvet_verified', 'true');
            document.getElementById('age-gate').style.display = 'none';
        }

        if(sessionStorage.getItem('velvet_verified') === 'true') {
            document.getElementById('age-gate').style.display = 'none';
        }

        async function fetchCategory(cat) {
            currentCategory = cat;
            document.getElementById('grid-home').innerHTML = "";
            document.getElementById('loading-spinner').classList.remove('hidden');
            try {
                const r = await fetch(`/api/data?q=${cat}`);
                allData = await r.json();
                renderGrid(allData);
            } catch(e) { console.error(e); }
            document.getElementById('loading-spinner').classList.add('hidden');
        }

        function manualRefresh() {
            document.querySelector('.refresh-btn i').classList.add('fa-spin');
            // Shuffle current data for "instant" feel
            allData = allData.sort(() => Math.random() - 0.5);
            renderGrid(allData);
            setTimeout(() => document.querySelector('.refresh-btn i').classList.remove('fa-spin'), 600);
        }

        function renderGrid(data) {
            document.getElementById('grid-home').innerHTML = data.map(i => `
                <div onclick="openPlayer('${i.id}')" class="relative group cursor-pointer active:scale-95 transition">
                    <img src="${i.poster}" class="rounded-lg aspect-[2/3] object-cover bg-zinc-900 w-full">
                    <div class="mt-2"><h3 class="text-sm font-bold text-white truncate">${i.title}</h3></div>
                    <div class="absolute top-2 right-2 bg-black/60 px-2 py-0.5 rounded text-[10px] font-bold text-pink-500">★ ${i.rating}</div>
                </div>`).join('');
        }

        function openPlayer(id) {
            const item = allData.find(i=>i.id==id);
            document.getElementById('play-title').innerText = item.title;
            document.getElementById('play-desc').innerText = item.overview;
            document.getElementById('v-frame').src = item.embed_url; 
            window.location.hash = 'watch';
            document.getElementById('section-player').classList.remove('hidden');
        }

        function closePlayer() {
            if (location.hash === '#watch') history.back();
            else {
                document.getElementById('section-player').classList.add('hidden');
                document.getElementById('v-frame').src = "";
            }
        }

        window.addEventListener('hashchange', () => {
            if (location.hash !== '#watch') {
                document.getElementById('section-player').classList.add('hidden');
                document.getElementById('v-frame').src = "";
            }
        });

        function setTab(cat, btn) {
            document.querySelectorAll('#cat-bar span').forEach(s => s.classList.remove('nav-active', 'text-pink-500'));
            btn.classList.add('nav-active', 'text-pink-500');
            fetchCategory(cat);
        }

        function searchCustom() {
            const q = document.getElementById('search-input').value;
            if(q.length > 2) fetchCategory(q);
        }

        fetchCategory('korean');
    </script>
</body>
</html>
"""

@app.route('/api/data')
def get_data():
    category = request.args.get('q', 'korean')
    with data_lock:
        return jsonify(load_content(category))

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Updated to port 8000 for Koyeb compatibility
    app.run(host='0.0.0.0', port=8000, threaded=True)
