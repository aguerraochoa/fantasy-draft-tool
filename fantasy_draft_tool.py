#!/usr/bin/env python3
"""
Fantasy Draft Tool
Reads FantasyPros CSV rankings and displays top 3 players per position
with both overall and position-specific rankings.
"""

import csv
import json
import requests
from typing import Dict, List, Optional, Tuple, Set
import unicodedata
from dataclasses import dataclass
import re
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

@dataclass
class Player:
    """Represents a fantasy football player with rankings"""
    name: str
    team: str
    position: str
    overall_rank: int
    position_rank: int
    tier: int
    bye_week: int
    sos_season: str
    ecr_vs_adp: int
    sleeper_id: Optional[str] = None
    drafted: bool = False
    drafted_by: Optional[str] = None

class FantasyDraftTool:
    def __init__(self, csv_file_path: str):
        self.csv_file_path = csv_file_path
        self.players: List[Player] = []
        self.sleeper_players: Dict[str, dict] = {}
        self.sleeper_draft_id: Optional[str] = None
        self.drafted_sleeper_ids: Set[str] = set()
        # Cache of normalized name to Sleeper player ID for faster matching
        self._normalized_sleeper_name_to_id: Dict[str, str] = {}
        self._position_to_normalized_names: Dict[str, Dict[str, str]] = {}

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Return a normalized string for robust name matching.

        - lowercase
        - remove accents
        - remove punctuation and extra whitespace
        - strip common suffixes (jr, sr, ii, iii, iv)
        - collapse spaces
        """
        if not name:
            return ""
        # Lower and remove accents
        name_low = unicodedata.normalize("NFKD", name.lower())
        name_low = "".join([c for c in name_low if not unicodedata.combining(c)])
        # Remove punctuation
        cleaned = re.sub(r"[^a-z0-9\s]", " ", name_low)
        # Remove common suffixes
        cleaned = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", cleaned)
        # Collapse spaces
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned
    
    @staticmethod
    def _parse_int_field(value: str, default: int = 0) -> int:
        """Parse an integer field that may contain '-', '+N', or be empty.

        Returns the parsed integer, or the provided default if parsing fails.
        """
        if value is None:
            return default
        s = str(value).strip()
        if s in {"", "-", "NA", "N/A"}:
            return default
        # Allow "+123" style values
        if s.startswith("+"):
            s = s[1:]
        try:
            return int(s)
        except ValueError:
            # Fallback: extract first signed integer substring, if any
            m = re.search(r"-?\d+", s)
            if m:
                try:
                    return int(m.group(0))
                except ValueError:
                    return default
            return default
        
    def load_fantasypros_data_from_content(self, csv_content: str) -> None:
        """Load and parse FantasyPros CSV data from string content"""
        print("Loading FantasyPros data from content...")
        
        # Create a StringIO object to simulate a file
        from io import StringIO
        csv_file = StringIO(csv_content)
        
        reader = csv.DictReader(csv_file)
        
        # Debug: Print column names to help with troubleshooting
        if not self.players:  # Only print once
            print(f"CSV columns found: {list(reader.fieldnames)}")
        
        for row in reader:
            try:
                # Debug: Print first few rows to see the data
                if len(self.players) < 3:
                    print(f"Row data: {row}")
                
                # Parse position and position rank
                pos_match = re.match(r'([A-Z]+)(\d+)', row['POS'])
                if not pos_match:
                    print(f"Skipping row - couldn't parse position: {row['POS']}")
                    continue
                
                position = pos_match.group(1)
                position_rank = int(pos_match.group(2))
                
                # Parse SOS season (extract number from "X out of 5 stars")
                sos_field = row.get('SOS SEASON', row.get('SOS', ''))
                sos_match = re.search(r'(\d+)', sos_field)
                sos_season = sos_field if not sos_match else f"{sos_match.group(1)}/5"
                
                # Handle both column name variations for ECR VS ADP
                ecr_vs_adp_field = row.get('ECR VS. ADP', row.get('ECR VS ADP', ''))
                
                # Parse tier - handle potential string values
                tier_value = row['TIERS']
                if isinstance(tier_value, str):
                    tier_value = tier_value.strip()
                tier = int(tier_value)
                
                player = Player(
                    name=row['PLAYER NAME'].strip(),
                    team=row['TEAM'].strip(),
                    position=position,
                    overall_rank=int(row['RK']),
                    position_rank=position_rank,
                    tier=tier,
                    bye_week=self._parse_int_field(row.get('BYE WEEK', row.get('BYE', '')), 0),
                    sos_season=sos_season,
                    ecr_vs_adp=self._parse_int_field(ecr_vs_adp_field, 0)
                )
                
                self.players.append(player)
                
            except (ValueError, KeyError) as e:
                print(f"Error parsing row: {row}")
                print(f"Error details: {e}")
                print(f"Available columns: {list(row.keys())}")
                continue
        
        print(f"Loaded {len(self.players)} players from FantasyPros data")
    
    def load_scraped_data(self, scraped_players: List[Dict], scoring_format: str) -> None:
        """Load and parse scraped FantasyPros data"""
        print(f"Loading {scoring_format} scraped data...")
        
        self.players = []  # Clear existing players
        
        for player_data in scraped_players:
            try:
                # Extract data from scraped format
                name = player_data.get('player_name', '').strip()
                team = player_data.get('player_team_id', '').strip()
                position = player_data.get('player_position_id', '').strip()
                overall_rank = int(player_data.get('rank_ecr', 0))
                tier = int(player_data.get('tier', 1))
                bye_week = self._parse_int_field(player_data.get('player_bye_week', ''), 0)
                
                # Parse position rank from pos_rank field (e.g., "WR1" -> 1)
                pos_rank_str = player_data.get('pos_rank', '')
                position_rank = 0
                if pos_rank_str:
                    pos_match = re.match(r'[A-Z]+(\d+)', pos_rank_str)
                    if pos_match:
                        position_rank = int(pos_match.group(1))
                
                # Set default values for missing fields
                sos_season = "3/5"  # Default strength of schedule
                ecr_vs_adp = 0      # Default ECR vs ADP difference
                
                player = Player(
                    name=name,
                    team=team,
                    position=position,
                    overall_rank=overall_rank,
                    position_rank=position_rank,
                    tier=tier,
                    bye_week=bye_week,
                    sos_season=sos_season,
                    ecr_vs_adp=ecr_vs_adp
                )
                
                self.players.append(player)
                
            except (ValueError, KeyError) as e:
                print(f"Error parsing scraped player data: {player_data}")
                print(f"Error details: {e}")
                continue
        
        print(f"Loaded {len(self.players)} players from {scoring_format} scraped data")
    
    def load_custom_csv_data(self, csv_content: str) -> None:
        """Load and parse custom CSV data with standardized column names"""
        print("Loading custom CSV data...")
        
        self.players = []  # Clear existing players
        
        # Create a StringIO object to simulate a file
        from io import StringIO
        csv_file = StringIO(csv_content)
        
        reader = csv.DictReader(csv_file)
        
        # Debug: Print column names to help with troubleshooting
        if not self.players:  # Only print once
            print(f"Custom CSV columns found: {list(reader.fieldnames)}")
        
        for row in reader:
            try:
                # Debug: Print first few rows to see the data
                if len(self.players) < 3:
                    print(f"Custom row data: {row}")
                
                # Parse position and position rank from pos_rank field if available
                position_rank = 0
                if 'pos_rank' in row and row['pos_rank']:
                    pos_match = re.match(r'[A-Z]+(\d+)', row['pos_rank'])
                    if pos_match:
                        position_rank = int(pos_match.group(1))
                
                # Parse tier with default value
                tier = 1  # Default tier
                if 'tier' in row and row['tier']:
                    try:
                        tier = int(row['tier'])
                    except ValueError:
                        tier = 1
                
                # Parse bye week with default value
                bye_week = 0  # Default bye week
                if 'bye_week' in row and row['bye_week']:
                    bye_week = self._parse_int_field(row['bye_week'], 0)
                
                # Parse ECR vs ADP with default value
                ecr_vs_adp = 0  # Default ECR vs ADP difference
                if 'ecr_vs_adp' in row and row['ecr_vs_adp']:
                    ecr_vs_adp = self._parse_int_field(row['ecr_vs_adp'], 0)
                
                # Set default values for missing fields
                sos_season = "3/5"  # Default strength of schedule
                
                player = Player(
                    name=row['name'].strip(),
                    team=row['team'].strip(),
                    position=row['position'].strip(),
                    overall_rank=int(row['rank']),
                    position_rank=position_rank,
                    tier=tier,
                    bye_week=bye_week,
                    sos_season=sos_season,
                    ecr_vs_adp=ecr_vs_adp
                )
                
                self.players.append(player)
                
            except (ValueError, KeyError) as e:
                print(f"Error parsing custom CSV row: {row}")
                print(f"Error details: {e}")
                print(f"Available columns: {list(row.keys())}")
                continue
        
        print(f"Loaded {len(self.players)} players from custom CSV data")
    
    def load_fantasypros_data(self) -> None:
        """Load and parse FantasyPros CSV data from file"""
        print("Loading FantasyPros data...")
        
        with open(self.csv_file_path, 'r', encoding='utf-8') as file:
            csv_content = file.read()
        
        self.load_fantasypros_data_from_content(csv_content)
    
    def fetch_sleeper_data(self) -> None:
        """Fetch player data from Sleeper API"""
        print("Fetching Sleeper API data...")
        
        try:
            response = requests.get("https://api.sleeper.app/v1/players/nfl")
            response.raise_for_status()
            self.sleeper_players = response.json()
            print(f"Fetched {len(self.sleeper_players)} players from Sleeper API")
        except requests.RequestException as e:
            print(f"Error fetching Sleeper data: {e}")
            self.sleeper_players = {}
    
    def match_players(self) -> None:
        """Match FantasyPros players with Sleeper players using fuzzy matching"""
        print("Matching players between FantasyPros and Sleeper...")
        
        # Create a mapping of Sleeper player names
        sleeper_names: Dict[str, str] = {}
        normalized_map: Dict[str, str] = {}
        position_map: Dict[str, Dict[str, str]] = {}
        for player_id, sleeper_player in self.sleeper_players.items():
            full_name = sleeper_player.get('full_name') or ""
            if sleeper_player.get('full_name'):
                sleeper_names[full_name] = player_id
                normalized_map[self._normalize_name(full_name)] = player_id
            # Include search_full_name if present
            search_full_name = sleeper_player.get('search_full_name')
            if search_full_name:
                normalized_map[self._normalize_name(search_full_name)] = player_id
            # Include first + last combos if present
            first = sleeper_player.get('first_name') or ""
            last = sleeper_player.get('last_name') or ""
            if first and last:
                normalized_map[self._normalize_name(f"{first} {last}")] = player_id

            # Build position-specific normalized map
            pos = (sleeper_player.get('position') or '').upper()
            if pos:
                if pos not in position_map:
                    position_map[pos] = {}
                if full_name:
                    position_map[pos][self._normalize_name(full_name)] = player_id
                if search_full_name:
                    position_map[pos][self._normalize_name(search_full_name)] = player_id
                if first and last:
                    position_map[pos][self._normalize_name(f"{first} {last}")] = player_id
        
        matched_count = 0
        unmatched_players = []
        for fantasypros_player in self.players:
            # Try exact match first
            if fantasypros_player.name in sleeper_names:
                fantasypros_player.sleeper_id = sleeper_names[fantasypros_player.name]
                matched_count += 1
                continue
            
            # Try normalized exact match
            normalized_fp = self._normalize_name(fantasypros_player.name)
            if normalized_fp in normalized_map:
                fantasypros_player.sleeper_id = normalized_map[normalized_fp]
                matched_count += 1
                continue

            # Try fuzzy matching on normalized names (prefer same-position candidates)
            candidates_map = position_map.get(fantasypros_player.position, {}) or normalized_map
            candidate_keys = list(candidates_map.keys())
            best_match = process.extractOne(
                normalized_fp,
                candidate_keys,
                scorer=fuzz.token_sort_ratio,
            )

            if best_match and best_match[1] >= 95:
                chosen_key = best_match[0]
                
                # Additional validation: check for common name confusions
                fp_normalized = self._normalize_name(fantasypros_player.name).lower()
                sleeper_normalized = chosen_key.lower()
                
                # Reject matches if first names are completely different
                fp_first = fp_normalized.split()[0] if fp_normalized.split() else ""
                sleeper_first = sleeper_normalized.split()[0] if sleeper_normalized.split() else ""
                
                # Only proceed if first names are very similar or identical
                if len(fp_first) > 0 and len(sleeper_first) > 0:
                    first_name_similarity = fuzz.ratio(fp_first, sleeper_first)
                    if first_name_similarity >= 85:  # First names must be very similar
                        fantasypros_player.sleeper_id = candidates_map[chosen_key]
                        matched_count += 1
                        continue

            # Fallback: try last-name + team + position heuristic (handles nicknames like "Hollywood Brown")
            try:
                last_name = self._normalize_name(fantasypros_player.name).split(" ")[-1]
            except Exception:
                last_name = ""
            team = (fantasypros_player.team or "").upper()
            pos = (fantasypros_player.position or "").upper()
            fallback_candidates: List[str] = []
            if last_name and team and team != "FA" and pos:
                for sp_id, sp in self.sleeper_players.items():
                    sp_last = self._normalize_name(sp.get('last_name', ''))
                    sp_team = (sp.get('team') or "").upper()
                    sp_pos = (sp.get('position') or "").upper()
                    if sp_last == last_name and sp_team == team and sp_pos == pos:
                        fallback_candidates.append(sp_id)
            if len(fallback_candidates) == 1:
                fantasypros_player.sleeper_id = fallback_candidates[0]
                matched_count += 1
                continue
            
            # If we get here, the player wasn't matched
            unmatched_players.append(fantasypros_player)

        print(f"Matched {matched_count} out of {len(self.players)} players")
        
        # Print unmatched players for debugging
        if unmatched_players:
            print(f"\nUnmatched players ({len(unmatched_players)}):")
            for player in unmatched_players:
                print(f"  - {player.name} ({player.team}) - {player.position} - Overall Rank: {player.overall_rank}")
                # Show some potential matches from Sleeper for debugging
                normalized_fp = self._normalize_name(player.name)
                candidates_map = position_map.get(player.position, {}) or normalized_map
                candidate_keys = list(candidates_map.keys())
                best_match = process.extractOne(
                    normalized_fp,
                    candidate_keys,
                    scorer=fuzz.token_sort_ratio,
                )
                if best_match:
                    print(f"    Best fuzzy match: {best_match[0]} (score: {best_match[1]})")
                print()
        # Re-apply drafted status if we already know drafted Sleeper IDs
        if self.drafted_sleeper_ids:
            self.apply_drafted_status()

    def set_sleeper_draft_id(self, draft_id: str) -> None:
        """Configure the Sleeper draft ID for live draft syncing"""
        self.sleeper_draft_id = draft_id.strip() or None
        if self.sleeper_draft_id:
            print(f"Sleeper draft ID set to: {self.sleeper_draft_id}")
        else:
            print("Sleeper draft ID cleared.")

    # ------------------------------
    # Sleeper discovery helper APIs
    # ------------------------------
    @staticmethod
    def get_current_season_year() -> int:
        """Return the current NFL season year (UTC-based)."""
        from datetime import datetime
        now = datetime.utcnow()
        return now.year

    @staticmethod
    def fetch_user_id_by_username(username: str) -> Optional[str]:
        """Look up a Sleeper user_id from a username."""
        try:
            if not username:
                return None
            url = f"https://api.sleeper.app/v1/user/{username}"
            resp = requests.get(url)
            resp.raise_for_status()
            data = resp.json()
            return data.get("user_id")
        except requests.RequestException as e:
            print(f"Error fetching user_id for username '{username}': {e}")
            return None

    @staticmethod
    def fetch_user_leagues(user_id: str, season_year: int) -> List[dict]:
        """Get all leagues for a user for a given season."""
        try:
            if not user_id:
                return []
            url = f"https://api.sleeper.app/v1/user/{user_id}/leagues/nfl/{season_year}"
            resp = requests.get(url)
            resp.raise_for_status()
            leagues = resp.json()
            if isinstance(leagues, list):
                return leagues
            return []
        except requests.RequestException as e:
            print(f"Error fetching leagues for user_id '{user_id}': {e}")
            return []

    @staticmethod
    def fetch_league_drafts(league_id: str) -> List[dict]:
        """Get all drafts for a league (typically one, but may include past drafts)."""
        try:
            if not league_id:
                return []
            url = f"https://api.sleeper.app/v1/league/{league_id}/drafts"
            resp = requests.get(url)
            resp.raise_for_status()
            drafts = resp.json()
            if isinstance(drafts, list):
                return drafts
            return []
        except requests.RequestException as e:
            print(f"Error fetching drafts for league_id '{league_id}': {e}")
            return []

    # ------------------------------
    # Weekly Rankings functionality
    # ------------------------------
    @staticmethod
    def get_weekly_rankings_files() -> Dict[str, str]:
        """Get the latest weekly rankings files from the weekly_rankings folder."""
        import os
        import glob
        
        rankings_dir = "weekly_rankings"
        if not os.path.exists(rankings_dir):
            return {}
        
        # Look for files matching the pattern: FantasyPros_2025_Week_X_TYPE_Rankings.csv
        files = {}
        
        # Find OP (Offensive Players) file
        op_files = glob.glob(f"{rankings_dir}/FantasyPros_*_Week_*_OP_Rankings.csv")
        if op_files:
            # Get the latest week (assuming you delete previous weeks)
            files['OP'] = op_files[0]
        
        # Find DST file
        dst_files = glob.glob(f"{rankings_dir}/FantasyPros_*_Week_*_DST_Rankings.csv")
        if dst_files:
            files['DST'] = dst_files[0]
        
        # Find K (Kicker) file
        k_files = glob.glob(f"{rankings_dir}/FantasyPros_*_Week_*_K_Rankings.csv")
        if k_files:
            files['K'] = k_files[0]
        
        return files

    @staticmethod
    def load_weekly_rankings() -> Dict[str, List[Dict]]:
        """Load weekly rankings from CSV files."""
        files = FantasyDraftTool.get_weekly_rankings_files()
        rankings = {}
        
        for position_type, file_path in files.items():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    rankings[position_type] = list(reader)
                print(f"Loaded {len(rankings[position_type])} {position_type} rankings from {file_path}")
            except Exception as e:
                print(f"Error loading {position_type} rankings from {file_path}: {e}")
                rankings[position_type] = []
        
        return rankings

    @staticmethod
    def fetch_league_rosters(league_id: str) -> List[dict]:
        """Get all rosters in a league."""
        try:
            if not league_id:
                return []
            url = f"https://api.sleeper.app/v1/league/{league_id}/rosters"
            resp = requests.get(url)
            resp.raise_for_status()
            rosters = resp.json()
            if isinstance(rosters, list):
                return rosters
            return []
        except requests.RequestException as e:
            print(f"Error fetching rosters for league_id '{league_id}': {e}")
            return []

    @staticmethod
    def fetch_league_users(league_id: str) -> List[dict]:
        """Get all users in a league."""
        try:
            if not league_id:
                return []
            url = f"https://api.sleeper.app/v1/league/{league_id}/users"
            resp = requests.get(url)
            resp.raise_for_status()
            users = resp.json()
            if isinstance(users, list):
                return users
            return []
        except requests.RequestException as e:
            print(f"Error fetching users for league_id '{league_id}': {e}")
            return []

    # ------------------------------
    # Weekly Rankings Analysis
    # ------------------------------
    @staticmethod
    def analyze_weekly_rankings(weekly_rankings: Dict[str, List[Dict]], user_players: List[dict], sleeper_players: Dict[str, dict], roster_settings: Dict, all_league_players: List[dict] = None) -> Dict:
        """Analyze weekly rankings and provide start/sit recommendations based on rankings and roster requirements."""
        analysis = {
            'starters': [],
            'bench': [],
            'defenses': [],
            'kickers': [],
            'waiver_suggestions': {
                'defenses': [],
                'kickers': []
            }
        }
        
        # Process offensive players (QB, RB, WR, TE) and create ranked list
        user_offensive_players = []
        if 'OP' in weekly_rankings:
            op_rankings = weekly_rankings['OP']
            
            for rank_idx, ranking in enumerate(op_rankings):
                player_name = ranking.get('PLAYER NAME', '').strip()
                position_with_rank = ranking.get('POS', '').strip()
                
                # Extract base position from position with rank (e.g., "WR2" -> "WR", "QB9" -> "QB")
                base_position = position_with_rank
                if position_with_rank and position_with_rank[0].isalpha():
                    # Find where the position ends and rank begins
                    for i, char in enumerate(position_with_rank):
                        if char.isdigit():
                            base_position = position_with_rank[:i]
                            break
                
                # Find matching player in user's roster using fuzzy matching
                matched = False
                for user_player in user_players:
                    sleeper_player = sleeper_players.get(user_player.get('player_id', ''))
                    if sleeper_player:
                        sleeper_name = sleeper_player.get('full_name', '')
                        
                        # Try exact match first
                        if sleeper_name == player_name:
                            user_offensive_players.append({
                                'name': player_name,
                                'position': base_position,  # Use base position for roster logic
                                'position_with_rank': position_with_rank,  # Keep original for display
                                'rank': rank_idx + 1,  # 1-based ranking
                                'team': sleeper_player.get('team', ''),
                                'sleeper_id': user_player.get('player_id'),
                                'is_on_roster': True
                            })
                            matched = True
                            break
                        
                        # Try normalized exact match
                        normalized_fp = FantasyDraftTool._normalize_name(player_name)
                        normalized_sleeper = FantasyDraftTool._normalize_name(sleeper_name)
                        if normalized_fp == normalized_sleeper:
                            user_offensive_players.append({
                                'name': player_name,
                                'position': base_position,
                                'position_with_rank': position_with_rank,
                                'rank': rank_idx + 1,
                                'team': sleeper_player.get('team', ''),
                                'sleeper_id': user_player.get('player_id'),
                                'is_on_roster': True
                            })
                            matched = True
                            break
                
                # If no exact match found, try fuzzy matching
                if not matched:
                    # Build candidate list from user's roster
                    roster_candidates = []
                    for user_player in user_players:
                        sleeper_player = sleeper_players.get(user_player.get('player_id', ''))
                        if sleeper_player:
                            sleeper_name = sleeper_player.get('full_name', '')
                            if sleeper_name:
                                roster_candidates.append((sleeper_name, user_player.get('player_id')))
                    
                    if roster_candidates:
                        # Try fuzzy matching
                        candidate_names = [name for name, _ in roster_candidates]
                        best_match = process.extractOne(
                            player_name,
                            candidate_names,
                            scorer=fuzz.token_sort_ratio,
                        )
                        
                        if best_match and best_match[1] >= 95:  # Very high confidence threshold
                            matched_name = best_match[0]
                            
                            # Additional validation: check for common name confusions
                            fp_normalized = FantasyDraftTool._normalize_name(player_name).lower()
                            sleeper_normalized = FantasyDraftTool._normalize_name(matched_name).lower()
                            
                            # Reject matches if first names are completely different
                            fp_first = fp_normalized.split()[0] if fp_normalized.split() else ""
                            sleeper_first = sleeper_normalized.split()[0] if sleeper_normalized.split() else ""
                            
                            # Only proceed if first names are very similar or identical
                            if len(fp_first) > 0 and len(sleeper_first) > 0:
                                first_name_similarity = fuzz.ratio(fp_first, sleeper_first)
                                if first_name_similarity >= 85:  # First names must be very similar
                                    # Find the corresponding player_id
                                    for name, player_id in roster_candidates:
                                        if name == matched_name:
                                            sleeper_player = sleeper_players.get(player_id)
                                            user_offensive_players.append({
                                                'name': player_name,
                                                'position': base_position,
                                                'position_with_rank': position_with_rank,
                                                'rank': rank_idx + 1,
                                                'team': sleeper_player.get('team', ''),
                                                'sleeper_id': player_id,
                                                'is_on_roster': True
                                            })
                                            break
        
        # Sort by rank (ascending - lower rank number is better)
        user_offensive_players.sort(key=lambda x: x['rank'])
        
        print(f"Found {len(user_offensive_players)} matching players after fuzzy matching")
        
        # Process defenses FIRST
        if 'DST' in weekly_rankings:
            dst_rankings = weekly_rankings['DST']
            print(f"Processing {len(dst_rankings)} defenses from weekly rankings...")
            
            for rank_idx, ranking in enumerate(dst_rankings):
                team_name = ranking.get('PLAYER NAME', '').strip()
                team_abbrev = ranking.get('TEAM', '').strip()
                
                # Check if user has this defense
                is_on_roster = False
                for user_player in user_players:
                    sleeper_player = sleeper_players.get(user_player.get('player_id', ''))
                    if sleeper_player and sleeper_player.get('position') == 'DEF':
                        sleeper_team = sleeper_player.get('team', '')
                        sleeper_name = sleeper_player.get('full_name', '')
                        
                        # Try multiple matching strategies
                        if (sleeper_team == team_abbrev or 
                            sleeper_team == team_name or 
                            sleeper_name == team_name or
                            team_abbrev in sleeper_name or
                            team_name in sleeper_name):
                            
                            analysis['defenses'].append({
                                'name': team_name,
                                'rank': rank_idx + 1,
                                'team': team_abbrev,
                                'sleeper_id': user_player.get('player_id'),
                                'is_on_roster': True
                            })
                            print(f"Matched defense: {team_name} ({team_abbrev}) - Rank #{rank_idx + 1}")
                            is_on_roster = True
                            break
                
                # If not on roster, check if it's available (not owned by any team in the league)
                if not is_on_roster:
                    # Check if this defense is owned by any team in the league
                    is_available = True
                    if all_league_players:
                        for league_player in all_league_players:
                            sleeper_player = sleeper_players.get(league_player.get('player_id', ''))
                            if sleeper_player and sleeper_player.get('position') == 'DEF':
                                sleeper_team = sleeper_player.get('team', '')
                                sleeper_name = sleeper_player.get('full_name', '')
                                
                                # Check if this is the same defense
                                if (sleeper_team == team_abbrev or 
                                    sleeper_team == team_name or 
                                    sleeper_name == team_name or
                                    team_abbrev in sleeper_name or
                                    team_name in sleeper_name):
                                    is_available = False
                                    break
                    
                    if is_available:
                        analysis['waiver_suggestions']['defenses'].append({
                            'name': team_name,
                            'rank': rank_idx + 1,
                            'team': team_abbrev,
                            'is_on_roster': False
                        })
            
            print(f"Found {len(analysis['defenses'])} defenses on roster")
        
        # Process kickers FIRST
        if 'K' in weekly_rankings:
            k_rankings = weekly_rankings['K']
            print(f"Processing {len(k_rankings)} kickers from weekly rankings...")
            
            for rank_idx, ranking in enumerate(k_rankings):
                player_name = ranking.get('PLAYER NAME', '').strip()
                team_abbrev = ranking.get('TEAM', '').strip()
                
                # Check if user has this kicker using fuzzy matching
                is_on_roster = False
                for user_player in user_players:
                    sleeper_player = sleeper_players.get(user_player.get('player_id', ''))
                    if sleeper_player and sleeper_player.get('position') == 'K':
                        sleeper_name = sleeper_player.get('full_name', '')
                        
                        # Try exact match first
                        if sleeper_name == player_name:
                            analysis['kickers'].append({
                                'name': player_name,
                                'rank': rank_idx + 1,
                                'team': sleeper_player.get('team', ''),
                                'sleeper_id': user_player.get('player_id'),
                                'is_on_roster': True
                            })
                            print(f"Matched kicker: {player_name} - Rank #{rank_idx + 1}")
                            is_on_roster = True
                            break
                        
                        # Try normalized match
                        normalized_fp = FantasyDraftTool._normalize_name(player_name)
                        normalized_sleeper = FantasyDraftTool._normalize_name(sleeper_name)
                        if normalized_fp == normalized_sleeper:
                            analysis['kickers'].append({
                                'name': player_name,
                                'rank': rank_idx + 1,
                                'team': sleeper_player.get('team', ''),
                                'sleeper_id': user_player.get('player_id'),
                                'is_on_roster': True
                            })
                            print(f"Matched kicker (normalized): {player_name} - Rank #{rank_idx + 1}")
                            is_on_roster = True
                            break
                
                # If not on roster, check if it's available (not owned by any team in the league)
                if not is_on_roster:
                    # Check if this kicker is owned by any team in the league
                    is_available = True
                    if all_league_players:
                        for league_player in all_league_players:
                            sleeper_player = sleeper_players.get(league_player.get('player_id', ''))
                            if sleeper_player and sleeper_player.get('position') == 'K':
                                sleeper_name = sleeper_player.get('full_name', '')
                                
                                # Check if this is the same kicker
                                if (sleeper_name == player_name or
                                    FantasyDraftTool._normalize_name(sleeper_name) == FantasyDraftTool._normalize_name(player_name)):
                                    is_available = False
                                    break
                    
                    if is_available:
                        analysis['waiver_suggestions']['kickers'].append({
                            'name': player_name,
                            'rank': rank_idx + 1,
                            'team': team_abbrev,
                            'is_on_roster': False
                        })
            
            print(f"Found {len(analysis['kickers'])} kickers on roster")
        
        # Sort DST and K by rank
        analysis['defenses'].sort(key=lambda x: x['rank'])
        analysis['kickers'].sort(key=lambda x: x['rank'])
        analysis['waiver_suggestions']['defenses'].sort(key=lambda x: x['rank'])
        analysis['waiver_suggestions']['kickers'].sort(key=lambda x: x['rank'])
        
        # Create combined top 5 lists for waiver suggestions (including your own players)
        all_defenses = analysis['defenses'] + analysis['waiver_suggestions']['defenses']
        all_defenses.sort(key=lambda x: x['rank'])
        analysis['waiver_suggestions']['defenses'] = all_defenses[:5]  # Top 5 overall
        
        all_kickers = analysis['kickers'] + analysis['waiver_suggestions']['kickers']
        all_kickers.sort(key=lambda x: x['rank'])
        analysis['waiver_suggestions']['kickers'] = all_kickers[:5]  # Top 5 overall
        
        # Determine starting lineup based on roster requirements
        starters = []
        bench = []
        
        # Count how many of each position we need
        position_requirements = {
            'QB': roster_settings.get('QB', 0),
            'RB': roster_settings.get('RB', 0),
            'WR': roster_settings.get('WR', 0),
            'TE': roster_settings.get('TE', 0),
            'WRRB_FLEX': roster_settings.get('WRRB_FLEX', 0),
            'FLEX': roster_settings.get('FLEX', 0),  # RB, WR, or TE
            'WRRBTE_FLEX': roster_settings.get('WRRBTE_FLEX', 0),  # RB, WR, or TE (same as FLEX)
            'SUPER_FLEX': roster_settings.get('SUPER_FLEX', 0)  # QB, RB, WR, or TE
        }
        
        # Track how many of each position we've used
        position_used = {pos: 0 for pos in position_requirements.keys()}
        
        # First pass: Fill required positions
        for player in user_offensive_players:
            pos = player['position']
            if pos in position_requirements and position_used[pos] < position_requirements[pos]:
                starters.append(player)
                position_used[pos] += 1
            else:
                bench.append(player)
        
        # Second pass: Fill flex positions
        # Create lists of eligible players for each flex type
        all_flex_players = [p for p in bench if p['position'] in ['QB', 'RB', 'WR', 'TE']]
        wrrbte_flex_players = [p for p in bench if p['position'] in ['RB', 'WR', 'TE']]
        wrrb_flex_players = [p for p in bench if p['position'] in ['RB', 'WR']]
        
        # Sort all lists by rank (ascending - lower rank is better)
        all_flex_players.sort(key=lambda x: x['rank'])
        wrrbte_flex_players.sort(key=lambda x: x['rank'])
        wrrb_flex_players.sort(key=lambda x: x['rank'])
        
        # Fill SUPER_FLEX (can use QB, RB, WR, or TE) - highest priority
        super_flex_needed = position_requirements.get('SUPER_FLEX', 0)
        for _ in range(super_flex_needed):
            if all_flex_players:
                best_flex = all_flex_players.pop(0)
                best_flex['flex_slot'] = 'SUPER_FLEX'  # Track which flex slot this player fills
                starters.append(best_flex)
                bench.remove(best_flex)
                # Remove from other flex lists if present
                if best_flex in wrrbte_flex_players:
                    wrrbte_flex_players.remove(best_flex)
                if best_flex in wrrb_flex_players:
                    wrrb_flex_players.remove(best_flex)
        
        # Fill FLEX (can use RB, WR, or TE)
        flex_needed = position_requirements.get('FLEX', 0)
        for _ in range(flex_needed):
            if wrrbte_flex_players:
                best_flex = wrrbte_flex_players.pop(0)
                best_flex['flex_slot'] = 'FLEX'  # Track which flex slot this player fills
                starters.append(best_flex)
                bench.remove(best_flex)
                # Remove from WRRB_FLEX list if present
                if best_flex in wrrb_flex_players:
                    wrrb_flex_players.remove(best_flex)
        
        # Fill WRRBTE_FLEX (can use RB, WR, or TE) - same as FLEX
        wrrbte_flex_needed = position_requirements.get('WRRBTE_FLEX', 0)
        for _ in range(wrrbte_flex_needed):
            if wrrbte_flex_players:
                best_flex = wrrbte_flex_players.pop(0)
                best_flex['flex_slot'] = 'WRRBTE_FLEX'  # Track which flex slot this player fills
                starters.append(best_flex)
                bench.remove(best_flex)
                # Remove from WRRB_FLEX list if present
                if best_flex in wrrb_flex_players:
                    wrrb_flex_players.remove(best_flex)
        
        # Fill WRRB_FLEX (can use RB or WR only)
        wrrb_flex_needed = position_requirements.get('WRRB_FLEX', 0)
        for _ in range(wrrb_flex_needed):
            if wrrb_flex_players:
                best_flex = wrrb_flex_players.pop(0)
                best_flex['flex_slot'] = 'WRRB_FLEX'  # Track which flex slot this player fills
                starters.append(best_flex)
                bench.remove(best_flex)
        
        # Sort starters by roster requirements order and rank within position
        sorted_starters = []
        
        # Create the position order based on roster_settings order and counts
        position_order = []
        
        # Add positions in the order they appear in roster_settings with their counts
        for pos, count in roster_settings.items():
            if count > 0 and pos in ['QB', 'RB', 'WR', 'TE', 'SUPER_FLEX', 'FLEX', 'WRRBTE_FLEX', 'WRRB_FLEX']:
                for _ in range(count):
                    position_order.append(pos)
        
        # Group starters by their assigned position slot
        # For flex players, use their flex_slot, for others use their position
        starters_by_pos = {}
        for starter in starters:
            # Use flex_slot if it exists (for flex players), otherwise use position
            pos = starter.get('flex_slot', starter['position'])
            if pos not in starters_by_pos:
                starters_by_pos[pos] = []
            starters_by_pos[pos].append(starter)
        
        # Debug: print what we have
        print(f"Starters by position: {list(starters_by_pos.keys())}")
        print(f"Position order from roster settings: {position_order}")
        for pos, players in starters_by_pos.items():
            print(f"{pos}: {[p['name'] for p in players]}")
        
        # Sort each position group by rank (ascending - lower rank is better)
        for pos in starters_by_pos:
            starters_by_pos[pos].sort(key=lambda x: x['rank'])
        
        # Add starters following the roster requirements order
        position_counts = {}
        for pos in position_order:
            if pos not in position_counts:
                position_counts[pos] = 0
            
            if pos in starters_by_pos and position_counts[pos] < len(starters_by_pos[pos]):
                sorted_starters.append(starters_by_pos[pos][position_counts[pos]])
                position_counts[pos] += 1
        
        # Add DST and K to starting lineup - always use best available (waiver wire or roster)
        dst_needed = roster_settings.get('DEF', 0)
        k_needed = roster_settings.get('K', 0)
        
        # Add K to lineup first - prioritize best available from all sources
        if k_needed > 0:
            best_k = None
            is_waiver_wire = False
            
            # Check if best waiver wire K is better than best roster K
            if analysis['waiver_suggestions']['kickers']:
                best_waiver_k = analysis['waiver_suggestions']['kickers'][0]
                if analysis['kickers']:
                    best_roster_k = analysis['kickers'][0]
                    # Use waiver wire K if it has better rank (lower number)
                    if best_waiver_k['rank'] < best_roster_k['rank']:
                        best_k = best_waiver_k
                        is_waiver_wire = True
                    else:
                        best_k = best_roster_k
                else:
                    # No roster K, use waiver wire
                    best_k = best_waiver_k
                    is_waiver_wire = True
            elif analysis['kickers']:
                # Only roster K available
                best_k = analysis['kickers'][0]
            
            if best_k:
                best_k = best_k.copy()  # Don't modify original
                best_k['position'] = 'K'
                if is_waiver_wire:
                    best_k['is_waiver_wire'] = True
                sorted_starters.append(best_k)
        
        # Add DST to lineup after kicker - prioritize best available from all sources
        if dst_needed > 0:
            best_dst = None
            is_waiver_wire = False
            
            # Check if best waiver wire DST is better than best roster DST
            if analysis['waiver_suggestions']['defenses']:
                best_waiver_dst = analysis['waiver_suggestions']['defenses'][0]
                if analysis['defenses']:
                    best_roster_dst = analysis['defenses'][0]
                    # Use waiver wire DST if it has better rank (lower number)
                    if best_waiver_dst['rank'] < best_roster_dst['rank']:
                        best_dst = best_waiver_dst
                        is_waiver_wire = True
                    else:
                        best_dst = best_roster_dst
                else:
                    # No roster DST, use waiver wire
                    best_dst = best_waiver_dst
                    is_waiver_wire = True
            elif analysis['defenses']:
                # Only roster DST available
                best_dst = analysis['defenses'][0]
            
            if best_dst:
                best_dst = best_dst.copy()  # Don't modify original
                best_dst['position'] = 'DEF'
                if is_waiver_wire:
                    best_dst['is_waiver_wire'] = True
                sorted_starters.append(best_dst)
        
        analysis['starters'] = sorted_starters
        analysis['bench'] = bench
        
        return analysis

    @staticmethod
    def get_league_roster_settings(league_id: str) -> Dict:
        """Get league roster settings to understand lineup requirements."""
        try:
            url = f"https://api.sleeper.app/v1/league/{league_id}"
            resp = requests.get(url)
            resp.raise_for_status()
            league_data = resp.json()
            
            # Extract roster settings
            roster_positions = league_data.get('roster_positions', [])
            position_counts = {}
            for pos in roster_positions:
                position_counts[pos] = position_counts.get(pos, 0) + 1
            
            return position_counts
        except requests.RequestException as e:
            print(f"Error fetching league settings for league_id '{league_id}': {e}")
            return {}

    def fetch_sleeper_draft_picks(self) -> None:
        """Fetch current picks from the configured Sleeper draft and update drafted status"""
        if not self.sleeper_draft_id:
            print("No Sleeper draft ID configured. Set it first to enable live draft syncing.")
            return

        print("Fetching current draft picks from Sleeper...")
        try:
            response = requests.get(f"https://api.sleeper.app/v1/draft/{self.sleeper_draft_id}/picks")
            response.raise_for_status()
            picks = response.json()

            drafted_ids: Set[str] = set()
            # Build a mapping of drafted Sleeper player IDs
            for pick in picks:
                player_id = pick.get('player_id')
                if player_id:
                    drafted_ids.add(str(player_id))

            self.drafted_sleeper_ids = drafted_ids
            self.apply_drafted_status()
            print(f"Detected {len(self.drafted_sleeper_ids)} drafted players from the Sleeper draft.")

        except requests.RequestException as e:
            print(f"Error fetching draft picks: {e}")

    def apply_drafted_status(self) -> None:
        """Mark players as drafted based on collected Sleeper player IDs"""
        # Reset drafted flags first
        for player in self.players:
            player.drafted = False
            player.drafted_by = None

        if not self.drafted_sleeper_ids:
            return

        # Build normalized name map for drafted Sleeper players
        drafted_normalized_names: Set[str] = set()
        drafted_position_by_id: Dict[str, str] = {}
        for drafted_id in self.drafted_sleeper_ids:
            sp = self.sleeper_players.get(drafted_id)
            if not sp:
                continue
            drafted_position_by_id[drafted_id] = sp.get('position', '')
            drafted_normalized_names.add(self._normalize_name(sp.get('full_name', '')))

        # First pass: Apply drafted status where we have a Sleeper ID direct match
        for player in self.players:
            if player.sleeper_id and player.sleeper_id in self.drafted_sleeper_ids:
                player.drafted = True

        # Second pass: Fallback by normalized name and position if no Sleeper ID matched
        for player in self.players:
            if player.drafted:
                continue
            norm_name = self._normalize_name(player.name)
            if norm_name in drafted_normalized_names:
                # If we can verify position, do so to avoid false positives
                # Sleeper positions are like 'QB', 'RB', 'WR', 'TE'
                # Try to find a drafted sleeper player with same normalized name and same position
                for drafted_id in self.drafted_sleeper_ids:
                    sp = self.sleeper_players.get(drafted_id)
                    if not sp:
                        continue
                    if self._normalize_name(sp.get('full_name', '')) == norm_name:
                        sleeper_pos = (sp.get('position') or '').upper()
                        if not sleeper_pos or sleeper_pos == player.position:
                            player.drafted = True
                            break

    def get_unmatched_drafted_from_sleeper(self) -> List[dict]:
        """Return drafted Sleeper players that we could not map to any of our players."""
        if not self.drafted_sleeper_ids:
            return []
        # Build normalized names for players we consider drafted
        drafted_norms = set()
        for p in self.players:
            if p.drafted:
                drafted_norms.add(self._normalize_name(p.name))

        unmatched = []
        for drafted_id in self.drafted_sleeper_ids:
            sp = self.sleeper_players.get(drafted_id)
            if not sp:
                continue
            norm = self._normalize_name(sp.get('full_name', ''))
            if norm not in drafted_norms:
                unmatched.append({
                    'player_id': drafted_id,
                    'full_name': sp.get('full_name'),
                    'position': sp.get('position'),
                    'team': sp.get('team') or sp.get('team_name'),
                })
        return unmatched
    
    def get_top_players_by_position(self, position: str, limit: int = 3) -> List[Player]:
        """Get top N players for a specific position"""
        position_players = [p for p in self.players if p.position == position and not p.drafted]
        return sorted(position_players, key=lambda x: x.overall_rank)[:limit]

    def get_top_overall_available(self, limit: int = 5) -> List[Player]:
        """Get top N overall players that are not drafted yet"""
        available_players = [p for p in self.players if not p.drafted]
        return sorted(available_players, key=lambda x: x.overall_rank)[:limit]

    def get_drafted_players(self) -> List[Player]:
        """Get all players marked as drafted, ordered by overall rank"""
        drafted_players = [p for p in self.players if p.drafted]
        return sorted(drafted_players, key=lambda x: x.overall_rank)
    
    def display_draft_board(self) -> None:
        """Display the draft board with top 3 players per position"""
        print("\n" + "="*80)
        print("FANTASY DRAFT BOARD - TOP 3 PLAYERS PER POSITION")
        print("="*80)
        
        # Define fantasy positions in order of importance
        positions = ['RB', 'WR', 'QB', 'TE']
        
        for position in positions:
            top_players = self.get_top_players_by_position(position, 3)
            
            if not top_players:
                continue
            
            print(f"\n{position} (Running Backs)" if position == 'RB' else 
                  f"{position} (Wide Receivers)" if position == 'WR' else
                  f"{position} (Quarterbacks)" if position == 'QB' else
                  f"{position} (Tight Ends)")
            print("-" * 60)
            
            for i, player in enumerate(top_players, 1):
                sleeper_info = ""
                if player.sleeper_id and player.sleeper_id in self.sleeper_players:
                    sleeper_player = self.sleeper_players[player.sleeper_id]
                    if sleeper_player.get('injury_status'):
                        sleeper_info = f" [{sleeper_player['injury_status']}]"
                
                print(f"{i}. {player.name} ({player.team})")
                print(f"    Overall: #{player.overall_rank} | {position} Rank: #{player.position_rank} | "
                      f"Tier: {player.tier} | Bye: {player.bye_week} | SOS: {player.sos_season}")
                if player.ecr_vs_adp != 0:
                    adp_text = f"ADP: {'+' if player.ecr_vs_adp > 0 else ''}{player.ecr_vs_adp}"
                    print(f"    {adp_text}")
                if sleeper_info:
                    print(f"    Sleeper Status: {sleeper_info}")
                print()
    
    def search_player(self, name: str) -> Optional[Player]:
        """Search for a specific player by name"""
        for player in self.players:
            if name.lower() in player.name.lower():
                return player
        return None
    
    def display_player_details(self, player: Player) -> None:
        """Display detailed information about a specific player"""
        print(f"\n{'='*50}")
        print(f"PLAYER DETAILS: {player.name}")
        print(f"{'='*50}")
        print(f"Team: {player.team}")
        print(f"Position: {player.position} (Rank #{player.position_rank})")
        print(f"Overall Rank: #{player.overall_rank}")
        print(f"Tier: {player.tier}")
        print(f"Bye Week: {player.bye_week}")
        print(f"Strength of Schedule: {player.sos_season}")
        print(f"ECR vs ADP: {player.ecr_vs_adp:+d}")
        
        if player.sleeper_id and player.sleeper_id in self.sleeper_players:
            sleeper_player = self.sleeper_players[player.sleeper_id]
            print(f"\nSleeper Info:")
            print(f"Status: {sleeper_player.get('status', 'Unknown')}")
            if sleeper_player.get('injury_status'):
                print(f"Injury Status: {sleeper_player['injury_status']}")
            if sleeper_player.get('injury_notes'):
                print(f"Injury Notes: {sleeper_player['injury_notes']}")
        print(f"Drafted: {'Yes' if player.drafted else 'No'}")

def main():
    """Main function to run the fantasy draft tool"""
    print("Fantasy Draft Tool")
    print("==================")
    
    # You'll need to update this path to your CSV file
    csv_file = "draft.csv"  # Update this path
    
    try:
        # Initialize the tool
        draft_tool = FantasyDraftTool(csv_file)
        
        # Load data
        draft_tool.load_fantasypros_data()
        draft_tool.fetch_sleeper_data()
        draft_tool.match_players()

        # Optional: configure Sleeper draft ID for live syncing
        try:
            draft_id_input = input("Enter Sleeper draft ID (optional, press Enter to skip): ").strip()
        except KeyboardInterrupt:
            draft_id_input = ""
        if draft_id_input:
            draft_tool.set_sleeper_draft_id(draft_id_input)
            draft_tool.fetch_sleeper_draft_picks()
        
        # Display the draft board
        draft_tool.display_draft_board()
        
        # Interactive search
        while True:
            print("\n" + "="*50)
            print("OPTIONS:")
            print("1. View draft board again")
            print("2. Search for a player")
            print("3. Refresh draft status from Sleeper")
            print("4. Set or change Sleeper draft ID")
            print("5. Exit")
            print("="*50)
            
            choice = input("Enter your choice (1-5): ").strip()
            
            if choice == "1":
                draft_tool.display_draft_board()
            elif choice == "2":
                search_name = input("Enter player name to search: ").strip()
                player = draft_tool.search_player(search_name)
                if player:
                    draft_tool.display_player_details(player)
                else:
                    print(f"No player found matching '{search_name}'")
            elif choice == "3":
                draft_tool.fetch_sleeper_draft_picks()
                draft_tool.display_draft_board()
            elif choice == "4":
                new_id = input("Enter new Sleeper draft ID (leave empty to clear): ").strip()
                draft_tool.set_sleeper_draft_id(new_id)
                if new_id:
                    draft_tool.fetch_sleeper_draft_picks()
                draft_tool.display_draft_board()
            elif choice == "5":
                print("Good luck with your draft!")
                break
            else:
                print("Invalid choice. Please enter a number from 1 to 5.")
                
    except FileNotFoundError:
        print(f"Error: Could not find CSV file '{csv_file}'")
        print("Please make sure the FantasyPros CSV file is in the same directory as this script.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
