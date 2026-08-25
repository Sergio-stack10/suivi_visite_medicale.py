import streamlit as st
import pandas as pd
import numpy as np
import datetime
import io
import os
import pickle
import plotly.express as px
import re
import contextlib
import uuid
import pymongo
import bson

# --- CONFIGURATION DE LA PAGE (Doit être la 1ère commande Streamlit) ---
st.set_page_config(page_title="Suivi Visites Médicales", page_icon="🏥", layout="wide")

# --- SYSTÈME D'AUTHENTIFICATION ROBUSTE ---
@st.cache_resource
def get_token_store():
    return {}

def check_password():
    token_store = get_token_store()

    if st.session_state.get("password_correct"):
        return True

    params = st.query_params
    if "token" in params:
        token = params["token"]
        try:
            if token in token_store:
                user_data = token_store[token]
                st.session_state["password_correct"] = True
                st.session_state["role"] = user_data["role"]
                st.session_state["username"] = user_data["username"]
                st.session_state["token"] = token
                return True
            else:
                st.query_params.clear()
        except Exception:
            st.query_params.clear()

    def password_entered():
        user = st.session_state["username"]
        pwd = st.session_state["password"]
        
        admin_users = st.secrets.get("admin", {})
        consult_users = st.secrets.get("consultation", {})
        
        if user in admin_users and pwd == admin_users[user]:
            st.session_state["password_correct"] = True
            st.session_state["role"] = "admin"
            if "password" in st.session_state: del st.session_state["password"]
            token = str(uuid.uuid4())
            token_store[token] = {"username": user, "role": "admin"}
            st.session_state["token"] = token
            st.query_params["token"] = token
            
        elif user in consult_users and pwd == consult_users[user]:
            st.session_state["password_correct"] = True
            st.session_state["role"] = "consultation"
            if "password" in st.session_state: del st.session_state["password"]
            token = str(uuid.uuid4())
            token_store[token] = {"username": user, "role": "consultation"}
            st.session_state["token"] = token
            st.query_params["token"] = token
        else:
            st.session_state["password_correct"] = False

    st.text_input("Nom d'utilisateur", key="username")
    st.text_input("Mot de passe", type="password", key="password")
    st.button("Se connecter", on_click=password_entered)
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("😕 Utilisateur ou mot de passe inconnu")
    return False

if not check_password():
    st.stop()

# Récupération du rôle pour conditionner l'affichage
role = st.session_state.get("role", "consultation")

# --- BOUTON DE DÉCONNEXION ---
with st.sidebar:
    st.markdown(f"👤 **Utilisateur :** {st.session_state.get('username', 'N/A')}")
    st.markdown(f"🔑 **Rôle :** {role.capitalize()}")
    if st.button("🚪 Se déconnecter"):
        token_store = get_token_store()
        token = st.session_state.get("token")
        if token and token in token_store:
            del token_store[token]
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.query_params.clear()
        st.rerun()
    st.markdown("---")

st.title("🏥 Suivi des Visites Médicales")

# --- INJECTION CSS POUR LA CHARTRE GRAPHIQUE ---
custom_css = """
<style>
    /* 1. IMPORTATION D'UNE POLICE MODERNE (Google Fonts) */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, .stApp {
        font-family: 'Outfit', sans-serif !important;
    }
    
    /* 2. STRUCTURE GÉNÉRALE (Sans forcer la couleur pour respecter le mode nuit) */
    .stApp, .block-container { 
        padding-top: 4rem !important; 
        padding-bottom: 2rem !important; 
        max-width: 1200px; /* Centre l'application pour un rendu plus propre sur grands écrans */
        margin: auto;
    }
    
    h1 { 
        color: #25E2CC !important; 
        font-weight: 700 !important; 
        padding-bottom: 15px !important; 
        border-bottom: 3px solid #003D5B !important; 
        margin-bottom: 30px !important;
    }
    h2, h3 { color: #003D5B !important; font-weight: 600 !important; }
    
    /* 3. EFFET "CARTE" POUR LES BLOCS DE CONTENU (Glassmorphism léger) */
    /* Cela s'applique aux conteneurs et aux tableaux */
    [data-testid="stVerticalBlock"] > div:has(> [data-testid="stDataFrame"]) {
        background-color: rgba(128, 128, 128, 0.05); /* Fond gris très transparent */
        border: 1px solid rgba(128, 128, 128, 0.1); /* Bordure discrète */
        border-radius: 12px; /* Coins arrondis */
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05); /* Ombre douce */
        margin-bottom: 20px;
    }
    
    /* 4. BARRE LATÉRALE (Sidebar) Plus Premium */
    section[data-testid="stSidebar"] { 
        background-color: #001a26 !important; /* Bleu marine très foncé */
        border-right: 2px solid #25E2CC !important;
    }
    section[data-testid="stSidebar"] > div:first-child { padding-top: 30px !important; }
    section[data-testid="stSidebar"] label { color: #A8F3EB !important; font-weight: 500 !important; }
    
    /* 5. ONGLETS (Tabs) - Forme de pilule moderne */
    .stTabs [data-baseweb="tab-list"] { gap: 10px !important; }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        color: gray !important;
        border: 1px solid transparent !important;
        border-radius: 30px !important; /* Forme de pilule */
        padding: 10px 25px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        box-shadow: none !important;
        clip-path: none !important; /* On retire l'ancienne forme coupée */
    }
    .stTabs [data-baseweb="tab"]:hover { 
        background-color: rgba(37, 226, 204, 0.1) !important; 
        color: #25E2CC !important;
    }
    .stTabs [aria-selected="true"] { 
        background-color: #003D5B !important; 
        color: #FFFFFF !important; 
        box-shadow: 0 4px 12px rgba(0, 61, 91, 0.3) !important;
    }
    .stTabs [data-baseweb="tab-highlight"] { background-color: transparent !important; }
    .stTabs [data-baseweb="tab-border-bottom"] { display: none !important; }
    
    /* 6. BOUTONS - Effet de profondeur au survol */
    div.stButton > button {
        background-color: #003D5B; color: #FFFFFF; border: none; padding: 12px 30px;
        border-radius: 30px; font-weight: 600; transition: all 0.3s ease; width: 100%;
    }
    div.stButton > button:hover { 
        background-color: #25E2CC !important; color: #002032 !important; 
        transform: translateY(-3px); /* Le bouton se soulève */
        box-shadow: 0 8px 15px rgba(37, 226, 204, 0.3) !important; /* Ombre turquoise */
    }
    .stDownloadButton > button { 
        background-color: #25E2CC !important; color: #002032 !important; border: none !important; 
        border-radius: 30px !important; font-weight: 600 !important; width: 100%;
    }
    .stDownloadButton > button:hover { 
        background-color: #007380 !important; color: #FFFFFF !important; transform: translateY(-3px);
    }
    
    /* 7. MÉTRIQUES (st.metric) - Style "Dashboard" */
    [data-testid="stMetric"] {
        background-color: rgba(128, 128, 128, 0.05);
        border: 1px solid rgba(128, 128, 128, 0.1);
        border-radius: 12px;
        padding: 15px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    [data-testid="stMetricLabel"] { color: gray !important; font-size: 12px !important; text-transform: uppercase; letter-spacing: 1px; }
    [data-testid="stMetricValue"] { color: #003D5B !important; font-weight: 700 !important; font-size: 24px !important; }
    
    /* 8. FOOTER */
    .footer-fix {
        position: fixed !important; left: 0 !important; bottom: 0 !important; width: 100% !important;
        background-color: #001a26 !important; color: #A8F3EB !important; text-align: center !important;
        font-size: 12px !important; padding: 10px !important; z-index: 999999 !important; 
        border-top: 2px solid #25E2CC !important;
    }
    
    /* 9. MASQUER LES LOGOS STREAMLIT (Gardé intact pour ton interface propre) */
    .stDeployButton, [data-testid="stDeployButton"] { display: none !important; }
    div[class*="_link_"], div[class*="_profilePreview_"], img[data-testid="appCreatorAvatar"], [data-testid="stLogo"] { display: none !important; }
    [data-testid="stHeaderActionElements"] a[href*="github.com"], [data-testid="stHeaderActionElements"] a[href*="streamlit.io"] { display: none !important; }
    #MainMenu, footer { visibility: hidden !important; }

    /* Bouton sidebar flottant */
    [data-testid="stSidebarCollapseButton"] {
        opacity: 1 !important; background-color: #25E2CC !important; border: none !important; border-radius: 20px !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2) !important;
    }
    [data-testid="stSidebarCollapseButton"] svg { color: #002032 !important; fill: #002032 !important; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- DICTIONNAIRE DE MAPPAGE DES PROJETS ---
def get_mapped_project(projet):
    p = str(projet)
    mapping = {
        '18431': 'ORG ATH', '16187': 'BTL AT', '18354': 'AC',
        '16294': 'TE FOC', '21548': 'BKM POLY', '17042': 'CPR',
        '17439': 'FB', '25641': 'SHI', '16152': 'ORG HD',
        '22280': 'AY', '16315': 'MF', '18142': 'BB',
        '16872': 'CST', '16334': 'C+ INT', '12777': 'PF',
        '16873': 'BF', '17139': 'LP', '17056': 'ZAL TMM',
        '21565': 'SBX', '17057': 'VP SC', '16808': 'RRG',
        '16669': 'IZI', '17178': 'BKM', '17060': 'AUC',
        '11836': 'DRM', '11834': '3DS', '16966': 'LC',
        '16643': 'ZAL TNR', '24323': 'LYX', '16950': 'DB TMM',
        '17534': 'TRP', '17914': 'ZP', '16999': 'TII',
        '16412': 'HP', '16952': 'BTL DIG', '17429': 'GRA',
        '18175': 'RCI MG', '17230': 'JTR', '21550': 'CPR BE',
        '18338': 'MZ', '17130': 'MO', '24158': 'YK',
        '12480': 'C+ FR', '11753': 'VAL', '13966': 'H&H',
        '17401': '24S', '16571': 'TRK', '25659': 'ZAL DE',
        '11733': 'BF POLY', '23126': 'STC', '24474': 'CNX',
        '23404': 'C2B', '17567': 'POL', '26711': 'ADV',
        '24241': 'OPEX', '17043': 'DB TNR', '16827': 'LBC',
        '18013': 'BA', '16897': 'LC ANT', '16953': 'STY',
        '16437': 'ORG PRT', '18418': 'RIV TMM', '16352': 'RIV UK TMM',
        '17131': 'FLT', '18345': 'RIV ANT', '16351': 'RIV UK ANT',
        '26044': 'CNX', '980005758': 'LEAD', '980010299': 'ZPL',
        '2517': 'RECRU'
    }
    for k, v in mapping.items():
        if p.startswith(k):
            return v
    
    str_mappings = {
        'Depot Bingo Polyglot': 'DEPOT BINGO POLYGLOT', 'Gallinée': 'GALLINÉE',
        'Direct Energie BOC': 'DIRECT ENERGIE BOC', 'Hostnfly': 'HOSTNFLY',
        'TK Home Solutions': 'TK HOME SOLUTIONS', '4165 Piana': 'PIANA',
        'Hellowork': 'HELLOWORK', 'Lydia': 'LYDIA', 'Club Funding': 'CLUB FUNDING',
        'Wengo': 'WENGO', 'Califrais': 'CALIFRAIS', 'Joko': 'JOKO CUSTOMER CARE',
        'WorlRemit': 'WORLREMIT', '4132 SENDWAVE': 'SENDWAVE', 'Tiiko': 'TIIKO',
        'COLISEE': 'COLISEE', 'ENI SC': 'ENI SC', 'OMEO': 'OMEO',
        'WORLDR SENDWAVE': 'WORLDR SENDWAVE', 'GPASPLUS': 'GPASPLUS',
        'Footovision': 'FOOTOVISION', 'Sika Webhelp': 'SIKA WEBHELP OD',
        'Tuffy Wall': 'TUFFY WALL', 'DOMISERVE': 'DOMISERVE',
        '22409 - Pnp': 'PNP TMM', '22432 - Other': 'OTHER', '22409 - Other': 'OTHER',
        '21317 - Legalplace': 'LEGALPLACE', '16679 - Gexel': 'GEXEL',
        '2921 - Originenergy': 'ORIGINENERGY', '23330 - Opexother': 'OPEXOTHER',
        '23776 - Other': 'OTHER', '14309 - Bytedance': 'BYTEDANCE',
        '4125 - Ceaa': 'CEAA', '24818 - Power Fleet': 'POWERFLEET',
        '12229 - Other': 'OTHER', '12230 - Other': 'OTHER',
        'WHFR157 - P_DMS': 'BYTEL DIGITAL', 'WHFR2857 - P_4073': 'RIVER DE',
        'WHUS012 - P_Gexel': 'GEXEL', 'WHFR2962 - Piana': 'PIANA',
        'WHCRIT225 - A540 P_AL': 'VEEPEE SC', 'WHFR894 - P_TLS SGS': 'SGS',
        'WHNL287 - Basic-fit': 'BASIC FIT NL', 'WHFR2963 - Colis Privac': 'COLIS PRIVÉ'
    }
    for k, v in str_mappings.items():
        if k.lower() in p.lower():
            return v
    return p

# --- BARRE LATÉRALE AVEC IMPORTS RÉDUITS ---
with st.sidebar.expander("📥 Importation des fichiers", expanded=True):
    if role == "admin":
        files_planning = st.file_uploader("Fichiers Planning (Obligatoire)", type=['xlsx', 'xls', 'xlsb'], accept_multiple_files=True)
        file_a_passer = st.file_uploader("Fichier PLANIFICATION VISITE SYSTEMATIQUE", type=['xlsx'])
        file_rta = st.file_uploader("Fichier Enregistrement visite médicale (RTA)", type=['xlsx'])
    else:
        st.info("🔒 Mode consultation : Vous n'avez pas accès aux imports de fichiers.")
        files_planning = []
        file_a_passer = None
        file_rta = None

jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

# --- SYSTÈME D'HISTORIQUE PERSISTANT ---
def get_mongo_client():
    mongo_uri = st.secrets.get("MONGO_URI")
    if not mongo_uri:
        return None
    
    try:
        client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        return client
    except Exception as e:
        safe_error = str(e).replace(mongo_uri, "[URI MASQUÉE]")
        st.error(f"Erreur de connexion à MongoDB : {safe_error}")
        return None

def load_history():
    client = get_mongo_client()
    if client is None:
        if os.path.exists("medical_tracking.pkl"):
            try:
                with open("medical_tracking.pkl", "rb") as f:
                    return pickle.load(f)
            except:
                pass
        return {'plannings': {}, 'medical_list': None, 'rta_data': None}
    
    try:
        db = client["visite_medicale_db"]
        collection = db["app_state"]
        doc = collection.find_one({"_id": 1})
        if doc:
            return pickle.loads(doc['data'])
        return {'plannings': {}, 'medical_list': None, 'rta_data': None}
    except Exception as e:
        st.error(f"Erreur de connexion à la base de données : {e}")
        return {'plannings': {}, 'medical_list': None, 'rta_data': None}

def save_history():
    client = get_mongo_client()
    if client is None:
        try:
            with open("medical_tracking.pkl", "wb") as f:
                pickle.dump(st.session_state.history_data, f)
        except Exception as e:
            st.error(f"Erreur lors de la sauvegarde locale : {e}")
        return

    try:
        db = client["visite_medicale_db"]
        collection = db["app_state"]
        pickle_bytes = pickle.dumps(st.session_state.history_data)
        collection.update_one(
            {"_id": 1}, 
            {"$set": {"data": bson.Binary(pickle_bytes)}}, 
            upsert=True
        )
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde cloud : {e}")

if 'history_data' not in st.session_state:
    st.session_state.history_data = load_history()

# --- FONCTION DE SYNCHRONISATION DU STATUT ---
def sync_statut_with_plannings(medical_list, history_plannings):
    if medical_list is None or medical_list.empty:
        return medical_list
        
    all_plannings = []
    for p_df in history_plannings.values():
        if 'Statut' in p_df.columns:
            all_plannings.append(p_df[['WORKDAY ID', 'Paid ID', 'Statut']].copy())
            
    if not all_plannings:
        return medical_list
        
    plannings_concat = pd.concat(all_plannings, ignore_index=True).drop_duplicates(subset=['WORKDAY ID'])
    
    plannings_concat['WORKDAY ID'] = plannings_concat['WORKDAY ID'].astype(str).str.replace(" ", "").str.upper()
    if 'Paid ID' in plannings_concat.columns:
        plannings_concat['Paid ID'] = plannings_concat['Paid ID'].astype(str).str.replace(" ", "").str.upper()
        
    medical_list['WORKDAY ID'] = medical_list['WORKDAY ID'].astype(str).str.replace(" ", "").str.upper()
    
    map_wid = dict(zip(plannings_concat['WORKDAY ID'], plannings_concat['Statut']))
    medical_list['Statut'] = medical_list['WORKDAY ID'].map(map_wid)
    
    if 'Payroll ID' in medical_list.columns and 'Paid ID' in plannings_concat.columns:
        missing_mask = medical_list['Statut'].isna()
        if missing_mask.any():
            map_pid = dict(zip(plannings_concat['Paid ID'], plannings_concat['Statut']))
            medical_list.loc[missing_mask, 'Statut'] = medical_list.loc[missing_mask, 'Payroll ID'].astype(str).str.replace(" ", "").str.upper().map(map_pid)
            
    medical_list['Statut'] = medical_list['Statut'].fillna('ENC')
    medical_list['Statut'] = medical_list['Statut'].apply(lambda x: 'CC' if 'ADVISOR' in str(x).upper() or 'CUSTOMER SERVICE' in str(x).upper() or 'CC' in str(x).upper() else 'ENC')
    
    return medical_list

if st.session_state.history_data.get('medical_list') is not None:
    med_list = st.session_state.history_data['medical_list']
    for col in ['Prénom', 'Date d\'embauche', 'Ancienneté', 'Ancienneté_num', 'Payroll ID', 'Créneau Visite', 'Statut']:
        if col not in med_list.columns:
            if col == 'Ancienneté_num':
                med_list[col] = 0
            elif col == 'Date d\'embauche' or col == 'Créneau Visite':
                med_list[col] = pd.NaT
            elif col == 'Statut':
                med_list[col] = 'ENC'
            else:
                med_list[col] = ''
    
    med_list = sync_statut_with_plannings(med_list, st.session_state.history_data.get('plannings', {}))
    st.session_state.history_data['medical_list'] = med_list
    
if 'current_week' not in st.session_state:
    st.session_state.current_week = None

def get_dates_from_week(week_name):
    try:
        match = re.search(r'\d+', str(week_name))
        if match:
            week_num = int(match.group())
            year = datetime.date.today().year
            monday = datetime.date.fromisocalendar(year, week_num, 1)
            return {j: (monday + datetime.timedelta(days=i)) for i, j in enumerate(jours)}
    except:
        pass
    return {j: datetime.date.today() for j in jours}

# --- FONCTIONS UTILITAIRES ---
@st.cache_data
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

def is_planned(val):
    if pd.isna(val) or isinstance(val, bool): return False
    if isinstance(val, (int, float, np.number)): return val > 0
    if isinstance(val, (datetime.time, datetime.datetime, pd.Timestamp)):
        t = val.time() if isinstance(val, (datetime.datetime, pd.Timestamp)) else val
        return t != datetime.time(0, 0, 0)
    val_str = str(val).strip()
    if val_str in ['', '*', 'nan', 'None', '0', '0:00', '00:00', '0:00:00', '00:00:00']: return False
    try:
        dt = pd.to_datetime(val_str, errors='coerce')
        if not pd.isna(dt): return dt.time() != datetime.time(0, 0, 0)
    except: pass
    try: return float(val_str) > 0
    except: pass
    if any(c.isalpha() for c in val_str): return False
    return False

def get_time_obj(val):
    if pd.isna(val) or str(val).strip() in ['', '*', 'nan']: return None
    if isinstance(val, datetime.time): return val
    if isinstance(val, (datetime.datetime, pd.Timestamp)): return val.time()
    if isinstance(val, (int, float, np.number)) and not isinstance(val, bool):
        if 0 < val < 1: 
            total_seconds = int(val * 86400)
            h = total_seconds // 3600
            m = (total_seconds % 3600) // 60
            s = total_seconds % 60
            return datetime.time(h, m, s)
        try:
            dt = pd.to_datetime(val, errors='coerce')
            if not pd.isna(dt): return dt.time()
        except: pass
    val_str = str(val).strip()
    if val_str in ['0', '0:00', '00:00', '0:00:00', '00:00:00']: return None
    try:
        dt = pd.to_datetime(val_str, errors='coerce')
        if not pd.isna(dt): return dt.time()
    except: pass
    return None

def format_time_display(val):
    t = get_time_obj(val)
    if t: return t.strftime('%H:%M')
    return str(val).strip() if not pd.isna(val) and str(val).strip() not in ['nan'] else ""

def format_duration(mins):
    if pd.isna(mins) or mins == 0: return "0min"
    h = int(mins // 60)
    m = int(mins % 60)
    return f"{h}h {m}min" if h > 0 else f"{m}min"

def calculate_anciennete(hire_date_str):
    try:
        hd = pd.to_datetime(hire_date_str, errors='coerce')
        if pd.isna(hd): return ''
        today = datetime.date.today()
        months = (today.year - hd.year) * 12 + (today.month - hd.month)
        if months < 0: return '0 mois'
        years = months // 12
        rem_months = months % 12
        return f"{years} an(s) {rem_months} mois" if years > 0 else f"{rem_months} mois"
    except:
        return ''

def calculate_anciennete_num(hire_date_str):
    try:
        hd = pd.to_datetime(hire_date_str, errors='coerce')
        if pd.isna(hd): return 0
        today = datetime.date.today()
        months = (today.year - hd.year) * 12 + (today.month - hd.month)
        return max(0, months)
    except:
        return 0

def get_final_status(row):
    statut = str(row.get('Statut Visite', '')).lower().strip()
    com = str(row.get('Commentaire', '')).lower()
    if 'ok' in com:
        return 'Visite effectuée'
    if 'absent' in com or 'report' in com:
        return 'Absent/Reporté'
    if statut in ['planifié', 'planifie']:
        return 'Planifié'
    return 'Non Planifié'

# --- FONCTIONS DE TRAITEMENT ---
def get_week_number(file, engine):
    try:
        xls = pd.ExcelFile(file, engine=engine)
        for sheet in xls.sheet_names:
            df_head = pd.read_excel(file, sheet_name=sheet, nrows=5, header=None, engine=engine)
            for i in range(min(5, len(df_head))):
                for j in range(min(15, len(df_head.columns))):
                    val = df_head.iloc[i, j]
                    if pd.notna(val):
                        dt = pd.to_datetime(val, errors='coerce')
                        if pd.isna(dt):
                            dt = pd.to_datetime(str(val), errors='coerce')
                        if not pd.isna(dt):
                            return f"S{dt.isocalendar().week:02d}"
    except:
        pass
    return None

def parse_planning(files, jours):
    all_planning = []
    for file in files:
        engine = 'pyxlsb' if file.name.endswith('.xlsb') else None
        xls = pd.ExcelFile(file, engine=engine)
        df = None
        if "Tout (WFO+WFH)" in xls.sheet_names:
            df = pd.read_excel(file, sheet_name="Tout (WFO+WFH)", header=None, skiprows=3, engine=engine)
            cols = [3, 4, 5, 6, 7, 10, 11, 12, 13, 15, 16, 17, 19, 20, 21, 23, 24, 25, 27, 28, 29, 31, 32, 33, 35, 36, 37]
            new_cols = ['TRANSPORT', 'WORKDAY ID', 'Paid ID', 'Nom', 'Projet', 'Statut', 
                        'Lundi_DE', 'Lundi_A', 'Lundi_Pause', 'Mardi_DE', 'Mardi_A', 'Mardi_Pause', 
                        'Mercredi_DE', 'Mercredi_A', 'Mercredi_Pause', 'Jeudi_DE', 'Jeudi_A', 'Jeudi_Pause', 
                        'Vendredi_DE', 'Vendredi_A', 'Vendredi_Pause', 'Samedi_DE', 'Samedi_A', 'Samedi_Pause', 
                        'Dimanche_DE', 'Dimanche_A', 'Dimanche_Pause']
            df = df.iloc[:, cols]
            df.columns = new_cols
            
        elif "TMM" in xls.sheet_names:
            df_head = pd.read_excel(file, sheet_name="TMM", header=None, nrows=10, engine=engine)
            header_row_idx = None
            trans_col_idx = 0
            for i in range(len(df_head)):
                row = df_head.iloc[i].astype(str).str.strip().tolist()
                if "Transport" in row:
                    header_row_idx = i
                    trans_col_idx = row.index("Transport")
                    break
            if header_row_idx is not None:
                df = pd.read_excel(file, sheet_name="TMM", header=None, skiprows=header_row_idx + 1, engine=engine)
                offset = trans_col_idx
                cols = [0 + offset, 4 + offset, 2 + offset, 5 + offset, 8 + offset, 10 + offset, 11 + offset, 12 + offset, 13 + offset, 17 + offset, 18 + offset, 19 + offset, 23 + offset, 24 + offset, 25 + offset, 29 + offset, 30 + offset, 31 + offset, 35 + offset, 36 + offset, 37 + offset, 41 + offset, 42 + offset, 43 + offset, 47 + offset, 48 + offset, 49 + offset]
                new_cols = ['TRANSPORT', 'WORKDAY ID', 'Paid ID', 'Nom', 'Projet', 'Statut', 
                            'Lundi_DE', 'Lundi_A', 'Lundi_Pause', 'Mardi_DE', 'Mardi_A', 'Mardi_Pause', 
                            'Mercredi_DE', 'Mercredi_A', 'Mercredi_Pause', 'Jeudi_DE', 'Jeudi_A', 'Jeudi_Pause', 
                            'Vendredi_DE', 'Vendredi_A', 'Vendredi_Pause', 'Samedi_DE', 'Samedi_A', 'Samedi_Pause', 
                            'Dimanche_DE', 'Dimanche_A', 'Dimanche_Pause']
                df = df.iloc[:, cols]
                df.columns = new_cols
            else:
                continue
        else: 
            continue
            
        df['WORKDAY ID'] = df['WORKDAY ID'].astype(str).str.replace(" ", "").str.replace(".0", "").str.upper()
        df['Paid ID'] = df['Paid ID'].astype(str).str.replace(" ", "").str.upper()
        df = df[df['WORKDAY ID'].str.contains(r'[A-Z0-9]', na=False)]
        df = df[~df['WORKDAY ID'].isin(['NAN', 'NONE', '*', ''])]
        for j in jours:
            df[f'{j}_Flag'] = df[f'{j}_DE'].apply(lambda x: 1 if is_planned(x) else 0)
        all_planning.append(df)
        
    if all_planning: 
        return pd.concat(all_planning, ignore_index=True).drop_duplicates(subset=['WORKDAY ID'])
    return pd.DataFrame()

def parse_liste_visite(file):
    try:
        df = pd.read_excel(file)
        cols_cleaned = [str(c).strip().upper() for c in df.columns]
        df.columns = cols_cleaned
        
        id_col = nom_col = prenom_col = projet_col = visite_col = hire_col = paid_col = statut_col = None
        for c in df.columns:
            if 'WORKDAY' in c or 'EMPLOYEE' in c or 'MATRICULE' in c: id_col = c
            if 'LAST' in c and 'NAME' in c: nom_col = c
            elif 'NOM' in c and nom_col is None: nom_col = c
            if 'FIRST' in c and 'NAME' in c: prenom_col = c
            if 'PROJET' in c or 'PROJECT' in c: projet_col = c
            if 'VISITE' in c or 'TYPE' in c: visite_col = c
            if 'HIRE' in c and 'DATE' in c: hire_col = c
            if 'PREVIOUS PAYROLL' in c or 'PAID ID' in c or 'PAYROLL ID' in c: paid_col = c
            if 'STATUT' in c or 'POSTE' in c or 'JOB' in c or 'TITLE' in c or 'POSITION' in c or 'ROLE' in c: statut_col = c
            
        if id_col is None: return None
            
        cols_to_keep = [id_col]
        if paid_col: cols_to_keep.append(paid_col)
        if nom_col: cols_to_keep.append(nom_col)
        if prenom_col: cols_to_keep.append(prenom_col)
        if projet_col: cols_to_keep.append(projet_col)
        if visite_col: cols_to_keep.append(visite_col)
        if hire_col: cols_to_keep.append(hire_col)
        if statut_col: cols_to_keep.append(statut_col)
        
        df = df[cols_to_keep].copy()
        
        if projet_col: df['Projet'] = df[projet_col]
        else: df['Projet'] = 'N/A'
            
        if visite_col: df['Priorité Visite'] = df[visite_col]
        else: df['Priorité Visite'] = 'N/A'
            
        if prenom_col: df = df.rename(columns={prenom_col: 'Prénom'})
        else: df['Prénom'] = ''
            
        if hire_col:
            df = df.rename(columns={hire_col: 'Date d\'embauche'})
        else:
            df['Date d\'embauche'] = pd.NaT
            
        if paid_col:
            df = df.rename(columns={paid_col: 'Payroll ID'})
        else:
            df['Payroll ID'] = ''
            
        if statut_col:
            raw_statut = df[statut_col].astype(str).str.upper()
            df['Statut'] = raw_statut.apply(lambda x: 'CC' if 'ADVISOR' in x or 'CUSTOMER SERVICE' in x or 'CC' in x else 'ENC')
        else:
            df['Statut'] = 'ENC'
            
        df[id_col] = df[id_col].astype(str).str.replace(" ", "").str.replace(".0", "").str.upper()
        df = df.rename(columns={id_col: 'WORKDAY ID'})
        if nom_col: df = df.rename(columns={nom_col: 'Nom'})
        if 'Nom' not in df.columns: df['Nom'] = ''
        
        df = df[df['WORKDAY ID'].str.contains(r'[A-Z0-9]', na=False)]
        df = df[~df['WORKDAY ID'].isin(['NAN', 'NONE', '*', ''])]
        
        df['Date d\'embauche'] = pd.to_datetime(df['Date d\'embauche'], errors='coerce')
        df['Ancienneté'] = df['Date d\'embauche'].apply(calculate_anciennete)
        df['Ancienneté_num'] = df['Date d\'embauche'].apply(calculate_anciennete_num)
        
        df['Statut Visite'] = 'Non Planifié'
        df['Date Visite'] = pd.NaT
        df['Créneau Visite'] = pd.NaT
        df['Shift Début'] = ''
        df['Shift Fin'] = ''
        df['Heure Départ'] = pd.NaT
        df['Heure Retour'] = pd.NaT
        df['Commentaire'] = ''
        
        final_cols = ['WORKDAY ID', 'Payroll ID', 'Nom', 'Prénom', 'Statut', 'Date d\'embauche', 'Ancienneté', 'Ancienneté_num', 'Projet', 'Priorité Visite', 'Statut Visite', 'Date Visite', 'Créneau Visite', 'Shift Début', 'Shift Fin', 'Heure Départ', 'Heure Retour', 'Commentaire']
        return df[final_cols].drop_duplicates(subset=['WORKDAY ID'])
    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier Visite: {e}")
        return None

def parse_rta_file(file):
    try:
        xls = pd.ExcelFile(file)
        sheet_name = "Suivi" if "Suivi" in xls.sheet_names else (xls.sheet_names[0] if xls.sheet_names else None)
        if not sheet_name: return None
            
        df = pd.read_excel(file, sheet_name=sheet_name)
        df = df.loc[:, ~df.columns.duplicated()]
        
        cols_cleaned = [str(c).strip().upper().replace('É', 'E').replace('È', 'E').replace('Ê', 'E').replace('À', 'A') for c in df.columns]
        df.columns = cols_cleaned
        
        rename_map = {
            'WORKDAY ID': 'WORKDAY ID', 'NOM': 'Nom', 'PRENOM': 'Prénom', 'STATUT VISITE': 'Statut Visite',
            'DATE VISITE': 'Date Visite', 'HEURE DEPART': 'Heure Départ', 'HEURE RETOUR': 'Heure Retour',
            'COMMENTAIRES': 'Commentaire', 'DUREE': 'Durée', 'PROJET': 'Projet'
        }
        
        current_renames = {k: v for k, v in rename_map.items() if k in df.columns}
        df = df.rename(columns=current_renames)
        df = df.loc[:, ~df.columns.duplicated()]
        df = df.replace(['*', '-', 'nan', 'None', ''], np.nan)
        
        if 'Date Visite' in df.columns:
            df['Date Visite'] = pd.to_datetime(df['Date Visite'], errors='coerce', dayfirst=True)
        if 'Heure Départ' in df.columns:
            df['Heure Départ'] = pd.to_datetime(df['Heure Départ'], errors='coerce')
        if 'Heure Retour' in df.columns:
            df['Heure Retour'] = pd.to_datetime(df['Heure Retour'], errors='coerce')
        if "DATE D'EMBAUCHE" in df.columns:
            df["DATE D'EMBAUCHE"] = pd.to_datetime(df["DATE D'EMBAUCHE"], errors='coerce', dayfirst=True)
                
        if 'WORKDAY ID' in df.columns:
            df['WORKDAY ID'] = df['WORKDAY ID'].astype(str).str.replace(" ", "").str.replace(".0", "").str.upper()
            
        return df
    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier RTA: {e}")
        return None

# --- AFFICHAGE DES ONGLETS ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📄 1. Planning MC & River", 
    "👥 2. Liste de collaborateurs", 
    "📅 3. Géneration planning visite",
    "📋 4. Planning visite",
    "✅ 5. Import fichier Suivi", 
    "🚫 6. Absences", 
    "📊 7. Dashboard & Extractions"
])

# --- PAGE 1 : REGROUPEMENT AVEC HISTORIQUE INTÉGRÉ ---
with tab1:
    available_weeks = list(st.session_state.history_data['plannings'].keys())
    
    col_h1, col_w1, col_w2 = st.columns([2, 3, 1])
    with col_h1:
        st.header("Planning MC & River")
    with col_w1:
        st.write("")
        if available_weeks:
            available_weeks.sort()
            st.session_state.current_week = st.selectbox("Semaine à afficher", available_weeks, key="p1_week_sel")
        else:
            st.session_state.current_week = None
            st.info("Aucune semaine chargée. Importez un planning ci-dessous.")
    with col_w2:
        st.write("")
        if role == "admin":
            if st.session_state.current_week:
                if st.button("🗑️ Supprimer semaine", key="btn_del_p1", use_container_width=True):
                    del st.session_state.history_data['plannings'][st.session_state.current_week]
                    save_history()
                    st.session_state.current_week = None
                    st.rerun()
        else:
            st.write("🔒 Consultation")
        
    st.markdown("---")
    
    default_week_name = ""
    if files_planning:
        for f in files_planning:
            engine = 'pyxlsb' if f.name.endswith('.xlsb') else None
            wk = get_week_number(f, engine)
            if wk:
                default_week_name = wk
                break
                
    week_name_input = st.text_input("Nom de la semaine à enregistrer", value=default_week_name, placeholder="Ex: S33, Semaine 34, etc.")
    
    if role == "admin":
        if st.button("🚀 Lancer l'import et le regroupement", key="btn_p1"):
            if files_planning:
                week_num = week_name_input.strip() if week_name_input else default_week_name
                if not week_num:
                    week_num = f"S{datetime.datetime.now().isocalendar().week:02d}"
                    
                with st.spinner("Traitement des fichiers en cours..."):
                    planning_df = parse_planning(files_planning, jours)
                    st.session_state.history_data['plannings'][week_num] = planning_df
                    
                    med_list_to_sync = st.session_state.history_data.get('medical_list')
                    if med_list_to_sync is not None:
                        med_list_to_sync = sync_statut_with_plannings(med_list_to_sync, st.session_state.history_data['plannings'])
                        st.session_state.history_data['medical_list'] = med_list_to_sync
                        
                    save_history()
                    st.session_state.current_week = week_num
                st.success(f"Semaine {week_num} chargée et sauvegardée avec succès !")
                st.rerun()
            else:
                st.error("Veuillez importer au moins un fichier de Planning dans le menu de gauche.")
    else:
        st.info("🔒 Action réservée aux administrateurs.")
            
    current_planning = st.session_state.history_data['plannings'].get(st.session_state.current_week) if st.session_state.current_week else None
    if current_planning is not None:
        st.markdown("---")
        display_planning = current_planning.copy()
        
        dates_map = get_dates_from_week(st.session_state.current_week)
        rename_map = {}
        for j in jours:
            d_str = dates_map[j].strftime('%d/%m/%Y')
            if f'{j}_DE' in display_planning.columns:
                rename_map[f'{j}_DE'] = f'{d_str} - Début'
                rename_map[f'{j}_A'] = f'{d_str} - Fin'
                rename_map[f'{j}_Pause'] = f'{d_str} - Pause'
                rename_map[f'{j}_Flag'] = f'{d_str} - Présent'
                
        display_planning = display_planning.rename(columns=rename_map)
        
        for j in jours:
            d_str = dates_map[j].strftime('%d/%m/%Y')
            for suffix in [' - Début', ' - Fin', ' - Pause']:
                col = f'{d_str}{suffix}'
                if col in display_planning.columns:
                    display_planning[col] = display_planning[col].apply(format_time_display)
        
        cols_to_show = ['TRANSPORT', 'WORKDAY ID', 'Paid ID', 'Nom', 'Projet']
        if 'Statut' in display_planning.columns: cols_to_show.append('Statut')
        for j in jours: 
            d_str = dates_map[j].strftime('%d/%m/%Y')
            cols_to_show += [f'{d_str} - Début', f'{d_str} - Fin', f'{d_str} - Présent']
        
        st.dataframe(display_planning[cols_to_show], use_container_width=True, height=600)
        
        st.markdown("---")
        st.download_button(
            label="📥 Exporter le planning (Excel)",
            data=to_excel(display_planning[cols_to_show]),
            file_name=f"planning_{st.session_state.current_week}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# --- PAGE 2 : LISTE DE COLLABORATEURS ---
with tab2:
    medical_list = st.session_state.history_data.get('medical_list')
    
    col_h2, col_imp2, col_del2 = st.columns([4, 2, 2])
    with col_h2:
        st.header("Liste des collaborateurs")
    with col_imp2:
        st.write("")
        if role == "admin":
            if st.button("📥 Charger fichier", key="btn_p2_load", use_container_width=True):
                if file_a_passer is not None:
                    with st.spinner("Lecture du fichier..."):
                        medical_df = parse_liste_visite(file_a_passer)
                        if medical_df is not None:
                            medical_df = sync_statut_with_plannings(medical_df, st.session_state.history_data.get('plannings', {}))
                            st.session_state.history_data['medical_list'] = medical_df
                            save_history()
                            st.success(f"{len(medical_df)} collaborateurs chargés avec succès !")
                            st.rerun()
                else:
                    st.error("Veuillez importer le fichier PLANIFICATION VISITE SYSTEMATIQUE dans le menu de gauche.")
        else:
            st.info("🔒 Admin")
    with col_del2:
        st.write("")
        if role == "admin":
            with st.popover("🗑️ Zone de danger", use_container_width=True):
                st.warning("Cette action supprimera définitivement la liste et tout l'historique de suivi.")
                confirm_p2 = st.checkbox("Je confirme vouloir TOUT supprimer", key="conf_del_p2")
                if st.button("Supprimer ALL", disabled=not confirm_p2, key="btn_del_p2", use_container_width=True):
                    st.session_state.history_data['medical_list'] = None
                    save_history()
                    st.success("Liste supprimée avec succès.")
                    st.rerun()
        else:
            st.write("🔒 Consultation")
            
    if medical_list is not None:
        st.markdown("---")
        st.subheader("Liste complète")
        
        col_f1, col_f2 = st.columns(2)
        with col_f1: 
            opts_projet = sorted(medical_list['Projet'].fillna('N/A').astype(str).unique().tolist())
            sel_projet = st.multiselect("Filtrer par Projet", opts_projet, key="f2_projet")
        with col_f2:
            opts_prio = sorted(medical_list['Priorité Visite'].dropna().astype(str).unique().tolist())
            sel_prio = st.multiselect("Filtrer par Priorité", opts_prio, key="f2_prio")
            
        df_filtered_p2 = medical_list.copy()
        if sel_projet: df_filtered_p2 = df_filtered_p2[df_filtered_p2['Projet'].astype(str).isin(sel_projet)]
        if sel_prio: df_filtered_p2 = df_filtered_p2[df_filtered_p2['Priorité Visite'].astype(str).isin(sel_prio)]
        
        export_cols = ['WORKDAY ID', 'Payroll ID', 'Nom', 'Prénom', 'Statut', 'Date d\'embauche', 'Ancienneté', 'Projet', 'Priorité Visite']
        display_p2 = df_filtered_p2.copy()
        display_p2['Date d\'embauche'] = pd.to_datetime(display_p2['Date d\'embauche'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('')
        
        st.dataframe(display_p2[export_cols], use_container_width=True, height=500)
        
        st.markdown("---")
        st.download_button(
            label="📥 Exporter la liste (Excel)",
            data=to_excel(display_p2[export_cols]),
            file_name="export_liste_visite.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("Aucune liste chargée.")

# --- PAGE 3 : PLANIFICATION SUR 5 JOURS ET GESTION ---
with tab3:
    medical_list = st.session_state.history_data.get('medical_list')
    
    col_h3, col_w3 = st.columns([4, 2])
    with col_h3:
        st.header("📅 Planification automatisée des visites (5 jours)")
    with col_w3:
        st.write("")
        if medical_list is not None:
            available_weeks = list(st.session_state.history_data['plannings'].keys())
            if available_weeks:
                available_weeks.sort()
                st.session_state.current_week = st.selectbox("Semaine à planifier", available_weeks, key="p3_week_sel")
            else:
                st.session_state.current_week = None
    
    if medical_list is None:
        st.warning("Veuillez charger la liste des visiteurs (Page 2).")
    else:
        available_weeks = list(st.session_state.history_data['plannings'].keys())
        if not available_weeks:
            st.warning("Veuillez importer un planning sur la Page 1.")
        else:
            current_planning = st.session_state.history_data['plannings'].get(st.session_state.current_week)
            
            dates_map = get_dates_from_week(st.session_state.current_week)
            match = re.search(r'\d+', str(st.session_state.current_week))
            week_num = int(match.group()) if match else datetime.date.today().isocalendar().week
            year = datetime.date.today().year
            monday = datetime.date.fromisocalendar(year, week_num, 1)
            
            st.markdown("---")
            
            with st.form("planning_form"):
                days_to_plan = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']
                cols = st.columns(5)
                plan_configs = []
                
                for i, day_name in enumerate(days_to_plan):
                    with cols[i]:
                        st.markdown(f"**{day_name}**")
                        actif = st.checkbox(f"Activer", value=True, key=f"actif_{i}")
                        
                        d = monday + datetime.timedelta(days=i)
                        st.date_input("Date", d, key=f"date_{i}_{st.session_state.current_week}", label_visibility="collapsed", disabled=True)
                        
                        c1, c2 = st.columns(2)
                        with c1: t1 = st.time_input("Début", datetime.time(9, 0), key=f"t1_{i}")
                        with c2: t2 = st.time_input("Fin", datetime.time(16, 0), key=f"t2_{i}")
                        n1 = st.number_input("Nb River", 0, 100, 5, key=f"n1_{i}")
                        n2 = st.number_input("Nb Autres", 0, 100, 20, key=f"n2_{i}")
                        prio = st.selectbox("Prioriser", ["Aucune priorité", "Visite systématique", "Visite d'embauche"], key=f"prio_{i}")
                        statut_filter = st.selectbox("Statut", ["Tous", "CC", "ENC"], key=f"statut_{i}")
                        plan_configs.append({
                            'actif': actif, 'day_name': day_name, 'date': d, 'debut': t1, 'fin': t2,
                            'qty_river': n1, 'qty_others': n2, 'prio': prio, 'statut_filter': statut_filter
                        })
                        
                submitted = st.form_submit_button("🚀 Générer la planification automatique", disabled=(role != "admin"))
                
            if submitted:
                total_planned = 0
                
                for config in plan_configs:
                    if not config['actif']:
                        continue
                        
                    date_obj = config['date']
                    day_idx = date_obj.weekday()
                    sel_day = jours[day_idx]
                    de_col = f"{sel_day}_DE"
                    a_col = f"{sel_day}_A"
                    
                    cols_to_drop = [c for c in ['Nom', 'Projet', 'Statut'] if c in current_planning.columns]
                    planning_to_merge = current_planning.drop(columns=cols_to_drop).copy()
                    
                    merged_wid = pd.merge(medical_list, planning_to_merge, on='WORKDAY ID', how='inner', suffixes=('', '_planning'))
                    
                    unmatched_med = medical_list[~medical_list['WORKDAY ID'].isin(merged_wid['WORKDAY ID'])].copy()
                    if 'Payroll ID' in unmatched_med.columns and 'Paid ID' in planning_to_merge.columns:
                        unmatched_med_renamed = unmatched_med.rename(columns={'Payroll ID': 'Paid ID'})
                        merged_pid = pd.merge(unmatched_med_renamed, planning_to_merge, on='Paid ID', how='inner', suffixes=('', '_planning'))
                        merged_pid['WORKDAY ID'] = merged_pid['WORKDAY ID'].fillna(merged_pid.get('WORKDAY ID_planning'))
                        merged_wid = pd.concat([merged_wid, merged_pid], ignore_index=True)
                        
                    working_df = merged_wid.copy()
                    
                    if working_df.empty:
                        continue
                        
                    working_df = working_df[working_df[de_col].apply(is_planned)].copy()
                    
                    def is_available_during_slot(row, de_c, a_c, c_debut, c_fin):
                        shift_debut = get_time_obj(row[de_c])
                        shift_fin = get_time_obj(row[a_c])
                        if not shift_debut or not shift_fin: return False
                        return shift_debut < c_fin and shift_fin > c_debut
                        
                    working_df['_is_avail'] = working_df.apply(lambda r: is_available_during_slot(r, de_col, a_col, config['debut'], config['fin']), axis=1)
                    working_df = working_df[working_df['_is_avail']].copy()
                    
                    if config.get('statut_filter') and config['statut_filter'] != "Tous":
                        working_df = working_df[working_df['Statut'].astype(str).str.upper() == config['statut_filter'].upper()]
                    
                    working_df = working_df[~working_df['Statut Visite'].isin(['Planifié', 'Visite Faite'])]
                    
                    working_df['_is_replan'] = working_df.apply(lambda r: 'absent' in str(r.get('Statut Visite', '')).lower() or 'report' in str(r.get('Statut Visite', '')).lower() or 'absent' in str(r.get('Commentaire', '')).lower() or 'report' in str(r.get('Commentaire', '')).lower(), axis=1)
                    
                    if config['prio'] != "Aucune priorité" and 'Priorité Visite' in working_df.columns:
                        working_df['_is_priority'] = working_df['Priorité Visite'].astype(str).str.strip().str.lower() == config['prio'].lower()
                        working_df = working_df.sort_values(by=['_is_replan', '_is_priority', 'Ancienneté_num'], ascending=[False, False, False])
                    else:
                        working_df['_is_priority'] = False
                        working_df = working_df.sort_values(by=['_is_replan', 'Ancienneté_num'], ascending=[False, False])
                    
                    is_river = working_df['Projet'].astype(str).str.contains('RIVER|AMAZON', case=False, na=False)
                    df_river = working_df[is_river]
                    df_others = working_df[~is_river]
                    
                    slots = []
                    current_slot_dt = datetime.datetime.combine(date_obj, config['debut'])
                    end_slot_dt = datetime.datetime.combine(date_obj, config['fin']) - datetime.timedelta(minutes=30)
                    while current_slot_dt <= end_slot_dt:
                        slots.append(current_slot_dt.time())
                        current_slot_dt += datetime.timedelta(minutes=30)
                        
                    slot_counts = {slot: 0 for slot in slots}
                    
                    def assign_slots(df_group, target_qty):
                        picked_count = 0
                        for idx, row in df_group.iterrows():
                            if picked_count >= target_qty:
                                break
                            
                            shift_d = get_time_obj(row[de_col])
                            shift_f = get_time_obj(row[a_col])
                            
                            if not shift_d or not shift_f:
                                continue
                            
                            shift_f_eval = shift_f
                            if shift_f < shift_d:
                                shift_f_eval = datetime.time(23, 59)
                            
                            assigned_slot = None
                            for slot in slots:
                                slot_end_dt = datetime.datetime.combine(date_obj, slot) + datetime.timedelta(minutes=30)
                                slot_end = slot_end_dt.time()
                                
                                if shift_d <= slot and shift_f_eval >= slot_end:
                                    if slot_counts[slot] < 4:
                                        assigned_slot = slot
                                        break
                                    
                            if assigned_slot is not None:
                                wid = row['WORKDAY ID']
                                medical_list.loc[medical_list['WORKDAY ID'] == wid, 'Statut Visite'] = 'Planifié'
                                medical_list.loc[medical_list['WORKDAY ID'] == wid, 'Date Visite'] = pd.to_datetime(date_obj)
                                slot_dt = datetime.datetime.combine(date_obj, assigned_slot)
                                medical_list.loc[medical_list['WORKDAY ID'] == wid, 'Créneau Visite'] = pd.to_datetime(slot_dt)
                                
                                comment_series = medical_list.loc[medical_list['WORKDAY ID'] == wid, 'Commentaire']
                                med_comment = str(comment_series.values[0]).lower() if not comment_series.empty else ''
                                if 'absent' in med_comment or 'report' in med_comment:
                                    medical_list.loc[medical_list['WORKDAY ID'] == wid, 'Commentaire'] = ''
                                    medical_list.loc[medical_list['WORKDAY ID'] == wid, 'Heure Départ'] = pd.NaT
                                    medical_list.loc[medical_list['WORKDAY ID'] == wid, 'Heure Retour'] = pd.NaT
                                    
                                slot_counts[assigned_slot] += 1
                                picked_count += 1
                        return picked_count

                    picked_river = assign_slots(df_river, config['qty_river'])
                    picked_others = assign_slots(df_others, config['qty_others'])
                    total_planned += picked_river + picked_others
                        
                st.session_state.history_data['medical_list'] = medical_list
                save_history()
                
                if total_planned > 0:
                    st.success(f"✅ {total_planned} collaborateurs planifiés au total sur les jours actifs !")
                else:
                    st.warning("Aucun collaborateur ne correspond aux critères pour les jours actifs (Créneaux ou Shifts incompatibles).")
            
            if role != "admin":
                st.info("🔒 Action réservée aux administrateurs.")

            st.markdown("---")
            st.subheader(f"📋 Personnes planifiées pour {st.session_state.current_week}")
            
            start_date = monday
            end_date = monday + datetime.timedelta(days=6)
            
            planned_this_week = medical_list[
                (medical_list['Statut Visite'] == 'Planifié') & 
                (pd.to_datetime(medical_list['Date Visite'], errors='coerce') >= pd.Timestamp(start_date)) & 
                (pd.to_datetime(medical_list['Date Visite'], errors='coerce') <= pd.Timestamp(end_date))
            ].copy()
            
            planned_this_week = planned_this_week.drop(columns=['Shift Début', 'Shift Fin'], errors='ignore')
            
            def enrich_shifts(df_to_enrich, history_plannings):
                if df_to_enrich.empty:
                    df_to_enrich['Shift Début'] = ''
                    df_to_enrich['Shift Fin'] = ''
                    return df_to_enrich
                df_to_enrich['DayOfWeek'] = pd.to_datetime(df_to_enrich['Date Visite'], errors='coerce').dt.dayofweek
                df_to_enrich['WeekNum'] = pd.to_datetime(df_to_enrich['Date Visite'], errors='coerce').dt.isocalendar().week
                shifts_debut = []
                shifts_fin = []
                indexed_plannings = {w_name: p_df.set_index('WORKDAY ID') for w_name, p_df in history_plannings.items()}
                for _, row in df_to_enrich.iterrows():
                    wid = row['WORKDAY ID']
                    day_idx = row['DayOfWeek']
                    week_num = row['WeekNum']
                    found_debut = ''
                    found_fin = ''
                    if pd.notna(week_num) and pd.notna(day_idx) and day_idx < 7:
                        for w_name, p_idx in indexed_plannings.items():
                            if str(int(week_num)).zfill(2) in w_name:
                                if wid in p_idx.index:
                                    day_name = jours[int(day_idx)]
                                    de_col = f"{day_name}_DE"
                                    a_col = f"{day_name}_A"
                                    if de_col in p_idx.columns:
                                        found_debut = format_time_display(p_idx.loc[wid, de_col])
                                        found_fin = format_time_display(p_idx.loc[wid, a_col])
                                break
                    shifts_debut.append(found_debut)
                    shifts_fin.append(found_fin)
                df_to_enrich['Shift Début'] = shifts_debut
                df_to_enrich['Shift Fin'] = shifts_fin
                df_to_enrich = df_to_enrich.drop(columns=['DayOfWeek', 'WeekNum'])
                return df_to_enrich

            planned_this_week = enrich_shifts(planned_this_week, st.session_state.history_data['plannings'])
            
            if not planned_this_week.empty:
                display_planned = planned_this_week[['WORKDAY ID', 'Payroll ID', 'Nom', 'Projet', 'Date Visite', 'Créneau Visite', 'Shift Début', 'Shift Fin', 'Priorité Visite']].copy()
                display_planned['Date Visite'] = display_planned['Date Visite'].dt.strftime('%d/%m/%Y')
                display_planned['Créneau Visite'] = pd.to_datetime(display_planned['Créneau Visite'], errors='coerce').dt.strftime('%H:%M').fillna('')
                
                st.dataframe(display_planned, use_container_width=True, height=300)
                
                col_d1, col_d2 = st.columns([1, 3])
                with col_d1:
                    if role == "admin":
                        if st.button("🗑️ Tout déplanifier (cette semaine)"):
                            mask = (medical_list['Statut Visite'] == 'Planifié') & \
                                   (pd.to_datetime(medical_list['Date Visite'], errors='coerce') >= pd.Timestamp(start_date)) & \
                                   (pd.to_datetime(medical_list['Date Visite'], errors='coerce') <= pd.Timestamp(end_date))
                            medical_list.loc[mask, 'Statut Visite'] = 'Non Planifié'
                            medical_list.loc[mask, 'Date Visite'] = pd.NaT
                            medical_list.loc[mask, 'Créneau Visite'] = pd.NaT
                            medical_list.loc[mask, 'Heure Départ'] = pd.NaT
                            medical_list.loc[mask, 'Heure Retour'] = pd.NaT
                            medical_list.loc[mask, 'Commentaire'] = ''
                            st.session_state.history_data['medical_list'] = medical_list
                            save_history()
                            st.success("Toutes les planifications de la semaine ont été supprimées.")
                            st.rerun()
                    else:
                        st.write("🔒 Consultation")
                
                if role == "admin":
                    with st.expander("❌ Annuler ou modifier la planification (Tableau interactif)", expanded=True):
                        st.markdown("💡 **Modifiez directement les cellules du tableau ci-dessous.** Pour planifier ou déplanifier quelqu'un, changez son Statut. Cliquez sur le bouton Sauvegarder en bas une fois terminé.")
                        
                        edit_df = medical_list[['WORKDAY ID', 'Nom', 'Projet', 'Statut Visite', 'Date Visite', 'Créneau Visite']].copy()
                        edit_df['Date Visite'] = pd.to_datetime(edit_df['Date Visite'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('')
                        edit_df['Créneau Visite'] = pd.to_datetime(edit_df['Créneau Visite'], errors='coerce').dt.strftime('%H:%M').fillna('')
                        
                        edited_df = st.data_editor(
                            edit_df,
                            num_rows="dynamic",
                            use_container_width=True,
                            height=600,
                            key="editor_p3_full",
                            disabled=['WORKDAY ID', 'Nom', 'Projet']
                        )
                        
                        if st.button("💾 Sauvegarder les modifications manuelles"):
                            edited_df['Date Visite'] = pd.to_datetime(edited_df['Date Visite'], format='%d/%m/%Y', errors='coerce')
                            edited_df['Créneau Visite'] = pd.to_datetime(edited_df['Créneau Visite'], format='%H:%M', errors='coerce')
                            
                            for idx, row in edited_df.iterrows():
                                wid = row['WORKDAY ID']
                                mask = medical_list['WORKDAY ID'] == wid
                                
                                statut = str(row['Statut Visite']).strip()
                                
                                if statut.lower() == 'non planifié':
                                    medical_list.loc[mask, 'Statut Visite'] = 'Non Planifié'
                                    medical_list.loc[mask, 'Date Visite'] = pd.NaT
                                    medical_list.loc[mask, 'Créneau Visite'] = pd.NaT
                                else:
                                    medical_list.loc[mask, 'Statut Visite'] = statut
                                    medical_list.loc[mask, 'Date Visite'] = row['Date Visite']
                                    medical_list.loc[mask, 'Créneau Visite'] = row['Créneau Visite']
                            
                            st.session_state.history_data['medical_list'] = medical_list
                            save_history()
                            st.success("Modifications manuelles sauvegardées avec succès !")
                            st.rerun()
            else:
                st.info("Aucune personne planifiée pour cette semaine pour le moment.")

# --- PAGE 4 : PLANIFICATION GLOBALE ---
with tab4:
    medical_list = st.session_state.history_data.get('medical_list')
    
    if medical_list is not None:
        planned_list = medical_list[medical_list['Statut Visite'] == 'Planifié'].copy()
        
        if not planned_list.empty:
            planned_list = enrich_shifts(planned_list, st.session_state.history_data['plannings'])
            show_cols = ['WORKDAY ID', 'Payroll ID', 'Nom', 'Prénom', 'Statut', 'Date d\'embauche', 'Ancienneté', 'Projet', 'Priorité Visite', 'Statut Visite', 'Date Visite', 'Créneau Visite', 'Shift Début', 'Shift Fin']
            planned_list['Date Visite'] = pd.to_datetime(planned_list['Date Visite'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('')
            planned_list['Date d\'embauche'] = pd.to_datetime(planned_list['Date d\'embauche'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('')
            planned_list['Créneau Visite'] = pd.to_datetime(planned_list['Créneau Visite'], errors='coerce').dt.strftime('%H:%M').fillna('')
            
            col_title, col_export, col_delete = st.columns([4, 2, 2])
            with col_title:
                st.header("📋 Planning visite")
            with col_export:
                st.write("")
                st.download_button(
                    label="📥 Exporter (Excel)", data=to_excel(planned_list[show_cols]),
                    file_name="planification_globale.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True
                )
            with col_delete:
                st.write("")
                if role == "admin":
                    with st.popover("🗑️ Zone de danger", use_container_width=True):
                        st.warning("Supprime DÉFINITIVEMENT TOUTES les planifications de TOUTES les semaines.")
                        confirm_p4 = st.checkbox("Je confirme vouloir TOUT supprimer", key="conf_del_p4")
                        if st.button("Supprimer ALL", disabled=not confirm_p4, key="btn_del_p4", use_container_width=True):
                            mask = medical_list['Statut Visite'] == 'Planifié'
                            medical_list.loc[mask, 'Statut Visite'] = 'Non Planifié'
                            medical_list.loc[mask, 'Date Visite'] = pd.NaT
                            medical_list.loc[mask, 'Créneau Visite'] = pd.NaT
                            medical_list.loc[mask, 'Heure Départ'] = pd.NaT
                            medical_list.loc[mask, 'Heure Retour'] = pd.NaT
                            medical_list.loc[mask, 'Commentaire'] = ''
                            st.session_state.history_data['medical_list'] = medical_list
                            save_history()
                            st.success("Toutes les planifications ont été supprimées.")
                            st.rerun()
                else:
                    st.write("🔒 Consultation")
            
            st.markdown("---")
            st.dataframe(planned_list[show_cols], use_container_width=True, height=600)
        else:
            st.header("📋 Planning visite")
            st.info("Aucune visite planifiée pour le moment.")
    else:
        st.header("📋 Planning visite")
        st.warning("Aucune donnée disponible. Importez la liste (Page 2).")

# --- PAGE 5 : IMPORT RTA & SUIVI ---
with tab5:
    col_h5, col_imp5, col_del5 = st.columns([4, 2, 2])
    with col_h5:
        st.header("📥 Import du fichier Suivi")
    with col_imp5:
        st.write("")
        if role == "admin":
            if st.button("📥 Importer RTA", key="btn_imp_p5", use_container_width=True):
                if file_rta is not None:
                    with st.spinner("Mise à jour des données..."):
                        rta_df = parse_rta_file(file_rta)
                        if rta_df is not None:
                            st.session_state.history_data['rta_data'] = rta_df
                            save_history()
                            st.success("✅ Données RTA importées avec succès !")
                            st.rerun()
                else:
                    st.error("Veuillez importer le fichier RTA dans le menu de gauche.")
        else:
            st.info("🔒 Admin")
    with col_del5:
        st.write("")
        if role == "admin":
            if st.session_state.history_data.get('rta_data') is not None:
                if st.button("🗑️ Supprimer RTA", key="btn_del_p5", use_container_width=True):
                    st.session_state.history_data['rta_data'] = None
                    save_history()
                    st.success("Données RTA supprimées.")
                    st.rerun()
        else:
            st.write("🔒 Consultation")
            
    st.markdown("---")
    
    if role == "admin":
        st.markdown("Importez le fichier rempli par les RTA (feuille 'Suivi'). Les données s'afficheront ci-dessous et alimenteront le Dashboard (Page 7).")
        st.markdown("---")
    
    st.subheader("Données de la feuille 'Suivi'")
    
    rta_data = st.session_state.history_data.get('rta_data')
    if rta_data is not None:
        display_rta = rta_data.copy()
        
        display_rta.columns = [str(c).strip() for c in display_rta.columns]
        rename_dict = { 'PROJET': 'Projet', 'COMMENTAIRES': 'Commentaire' }
        display_rta = display_rta.rename(columns={k: v for k, v in rename_dict.items() if k in display_rta.columns})
        
        if 'Nom' in display_rta.columns and 'Prénom' in display_rta.columns:
            display_rta['Nom complet'] = display_rta['Nom'].fillna('').astype(str) + ' ' + display_rta['Prénom'].fillna('').astype(str)
            display_rta = display_rta.drop(columns=['Nom', 'Prénom'])
        else:
            display_rta['Nom complet'] = ''
            
        medical_list = st.session_state.history_data.get('medical_list')
        if medical_list is not None and 'Payroll ID' in medical_list.columns:
            payroll_df = medical_list[['WORKDAY ID', 'Payroll ID']].drop_duplicates(subset=['WORKDAY ID']).copy()
            payroll_df['WORKDAY ID'] = payroll_df['WORKDAY ID'].astype(str).str.strip()
            display_rta['WORKDAY ID'] = display_rta['WORKDAY ID'].astype(str).str.strip()
            display_rta = display_rta.merge(payroll_df, on='WORKDAY ID', how='left')
        else:
            display_rta['Payroll ID'] = ''
            
        if 'Date Visite' in display_rta.columns:
            display_rta['Date Visite'] = pd.to_datetime(display_rta['Date Visite'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('')
        if 'Heure Départ' in display_rta.columns:
            display_rta['Heure Départ'] = pd.to_datetime(display_rta['Heure Départ'], errors='coerce').dt.strftime('%H:%M').fillna('')
        if 'Heure Retour' in display_rta.columns:
            display_rta['Heure Retour'] = pd.to_datetime(display_rta['Heure Retour'], errors='coerce').dt.strftime('%H:%M').fillna('')
            
        desired_order = ['WORKDAY ID', 'Payroll ID', 'Nom complet', 'Projet', 'Statut Visite', 'Date Visite', 'Heure Départ', 'Heure Retour', 'Durée', 'Commentaire']
        final_cols = [c for c in desired_order if c in display_rta.columns]
        
        if 'Durée' in final_cols:
            display_rta['Durée'] = display_rta['Durée'].astype(str).replace('NaT', '').replace('nan', '')
            
        st.dataframe(display_rta[final_cols], use_container_width=True, height=600)
    else:
        st.info("Aucune donnée RTA importée pour le moment.")

# --- PAGE 6 : ABSENCES ---
with tab6:
    col_h6, col_r6 = st.columns([5, 1])
    with col_h6:
        st.header("🚫 Suivi des Absences")
    with col_r6:
        st.write("")
        if st.button("🔄 Actualiser", key="refresh_p6", use_container_width=True):
            st.rerun()
            
    rta_data = st.session_state.history_data.get('rta_data')
    
    if rta_data is not None:
        abs_df = rta_data.copy()
        
        if 'Statut Visite' not in abs_df.columns: abs_df['Statut Visite'] = ''
        if 'Commentaire' not in abs_df.columns: abs_df['Commentaire'] = ''
            
        abs_mask = abs_df['Statut Visite'].astype(str).str.lower().str.contains('absent|reporté|reporte', na=False) | \
                   abs_df['Commentaire'].astype(str).str.lower().str.contains('absent|reporté|reporte', na=False)
        abs_df = abs_df[abs_mask].copy()
        
        if 'Nom' in abs_df.columns and 'Prénom' in abs_df.columns:
            abs_df['Nom complet'] = abs_df['Nom'].fillna('').astype(str) + ' ' + abs_df['Prénom'].fillna('').astype(str)
        else:
            abs_df['Nom complet'] = ''
            
        show_cols = ['WORKDAY ID', 'Nom complet', 'Projet', 'Priorité Visite', 'Statut Visite', 'Date Visite', 'Commentaire']
        show_cols = [c for c in show_cols if c in abs_df.columns]
        
        if 'Date Visite' in abs_df.columns:
            abs_df['Date Visite'] = pd.to_datetime(abs_df['Date Visite'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('')
        
        st.dataframe(abs_df[show_cols], use_container_width=True, height=600)
        
        st.markdown("---")
        st.download_button(
            label="📥 Exporter les absences (Excel)", data=to_excel(abs_df[show_cols]),
            file_name="absences_visites.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("Aucune donnée disponible. Veuillez importer le fichier RTA (Page 5).")

# --- PAGE 7 : DASHBOARD & EXTRACTIONS ---
with tab7:
    col_h7, col_r7 = st.columns([5, 1])
    with col_h7:
        st.header("État d'avancement et extractions")
    with col_r7:
        st.write("")
        if st.button("🔄 Actualiser", key="refresh_p7", use_container_width=True):
            st.rerun()
            
    rta_data = st.session_state.history_data.get('rta_data')
    
    if rta_data is not None:
        med_df = rta_data.copy()
        
        if 'Heure Départ' in med_df.columns and 'Heure Retour' in med_df.columns:
            med_df['Heure Départ'] = pd.to_datetime(med_df['Heure Départ'], errors='coerce')
            med_df['Heure Retour'] = pd.to_datetime(med_df['Heure Retour'], errors='coerce')
            med_df['Durée (min)'] = (med_df['Heure Retour'] - med_df['Heure Départ']).dt.total_seconds() / 60
            med_df.loc[med_df['Durée (min)'] < 0, 'Durée (min)'] = np.nan 
        else:
            med_df['Durée (min)'] = np.nan
            
        if 'Projet' in med_df.columns:
            med_df['Projet_Affichage'] = med_df['Projet'].apply(get_mapped_project)
        else:
            med_df['Projet_Affichage'] = 'N/A'
            
        for col in ['Statut Visite', 'Commentaire', 'Nom', 'Prénom', 'Date Visite']:
            if col not in med_df.columns:
                med_df[col] = ''
        
        med_df['Graph Status'] = med_df.apply(get_final_status, axis=1)
        
        st.markdown("---")
        
        available_projects = sorted(med_df['Projet_Affichage'].unique().tolist())
        selected_projects = st.multiselect("Filtrer par Projet", available_projects, default=available_projects, key="p7_projet_filter")
        
        if selected_projects:
            med_df = med_df[med_df['Projet_Affichage'].isin(selected_projects)]
        else:
            med_df = med_df.iloc[0:0]
            
        condition_fait = med_df['Graph Status'] == 'Visite effectuée'
        condition_abs = med_df['Graph Status'] == 'Absent/Reporté'
        
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        total_a_passer = len(med_df)
        total_fait = len(med_df[condition_fait])
        total_planifie = len(med_df[med_df['Statut Visite'].astype(str).str.lower().isin(['planifié', 'planifie'])])
        total_absent = len(med_df[condition_abs])
        
        col_m1.metric("Total à passer", total_a_passer)
        col_m2.metric("Visites effectuées", total_fait, delta=f"{(total_fait/total_a_passer*100):.1f}%" if total_a_passer > 0 else "0%")
        col_m3.metric("Planifiés", total_planifie)
        col_m4.metric("Absents / Reportés", total_absent)
        
        st.markdown("---")
        
        project_order = med_df['Projet_Affichage'].value_counts().index.tolist()
        
        st.subheader("1. Total à passer vs Planifié")
        g1_df = med_df.copy()
        
        if 'Statut Visite' in g1_df.columns:
            g1_df['Statut Graph'] = g1_df['Statut Visite'].astype(str).apply(
                lambda x: 'Planifié' if str(x).strip().lower() in ['planifié', 'planifie'] else 'Non Planifié'
            )
        else:
            g1_df['Statut Graph'] = 'Non Planifié'
        
        if not g1_df.empty:
            counts_df = g1_df.groupby(['Projet_Affichage', 'Statut Graph']).size().unstack(fill_value=0).reset_index()
            for col in ['Planifié', 'Non Planifié']:
                if col not in counts_df.columns:
                    counts_df[col] = 0
            counts_df['Total'] = counts_df['Planifié'] + counts_df['Non Planifié']
            counts_df = counts_df.sort_values('Total', ascending=False)
            
            fig1 = px.bar(
                counts_df, 
                x='Projet_Affichage', 
                y='Total',
                color_discrete_sequence=['#747474']
            )
            fig1.data[0].name = 'Total'
            fig1.data[0].showlegend = True
            fig1.data[0].text = counts_df['Total']
            fig1.data[0].textposition = 'outside'
            
            fig1.add_bar(
                x=counts_df['Projet_Affichage'], 
                y=counts_df['Planifié'],
                name='Planifié',
                marker_color='#003D5B',
                text=counts_df['Planifié'],
                textposition='auto'
            )
            
            fig1.update_layout(
                barmode='overlay', 
                legend_title_text='Légende',
                yaxis_range=[0, counts_df['Total'].max() * 1.15]
            )
            st.plotly_chart(fig1, use_container_width=True)
        else:
            st.info("Aucune donnée disponible.")
            
        st.markdown("---")
        
        st.subheader("2. Planifié vs Visite effectuée vs Absents/Reporté")
        
        g2_data = []
        for proj in project_order:
            proj_df = med_df[med_df['Projet_Affichage'] == proj]
            
            planifie_count = len(proj_df[proj_df['Statut Visite'].astype(str).str.strip().str.lower().isin(['planifié', 'planifie'])])
            
            com_lower = proj_df['Commentaire'].astype(str).str.lower()
            faite_count = len(proj_df[com_lower.str.contains('ok', na=False)])
            abs_count = len(proj_df[com_lower.str.contains('absent|report', na=False)])
            
            if planifie_count + faite_count + abs_count > 0:
                g2_data.append({
                    'Projet_Affichage': proj, 
                    'Planifié': planifie_count, 
                    'Visite effectuée': faite_count, 
                    'Absent/Reporté': abs_count
                })
            
        counts_g2_df = pd.DataFrame(g2_data)
        
        if not counts_g2_df.empty:
            counts_g2_df = counts_g2_df.sort_values('Planifié', ascending=False)
            g2_order = counts_g2_df['Projet_Affichage'].tolist()
            
            fig2 = px.bar(
                counts_g2_df, 
                x='Projet_Affichage', 
                y=['Planifié', 'Visite effectuée', 'Absent/Reporté'],
                barmode='group',
                text_auto=True,
                category_orders={'Projet_Affichage': g2_order},
                color_discrete_sequence=['#003D5B', '#25E2CC', '#FBCA18']
            )
            fig2.update_traces(textposition='outside')
            max_val = counts_g2_df[['Planifié', 'Visite effectuée', 'Absent/Reporté']].max().max()
            fig2.update_layout(yaxis_range=[0, max_val * 1.15])
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Aucune donnée disponible.")
            
        st.markdown("---")
        
        col_p1, col_p2 = st.columns([1, 2])
        with col_p1:
            st.subheader("Avancement Global")
            
            ANNEAU_ROTATION = 0
            ANNEAU_DIRECTION = 'clockwise'
            ANNEAU_EPAISSEUR = 0.6
            HACHURE_TAILLE = 8
            
            if total_a_passer > 0:
                val_effectuee = total_fait
                val_reste_planifie = max(0, total_planifie - total_fait) 
                val_non_planifie = max(0, total_a_passer - total_planifie)
                
                donut_data = []
                if val_effectuee > 0:
                    donut_data.append({'Statut': 'Visite effectuée', 'Nombre': val_effectuee})
                if val_reste_planifie > 0:
                    donut_data.append({'Statut': 'Reste Planifié', 'Nombre': val_reste_planifie})
                if val_non_planifie > 0:
                    donut_data.append({'Statut': 'Non Planifié', 'Nombre': val_non_planifie})
                    
                donut_df = pd.DataFrame(donut_data)
                
                fig_site = px.pie(
                    donut_df, 
                    names='Statut', 
                    values='Nombre', 
                    color='Statut',
                    title="Planifié & Effectuée vs Total", 
                    hole=ANNEAU_EPAISSEUR,
                    color_discrete_map={
                        'Visite effectuée': '#25E2CC', 
                        'Reste Planifié': '#003D5B',   
                        'Non Planifié': '#747474'      
                    }
                )
                
                fig_site.update_traces(sort=False, rotation=ANNEAU_ROTATION, direction=ANNEAU_DIRECTION)
                
                shapes = ['/' if s == 'Visite effectuée' else '' for s in donut_df['Statut']]
                
                bgcolors = ['#003D5B' if s == 'Visite effectuée' else ('#003D5B' if s == 'Reste Planifié' else '#747474') for s in donut_df['Statut']]
                fcolors = ['#25E2CC' if s == 'Visite effectuée' else '#FFFFFF' for s in donut_df['Statut']]
                
                fig_site.update_traces(
                    marker=dict(
                        pattern=dict(
                            shape=shapes, 
                            fillmode='overlay', 
                            fgcolor=fcolors,
                            bgcolor=bgcolors, 
                            size=HACHURE_TAILLE
                        )
                    )
                )
                
                pct_planif = (total_planifie / total_a_passer * 100)
                pct_fait = (total_fait / total_a_passer * 100)
                
                custom_text = []
                for s in donut_df['Statut']:
                    if s == 'Visite effectuée':
                        custom_text.append(f"Visite effectuée<br>{total_fait} ({pct_fait:.1f}%)")
                    elif s == 'Reste Planifié':
                        custom_text.append(f"Total Planifié<br>{total_planifie} ({pct_planif:.1f}%)")
                    else:
                        custom_text.append("")
                
                pull_values = [0.05 if s in ['Visite effectuée', 'Reste Planifié'] else 0 for s in donut_df['Statut']]
                
                fig_site.update_traces(
                    text=custom_text, 
                    textinfo='text', 
                    textposition='outside',
                    outsidetextfont_size=12,
                    pull=pull_values,
                    insidetextorientation='radial'
                )
                fig_site.update_layout(showlegend=False, margin=dict(t=40, b=20, l=20, r=20))
                
                st.plotly_chart(fig_site, use_container_width=True)
            else:
                st.info("Aucune donnée disponible.")
            
        with col_p2:
            st.subheader("Durée moyenne par jour")
            med_df['Date'] = pd.to_datetime(med_df['Date Visite'], errors='coerce').dt.date
            avg_df = med_df.dropna(subset=['Durée (min)']).groupby('Date')['Durée (min)'].mean().reset_index()
            if not avg_df.empty:
                avg_df['Durée Moyenne'] = avg_df['Durée (min)'].apply(format_duration)
                st.dataframe(avg_df[['Date', 'Durée Moyenne']], use_container_width=True, hide_index=True)
            else:
                st.info("Aucune donnée de durée disponible pour le moment.")
        
        st.markdown("---")
        
        st.subheader("Top 5 des durées les plus élevées")
        top5_df = med_df.dropna(subset=['Durée (min)']).nlargest(5, 'Durée (min)')[['WORKDAY ID', 'Nom', 'Prénom', 'Projet_Affichage', 'Heure Départ', 'Heure Retour', 'Durée (min)']].copy()
        if not top5_df.empty:
            top5_df['Heure Départ'] = top5_df['Heure Départ'].dt.strftime('%H:%M')
            top5_df['Heure Retour'] = top5_df['Heure Retour'].dt.strftime('%H:%M')
            top5_df['Durée'] = top5_df['Durée (min)'].apply(format_duration)
            top5_df['Nom Complet'] = top5_df['Nom'].astype(str) + ' ' + top5_df['Prénom'].astype(str)
            st.dataframe(top5_df[['WORKDAY ID', 'Nom Complet', 'Projet_Affichage', 'Heure Départ', 'Heure Retour', 'Durée']], use_container_width=True, hide_index=True)
        else:
            st.info("Aucune donnée de durée disponible pour le moment.")
        
        st.markdown("---")
        
        st.subheader("✅ Liste des visites effectuées")
        
        done_df = med_df[med_df['Commentaire'].astype(str).str.lower().str.contains('ok', na=False)].copy()
        
        if not done_df.empty:
            done_df['Nom complet'] = done_df['Nom'].fillna('').astype(str) + ' ' + done_df['Prénom'].fillna('').astype(str)
            
            if 'Payroll ID' not in done_df.columns:
                done_df['Payroll ID'] = ''
            if 'Projet' not in done_df.columns:
                done_df['Projet'] = done_df['Projet_Affichage'] if 'Projet_Affichage' in done_df.columns else 'N/A'
                
            done_df['Statut visite'] = 'Done'
            
            cols_to_show_done = ['WORKDAY ID', 'Payroll ID', 'Nom complet', 'Projet', 'Statut visite']
            st.dataframe(done_df[cols_to_show_done], use_container_width=True, hide_index=True)
        else:
            st.info("Aucune visite effectuée (commentaire OK) pour le moment.")
        
        st.markdown("---")
        
        st.subheader("📅 Extraction du Rapport Journalier")
        col_r1, col_r2 = st.columns([1, 3])
        with col_r1:
            date_rapport = st.date_input("Sélectionner la date du rapport", datetime.date.today(), key="p7_date_rap")
            if st.button("Générer le rapport du jour", key="btn_p7_rap"):
                rapport_df = med_df[pd.to_datetime(med_df['Date Visite'], errors='coerce').dt.normalize() == pd.Timestamp(date_rapport)]
                st.session_state['rapport_journalier'] = rapport_df
                
        with col_r2:
            if 'rapport_journalier' in st.session_state:
                rapport = st.session_state['rapport_journalier']
                st.write(f"**{len(rapport)} collaborateurs concernés le {date_rapport.strftime('%d/%m/%Y')}**")
                if not rapport.empty:
                    show_cols = [c for c in ['WORKDAY ID', 'Nom', 'Projet_Affichage', 'Heure Départ', 'Heure Retour', 'Statut Visite', 'Commentaire'] if c in rapport.columns]
                    st.download_button(
                        label="📥 Télécharger le rapport journalier (Excel)", data=to_excel(rapport[show_cols]),
                        file_name=f"rapport_visite_{date_rapport.strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.info("Aucune visite planifiée pour cette date.")
        
        st.markdown("---")
        st.subheader("📥 Extraction complète (Format Export)")
        
        export_cols = [c for c in ['WORKDAY ID', 'Nom', 'Projet_Affichage', 'Statut Visite', 'Date Visite'] if c in med_df.columns]
        st.download_button(
            label="Télécharger le suivi global (Format Export)", data=to_excel(med_df[export_cols]),
            file_name="export_visites_medicales.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("Aucune donnée disponible. Veuillez importer le fichier RTA (Page 5).")

# --- SIGNATURE FIXEE EN BAS ---
st.markdown(
    "<div class='footer-fix'>Developed by <span style='color: #25E2CC; font-weight: 700; letter-spacing: 1px; margin-left: 2px;'> TEAM TMM 🦄</span></div>", 
    unsafe_allow_html=True
)