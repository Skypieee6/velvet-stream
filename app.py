import threading
import requests
import json
import os
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template_string, jsonify, request
from datetime import datetime

app = Flask(__name__)

# --- CONFIGURATION ---
data_lock = threading.Lock()
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
CACHE_DURATION = 300  # 5 minutes cache

# Simple cache implementation
cache = {}
cache_timestamps = {}

# --- BACKEND ---
def fetch_single_page(query, page_num):
    try:
        url = f'https://www.eporner.com/api/v2/video/search/?query={query}&per_page=100&page={page_num}&format=json'
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r.json().get('videos', [])
        else:
            print(f"API returned status {r.status_code} for {url}")
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return []

def load_content(query="korean", force_refresh=False):
    cache_key = f"content_{query}"
    
    # Check cache first
    if not force_refresh and cache_key in cache:
        if datetime.now().timestamp() - cache_timestamps[cache_key] < CACHE_DURATION:
            return cache[cache_key]
    
    all_videos = []
    print(f"Fetching content for query: {query}")
    
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = executor.map(lambda p: fetch_single_page(query, p), range(1, 4))  # Reduced to 3 pages
            for video_list in futures:
                if video_list:
                    for v in video_list:
                        # Validate embed URL
                        embed_url = v.get('embed', '')
                        if not embed_url.startswith('http'):
                            embed_url = f"https://www.eporner.com/embed/{v['id']}"
                        
                        all_videos.append({
                            "id": v['id'],
                            "title": v['title'],
                            "poster": v['default_thumb']['src'],
                            "rating": v['rate'],
                            "categories": v['keywords'].split(',')[:2] if 'keywords' in v else [],
                            "overview": f"{v['length_min']} min • {v['views']} views",
                            "embed_url": embed_url,
                            "added": v.get('added', ''),
                            "views": v.get('views', 0)
                        })
        
        # Update cache
        with data_lock:
            cache[cache_key] = all_videos
            cache_timestamps[cache_key] = datetime.now().timestamp()
            
        print(f"Loaded {len(all_videos)} videos for '{query}'")
        
    except Exception as e:
        print(f"Error in load_content: {e}")
        # Return cached data if available, even if stale
        if cache_key in cache:
            return cache[cache_key]
    
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
    
    <!-- AD SCRIPTS (Only in non-critical areas) -->
    <script>
        // Load ads after page is ready
        document.addEventListener('DOMContentLoaded', function() {
            // Top banner ad
            setTimeout(() => {
                const topAdScript = document.createElement('script');
                topAdScript.type = 'text/javascript';
                topAdScript.innerHTML = `
                    atOptions = {
                        'key' : '9b5a73fe92b9613d4ea6430a59a86eea',
                        'format' : 'iframe',
                        'height' : 50,
                        'width' : 320,
                        'params' : {}
                    };
                `;
                document.head.appendChild(topAdScript);
                
                const topAdInvoke = document.createElement('script');
                topAdInvoke.src = 'https://www.highperformanceformat.com/9b5a73fe92b9613d4ea6430a59a86eea/invoke.js';
                topAdInvoke.async = true;
                document.head.appendChild(topAdInvoke);
            }, 1000);
        });
    </script>

    <style>
        * { -webkit-tap-highlight-color: transparent; }
        body { background: #000; color: #fce7f3; font-family: -apple-system, BlinkMacSystemFont, Roboto, sans-serif; overflow-x: hidden; user-select: none; padding-bottom: 80px; }
        ::-webkit-scrollbar { display: none; }
        .hidden { display: none !important; }
        .nav-active { color: #db2777; border-bottom: 2px solid #db2777; }
        .spinner { border: 3px solid rgba(255, 255, 255, 0.1); border-left-color: #db2777; border-radius: 50%; width: 30px; height: 30px; animation: spin 0.6s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .refresh-btn { position: fixed; bottom: 80px; right: 20px; background: #db2777; color: white; width: 50px; height: 50px; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 15px rgba(219, 39, 119, 0.5); z-index: 900; cursor: pointer; border: 2px solid rgba(255,255,255,0.2); }
        .refresh-btn:active { transform: scale(0.9); }
        #age-gate { position: fixed; inset: 0; background: #000; z-index: 99999; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 20px; }
        .enter-btn { background: #db2777; color: white; padding: 15px 40px; border-radius: 50px; font-weight: bold; font-size: 18px; text-transform: uppercase; margin-top: 20px; box-shadow: 0 0 20px rgba(219, 39, 119, 0.6); }
        .debug-panel { background: rgba(0, 0, 0, 0.9); border: 1px solid #333; border-radius: 10px; padding: 15px; margin-top: 15px; font-size: 12px; }
        .url-display { background: #111; padding: 8px; border-radius: 5px; font-family: monospace; word-break: break-all; margin: 5px 0; }
        .status-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px; margin-left: 10px; }
        .status-ok { background: #10b981; color: white; }
        .status-error { background: #ef4444; color: white; }
        .status-loading { background: #f59e0b; color: white; }
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

    <!-- Top Banner Ad Slot -->
    <div class="w-full h-[50px] bg-black border-b border-zinc-800 flex items-center justify-center overflow-hidden" id="top-banner">
        <div class="text-zinc-600 text-sm">Ad loading...</div>
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
            <span onclick="setTab('amateur', this)" class="cursor-pointer">Amateur</span>
            <span onclick="setTab('hentai', this)" class="cursor-pointer">Hentai</span>
            <span onclick="setTab('milf', this)" class="cursor-pointer">MILF</span>
            <span onclick="setTab('asian', this)" class="cursor-pointer">Asian</span>
            <span onclick="setTab('vr', this)" class="cursor-pointer">VR</span>
            <span onclick="setTab('blonde', this)" class="cursor-pointer">Blonde</span>
            <span onclick="setTab('latina', this)" class="cursor-pointer">Latina</span>
            <span onclick="setTab('pov', this)" class="cursor-pointer">POV</span>
        </div>
    </header>

    <div id="section-home" class="min-h-screen">
        <div id="grid-home" class="p-4 grid grid-cols-2 gap-3"></div>
        <div id="loading-spinner" class="flex justify-center p-10 hidden"><div class="spinner"></div></div>
    </div>

    <!-- Bottom Ad Slot -->
    <div class="fixed bottom-0 w-full h-[60px] bg-black border-t border-zinc-800 z-[200] flex items-center justify-center">
        <div class="text-zinc-600 text-sm">Advertisement</div>
    </div>

    <!-- VIDEO PLAYER SECTION (CRITICAL - NO ADS HERE) -->
    <div id="section-player" class="hidden fixed inset-0 bg-black z-[500] overflow-y-auto pb-20">
        <div class="relative w-full aspect-video bg-black sticky top-0 z-50">
            <!-- Video Container -->
            <div id="video-container" class="w-full h-full relative bg-black">
                <iframe 
                    id="v-frame" 
                    class="w-full h-full border-0 absolute inset-0 z-20"
                    allow="autoplay; fullscreen; encrypted-media; picture-in-picture" 
                    allowfullscreen
                    sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
                    referrerpolicy="no-referrer"
                ></iframe>
                
                <!-- Fallback if iframe fails -->
                <div id="video-fallback" class="absolute inset-0 flex flex-col items-center justify-center bg-zinc-900 hidden">
                    <i class="fa fa-exclamation-triangle text-4xl text-yellow-500 mb-4"></i>
                    <p class="text-white mb-2">Video failed to load</p>
                    <button onclick="testEmbedUrl()" class="bg-pink-600 text-white px-4 py-2 rounded text-sm">Test URL</button>
                    <button onclick="closePlayer()" class="bg-zinc-700 text-white px-4 py-2 rounded text-sm mt-2">Close</button>
                </div>
                
                <!-- Loading overlay -->
                <div id="video-loading" class="absolute inset-0 flex items-center justify-center bg-black bg-opacity-80 z-30">
                    <div class="spinner"></div>
                    <span class="ml-3 text-white">Loading player...</span>
                </div>
            </div>
            
            <!-- Close button -->
            <div onclick="closePlayer()" class="absolute top-4 left-4 bg-black/60 text-white p-2 w-8 h-8 flex items-center justify-center rounded-full cursor-pointer z-[60] active:scale-90 transition">
                <i class="fa fa-chevron-left text-xs"></i>
            </div>
            
            <!-- Debug button -->
            <div onclick="toggleDebug()" class="absolute top-4 right-4 bg-black/60 text-white p-2 w-8 h-8 flex items-center justify-center rounded-full cursor-pointer z-[60] active:scale-90 transition">
                <i class="fa fa-bug text-xs"></i>
            </div>
        </div>
        
        <!-- Video Info -->
        <div class="p-5">
            <h1 id="play-title" class="text-lg font-bold text-white leading-tight mb-2"></h1>
            <p id="play-desc" class="text-xs text-zinc-400 mb-4"></p>
            <div id="debug-info" class="hidden"></div>
            
            <!-- DEBUG PANEL -->
            <div id="debug-panel" class="debug-panel hidden">
                <h3 class="text-white font-bold mb-2">Debug Information</h3>
                <p class="text-zinc-400 text-xs mb-2">Embed URL:</p>
                <div id="debug-url" class="url-display"></div>
                
                <div class="flex gap-2 mt-3">
                    <button onclick="testEmbedUrl()" class="bg-blue-600 text-white px-3 py-1 rounded text-xs">Test URL in New Tab</button>
                    <button onclick="copyEmbedUrl()" class="bg-zinc-700 text-white px-3 py-1 rounded text-xs">Copy URL</button>
                    <button onclick="reloadIframe()" class="bg-green-600 text-white px-3 py-1 rounded text-xs">Reload Player</button>
                </div>
                
                <div class="mt-3">
                    <label class="text-zinc-400 text-xs">Player Status:</label>
                    <span id="player-status" class="status-badge status-loading">Loading</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        let allData = [];
        let currentCategory = 'korean';
        let currentEmbedUrl = '';
        let debugMode = false;

        function manualRefresh() {
            document.querySelector('.refresh-btn i').classList.add('fa-spin');
            fetchCategory(currentCategory, true);
        }

        function checkAge() {
            if(sessionStorage.getItem('velvet_age_verified_v2') === 'true') {
                document.getElementById('age-gate').style.display = 'none';
            }
        }
        
        function enterSite() {
            sessionStorage.setItem('velvet_age_verified_v2', 'true');
            document.getElementById('age-gate').style.display = 'none';
        }

        async function fetchCategory(cat, forceRefresh = false) {
            currentCategory = cat;
            document.getElementById('grid-home').innerHTML = "";
            document.getElementById('loading-spinner').classList.remove('hidden');
            
            try {
                const url = forceRefresh ? `/api/data?q=${cat}&refresh=true` : `/api/data?q=${cat}`;
                const r = await fetch(url);
                allData = await r.json();
                renderGrid(allData);
            } catch(e) { 
                console.error('Fetch error:', e);
                document.getElementById('grid-home').innerHTML = `
                    <div class="col-span-2 text-center p-10">
                        <i class="fa fa-wifi text-4xl text-zinc-600 mb-3"></i>
                        <p class="text-zinc-400">Failed to load content</p>
                        <button onclick="fetchCategory('${cat}', true)" class="bg-pink-600 text-white px-4 py-2 rounded mt-4">Retry</button>
                    </div>
                `;
            }
            
            document.getElementById('loading-spinner').classList.add('hidden');
            document.querySelector('.refresh-btn i').classList.remove('fa-spin');
        }

        function setTab(cat, btn) {
            document.querySelectorAll('#cat-bar span').forEach(s => { 
                s.classList.remove('nav-active', 'text-pink-500'); 
            });
            btn.classList.add('nav-active', 'text-pink-500');
            fetchCategory(cat);
        }

        function searchCustom() {
            const q = document.getElementById('search-input').value.trim();
            if(q.length > 1) {
                document.querySelectorAll('#cat-bar span').forEach(s => { 
                    s.classList.remove('nav-active', 'text-pink-500'); 
                });
                fetchCategory(q);
            }
        }

        function renderGrid(data) {
            if(data.length === 0) {
                document.getElementById('grid-home').innerHTML = `
                    <div class="col-span-2 text-center p-10">
                        <i class="fa fa-film text-4xl text-zinc-600 mb-3"></i>
                        <p class="text-zinc-400">No videos found</p>
                    </div>
                `;
                return;
            }
            
            document.getElementById('grid-home').innerHTML = data.map(i => `
                <div onclick="openPlayer('${i.id}')" class="relative group cursor-pointer active:opacity-80">
                    <img src="${i.poster}" alt="${i.title}" class="rounded-lg aspect-[2/3] object-cover bg-zinc-900 w-full" onerror="this.src='https://placehold.co/300x450/111/333?text=No+Image'">
                    <div class="mt-2">
                        <h3 class="text-sm font-bold text-white truncate">${i.title}</h3>
                        <p class="text-xs text-zinc-500 mt-1">${i.overview}</p>
                    </div>
                    <div class="absolute top-2 right-2 bg-black/60 px-2 py-0.5 rounded text-[10px] font-bold text-pink-500">★ ${i.rating}</div>
                </div>`).join('');
        }

        function openPlayer(id) {
            const item = allData.find(i => i.id == id);
            if(!item) {
                alert('Video not found');
                return;
            }
            
            currentEmbedUrl = item.embed_url;
            console.log('Opening player with URL:', currentEmbedUrl);
            
            document.getElementById('play-title').innerText = item.title;
            document.getElementById('play-desc').innerText = item.overview;
            
            // Show loading
            document.getElementById('video-loading').classList.remove('hidden');
            document.getElementById('video-fallback').classList.add('hidden');
            
            // Update debug panel
            document.getElementById('debug-url').innerText = currentEmbedUrl;
            updatePlayerStatus('loading');
            
            const frame = document.getElementById('v-frame');
            
            // Clear previous iframe
            frame.src = '';
            
            // Set new source after a brief delay
            setTimeout(() => {
                frame.src = currentEmbedUrl;
                console.log('Iframe source set to:', currentEmbedUrl);
                
                // Set timeout for iframe load
                setTimeout(() => {
                    if(frame.contentWindow && frame.contentWindow.document) {
                        updatePlayerStatus('loaded');
                        document.getElementById('video-loading').classList.add('hidden');
                    } else {
                        // Check if iframe loaded properly
                        frame.onload = function() {
                            updatePlayerStatus('loaded');
                            document.getElementById('video-loading').classList.add('hidden');
                        };
                        
                        frame.onerror = function() {
                            updatePlayerStatus('error');
                            document.getElementById('video-loading').classList.add('hidden');
                            document.getElementById('video-fallback').classList.remove('hidden');
                        };
                    }
                }, 2000);
                
            }, 100);
            
            document.getElementById('section-player').classList.remove('hidden');
            
            // Show debug panel if debug mode is on
            if(debugMode) {
                document.getElementById('debug-panel').classList.remove('hidden');
            }
        }

        function closePlayer() {
            const frame = document.getElementById('v-frame');
            frame.src = '';
            document.getElementById('section-player').classList.add('hidden');
            document.getElementById('debug-panel').classList.add('hidden');
            document.getElementById('video-fallback').classList.add('hidden');
            updatePlayerStatus('idle');
        }

        function toggleDebug() {
            debugMode = !debugMode;
            const panel = document.getElementById('debug-panel');
            panel.classList.toggle('hidden');
        }

        function updatePlayerStatus(status) {
            const badge = document.getElementById('player-status');
            badge.className = 'status-badge ';
            
            switch(status) {
                case 'loading':
                    badge.classList.add('status-loading');
                    badge.textContent = 'Loading';
                    break;
                case 'loaded':
                    badge.classList.add('status-ok');
                    badge.textContent = 'Loaded';
                    break;
                case 'error':
                    badge.classList.add('status-error');
                    badge.textContent = 'Error';
                    break;
                case 'idle':
                    badge.classList.add('status-loading');
                    badge.textContent = 'Idle';
                    break;
            }
        }

        function testEmbedUrl() {
            if(currentEmbedUrl) {
                window.open(currentEmbedUrl, '_blank');
            }
        }

        function copyEmbedUrl() {
            if(currentEmbedUrl) {
                navigator.clipboard.writeText(currentEmbedUrl)
                    .then(() => alert('URL copied to clipboard'))
                    .catch(err => console.error('Copy failed:', err));
            }
        }

        function reloadIframe() {
            const frame = document.getElementById('v-frame');
            const currentSrc = frame.src;
            frame.src = '';
            setTimeout(() => {
                frame.src = currentSrc;
                updatePlayerStatus('loading');
                document.getElementById('video-loading').classList.remove('hidden');
            }, 100);
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            if(e.key === 'Escape') {
                closePlayer();
            }
            if(e.key === 'd' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                toggleDebug();
            }
        });

        // Initialize
        fetchCategory('korean');
        checkAge();
    </script>
</body>
</html>
"""

@app.route('/api/data')
def get_data():
    category = request.args.get('q', 'korean')
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    
    with data_lock:
        data = load_content(category, force_refresh)
        return jsonify(data)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/health')
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    print("Starting Velvet Streaming Server...")
    print("Access the site at: http://localhost:8000")
    print("Health check at: http://localhost:8000/health")
    app.run(host='0.0.0.0', port=8000, threaded=True, debug=False)
