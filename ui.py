#!/usr/bin/env python3
import os
import re
from typing import List, Dict
import io

import streamlit as st

from fantasy_draft_tool import FantasyDraftTool, Player
from league_manager import LeagueManager


st.set_page_config(page_title="Fantasy Draft Tool", layout="wide")


def initialize_session_state() -> None:
    if "draft_tool" not in st.session_state:
        st.session_state.draft_tool = None


def extract_draft_id_from_url(url: str) -> str:
    """Extract draft ID from Sleeper URL"""
    if not url:
        return ""
    
    # Remove any whitespace
    url = url.strip()
    
    # Handle different URL formats
    patterns = [
        r'https?://sleeper\.com/draft/nfl/(\d+)',  # New format: sleeper.com/draft/nfl/ID
        r'https?://sleeper\.app/draft/(\d+)',      # Old format: sleeper.app/draft/ID
        r'sleeper\.com/draft/nfl/(\d+)',           # Without protocol
        r'sleeper\.app/draft/(\d+)',               # Without protocol
        r'/draft/nfl/(\d+)',                       # Just path with nfl
        r'/draft/(\d+)',                           # Just path
        r'(\d+)'                                   # Just the number if that's all they paste
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return ""

def inject_css() -> None:
    """Inject minimal CSS for readable vertical player cards."""
    st.markdown(
        """
        <style>
        /* App background and sidebar (dark) */
        [data-testid="stAppViewContainer"] { background: #0f172a; color: #e2e8f0; }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stSidebar"] { background: #0b1220; }
        /* Global text set to white for readability */
        body, .stApp, .stMarkdown, .stText, .stCaption, p, span, label,
        [data-testid="stWidgetLabel"], [data-baseweb="toggle"] label,
        [data-baseweb="select"] label, [data-testid="stSidebar"] * {
            color: #ffffff !important;
        }
        /* Inputs on dark background */
        .stTextInput input, .stTextArea textarea, .stTextInput > div > div > input {
            background: #111827 !important;
            color: #ffffff !important;
            border: 1px solid #334155 !important;
        }
        .stTextInput input::placeholder, .stTextArea textarea::placeholder {
            color: #ffffff !important;
            opacity: 0.85;
        }
        /* Buttons: default like hover (dark), with lighter hover */
        .stButton > button {
            background: #1f2937 !important; /* hover look as default */
            color: #ffffff !important;
            border: 1px solid #334155 !important;
            border-radius: 12px !important;
            box-shadow: none !important;
            transition: background 120ms ease, border-color 120ms ease, transform 60ms ease;
        }
        .stButton > button:hover {
            background: #263244 !important; /* slightly lighter on hover */
            border-color: #3b4456 !important;
        }
        .stButton > button:active {
            transform: translateY(1px);
        }
        /* Ensure sidebar buttons match */
        [data-testid="stSidebar"] .stButton > button {
            background: #1f2937 !important;
            color: #ffffff !important;
            border: 1px solid #334155 !important;
        }
        /* Form submit buttons - darker theme */
        .stFormSubmitButton > button {
            background: #0f172a !important;
            color: #e5e7eb !important;
            border: 1px solid #475569 !important;
            border-radius: 8px !important;
        }
        .stFormSubmitButton > button:hover {
            background: #1e293b !important;
            border-color: #64748b !important;
        }
        /* Download buttons - darker theme */
        .stDownloadButton > button {
            background: #0f172a !important;
            color: #e5e7eb !important;
            border: 1px solid #475569 !important;
            border-radius: 8px !important;
        }
        .stDownloadButton > button:hover {
            background: #1e293b !important;
            border-color: #64748b !important;
        }
        /* Selectbox styling - dark theme */
        .stSelectbox > div > div {
            background: #0f172a !important;
            border: 1px solid #475569 !important;
            color: #e5e7eb !important;
        }
        .stSelectbox > div > div:hover {
            border-color: #64748b !important;
        }
        .stSelectbox > div > div > div {
            background: #0f172a !important;
            color: #e5e7eb !important;
        }
        /* Fix selectbox text color */
        .stSelectbox > div > div > div > div {
            color: #e5e7eb !important;
            background: #0f172a !important;
        }
        /* Fix selectbox placeholder and selected text */
        .stSelectbox input, .stSelectbox select {
            color: #e5e7eb !important;
            background: #0f172a !important;
        }
        /* Fix input field placeholder text color */
        .stTextInput input::placeholder {
            color: #9ca3af !important;
            opacity: 0.8 !important;
        }
        .stTextInput input {
            color: #e5e7eb !important;
            background: #0f172a !important;
        }
        /* Ensure dropdown options are visible */
        .stSelectbox [role="listbox"] {
            background: #0f172a !important;
            color: #e5e7eb !important;
        }
        .stSelectbox [role="option"] {
            background: #0f172a !important;
            color: #e5e7eb !important;
        }
        .stSelectbox [role="option"]:hover {
            background: #1e293b !important;
        }
        /* Target all selectbox elements to remove white backgrounds */
        .stSelectbox * {
            background: #0f172a !important;
        }
        /* Main selector text should be light */
        .stSelectbox > div > div > div > div {
            color: #e5e7eb !important;
        }
        /* Specific targeting for the selected option display */
        .stSelectbox > div > div > div > div > div {
            background: #0f172a !important;
            color: #e5e7eb !important;
        }
        /* Target any remaining white backgrounds in selectbox */
        .stSelectbox div[style*="background"] {
            background: #0f172a !important;
        }
        .stSelectbox div[style*="white"] {
            background: #0f172a !important;
        }
        /* Force override any white backgrounds with !important */
        .stSelectbox div[style*="background-color: white"] {
            background-color: #0f172a !important;
        }
        .stSelectbox div[style*="background: white"] {
            background: #0f172a !important;
        }
        /* Target the specific dropdown option that's showing white */
        .stSelectbox > div > div > div > div > div[style*="background"] {
            background: #0f172a !important;
        }
        /* Override any remaining white backgrounds */
        .stSelectbox div {
            background: #0f172a !important;
        }
        /* Ensure text remains visible */
        .stSelectbox div {
            color: #e5e7eb !important;
        }
        /* Target the dropdown list container specifically */
        .stSelectbox [data-baseweb="popover"] {
            background: #0f172a !important;
        }
        .stSelectbox [data-baseweb="popover"] * {
            background: #0f172a !important;
            color: #000000 !important;
        }
        /* Target any popover or dropdown containers */
        .stSelectbox [role="listbox"], .stSelectbox [role="menu"] {
            background: #0f172a !important;
        }
        .stSelectbox [role="listbox"] *, .stSelectbox [role="menu"] * {
            background: #0f172a !important;
            color: #000000 !important;
        }
        /* Force override any remaining white backgrounds */
        .stSelectbox *[style*="white"] {
            background: #0f172a !important;
        }
        .stSelectbox *[style*="background"] {
            background: #0f172a !important;
        }
        /* Target the specific dropdown that's showing white */
        .stSelectbox > div > div > div > div > div > div {
            background: #0f172a !important;
        }
        /* Override any Streamlit-specific dropdown styling */
        .stSelectbox [data-testid="stSelectbox"] {
            background: #0f172a !important;
        }
        .stSelectbox [data-testid="stSelectbox"] * {
            background: #0f172a !important;
        }
        /* Fix expander header text color for readability */
        .streamlit-expanderHeader {
            color: #e5e7eb !important;
            background: #0f172a !important;
        }
        .streamlit-expanderHeader:hover {
            color: #ffffff !important;
            background: #1e293b !important;
        }
        /* Ensure expander content text is readable */
        .streamlit-expanderContent {
            color: #e5e7eb !important;
        }
        /* Fix any white text in expanders */
        .streamlit-expanderHeader * {
            color: #e5e7eb !important;
        }
        /* Force override expander header background */
        .streamlit-expanderHeader {
            background-color: #0f172a !important;
        }
        /* Target the expander header container */
        [data-testid="stExpander"] {
            background: #0f172a !important;
        }
        [data-testid="stExpander"] * {
            background: #0f172a !important;
        }
        /* Override any white backgrounds in expanders */
        .streamlit-expanderHeader[style*="background"] {
            background: #0f172a !important;
        }
        .streamlit-expanderHeader div[style*="background"] {
            background: #0f172a !important;
        }
        /* Ensure buttons are properly aligned */
        .stButton > button {
            margin-top: 0 !important;
            margin-bottom: 0 !important;
        }
        /* Streamlit popover/menu (Deploy/3-dot menu) */
        [data-baseweb="popover"] {
            background: #111827 !important;
            color: #ffffff !important;
            border: 1px solid #334155 !important;
            box-shadow: 0 8px 24px rgba(0,0,0,0.4) !important;
        }
        [data-baseweb="popover"] * { color: #ffffff !important; }
        [data-baseweb="menu"], [role="menu"] {
            background: #111827 !important;
            color: #ffffff !important;
        }
        [data-baseweb="menu"] *, [role="menu"] * { color: #ffffff !important; }
        /* Ensure menu item rows (including disabled/headers) are dark */
        [data-baseweb="menu"] li,
        [data-baseweb="menu"] [role="menuitem"],
        [data-baseweb="menu"] [aria-disabled="true"],
        [role="menu"] [aria-disabled="true"],
        [data-baseweb="menu"] [disabled] {
            background: #0f172a !important;
            color: #e5e7eb !important;
            opacity: 1 !important;
        }
        /* Hover/active states */
        [data-baseweb="menu"] li:hover,
        [data-baseweb="menu"] [role="menuitem"]:hover {
            background: #1f2937 !important;
        }
        [data-baseweb="menu"] hr { border-color: #334155 !important; }
        /* Headings */
        .app-title { font-weight: 800; font-size: 2.2rem; margin-bottom: 0.25rem; color: #ffffff; }
        .app-caption { color: #ffffff; margin-bottom: 1.25rem; }
        .section-title { font-weight: 800; font-size: 1.4rem; margin: 0.5rem 0 0.75rem; color: #ffffff; }
        .pos-header { font-weight: 800; font-size: 1.1rem; margin-bottom: 0.5rem; color: #ffffff; }
        /* Player cards */
        .player-card {
            border: 1px solid #1f2a3b;
            border-radius: 10px;
            padding: 14px 16px;
            margin-bottom: 12px;
            background: #111827;
            box-shadow: 0 1px 2px rgba(0,0,0,0.25);
        }
        .player-name { font-weight: 800; font-size: 1.05rem; margin-bottom: 4px; color: #e5e7eb; }
        .player-team { color: #9ca3af; font-weight: 700; margin-left: 6px; }
        .player-meta { color: #cbd5e1; font-size: 0.92rem; margin-top: 2px; }
        .player-injury { color: #f87171; font-size: 0.9rem; margin-top: 6px; font-weight: 700; }
        .badge { display:inline-block; padding: 2px 8px; background:#1f2937; border:1px solid #334155; color:#cbd5e1; border-radius:999px; font-size:12px; margin-right:6px; }
        .num-badge { display:inline-block; min-width: 24px; padding: 2px 6px; margin-right: 8px; text-align:center; background:#0b1220; border:1px solid #334155; color:#e5e7eb; border-radius:8px; font-weight:800; }
        
        /* File uploader styling for dark theme */
        .stFileUploader {
            background: #111827 !important;
            border: 2px dashed #334155 !important;
            border-radius: 12px !important;
            padding: 20px !important;
        }
        .stFileUploader > div {
            background: #111827 !important;
            border: none !important;
        }
        .stFileUploader [data-testid="stFileUploader"] {
            background: #111827 !important;
            border: 2px dashed #334155 !important;
            border-radius: 12px !important;
        }
        .stFileUploader [data-testid="stFileUploader"] > div {
            background: #111827 !important;
            border: none !important;
        }
        /* File uploader text and button */
        .stFileUploader p, .stFileUploader span, .stFileUploader label {
            color: #e5e7eb !important;
        }
        .stFileUploader button {
            background: #1f2937 !important;
            color: #ffffff !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
        }
        .stFileUploader button:hover {
            background: #263244 !important;
            border-color: #3b4456 !important;
        }
        /* Override any white backgrounds in file uploader */
        [data-testid="stFileUploader"] * {
            background: #111827 !important;
        }
        [data-testid="stFileUploader"] div[style*="background"] {
            background: #111827 !important;
        }
        
        /* Code blocks and inline code styling for dark theme */
        code, pre, .stMarkdown code {
            background: #1f2937 !important;
            color: #e5e7eb !important;
            border: 1px solid #334155 !important;
            border-radius: 4px !important;
            padding: 2px 6px !important;
        }
        pre {
            background: #1f2937 !important;
            color: #e5e7eb !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
            padding: 12px !important;
        }
        /* Inline code styling */
        .stMarkdown p code {
            background: #1f2937 !important;
            color: #e5e7eb !important;
            border: 1px solid #334155 !important;
            border-radius: 4px !important;
            padding: 2px 6px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_player_rows(players: List[Player], sleeper_players: Dict[str, dict]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for player in players:
        row: Dict[str, object] = {
            "Name": player.name,
            "Team": player.team,
            "Ovr": player.overall_rank,
            "Pos#": player.position_rank,
            "Tier": player.tier,
            "Bye": player.bye_week,
            "SOS": player.sos_season,
            "ECR vs ADP": player.ecr_vs_adp,
        }
        if player.sleeper_id and player.sleeper_id in sleeper_players:
            sp = sleeper_players[player.sleeper_id]
            if sp.get("injury_status"):
                row["Injury"] = sp.get("injury_status")
        rows.append(row)
    return rows


def render_sidebar() -> None:
    with st.sidebar:
        st.header("Setup")
        
        # FantasyPros Rankings Section
        st.subheader("🎯 FantasyPros Rankings")
        st.markdown("Choose your scoring format:")
        
        # All three buttons vertically stacked
        if st.button("📊 Standard", use_container_width=True):
            try:
                with st.spinner("Loading Standard rankings..."):
                    # Use scraper to get Standard rankings
                    from fantasy_rankings_scraper import scrape
                    scraper = scrape('fantasypros.com')
                    standard_players = scraper.data[1]  # Standard format
                    
                    # Create draft tool and load data
                    draft_tool = FantasyDraftTool("")
                    draft_tool.load_scraped_data(standard_players, "Standard")
                    
                    # Fetch and match Sleeper data
                    draft_tool.fetch_sleeper_data()
                    draft_tool.match_players()
                    
                    st.session_state.draft_tool = draft_tool
                    st.success(f"✅ Loaded {len(draft_tool.players)} Standard players successfully!")
                    
            except Exception as ex:
                st.error(f"❌ Error loading Standard rankings: {ex}")
        
        if st.button("📈 Half-PPR", use_container_width=True):
            try:
                with st.spinner("Loading Half-PPR rankings..."):
                    # Use scraper to get Half-PPR rankings
                    from fantasy_rankings_scraper import scrape
                    scraper = scrape('fantasypros.com')
                    half_ppr_players = scraper.data[2]  # Half-PPR format
                    
                    # Create draft tool and load data
                    draft_tool = FantasyDraftTool("")
                    draft_tool.load_scraped_data(half_ppr_players, "Half-PPR")
                    
                    # Fetch and match Sleeper data
                    draft_tool.fetch_sleeper_data()
                    draft_tool.match_players()
                    
                    st.session_state.draft_tool = draft_tool
                    st.success(f"✅ Loaded {len(draft_tool.players)} Half-PPR players successfully!")
                    
            except Exception as ex:
                st.error(f"❌ Error loading Half-PPR rankings: {ex}")
        
        if st.button("🏈 PPR", use_container_width=True):
            try:
                with st.spinner("Loading PPR rankings..."):
                    # Use scraper to get PPR rankings
                    from fantasy_rankings_scraper import scrape
                    scraper = scrape('fantasypros.com')
                    ppr_players = scraper.data[3]  # PPR format
                    
                    # Create draft tool and load data
                    draft_tool = FantasyDraftTool("")
                    draft_tool.load_scraped_data(ppr_players, "PPR")
                    
                    # Fetch and match Sleeper data
                    draft_tool.fetch_sleeper_data()
                    draft_tool.match_players()
                    
                    st.session_state.draft_tool = draft_tool
                    st.success(f"✅ Loaded {len(draft_tool.players)} PPR players successfully!")
                    
            except Exception as ex:
                st.error(f"❌ Error loading PPR rankings: {ex}")

        st.divider()

        # League Management Section
        st.subheader("🏈 League Management")
        
        # Initialize league manager in session state
        if "league_manager" not in st.session_state:
            from league_manager import LeagueManager
            st.session_state.league_manager = LeagueManager()
        
        league_manager = st.session_state.league_manager
        
        # Saved Leagues Section
        if league_manager.get_league_count() > 0:
            st.markdown("**Saved Leagues:**")
            
            # Get league names in original order (not sorted by last used)
            league_names = league_manager.get_all_leagues()
            
            # Display each league as a button
            for league_name in league_names:
                league = league_manager.get_league(league_name)
                if league:
                    # Check if this league is currently connected
                    is_connected = (st.session_state.draft_tool and 
                                  st.session_state.draft_tool.sleeper_draft_id == league.draft_id)
                    
                    # Create button with different styling based on connection status
                    if is_connected:
                        # Connected league - show as active
                        if st.button(f"🏈 {league_name} (Connected)", use_container_width=True, 
                                   key=f"league_{league_name}"):
                            # Already connected, just refresh
                            st.rerun()
                    else:
                        # Not connected - show as clickable
                        if st.button(f"🏈 {league_name}", use_container_width=True, 
                                   key=f"league_{league_name}"):
                            if st.session_state.draft_tool:
                                st.session_state.draft_tool.set_sleeper_draft_id(league.draft_id)
                                league_manager.mark_league_used(league_name)
                                st.success(f"✅ Connected to {league_name}!")
                                st.rerun()
                            else:
                                st.warning("⚠️ Load rankings first.")
                    
                    # Add delete button below each league button
                    if st.button(f"🗑️ Delete {league_name}", use_container_width=True, key=f"delete_{league_name}"):
                        if league_manager.delete_league(league_name):
                            st.success(f"✅ Deleted {league_name}")
                            st.rerun()
                        else:
                            st.error("❌ Failed to delete league")
                    
                    # Smaller separator between leagues
                    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        
        # Add New League Section
        with st.expander("➕ Add New League", expanded=False):
            with st.form("add_league_form"):
                new_league_name = st.text_input(
                    "League Name", 
                    placeholder="e.g., My Main League, Work League, etc.",
                    key="new_league_name"
                )
                
                new_draft_url = st.text_input(
                    "Sleeper Draft URL", 
                    placeholder="https://sleeper.app/draft/1234567890",
                    key="new_draft_url"
                )
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.form_submit_button("Save League", use_container_width=True):
                        if new_league_name.strip() and new_draft_url.strip():
                            # Extract draft ID from URL
                            draft_id = extract_draft_id_from_url(new_draft_url)
                            if draft_id:
                                if league_manager.add_league(new_league_name.strip(), new_draft_url.strip(), draft_id):
                                    st.success(f"✅ Saved league: {new_league_name}")
                                    st.rerun()
                                else:
                                    st.error("❌ League name already exists. Choose a different name.")
                            else:
                                st.error("❌ Could not extract draft ID from URL. Please check the format.")
                        else:
                            st.error("❌ Please fill in both league name and draft URL.")
                
                with col_b:
                    if st.form_submit_button("Test URL", use_container_width=True):
                        if new_draft_url.strip():
                            draft_id = extract_draft_id_from_url(new_draft_url)
                            if draft_id:
                                st.success(f"✅ Valid URL! Draft ID: {draft_id}")
                            else:
                                st.error("❌ Invalid URL format")
                        else:
                            st.error("❌ Please enter a draft URL first")
        
        # Export/Import Section
        with st.expander("📁 Export/Import Leagues", expanded=False):
            # Export section (top)
            if league_manager.get_league_count() > 0:
                export_data = league_manager.export_leagues()
                st.download_button(
                    label="📥 Export Leagues",
                    data=export_data,
                    file_name="fantasy_leagues_backup.json",
                    mime="application/json"
                )
            else:
                st.info("No leagues to export")
            
            # Import section (bottom)
            st.markdown("**Import Leagues:**")
            uploaded_leagues = st.file_uploader(
                "Import Leagues",
                type=['json'],
                help="Upload a previously exported leagues file"
            )
            
            if uploaded_leagues is not None:
                try:
                    leagues_content = uploaded_leagues.read().decode('utf-8')
                    if league_manager.import_leagues(leagues_content):
                        st.success("✅ Leagues imported successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to import leagues")
                except Exception as e:
                    st.error(f"❌ Error importing leagues: {e}")
        
        st.divider()
        
        # Quick Draft Actions (if connected)
        if st.session_state.draft_tool and st.session_state.draft_tool.sleeper_draft_id:
            # The refresh button will be moved to the main content area
            pass


def render_search(draft_tool: FantasyDraftTool) -> None:
    search_name = st.text_input("Search player by name")
    if not search_name:
        return

    player = draft_tool.search_player(search_name)
    if not player:
        st.warning("No player found.")
        return

    st.subheader(player.name)
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"Team: {player.team}")
        st.write(f"Position: {player.position} (Rank #{player.position_rank})")
        st.write(f"Overall Rank: #{player.overall_rank}")
        st.write(f"Tier: {player.tier}")
    with col2:
        st.write(f"Bye Week: {player.bye_week}")
        st.write(f"Strength of Schedule: {player.sos_season}")
        st.write(f"ECR vs ADP: {player.ecr_vs_adp:+d}")
        st.write(f"Drafted: {'Yes' if player.drafted else 'No'}")

    if player.sleeper_id and player.sleeper_id in draft_tool.sleeper_players:
        sp = draft_tool.sleeper_players[player.sleeper_id]
        st.write("Sleeper Status:", sp.get("status", "Unknown"))
        if sp.get("injury_status"):
            st.write("Injury Status:", sp.get("injury_status"))
        if sp.get("injury_notes"):
            st.write("Injury Notes:", sp.get("injury_notes"))


def render_player_card(player: Player, sleeper_players: Dict[str, dict], index: int = None) -> None:
    injury = None
    if player.sleeper_id and player.sleeper_id in sleeper_players:
        sp = sleeper_players[player.sleeper_id]
        injury = sp.get("injury_status")

    num_html = f"<span class='num-badge'>{index}.</span>" if index is not None else ""
    injury_html = f"<div class='player-injury'>Injury: {injury}</div>" if injury else ""

    st.markdown(
        f"""
        <div class="player-card">
          <div class="player-name">{num_html}{player.name}<span class="player-team">({player.team})</span></div>
          <div class="player-meta">
            <span class="badge">Overall #{player.overall_rank}</span>
            <span class="badge">{player.position} #{player.position_rank}</span>
            <span class="badge">Tier {player.tier}</span>
            <span class="badge">Bye {player.bye_week}</span>
            <span class="badge">SOS {player.sos_season}</span>
            <span class="badge">ECR vs ADP {player.ecr_vs_adp:+d}</span>
          </div>
          {injury_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_top_by_position(draft_tool: FantasyDraftTool) -> None:
    st.markdown("### Top 3 By Position (Available)")
    positions = ["RB", "WR", "QB", "TE"]

    # Arrange positions in two columns for readability
    for i in range(0, len(positions), 2):
        row_positions = positions[i : i + 2]
        cols = st.columns(len(row_positions))
        for col_idx, pos in enumerate(row_positions):
            with cols[col_idx]:
                st.markdown(f"<div class='pos-header'>{pos}</div>", unsafe_allow_html=True)
                top_players = draft_tool.get_top_players_by_position(pos, 3)
                if not top_players:
                    st.write("No players available.")
                    continue
                for idx, p in enumerate(top_players, start=1):
                    render_player_card(p, draft_tool.sleeper_players, idx)


def render_top_overall(draft_tool: FantasyDraftTool) -> None:
    cols = st.columns([0.7, 0.3])
    with cols[0]:
        st.markdown('<div class="section-title">Top Available Overall</div>', unsafe_allow_html=True)
    with cols[1]:
        show_10 = st.toggle("Show top 10 (otherwise top 5)", value=False)
    limit = 10 if show_10 else 5
    players = draft_tool.get_top_overall_available(limit)
    for idx, p in enumerate(players, start=1):
        render_player_card(p, draft_tool.sleeper_players, idx)


def main() -> None:
    initialize_session_state()
    inject_css()

    render_sidebar()

    if not st.session_state.draft_tool:
        st.info("👆 Use the sidebar to load FantasyPros rankings or upload your custom CSV file.")
        st.markdown("""
        ### Quick Start Options:
        
        **🎯 FantasyPros Rankings (Recommended):**
        - Click one of the scoring format buttons (Standard, Half-PPR, or PPR)
        - Rankings are automatically loaded from FantasyPros
        - No file download needed!
        
        **📁 Custom Rankings:**
        - Upload your own CSV file with the required format
        - See the CSV format requirements in the sidebar
        """)
        return

    draft_tool: FantasyDraftTool = st.session_state.draft_tool

    # Add refresh button on the right side of the main content
    if draft_tool.sleeper_draft_id:
        col_title, col_refresh = st.columns([0.7, 0.3])
        with col_title:
            st.markdown('<div class="app-title">Fantasy Draft Tool</div>', unsafe_allow_html=True)
            st.markdown('<div class="app-caption">Load FantasyPros rankings and manage multiple fantasy leagues with Sleeper integration.</div>', unsafe_allow_html=True)
        with col_refresh:
            if st.button("🔄 Refresh Draft Picks", use_container_width=True):
                with st.spinner("Refreshing draft picks..."):
                    draft_tool.fetch_sleeper_draft_picks()
                st.success("✅ Draft picks refreshed!")
                st.rerun()
    else:
        st.markdown('<div class="app-title">Fantasy Draft Tool</div>', unsafe_allow_html=True)
        st.markdown('<div class="app-caption">Load FantasyPros rankings and manage multiple fantasy leagues with Sleeper integration.</div>', unsafe_allow_html=True)

    render_top_overall(draft_tool)
    st.divider()
    render_search(draft_tool)
    st.divider()
    render_top_by_position(draft_tool)
    st.divider()

    # Drafted players list at bottom
    drafted = draft_tool.get_drafted_players()
    st.markdown("### Drafted Players")
    if not drafted:
        st.write("No drafted players detected yet.")
    else:
        # Numbered list of drafted players with team and position
        drafted_lines = [f"{i}. {p.name} ({p.team}) — {p.position} #{p.position_rank}" for i, p in enumerate(drafted, start=1)]
        st.markdown("\n".join(drafted_lines))

    # Optional debug: show unmatched drafted players from Sleeper (to diagnose missing mappings)
    with st.expander("Debug: Unmatched drafted players (from Sleeper)"):
        unmatched = draft_tool.get_unmatched_drafted_from_sleeper()
        if not unmatched:
            st.write("None")
        else:
            st.write(unmatched)


if __name__ == "__main__":
    main()


