import threading, requests, json, os, random
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template_string, jsonify, Response, request

app = Flask(__name__)

data_lock = threading.Lock()
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

def fetch_single_page(query, page_num):
    try:
        url = f'https://www.eporner.com/api/v2/video/search/?query={query}&per_page=100&page={page_num}&format=json'
        r = requests.get(url, headers=HEADERS, timeout=5)
        if r.status_code == 200: return r.json().get('videos', [])
    except: pass
    return []

def load_content(query="korean"):
    all_videos = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = executor.map(lambda p: fetch_single_page(query, p), range(1, 6))
        for video_list in futures:
            if video_list:
                for v in video_list:
                    all_videos.append({"id": v['id'], "title": v['title'], "poster": v['default_thumb']['src'], "rating": v['rate'], "embed_url": v['embed']})
    random.shuffle(all_videos)
    return all_videos

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Velvet | Premium Streaming</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <script src="https://pl28677108.effectivegatecpm.com/d6/80/bf/d680bf022b8cce934cc749d85082a05c.js"></script>
    <style>
        body { background: #000; color: #fce7f3; font-family: sans-serif; overflow-x: hidden; padding-bottom: 80px; }
        ::-webkit-scrollbar { display: none; }
        .nav-active { color: #db2777; border-bottom: 2px solid #db2777; }
        #age-gate { position: fixed; inset: 0; background: #000; z-index: 99999; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
    </style>
</head>
<body>
    <div id="age-gate">
        <button onclick="enterSite()" class="bg-pink-600 text-white px-10 py-4 rounded-full font-bold">I AM 18+</button>
    </div>

    <div class="w-full flex justify-center bg-zinc-900/50 py-1">
        <script type="text/javascript">atOptions={'key':'9b5a73fe92b9613d4ea6430a59a86eea','format':'iframe','height':50,'width':320,'params':{}};</script>
        <script type="text/javascript" src="https://www.highperformanceformat.com/9b5a73fe92b9613d4ea6430a59a86eea/invoke.js"></script>
    </div>

    <header class="sticky top-0 bg-black/95 z-[100] border-b border-white/10 p-4">
        <div class="flex items-center justify-between mb-2">
            <h1 class="font-black text-xl text-white">VELVET</h1>
            <input type="text" id="search-input" onchange="searchCustom()" placeholder="Search..." class="bg-zinc-900 rounded-full px-4 py-1 text-xs text-white outline-none">
        </div>
        <div id="cat-bar" class="flex space-x-4 overflow-x-auto text-[11px] font-bold text-zinc-500 uppercase">
            <span onclick="setTab('korean', this)" class="cursor-pointer nav-active text-pink-500">Korean</span>
            <span onclick="setTab('japanese', this)" class="cursor-pointer">Japanese</span>
            <span onclick="setTab('hentai', this)" class="cursor-pointer">Hentai</span>
        </div>
    </header>

    <div id="section-home">
        <div id="grid-home" class="p-4 grid grid-cols-2 gap-3"></div>
        <div class="flex justify-center p-6"><button id="load-more-btn" onclick="loadMore()" class="bg-zinc-800 text-white px-8 py-2 rounded-full text-xs font-bold">LOAD MORE</button></div>
    </div>

    <div id="section-player" class="hidden fixed inset-0 bg-black z-[500] overflow-y-auto">
        <div class="sticky top-0 z-50 bg-black relative aspect-video">
            <iframe id="v-frame" class="w-full h-full border-0" allow="autoplay; fullscreen" allowfullscreen></iframe>
            <div onclick="closePlayer()" class="absolute top-4 left-4 bg-black/60 text-white p-2 rounded-full"><i class="fa fa-chevron-left"></i></div>
        </div>
        <div class="p-5">
            <h1 id="play-title" class="text-lg font-bold text-white mb-2"></h1>
            <div class="w-full flex justify-center py-4">
                <script type="text/javascript">atOptions={'key':'df5144983cf79f7c44c0f80316b9c61a','format':'iframe','height':250,'width':300,'params':{}};</script>
                <script type="text/javascript" src="https://www.highperformanceformat.com/df5144983cf79f7c44c0f80316b9c61a/invoke.js"></script>
            </div>
            <h2 class="text-pink-500 font-bold uppercase text-xs mt-6 mb-4">Related Videos</h2>
            <div id="grid-related" class="grid grid-cols-2 gap-3"></div>
        </div>
    </div>

    <div class="fixed bottom-0 w-full bg-black border-t border-zinc-800 z-[200] flex justify-center py-1">
        <script type="text/javascript">atOptions={'key':'9b5a73fe92b9613d4ea6430a59a86eea','format':'iframe','height':50,'width':320,'params':{}};</script>
        <script type="text/javascript" src="https://www.highperformanceformat.com/9b5a73fe92b9613d4ea6430a59a86eea/invoke.js"></script>
    </div>

    <script>
        let allData = []; let disp = 20;
        function enterSite() { sessionStorage.setItem('v', '1'); document.getElementById('age-gate').style.display='none'; }
        if(sessionStorage.getItem('v')) document.getElementById('age-gate').style.display='none';

        async function fetchCategory(cat) {
            const r = await fetch(`/api/data?q=${cat}`);
            allData = await r.json(); disp = 20;
            renderGrid(allData.slice(0, disp), 'grid-home');
        }

        function loadMore() { disp += 20; renderGrid(allData.slice(0, disp), 'grid-home'); }

        function renderGrid(data, target) {
            document.getElementById(target).innerHTML = data.map(i => `
                <div onclick="openPlayer('${i.id}')" class="relative cursor-pointer">
                    <img src="${i.poster}" class="rounded-lg aspect-[2/3] object-cover w-full">
                    <h3 class="text-xs font-bold text-white truncate mt-1">${i.title}</h3>
                </div>`).join('');
        }

        function openPlayer(id) {
            const item = allData.find(i=>i.id==id);
            document.getElementById('play-title').innerText = item.title;
            document.getElementById('v-frame').src = item.embed_url; 
            const related = allData.filter(v => v.id !== id).sort(() => 0.5 - Math.random()).slice(0, 10);
            renderGrid(related, 'grid-related');
            window.location.hash = 'watch';
            document.getElementById('section-player').classList.remove('hidden');
        }

        function closePlayer() { if (location.hash === '#watch') history.back(); else document.getElementById('section-player').classList.add('hidden'); }
        window.addEventListener('hashchange', () => { if (location.hash !== '#watch') { document.getElementById('section-player').classList.add('hidden'); document.getElementById('v-frame').src = ""; } });
        function setTab(cat, btn) { document.querySelectorAll('#cat-bar span').forEach(s => s.classList.remove('nav-active', 'text-pink-500')); btn.classList.add('nav-active', 'text-pink-500'); fetchCategory(cat); }
        function searchCustom() { const q = document.getElementById('search-input').value; if(q.length > 2) fetchCategory(q); }
        fetchCategory('korean');
    </script>
</body>
</html>
"""

@app.route('/api/data')
def get_data():
    q = request.args.get('q', 'korean')
    with data_lock: return jsonify(load_content(q))

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, threaded=True)
