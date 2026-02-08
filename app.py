import threading
import requests
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# --- CONFIGURATION ---
data_lock = threading.Lock()
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# --- BACKEND ---
def fetch_single_page(query, page_num):
    """Fetch a single page of videos from the API"""
    try:
        url = f'https://www.eporner.com/api/v2/video/search/?query={query}&per_page=100&page={page_num}&thumbsize=big&format=json'
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get('videos', [])
        else:
            print(f"⚠️ API Error: Status {r.status_code} for {url}")
            return []
    except Exception as e:
        print(f"❌ Fetch error for page {page_num}: {e}")
        return []

def load_content(query="korean"):
    """Load videos for a query - SIMPLIFIED VERSION"""
    all_videos = []
    print(f"🔍 Loading content for: {query}")
    
    # Try to fetch first 2 pages only (for speed)
    try:
        # Try page 1 first
        page1_data = fetch_single_page(query, 1)
        if page1_data:
            for v in page1_data:
                # Ensure we have a valid embed URL
                embed_url = v.get('embed', '')
                if not embed_url.startswith('http'):
                    # Construct embed URL from video ID if needed
                    embed_url = f"https://www.eporner.com/embed/{v['id']}"
                
                all_videos.append({
                    "id": v['id'],
                    "title": v['title'][:80],  # Limit title length
                    "poster": v.get('default_thumb', {}).get('src', ''),
                    "rating": v.get('rate', 'N/A'),
                    "categories": v.get('keywords', '').split(',')[:2],
                    "overview": f"{v.get('length_min', 0)} min",
                    "embed_url": embed_url
                })
            
            print(f"✅ Loaded {len(all_videos)} videos for '{query}'")
        else:
            print(f"⚠️ No data received for '{query}'")
            
    except Exception as e:
        print(f"❌ Critical error loading content: {e}")
        # Return minimal fallback data to prevent complete failure
        all_videos = [{
            "id": "test",
            "title": "Test Video - API may be down",
            "poster": "",
            "rating": "0",
            "categories": ["test"],
            "overview": "0 min",
            "embed_url": "about:blank"
        }]
    
    return all_videos

# --- FRONTEND TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Velvet Stream</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        * { -webkit-tap-highlight-color: transparent; }
        body { background: #000; color: #fff; font-family: sans-serif; }
        .hidden { display: none !important; }
        .nav-active { color: #db2777; border-bottom: 2px solid #db2777; }
        .spinner { border: 3px solid rgba(255,255,255,0.1); border-top: 3px solid #db2777; border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        iframe { background: #000; }
    </style>
</head>
<body>

    <!-- Age Gate -->
    <div id="age-gate" style="position:fixed; inset:0; background:#000; z-index:9999; display:flex; flex-direction:column; align-items:center; justify-content:center;">
        <div style="color:#db2777; font-size:3rem; margin-bottom:1rem;"><i class="fa fa-exclamation-triangle"></i></div>
        <h1 style="font-size:1.5rem; font-weight:bold; margin-bottom:0.5rem;">18+ CONTENT ONLY</h1>
        <p style="color:#888; margin-bottom:2rem;">You must be 18 or older to enter</p>
        <button onclick="enterSite()" style="background:#db2777; color:white; padding:12px 40px; border-radius:25px; font-weight:bold;">ENTER SITE</button>
    </div>

    <!-- Main App -->
    <div id="app" class="hidden">
        <!-- Header -->
        <header style="position:sticky; top:0; background:#111; z-index:100; padding:1rem; border-bottom:1px solid #333;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div style="display:flex; align-items:center; gap:0.5rem;">
                    <i class="fa fa-fire" style="color:#db2777;"></i>
                    <h1 style="font-weight:bold; font-size:1.2rem;">VELVET</h1>
                </div>
                <div style="position:relative; width:50%;">
                    <i class="fa fa-search" style="position:absolute; left:10px; top:10px; color:#666; font-size:0.8rem;"></i>
                    <input id="search-input" type="text" placeholder="Search..." style="width:100%; background:#222; border:none; padding:8px 8px 8px 30px; border-radius:15px; color:white; font-size:0.9rem;" onkeypress="if(event.key=='Enter') searchCustom()">
                </div>
            </div>
            
            <!-- Categories -->
            <div id="cat-bar" style="display:flex; gap:1rem; overflow-x:auto; padding:1rem 0 0 0; font-size:0.8rem; color:#888;">
                <span onclick="setTab('korean', this)" class="nav-active" style="white-space:nowrap; cursor:pointer; padding-bottom:5px;">Korean</span>
                <span onclick="setTab('japanese', this)" style="white-space:nowrap; cursor:pointer; padding-bottom:5px;">Japanese</span>
                <span onclick="setTab('amateur', this)" style="white-space:nowrap; cursor:pointer; padding-bottom:5px;">Amateur</span>
                <span onclick="setTab('hentai', this)" style="white-space:nowrap; cursor:pointer; padding-bottom:5px;">Hentai</span>
                <span onclick="setTab('milf', this)" style="white-space:nowrap; cursor:pointer; padding-bottom:5px;">MILF</span>
            </div>
        </header>

        <!-- Video Grid -->
        <div id="section-home">
            <div id="grid-home" style="padding:1rem; display:grid; grid-template-columns:repeat(2, 1fr); gap:1rem;"></div>
            <div id="loading-spinner" style="padding:2rem; text-align:center;">
                <div class="spinner"></div>
                <p style="margin-top:1rem; color:#888;">Loading videos...</p>
            </div>
        </div>

        <!-- Refresh Button -->
        <div onclick="manualRefresh()" style="position:fixed; bottom:80px; right:20px; background:#db2777; color:white; width:50px; height:50px; border-radius:50%; display:flex; align-items:center; justify-content:center; cursor:pointer; box-shadow:0 4px 10px rgba(219,39,119,0.3);">
            <i class="fa fa-sync-alt"></i>
        </div>

        <!-- Video Player -->
        <div id="section-player" class="hidden" style="position:fixed; inset:0; background:#000; z-index:500;">
            <!-- Close button -->
            <div onclick="closePlayer()" style="position:absolute; top:15px; left:15px; z-index:50; background:rgba(0,0,0,0.7); color:white; width:40px; height:40px; border-radius:50%; display:flex; align-items:center; justify-content:center; cursor:pointer;">
                <i class="fa fa-times"></i>
            </div>
            
            <!-- Video Iframe -->
            <div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center;">
                <iframe id="v-frame" style="width:100%; height:100%; border:none;" allow="autoplay; fullscreen" allowfullscreen></iframe>
            </div>
            
            <!-- Video Info -->
            <div style="position:absolute; bottom:0; left:0; right:0; background:linear-gradient(transparent, #000); padding:2rem 1rem 1rem 1rem;">
                <h1 id="play-title" style="font-weight:bold; font-size:1.2rem;"></h1>
                <p id="play-desc" style="color:#888; margin-top:0.5rem;"></p>
            </div>
        </div>
    </div>

    <script>
        let allData = [];
        let currentCategory = 'korean';

        // Age verification
        function checkAge() {
            if(localStorage.getItem('velvet_age_verified') === 'true') {
                document.getElementById('age-gate').style.display = 'none';
                document.getElementById('app').classList.remove('hidden');
            }
        }
        
        function enterSite() {
            localStorage.setItem('velvet_age_verified', 'true');
            document.getElementById('age-gate').style.display = 'none';
            document.getElementById('app').classList.remove('hidden');
            fetchCategory('korean');
        }

        // Fetch videos
        async function fetchCategory(cat) {
            currentCategory = cat;
            document.getElementById('grid-home').innerHTML = '';
            document.getElementById('loading-spinner').style.display = 'block';
            
            try {
                console.log('Fetching category:', cat);
                const response = await fetch(`/api/data?q=${encodeURIComponent(cat)}`);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                allData = await response.json();
                console.log('Received data:', allData.length, 'videos');
                
                if (allData.length === 0) {
                    document.getElementById('grid-home').innerHTML = `
                        <div style="grid-column:1/-1; text-align:center; padding:3rem;">
                            <i class="fa fa-film" style="font-size:3rem; color:#444; margin-bottom:1rem;"></i>
                            <p style="color:#888;">No videos found for "${cat}"</p>
                        </div>
                    `;
                } else {
                    renderGrid(allData);
                }
                
            } catch (error) {
                console.error('Fetch error:', error);
                document.getElementById('grid-home').innerHTML = `
                    <div style="grid-column:1/-1; text-align:center; padding:3rem;">
                        <i class="fa fa-wifi" style="font-size:3rem; color:#444; margin-bottom:1rem;"></i>
                        <p style="color:#888;">Failed to load content</p>
                        <p style="color:#666; font-size:0.9rem; margin-top:0.5rem;">${error.message}</p>
                        <button onclick="fetchCategory('${cat}')" style="background:#db2777; color:white; padding:8px 20px; border-radius:15px; margin-top:1rem; border:none;">Retry</button>
                    </div>
                `;
            }
            
            document.getElementById('loading-spinner').style.display = 'none';
        }

        // Render video grid
        function renderGrid(data) {
            const grid = document.getElementById('grid-home');
            grid.innerHTML = '';
            
            data.forEach(item => {
                const div = document.createElement('div');
                div.style.cursor = 'pointer';
                div.onclick = () => openPlayer(item.id);
                
                div.innerHTML = `
                    <div style="position:relative;">
                        <img src="${item.poster || ''}" alt="${item.title}" 
                             style="width:100%; aspect-ratio:2/3; object-fit:cover; border-radius:8px; background:#222;"
                             onerror="this.src='data:image/svg+xml,<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 300 450\"><rect width=\"300\" height=\"450\" fill=\"%23222\"/><text x=\"150\" y=\"225\" font-family=\"Arial\" font-size=\"14\" fill=\"%23666\" text-anchor=\"middle\">No Image</text></svg>'">
                        <div style="position:absolute; top:8px; right:8px; background:rgba(0,0,0,0.7); color:#db2777; padding:2px 6px; border-radius:4px; font-size:0.7rem; font-weight:bold;">
                            ★ ${item.rating}
                        </div>
                    </div>
                    <div style="margin-top:8px;">
                        <h3 style="font-weight:bold; font-size:0.9rem; line-height:1.2; overflow:hidden; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;">
                            ${item.title}
                        </h3>
                        <p style="color:#888; font-size:0.8rem; margin-top:2px;">${item.overview}</p>
                    </div>
                `;
                
                grid.appendChild(div);
            });
        }

        // Tab navigation
        function setTab(cat, btn) {
            document.querySelectorAll('#cat-bar span').forEach(span => {
                span.classList.remove('nav-active');
            });
            btn.classList.add('nav-active');
            fetchCategory(cat);
        }

        // Search
        function searchCustom() {
            const query = document.getElementById('search-input').value.trim();
            if (query.length > 1) {
                fetchCategory(query);
            }
        }

        // Video player
        function openPlayer(id) {
            const item = allData.find(i => i.id == id);
            if (!item) return;
            
            console.log('Opening player with URL:', item.embed_url);
            
            document.getElementById('play-title').textContent = item.title;
            document.getElementById('play-desc').textContent = item.overview;
            
            const iframe = document.getElementById('v-frame');
            iframe.src = item.embed_url;
            
            document.getElementById('section-player').classList.remove('hidden');
        }

        function closePlayer() {
            const iframe = document.getElementById('v-frame');
            iframe.src = '';
            document.getElementById('section-player').classList.add('hidden');
        }

        function manualRefresh() {
            fetchCategory(currentCategory);
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closePlayer();
            }
        });

        // Initialize
        checkAge();
    </script>
</body>
</html>
"""

@app.route('/api/data')
def get_data():
    """API endpoint for frontend"""
    category = request.args.get('q', 'korean')
    print(f"📥 API request for category: {category}")
    
    with data_lock:
        data = load_content(category)
        return jsonify(data)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    print("🚀 Starting server...")
    print("👉 Open http://localhost:8000 in your browser")
    app.run(host='0.0.0.0', port=8000, threaded=True, debug=True)
