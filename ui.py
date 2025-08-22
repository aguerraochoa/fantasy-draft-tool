#!/usr/bin/env python3
import os
from typing import List, Dict
import io

import streamlit as st

from fantasy_draft_tool import FantasyDraftTool, Player


st.set_page_config(page_title="Fantasy Draft Tool", layout="wide")


def initialize_session_state() -> None:
    if "draft_tool" not in st.session_state:
        st.session_state.draft_tool = None


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
        
        # File uploader for CSV
        uploaded_file = st.file_uploader(
            "Upload FantasyPros CSV", 
            type=['csv'],
            help="Upload your FantasyPros rankings CSV file"
        )
        
        if uploaded_file is not None:
            # Show file info
            st.success(f"✅ File uploaded: {uploaded_file.name}")
            
            # Load data button
            if st.button("Load rankings and Sleeper data", use_container_width=True):
                try:
                    with st.spinner("Loading data..."):
                        # Create a temporary file-like object from the uploaded file
                        csv_content = uploaded_file.read().decode('utf-8')
                        
                        # Create draft tool with the uploaded data
                        draft_tool = FantasyDraftTool("")  # Empty path since we're using uploaded data
                        
                        # Load FantasyPros data from the uploaded content
                        draft_tool.load_fantasypros_data_from_content(csv_content)
                        
                        # Fetch and match Sleeper data
                        draft_tool.fetch_sleeper_data()
                        draft_tool.match_players()
                        
                        st.session_state.draft_tool = draft_tool
                        st.success(f"✅ Loaded {len(draft_tool.players)} players successfully!")
                        
                except Exception as ex:
                    st.error(f"❌ Error loading data: {ex}")
                    st.error("Make sure your CSV file has the correct FantasyPros format with columns: RK, TIERS, PLAYER NAME, TEAM, POS, BYE WEEK, SOS SEASON, ECR VS. ADP")

        st.divider()

        # Sleeper draft ID section
        st.subheader("Sleeper Draft Integration")
        st.markdown("""
        **Optional:** Connect to a live Sleeper draft to track picks in real-time.
        
        To get your draft ID:
        1. Open your Sleeper draft
        2. Look at the URL: `https://sleeper.app/draft/`**`YOUR_DRAFT_ID`**
        3. Copy the draft ID and paste it below
        """)
        
        draft_id_default = ""
        if st.session_state.draft_tool and st.session_state.draft_tool.sleeper_draft_id:
            draft_id_default = st.session_state.draft_tool.sleeper_draft_id or ""

        draft_id = st.text_input("Sleeper Draft ID", value=draft_id_default, placeholder="e.g., 1234567890")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Set/Update Draft ID", use_container_width=True):
                if st.session_state.draft_tool:
                    st.session_state.draft_tool.set_sleeper_draft_id(draft_id)
                    st.success("✅ Draft ID updated.")
                else:
                    st.warning("⚠️ Load rankings first.")
        with col_b:
            if st.button("Refresh Draft Picks", use_container_width=True):
                if st.session_state.draft_tool and st.session_state.draft_tool.sleeper_draft_id:
                    with st.spinner("Refreshing draft picks..."):
                        st.session_state.draft_tool.fetch_sleeper_draft_picks()
                    st.success("✅ Draft picks refreshed.")
                else:
                    st.warning("⚠️ Set Draft ID first.")


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
    st.markdown('<div class="app-title">Fantasy Draft Tool</div>', unsafe_allow_html=True)
    st.markdown('<div class="app-caption">Upload your FantasyPros CSV and get live draft rankings with Sleeper integration.</div>', unsafe_allow_html=True)
    inject_css()

    render_sidebar()

    if not st.session_state.draft_tool:
        st.info("👆 Use the sidebar to upload your FantasyPros CSV file and load the data.")
        st.markdown("""
        ### How to get your FantasyPros CSV:
        1. Go to [FantasyPros](https://www.fantasypros.com/nfl/rankings/consensus-cheatsheets.php)
        2. Export your rankings as CSV
        3. Upload the file using the sidebar
        """)
        return

    draft_tool: FantasyDraftTool = st.session_state.draft_tool

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


