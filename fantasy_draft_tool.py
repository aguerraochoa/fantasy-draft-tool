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
        
        for row in reader:
            try:
                # Parse position and position rank
                pos_match = re.match(r'([A-Z]+)(\d+)', row['POS'])
                if not pos_match:
                    continue
                
                position = pos_match.group(1)
                position_rank = int(pos_match.group(2))
                
                # Parse SOS season (extract number from "X out of 5 stars")
                sos_match = re.search(r'(\d+)', row['SOS SEASON'])
                sos_season = row['SOS SEASON'] if not sos_match else f"{sos_match.group(1)}/5"
                
                player = Player(
                    name=row['PLAYER NAME'].strip(),
                    team=row['TEAM'].strip(),
                    position=position,
                    overall_rank=int(row['RK']),
                    position_rank=position_rank,
                    tier=int(row['TIERS']),
                    bye_week=self._parse_int_field(row['BYE WEEK'], 0),
                    sos_season=sos_season,
                    ecr_vs_adp=self._parse_int_field(row['ECR VS. ADP'], 0)
                )
                
                self.players.append(player)
                
            except (ValueError, KeyError) as e:
                print(f"Error parsing row: {row} - {e}")
                continue
        
        print(f"Loaded {len(self.players)} players from FantasyPros data")
    
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

            if best_match and best_match[1] >= 88:
                chosen_key = best_match[0]
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
