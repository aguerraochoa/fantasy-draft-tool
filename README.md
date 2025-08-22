# Fantasy Draft Tool

A web-based fantasy football draft assistant that combines FantasyPros rankings with live Sleeper data.

## Features

- 📊 **FantasyPros Integration**: Upload your FantasyPros CSV rankings
- 🏈 **Live Sleeper Data**: Real-time player injury status and availability
- 🎯 **Live Draft Tracking**: Connect to your Sleeper draft to track picks in real-time
- 📱 **Responsive Web Interface**: Works on any device with a browser
- 🔍 **Player Search**: Find specific players quickly
- 📈 **Position Rankings**: Top players by position (RB, WR, QB, TE)

## Quick Start (Web App)

### Option 1: Use the Live Demo
Visit the deployed app at: [Your Streamlit Cloud URL]

### Option 2: Deploy Your Own (Free)

1. **Fork this repository** on GitHub
2. **Deploy to Streamlit Cloud**:
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with GitHub
   - Click "New app"
   - Select your forked repository
   - Set the main file path to: `ui.py`
   - Click "Deploy"

3. **Get your FantasyPros CSV**:
   - Visit [FantasyPros Rankings](https://www.fantasypros.com/nfl/rankings/consensus-cheatsheets.php)
   - Export your rankings as CSV
   - Download the file

4. **Use the app**:
   - Upload your CSV file
   - Optionally connect to your Sleeper draft
   - Start drafting!

## Local Development

### Prerequisites
- Python 3.8+
- pip

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/fantasy_draft_tool.git
   cd fantasy_draft_tool
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the web app**:
   ```bash
   streamlit run ui.py
   ```

4. **Or run the command line version**:
   ```bash
   python fantasy_draft_tool.py
   ```

## How to Use

### Getting FantasyPros Data
1. Go to [FantasyPros NFL Rankings](https://www.fantasypros.com/nfl/rankings/consensus-cheatsheets.php)
2. Customize your rankings (scoring, positions, etc.)
3. Export as CSV
4. Upload to the app

### Connecting to Sleeper Draft (Optional)
1. Open your Sleeper draft
2. Copy the draft ID from the URL: `https://sleeper.app/draft/YOUR_DRAFT_ID`
3. Paste the ID in the app
4. Click "Refresh Draft Picks" to sync

## Features Explained

### Top Available Players
- Shows the best undrafted players overall
- Toggle between top 5 and top 10

### Position Rankings
- Top 3 available players per position
- Organized by fantasy importance (RB, WR, QB, TE)

### Player Search
- Search by player name
- View detailed stats and Sleeper status

### Draft Tracking
- Real-time updates of drafted players
- Automatic removal from available lists
- Shows injury status from Sleeper

## File Structure

```
fantasy_draft_tool/
├── ui.py                    # Streamlit web interface
├── fantasy_draft_tool.py    # Core logic and CLI interface
├── requirements.txt         # Python dependencies
├── README.md               # This file
└── draft.csv               # Sample FantasyPros data
```

## Dependencies

- `streamlit` - Web interface
- `requests` - API calls to Sleeper
- `fuzzywuzzy` - Player name matching
- `python-Levenshtein` - String similarity

## Contributing

Feel free to submit issues and enhancement requests!

## License

MIT License - feel free to use this for your own drafts!
