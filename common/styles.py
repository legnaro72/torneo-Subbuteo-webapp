"""
styles.py — CSS centralizzato per tutte le app del Tournament Manager Subbuteo.

Questo modulo fornisce tutti gli stili CSS in modo che ogni app possa
importarli con una sola chiamata. È stato ridisegnato per supportare
Sleek Modern UI, Glassmorphism e animazioni premium.
"""
import streamlit as st

def inject_all_styles():
    """Inietta TUTTI gli stili strutturali e di design in un'unica chiamata."""
    
    # 🌟 CORE THEME VARIABLES & ANIMATIONS
    CSS_CORE = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');

    :root {
        --color-primary-dark: #1d3557;
        --color-primary-mid: #457b9d;
        --color-primary-light: #a8dadc;
        --color-accent: #e63946;
        --color-accent-hover: #ff4d5a;
        --color-success: #2a9d8f;
        
        --bg-gradient: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        --card-bg: rgba(255, 255, 255, 0.7);
        --card-border: rgba(255, 255, 255, 0.5);
        --card-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
        
        --text-main: #1d3557;
        --text-muted: #6c757d;
        --glass-blur: blur(12px);
    }

    /* Supporto Dark Theme — selettori multipli per compatibilità Streamlit */
    [data-theme="dark"],
    [data-testid="stAppViewContainer"][data-theme="dark"],
    .stApp[data-theme="dark"] {
        --color-primary-dark: #0A1128;
        --color-primary-mid: #1C3144;
        --color-primary-light: #009FFD;
        --color-accent: #E63946;
        
        --bg-gradient: linear-gradient(135deg, #0A1128 0%, #121e33 100%);
        --card-bg: rgba(16, 25, 48, 0.6);
        --card-border: rgba(255, 255, 255, 0.05);
        --card-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
        
        --text-main: #ffffff;
        --text-muted: #a0abc0;
    }
    
    /* Fallback: se il browser ha prefers-color-scheme dark */
    @media (prefers-color-scheme: dark) {
        :root {
            --color-primary-dark: #0A1128;
            --color-primary-mid: #1C3144;
            --color-primary-light: #009FFD;
            --color-accent: #E63946;
            
            --bg-gradient: linear-gradient(135deg, #0A1128 0%, #121e33 100%);
            --card-bg: rgba(16, 25, 48, 0.6);
            --card-border: rgba(255, 255, 255, 0.05);
            --card-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
            
            --text-main: #ffffff;
            --text-muted: #a0abc0;
        }
    }

    /* Animazioni Globali */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    @keyframes gradientShine {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    /* Override del font globale per un look molto più moderno */
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif !important;
    }
    
    /* Migliora lo sfondo principale dell'app */
    .stApp {
        background: var(--bg-gradient);
        background-attachment: fixed;
    }
    </style>
    """

    # 📱 LAYOUT & CONTAINERS
    CSS_LAYOUT = """
    <style>
    .appview-container .main .block-container {
        padding-top: 2.5rem !important;
        padding-right: 2rem !important;
        padding-left: 2rem !important;
        padding-bottom: 2rem !important;
        max-width: 1400px;
        animation: fadeInUp 0.6s ease-out forwards;
    }
    
    /* Separatori eleganti */
    hr {
        border: 0;
        height: 1px;
        background-image: linear-gradient(to right, transparent, var(--color-primary-mid), transparent);
        margin: 2rem 0;
        opacity: 0.5;
    }
    </style>
    """

    # 🔲 BUTTONS (Glass & Glow effects)
    CSS_BUTTONS = """
    <style>
    .stButton>button, 
    .stDownloadButton>button {
        background-size: 200% auto !important;
        background-image: linear-gradient(to right, var(--color-primary-mid) 0%, var(--color-primary-light) 50%, var(--color-primary-mid) 100%) !important;
        color: white !important;
        border-radius: 12px !important;
        padding: 0.6em 1.5em !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px;
        border: 1px solid rgba(255,255,255,0.1) !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2) !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
        text-transform: uppercase;
        font-size: 0.9em !important;
    }

    .stButton>button:hover,
    .stDownloadButton>button:hover {
        background-position: right center !important;
        transform: translateY(-2px) scale(1.02) !important;
        box-shadow: 0 8px 25px rgba(0,159,253,0.4) !important;
    }
    
    .stButton>button:active {
        transform: translateY(1px) scale(0.98) !important;
    }
    
    /* Input testuali & Select box con Glassmorphism */
    .stTextInput>div>div>input, 
    .stSelectbox>div>div>div {
        background: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 8px !important;
        color: var(--text-main) !important;
        backdrop-filter: var(--glass-blur);
        -webkit-backdrop-filter: var(--glass-blur);
        transition: all 0.3s ease;
    }
    
    .stTextInput>div>div>input:focus,
    .stSelectbox>div>div>div:focus {
        border-color: var(--color-primary-light) !important;
        box-shadow: 0 0 10px rgba(0,159,253,0.3) !important;
    }
    </style>
    """

    # 📋 DATAFRAME & TABELLE
    CSS_DATAFRAME = """
    <style>
    .stDataFrame {
        border: 1px solid var(--card-border);
        border-radius: 15px;
        box-shadow: var(--card-shadow);
        background: var(--card-bg);
        backdrop-filter: var(--glass-blur);
        -webkit-backdrop-filter: var(--glass-blur);
        padding: 5px;
        overflow: hidden;
    }
    
    /* Intestazioni tabella super moderne */
    [data-testid="stDataFrame"] th {
        background-color: rgba(0,0,0,0.05) !important;
        color: var(--color-primary-light) !important;
        font-weight: 800 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    [data-theme="dark"] [data-testid="stDataFrame"] th,
    .stApp[data-theme="dark"] [data-testid="stDataFrame"] th {
        background-color: rgba(255,255,255,0.05) !important;
    }
    
    [data-testid="stDataFrame"] td {
        font-weight: 500;
        color: var(--text-main) !important;
    }
    </style>
    """

    # 🏷️ TYPOGRAPHY & TITLES
    CSS_TITLES = """
    <style>
    .main-title {
        font-size: clamp(28px, 5vw, 48px);
        font-weight: 800;
        text-align: center;
        margin-bottom: 2.5rem;
        background: linear-gradient(135deg, var(--color-primary-light) 0%, #ffffff 50%, var(--color-primary-mid) 100%);
        background-size: 200% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: gradientShine 4s linear infinite;
        text-shadow: 0px 4px 10px rgba(0,0,0,0.1);
        padding: 10px;
    }
    
    .big-title {
        text-align: center;
        font-size: clamp(22px, 3.5vw, 36px);
        font-weight: 800;
        margin: 20px 0 15px;
        color: var(--text-main);
        background: var(--card-bg);
        border-radius: 12px;
        border: 1px solid var(--card-border);
        box-shadow: var(--card-shadow);
        padding: 15px;
        backdrop-filter: var(--glass-blur);
        -webkit-backdrop-filter: var(--glass-blur);
        transition: transform 0.3s ease;
    }
    .big-title:hover {
        transform: translateY(-2px);
    }
    
    .sub-title {
        font-size: 20px;
        font-weight: 600;
        margin-top: 15px;
        color: var(--color-primary-light);
        text-transform: uppercase;
        letter-spacing: 1.5px;
    }
    
    /* H3 globali (nei titoli del database, tab, ecc) */
    .main .block-container h3 {
        color: var(--text-main);
        font-weight: 800;
        background: var(--card-bg);
        border-left: 5px solid var(--color-primary-light);
        border-radius: 0 10px 10px 0;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        padding: 12px 20px;
        margin-top: 25px;
        backdrop-filter: var(--glass-blur);
        transition: border-color 0.3s ease;
    }
    .main .block-container h3:hover {
        border-color: var(--color-accent);
    }
    
    /* Effetto Pills */
    .pill {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        background: rgba(0, 159, 253, 0.15);
        color: var(--color-primary-light);
        font-weight: 700;
        border: 1px solid rgba(0, 159, 253, 0.3);
        font-size: 0.85em;
        backdrop-filter: blur(5px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    </style>
    """

    # 🗂️ SIDEBAR ENHANCEMENTS
    CSS_SIDEBAR = """
    <style>
    /* Sidebar sfumata (Glassmorphism) */
    [data-testid="stSidebar"] {
        background: var(--card-bg) !important;
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        border-right: 1px solid var(--card-border) !important;
        box-shadow: 5px 0 20px rgba(0,0,0,0.05);
    }
    
    /* Stile Headers Sidebar (h3, ecc) in modo universale */
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: var(--color-primary-light) !important;
        font-weight: 800 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-size: 1rem !important;
        margin-top: 15px !important;
        background: none !important;
    }
    
    /* Navigation Link Buttons (in sidebar) */
    [data-testid="stSidebar"] .stLinkButton a {
        background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.02) 100%) !important;
        border: 1px solid var(--card-border) !important;
        color: var(--text-main) !important;
        border-radius: 12px !important;
        padding: 0.8rem 1rem !important;
        font-weight: 600 !important;
        display: block !important;
        text-align: center !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05) !important;
        margin: 8px 0 !important;
    }
    
    [data-testid="stSidebar"] .stLinkButton a:hover {
        background: linear-gradient(135deg, var(--color-primary-mid) 0%, var(--color-primary-light) 100%) !important;
        color: white !important;
        transform: translateX(4px) !important;
        box-shadow: 0 6px 15px rgba(0,159,253,0.3) !important;
        border-color: transparent !important;
    }
    </style>
    """

    # 🃏 MATCH CARDS
    CSS_MATCH_CARDS = """
    <style>
    .match-card {
        border: 1px solid var(--card-border);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 15px;
        background: var(--card-bg);
        box-shadow: var(--card-shadow);
        backdrop-filter: var(--glass-blur);
        -webkit-backdrop-filter: var(--glass-blur);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .match-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; width: 4px; height: 100%;
        background: var(--color-primary-light);
        opacity: 0.7;
        transition: background 0.3s;
    }
    
    .match-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.15);
        border-color: var(--color-primary-light);
    }
    .match-card:hover::before {
        background: var(--color-accent);
    }
    
    .validation-status-ok { 
        color: var(--color-success); 
        font-weight: 800; 
        background: rgba(42, 157, 143, 0.15);
        padding: 4px 10px;
        border-radius: 6px;
    }
    .validation-status-nok { 
        color: var(--color-accent); 
        font-weight: 800; 
        background: rgba(230, 57, 70, 0.15);
        padding: 4px 10px;
        border-radius: 6px;
    }
    </style>
    """

    # Iniezione cumulativa
    st.markdown(CSS_CORE, unsafe_allow_html=True)
    st.markdown(CSS_LAYOUT, unsafe_allow_html=True)
    st.markdown(CSS_BUTTONS, unsafe_allow_html=True)
    st.markdown(CSS_DATAFRAME, unsafe_allow_html=True)
    st.markdown(CSS_TITLES, unsafe_allow_html=True)
    st.markdown(CSS_SIDEBAR, unsafe_allow_html=True)
    st.markdown(CSS_MATCH_CARDS, unsafe_allow_html=True)
    
    # 🌙 JS per rilevare il tema dark di Streamlit e propagare data-theme
    DARK_MODE_JS = """
    <script>
    (function() {
        function detectAndSetTheme() {
            // Streamlit imposta il colore di sfondo del body in modo diverso per dark/light
            const stApp = document.querySelector('.stApp');
            if (!stApp) return;
            
            const bgColor = window.getComputedStyle(stApp).backgroundColor;
            // Parse RGB values
            const rgb = bgColor.match(/\\d+/g);
            if (rgb) {
                const brightness = (parseInt(rgb[0]) * 299 + parseInt(rgb[1]) * 587 + parseInt(rgb[2]) * 114) / 1000;
                const isDark = brightness < 128;
                
                if (isDark) {
                    document.documentElement.setAttribute('data-theme', 'dark');
                    stApp.setAttribute('data-theme', 'dark');
                } else {
                    document.documentElement.removeAttribute('data-theme');
                    stApp.removeAttribute('data-theme');
                }
            }
        }
        
        // Rileva subito e poi osserva i cambiamenti
        detectAndSetTheme();
        
        // Osserva cambiamenti di stile (per switch tema runtime)
        const observer = new MutationObserver(detectAndSetTheme);
        const target = document.querySelector('.stApp');
        if (target) {
            observer.observe(target, { attributes: true, attributeFilter: ['style', 'class'] });
        }
        
        // Rileva anche il cambio di prefers-color-scheme
        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', detectAndSetTheme);
        }
        
        // Ricontrolla dopo un breve delay (Streamlit potrebbe inizializzare tardi)
        setTimeout(detectAndSetTheme, 500);
        setTimeout(detectAndSetTheme, 2000);
    })();
    </script>
    """
    st.markdown(DARK_MODE_JS, unsafe_allow_html=True)


def inject_hub_styles():
    """Stili specifici per l'Hub (landing page) - Dashboard Premium."""
    inject_all_styles()
    st.markdown("""
    <style>
    /* Griglia delle carte (Hub) */
    .card {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        backdrop-filter: var(--glass-blur);
        -webkit-backdrop-filter: var(--glass-blur);
        padding: 30px 25px;
        border-radius: 20px;
        box-shadow: var(--card-shadow);
        text-align: center;
        color: var(--text-main);
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        position: relative;
        overflow: hidden;
        margin-bottom: 25px;
    }
    
    .card::after {
        content: '';
        position: absolute;
        top: -50%; left: -50%;
        width: 200%; height: 200%;
        background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 60%);
        opacity: 0;
        transition: opacity 0.5s;
        pointer-events: none;
    }
    
    .card:hover {
        transform: translateY(-8px) scale(1.02);
        box-shadow: 0 20px 40px rgba(0, 159, 253, 0.15);
        border-color: rgba(0, 159, 253, 0.4);
    }
    
    .card:hover::after {
        opacity: 1;
    }

    .card-title {
        font-size: 26px;
        font-weight: 800;
        margin-bottom: 15px;
        color: var(--text-main);
    }
    
    .card-desc {
        font-size: 16px;
        margin-bottom: 30px;
        color: var(--text-muted);
        line-height: 1.6;
    }
    
    /* Pulsanti Hub */
    .card-link {
        display: inline-block;
        padding: 14px 28px;
        font-size: 15px;
        font-weight: 700;
        color: #ffffff !important;
        background-size: 200% auto;
        background-image: linear-gradient(135deg, var(--color-primary-mid) 0%, var(--color-primary-light) 50%, var(--color-primary-mid) 100%);
        border-radius: 50px;
        text-decoration: none;
        transition: all 0.3s ease;
        box-shadow: 0 6px 20px rgba(0,159,253,0.3);
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .card-link:hover {
        background-position: right center;
        transform: translateY(-3px);
        box-shadow: 0 10px 25px rgba(0,159,253,0.5);
    }
    
    .card-link-red {
        background-image: linear-gradient(135deg, #e63946 0%, #ff4d5a 50%, #e63946 100%);
        box-shadow: 0 6px 20px rgba(230,57,70,0.3);
    }
    .card-link-red:hover {
        box-shadow: 0 10px 25px rgba(230,57,70,0.5);
    }
    
    .card-link-beta {
        background-image: linear-gradient(135deg, #f4a261 0%, #e76f51 50%, #f4a261 100%);
        box-shadow: 0 6px 20px rgba(244,162,97,0.3);
    }
    .card-link-beta:hover {
        box-shadow: 0 10px 25px rgba(244,162,97,0.5);
    }
    
    /* Box manuale */
    .manual-box {
        background: linear-gradient(135deg, rgba(0,159,253,0.05) 0%, rgba(28,49,68,0.1) 100%);
        backdrop-filter: var(--glass-blur);
        border: 1px solid var(--card-border);
        padding: 30px;
        border-radius: 20px;
        text-align: center;
        margin-top: 30px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
    }
    .manual-box:hover {
        border-color: var(--color-primary-light);
        transform: translateY(-2px);
    }
    </style>
    """, unsafe_allow_html=True)
