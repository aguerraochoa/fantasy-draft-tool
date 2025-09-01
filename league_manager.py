#!/usr/bin/env python3
"""
League Manager for Fantasy Draft Tool
Handles saving, loading, editing, and managing multiple league draft URLs
"""

import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class League:
    """Represents a saved fantasy league"""
    name: str
    draft_url: str
    draft_id: str
    created_at: str
    last_used: str

class LeagueManager:
    def __init__(self, storage_file: str = "saved_leagues.json"):
        self.storage_file = storage_file
        self.leagues: Dict[str, League] = {}
        self.load_leagues()
    
    def load_leagues(self) -> None:
        """Load saved leagues from JSON file"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    leagues_data = json.load(f)
                    self.leagues = {
                        name: League(**league_data) 
                        for name, league_data in leagues_data.items()
                    }
                print(f"Loaded {len(self.leagues)} saved leagues")
            else:
                print("No saved leagues file found, starting fresh")
        except Exception as e:
            print(f"Error loading leagues: {e}")
            self.leagues = {}
    
    def save_leagues(self) -> None:
        """Save leagues to JSON file"""
        try:
            leagues_data = {
                name: asdict(league) 
                for name, league in self.leagues.items()
            }
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(leagues_data, f, indent=2, ensure_ascii=False)
            print(f"Saved {len(self.leagues)} leagues")
        except Exception as e:
            print(f"Error saving leagues: {e}")
    
    def add_league(self, name: str, draft_url: str, draft_id: str) -> bool:
        """Add a new league"""
        if name in self.leagues:
            return False  # League name already exists
        
        now = datetime.now().isoformat()
        league = League(
            name=name,
            draft_url=draft_url,
            draft_id=draft_id,
            created_at=now,
            last_used=now
        )
        
        self.leagues[name] = league
        self.save_leagues()
        return True
    
    def update_league(self, name: str, draft_url: str, draft_id: str) -> bool:
        """Update an existing league"""
        if name not in self.leagues:
            return False
        
        now = datetime.now().isoformat()
        self.leagues[name].draft_url = draft_url
        self.leagues[name].draft_id = draft_id
        self.leagues[name].last_used = now
        
        self.save_leagues()
        return True
    
    def delete_league(self, name: str) -> bool:
        """Delete a league"""
        if name in self.leagues:
            del self.leagues[name]
            self.save_leagues()
            return True
        return False
    
    def get_league(self, name: str) -> Optional[League]:
        """Get a specific league by name"""
        return self.leagues.get(name)
    
    def get_all_leagues(self) -> List[str]:
        """Get list of all league names"""
        return list(self.leagues.keys())
    
    def get_league_names_sorted(self) -> List[str]:
        """Get league names sorted by last used (most recent first)"""
        sorted_leagues = sorted(
            self.leagues.values(), 
            key=lambda x: x.last_used, 
            reverse=True
        )
        return [league.name for league in sorted_leagues]
    
    def mark_league_used(self, name: str) -> None:
        """Mark a league as recently used"""
        if name in self.leagues:
            self.leagues[name].last_used = datetime.now().isoformat()
            self.save_leagues()
    
    def export_leagues(self) -> str:
        """Export leagues to JSON string for sharing/backup"""
        try:
            return json.dumps(self.leagues, indent=2, ensure_ascii=False, default=asdict)
        except Exception as e:
            print(f"Error exporting leagues: {e}")
            return "{}"
    
    def import_leagues(self, json_data: str) -> bool:
        """Import leagues from JSON string"""
        try:
            imported_leagues = json.loads(json_data)
            for name, league_data in imported_leagues.items():
                if isinstance(league_data, dict):
                    # Handle both old and new format
                    if 'name' in league_data:
                        league = League(**league_data)
                    else:
                        # Convert old format to new
                        league = League(
                            name=name,
                            draft_url=league_data.get('draft_url', ''),
                            draft_id=league_data.get('draft_id', ''),
                            created_at=league_data.get('created_at', datetime.now().isoformat()),
                            last_used=league_data.get('last_used', datetime.now().isoformat())
                        )
                    self.leagues[name] = league
            
            self.save_leagues()
            return True
        except Exception as e:
            print(f"Error importing leagues: {e}")
            return False
    
    def get_league_count(self) -> int:
        """Get total number of saved leagues"""
        return len(self.leagues)
