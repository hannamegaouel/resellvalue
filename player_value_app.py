import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import io

# Page configuration
st.set_page_config(
    page_title="Transfer Window - Resell value calculator",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .recommendation-hold {
        background-color: #d4edda;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #28a745;
    }
    .recommendation-sell {
        background-color: #f8d7da;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #dc3545;
    }
    .recommendation-consider {
        background-color: #fff3cd;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #ffc107;
    }
    </style>
""", unsafe_allow_html=True)


class PlayerValueEstimator:
    def __init__(self):
        # More conservative age curves with slower growth and faster decline
        self.age_peak_curves = {
            'Attacker': {'peak_age': 27, 'decline_rate': 0.10},
            'Midfielder': {'peak_age': 28, 'decline_rate': 0.09},
            'Defender': {'peak_age': 29, 'decline_rate': 0.08},
            'Goalkeeper': {'peak_age': 31, 'decline_rate': 0.06}
        }
        
    def calculate_playing_time_factor(self, minutes_played, total_available_minutes):
        """
        Calculate multiplier based on playing time percentage in current season.
        Uses percentage of available minutes rather than absolute numbers.
        
        Args:
            minutes_played: Minutes the player has played
            total_available_minutes: Total minutes available so far this season
        """
        if total_available_minutes <= 0:
            return 1.0  # No penalty if season hasn't started
        
        # Calculate playing time percentage
        playing_time_pct = minutes_played / total_available_minutes
        
        # Apply factors based on percentage thresholds
        if playing_time_pct >= 0.75:
            return 1.0  # Regular starter (75%+ of available minutes)
        elif playing_time_pct >= 0.60:
            return 0.95  # Frequent player (60-75%)
        elif playing_time_pct >= 0.40:
            return 0.85  # Squad player (40-60%)
        elif playing_time_pct >= 0.20:
            return 0.70  # Backup (20-40%)
        else:
            return 0.55  # Limited playing time (<20%) - significant penalty
    
    def calculate_age_factor(self, current_age, position, years_ahead=2):
        """Calculate value multiplier based on age curve - MORE CONSERVATIVE"""
        curve = self.age_peak_curves.get(position, self.age_peak_curves['Midfielder'])
        peak_age = curve['peak_age']
        decline_rate = curve['decline_rate']
        
        future_age = current_age + years_ahead
        
        # Reduced growth rate from 0.15 to 0.10 for more conservative projections
        growth_rate = 0.10
        
        if current_age < peak_age:
            if future_age <= peak_age:
                years_to_grow = years_ahead
                return (1 + growth_rate) ** years_to_grow
            else:
                years_to_peak = peak_age - current_age
                years_past_peak = future_age - peak_age
                growth_factor = (1 + growth_rate) ** years_to_peak
                decline_factor = (1 - decline_rate) ** years_past_peak
                return growth_factor * decline_factor
        else:
            years_past_peak = future_age - peak_age
            return (1 - decline_rate) ** years_past_peak
    
    def calculate_momentum_factor(self, value_history):
        """Calculate momentum based on recent value changes - MORE CONSERVATIVE"""
        values = [v for v in value_history if pd.notna(v) and v > 0]
        
        if len(values) < 2:
            return 1.0
        
        growth_rates = []
        for i in range(1, len(values)):
            if values[i-1] > 0:
                rate = (values[i] - values[i-1]) / values[i-1]
                growth_rates.append(rate)
        
        if not growth_rates:
            return 1.0
        
        avg_growth = np.mean(growth_rates)
        recent_growth = growth_rates[-1] if growth_rates else 0
        weighted_growth = 0.6 * recent_growth + 0.4 * avg_growth
        
        # More conservative momentum multipliers
        if weighted_growth > 0.3:
            return 1.30
        elif weighted_growth > 0.2:
            return 1.20
        elif weighted_growth > 0.1:
            return 1.10
        elif weighted_growth > 0:
            return 1.05
        elif weighted_growth > -0.1:
            return 1.0
        else:
            return 0.80
    
    def calculate_premium_factor(self, player_data):
        """Calculate premium factors for asking price - MORE CONSERVATIVE"""
        premium = 1.0
        position = player_data.get('position', 'Midfielder')
        
        # League premium - slightly reduced
        top_tier_1 = ['Premier League']
        top_tier_2 = ['La Liga', 'Bundesliga', 'Serie A']
        top_tier_3 = ['Ligue 1', 'Primeira Liga', 'Eredivisie']
        
        league = str(player_data.get('league', '')).strip()
        
        if league in top_tier_1:
            premium += 0.12
        elif league in top_tier_2:
            premium += 0.10
        elif league in top_tier_3:
            premium += 0.06
        else:
            premium += 0.02
        
        # Age premium - more conservative
        age = player_data.get('age', 25)
        if age < 23:
            premium += 0.18
        elif age < 25:
            premium += 0.10
        elif age < 27:
            premium += 0.03
        
        # Performance premium - position-specific
        try:
            if position == 'Goalkeeper':
                clean_sheets = int(player_data.get('clean_sheets', 0))
                goals_conceded = int(player_data.get('goals_conceded', 0))
                matches_played = int(player_data.get('matches_played', 1))
                
                if matches_played > 0:
                    clean_sheet_ratio = clean_sheets / matches_played
                    goals_per_game = goals_conceded / matches_played
                    
                    if clean_sheet_ratio > 0.5 and goals_per_game < 0.8:
                        premium += 0.15
                    elif clean_sheet_ratio > 0.4 and goals_per_game < 1.0:
                        premium += 0.10
                    elif clean_sheet_ratio > 0.3 and goals_per_game < 1.2:
                        premium += 0.05
            
            elif position in ['Attacker', 'Midfielder']:
                goals = float(player_data.get('goals', 0))
                assists = float(player_data.get('assists', 0))
                total_contributions = goals + assists
                
                if total_contributions > 20:
                    premium += 0.15
                elif total_contributions > 10:
                    premium += 0.08
                elif total_contributions > 5:
                    premium += 0.04
            
        except (ValueError, TypeError):
            pass
        
        # Contract premium - more conservative
        try:
            contract_year = int(player_data.get('contract_expires', 2025))
            current_year = 2025
            years_remaining = contract_year - current_year
            
            if years_remaining >= 4:
                premium += 0.12
            elif years_remaining >= 3:
                premium += 0.08
            elif years_remaining >= 2:
                premium += 0.04
            elif years_remaining <= 1:
                premium -= 0.15
        except (ValueError, TypeError):
            pass
        
        return premium

    def estimate_future_value(self, current_value, age, position, value_history, 
                            minutes_played, total_available_minutes, years_ahead=2):
        """Estimate player value in future years with percentage-based playing time"""
        age_factor = self.calculate_age_factor(age, position, years_ahead)
        momentum_factor = self.calculate_momentum_factor(value_history)
        playing_time_factor = self.calculate_playing_time_factor(minutes_played, total_available_minutes)
        
        # Apply all factors including playing time
        base_projection = current_value * age_factor * momentum_factor * playing_time_factor
        
        # Increased uncertainty for more conservative estimates
        uncertainty = 0.20 + (0.06 * years_ahead)
        low_estimate = base_projection * (1 - uncertainty)
        high_estimate = base_projection * (1 + uncertainty * 1.3)
        
        return {
            'projected_value': base_projection,
            'low_estimate': low_estimate,
            'high_estimate': high_estimate,
            'age_factor': age_factor,
            'momentum_factor': momentum_factor,
            'playing_time_factor': playing_time_factor,
            'playing_time_pct': (minutes_played / total_available_minutes * 100) if total_available_minutes > 0 else 0
        }

    def analyze_player(self, player_data):
        """Complete analysis for a single player"""
        name = player_data['name']
        age = int(player_data['age'])
        position = player_data['position']
        current_value = float(player_data['current_value'])
        value_history = player_data['value_history']
        minutes_played = int(player_data.get('minutes_played', 0))
        total_available_minutes = int(player_data.get('total_available_minutes', 0))
        
        # Get projections with playing time consideration
        projection_1y = self.estimate_future_value(
            current_value, age, position, value_history, 
            minutes_played, total_available_minutes, 1
        )
        projection_2y = self.estimate_future_value(
            current_value, age, position, value_history, 
            minutes_played, total_available_minutes, 2
        )
        
        # Calculate premium
        premium = self.calculate_premium_factor(player_data)
        
        # More conservative asking prices
        asking_price_now = current_value * premium * 1.15
        asking_price_1y = projection_1y['projected_value'] * premium
        asking_price_2y = projection_2y['projected_value'] * premium
        
        # More conservative minimum (90% instead of 85%)
        minimum_now = asking_price_now * 0.90
        minimum_1y = asking_price_1y * 0.90
        minimum_2y = asking_price_2y * 0.90
        
        # Determine recommendation
        recommendation = self._get_recommendation(
            age, position, projection_1y, current_value, 
            player_data.get('contract_expires', 2027),
            minutes_played, total_available_minutes
        )
        
        return {
            'name': name,
            'current': {
                'value': current_value,
                'asking_price': asking_price_now,
                'minimum_price': minimum_now,
            },
            'projection_1y': {
                **projection_1y,
                'asking_price': asking_price_1y,
                'minimum_price': minimum_1y,
            },
            'projection_2y': {
                **projection_2y,
                'asking_price': asking_price_2y,
                'minimum_price': minimum_2y,
            },
            'premium_factor': premium,
            'recommendation': recommendation
        }

    def _get_recommendation(self, age, position, projection_1y, current_value, 
                          contract_year, minutes_played, total_available_minutes):
        """Generate recommendation - MORE CONSERVATIVE"""
        curve = self.age_peak_curves.get(position, self.age_peak_curves['Midfielder'])
        peak_age = curve['peak_age']
        
        growth_potential = projection_1y['projected_value'] / current_value
        years_to_contract = contract_year - 2025
        
        # Playing time consideration (percentage-based)
        if total_available_minutes > 0:
            playing_time_pct = minutes_played / total_available_minutes
            playing_time_good = playing_time_pct >= 0.50  # At least 50% of available minutes
        else:
            playing_time_good = True  # No penalty if season hasn't started
        
        # More conservative SELL recommendations
        if age >= peak_age + 1 or years_to_contract <= 1.5 or not playing_time_good:
            reason_parts = []
            if age >= peak_age + 1:
                reason_parts.append(f"age {age} (peak: {peak_age})")
            if years_to_contract <= 1.5:
                reason_parts.append(f"contract expires soon ({contract_year})")
            if not playing_time_good and total_available_minutes > 0:
                reason_parts.append(f"limited playing time ({playing_time_pct*100:.0f}%)")
            
            reasoning = "Sell now: " + ", ".join(reason_parts) + ". Value may decline."
            
            return {
                'action': 'SELL',
                'reasoning': reasoning,
                'color': 'sell'
            }
        
        # More conservative HOLD recommendations
        elif age < peak_age - 2 and growth_potential > 1.15 and years_to_contract >= 3 and playing_time_good:
            if total_available_minutes > 0:
                reasoning = f"Young player ({age}) with strong growth potential (+{(growth_potential-1)*100:.0f}%) and regular playing time ({playing_time_pct*100:.0f}%)."
            else:
                reasoning = f"Young player ({age}) with strong growth potential (+{(growth_potential-1)*100:.0f}%)."
            
            return {
                'action': 'HOLD',
                'reasoning': reasoning,
                'color': 'hold'
            }
        
        # Everything else is CONSIDER
        else:
            if total_available_minutes > 0:
                reasoning = f"At transition point. Evaluate offers carefully. Playing time: {playing_time_pct*100:.0f}% of available minutes."
            else:
                reasoning = f"At transition point. Evaluate offers carefully. Monitor playing time throughout season."
            
            return {
                'action': 'CONSIDER OFFERS',
                'reasoning': reasoning,
                'color': 'consider'
            }


def main():
    st.markdown('<h1 class="main-header">⚽ Player Resale Value Estimator</h1>', unsafe_allow_html=True)
    
    # Initialize session state
    if 'players' not in st.session_state:
        st.session_state.players = []
    
    # Initialize estimator
    estimator = PlayerValueEstimator()
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Home", "Add Players", "Player Analysis", "Squad Overview"])
    
    if page == "Home":
        show_home_page()
    elif page == "Add Players":
        show_add_players_page()
    elif page == "Player Analysis":
        show_player_analysis_page(estimator)
    elif page == "Squad Overview":
        show_squad_overview_page(estimator)


def show_home_page():
    st.markdown("""
    
    ### ✨ Key Features
    - **Percentage-Based Playing Time**: Analyzes playing time as % of available minutes (works at any point in season)
    - **Position-Specific Metrics**: 
        - Goalkeepers: Clean sheets and goals conceded
        - Attackers/Midfielders: Goals and assists
        - Defenders: Excluded from offensive stats
    - **Age trajectory modeling** with position-specific peak ages
    - **Market momentum analysis** based on value history
    - **Premium calculations** for league, age, performance, and contract duration
    - **Smart recommendations** (Hold/Sell/Consider)
    
    ### 🚀 Get Started
    1. **Add Players** - Input your player data
    2. **Player Analysis** - Get individual valuations
    3. **Squad Overview** - See total portfolio value
    
    ---
    
    """)
    
    # Quick stats if players exist
    if st.session_state.players:
        st.markdown("### 📈 Current Squad Statistics")
        total_value = sum(p['current_value'] for p in st.session_state.players)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Squad Value", f"€{total_value:,.0f}M")
        with col2:
            st.metric("Players in Database", len(st.session_state.players))
        with col3:
            avg_age = sum(p['age'] for p in st.session_state.players) / len(st.session_state.players)
            st.metric("Average Age", f"{avg_age:.1f}")


def show_add_players_page():
    st.subheader("➕ Add New Player")
    
    # First, select position outside the form
    st.markdown("### Step 1: Select Position")
    position = st.selectbox("Position*", 
                           ["Attacker", "Midfielder", "Defender", "Goalkeeper"],
                           key="position_selector")
    
    # Show position-specific info
    if position == "Goalkeeper":
        st.info("📊 **Goalkeeper Stats**: You'll enter Clean Sheets and Goals Conceded")
    elif position == "Defender":
        st.warning("⚠️ **Important**: Goals and assists are NOT considered for defenders in valuation")
    else:
        st.info("⚽ **Performance Stats**: You'll enter Goals and Assists")
    
    st.markdown("---")
    st.markdown("### Step 2: Enter Player Details")
    
    with st.form("add_player_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Player Name*", placeholder="e.g., Mohamed Salah")
            age = st.number_input("Age*", min_value=16, max_value=40, value=25)
            league = st.selectbox("Current League*",
                                 ["Premier League", "La Liga", "Bundesliga", "Serie A",
                                  "Ligue 1", "Primeira Liga", "Eredivisie", "Other"])
        
        with col2:
            current_value = st.number_input("Current Market Value (€M)*", 
                                          min_value=0.1, max_value=200.0, 
                                          value=10.0, step=0.5)
            contract_expires = st.number_input("Contract Expires (Year)*", 
                                             min_value=2025, max_value=2035, 
                                             value=2027)
        
        st.markdown("##### ⏱️ Playing Time (Percentage-Based)")
        st.info("💡 **New Feature**: Enter minutes as a percentage of total available minutes. Works at any point in the season!")
        
        col_time1, col_time2 = st.columns(2)
        with col_time1:
            minutes_played = st.number_input("Minutes Played*",
                                           min_value=0, max_value=5000,
                                           value=0,
                                           help="Minutes played this season")
        with col_time2:
            total_available_minutes = st.number_input("Total Available Minutes*",
                                                     min_value=0, max_value=5000,
                                                     value=0,
                                                     help="Total minutes team has played this season (e.g., 10 matches × 90 min = 900 min)")
        
        # Show percentage automatically
        if total_available_minutes > 0:
            playing_pct = (minutes_played / total_available_minutes) * 100
            st.markdown(f"**Playing Time: {playing_pct:.1f}%** of available minutes")
            if playing_pct >= 75:
                st.success("✅ Regular starter")
            elif playing_pct >= 60:
                st.info("ℹ️ Frequent player")
            elif playing_pct >= 40:
                st.warning("⚠️ Squad player")
            elif playing_pct >= 20:
                st.warning("⚠️ Backup")
            else:
                st.error("❌ Limited playing time")
        
        st.markdown("##### Historical Values (Optional but Recommended)")
        st.markdown("*Enter values from previous years for better projections*")
        
        col3, col4, col5 = st.columns(3)
        with col3:
            value_1y_ago = st.number_input("Value 1 Year Ago (€M)", 
                                          min_value=0.0, value=0.0, step=0.5)
        with col4:
            value_2y_ago = st.number_input("Value 2 Years Ago (€M)", 
                                          min_value=0.0, value=0.0, step=0.5)
        with col5:
            value_3y_ago = st.number_input("Value 3 Years Ago (€M)", 
                                          min_value=0.0, value=0.0, step=0.5)
        
        st.markdown("##### Current Season Statistics (Optional)")
        
        # Position-specific stats
        if position == "Goalkeeper":
            st.markdown("**🧤 Goalkeeper Performance Metrics**")
            col6, col7, col8 = st.columns(3)
            with col6:
                clean_sheets = st.number_input("Clean Sheets", min_value=0, value=0,
                                              help="Number of matches without conceding")
            with col7:
                goals_conceded = st.number_input("Goals Conceded", min_value=0, value=0,
                                                help="Total goals conceded this season")
            with col8:
                matches_played = st.number_input("Matches Played", min_value=0, value=0)
            
            goals = 0
            assists = 0
        
        elif position == "Defender":
            st.markdown("**🛡️ Defender Metrics** (Goals/assists not used in valuation)")
            col6, col7 = st.columns(2)
            with col6:
                matches_played = st.number_input("Matches Played", min_value=0, value=0)
            with col7:
                st.write("")
            
            goals = 0
            assists = 0
            clean_sheets = 0
            goals_conceded = 0
        
        else:  # Attacker or Midfielder
            st.markdown(f"**⚽ {position} Performance Metrics**")
            col6, col7, col8 = st.columns(3)
            with col6:
                goals = st.number_input("Goals", min_value=0, value=0,
                                       help="Goals scored this season")
            with col7:
                assists = st.number_input("Assists", min_value=0, value=0,
                                         help="Assists provided this season")
            with col8:
                matches_played = st.number_input("Matches Played", min_value=0, value=0)
            
            clean_sheets = 0
            goals_conceded = 0
        
        submitted = st.form_submit_button("➕ Add Player", use_container_width=True)
        
        if submitted:
            if not name:
                st.error("Please enter player name")
            else:
                # Build value history
                value_history = [current_value]
                if value_1y_ago > 0:
                    value_history.insert(0, value_1y_ago)
                if value_2y_ago > 0:
                    value_history.insert(0, value_2y_ago)
                if value_3y_ago > 0:
                    value_history.insert(0, value_3y_ago)
                
                player_data = {
                    'name': name,
                    'age': age,
                    'position': position,
                    'league': league,
                    'current_value': current_value,
                    'contract_expires': contract_expires,
                    'minutes_played': minutes_played,
                    'total_available_minutes': total_available_minutes,
                    'goals': goals,
                    'assists': assists,
                    'clean_sheets': clean_sheets,
                    'goals_conceded': goals_conceded,
                    'matches_played': matches_played,
                    'value_history': value_history,
                }
                
                st.session_state.players.append(player_data)
                st.success(f"✅ {name} added successfully!")
                st.balloons()
    
    # Show existing players
    if st.session_state.players:
        st.markdown("---")
        st.subheader("Current Squad")
        
        for idx, player in enumerate(st.session_state.players):
            playing_pct = (player['minutes_played'] / player['total_available_minutes'] * 100) if player['total_available_minutes'] > 0 else 0
            
            with st.expander(f"{player['name']} - {player['position']} - €{player['current_value']}M - Playing Time: {playing_pct:.0f}%"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Age:** {player['age']}")
                    st.write(f"**League:** {player['league']}")
                with col2:
                    st.write(f"**Contract:** {player['contract_expires']}")
                    st.write(f"**Minutes:** {player['minutes_played']}/{player['total_available_minutes']}")
                with col3:
                    if player['position'] == 'Goalkeeper':
                        st.write(f"**Clean Sheets:** {player['clean_sheets']}")
                        st.write(f"**Goals Conceded:** {player['goals_conceded']}")
                    elif player['position'] != 'Defender':
                        st.write(f"**Goals:** {player['goals']}")
                        st.write(f"**Assists:** {player['assists']}")
                
                if st.button(f"🗑️ Remove {player['name']}", key=f"remove_{idx}"):
                    st.session_state.players.pop(idx)
                    st.rerun()


def show_player_analysis_page(estimator):
    st.subheader("📊 Individual Player Analysis")
    
    if not st.session_state.players:
        st.warning("No players in database. Please add players first.")
        return
    
    player_names = [p['name'] for p in st.session_state.players]
    selected_name = st.selectbox("Select Player", player_names)
    
    player_data = next(p for p in st.session_state.players if p['name'] == selected_name)
    
    # Run analysis
    analysis = estimator.analyze_player(player_data)
    
    # Display results
    st.markdown("---")
    
    # Header with player info
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Age", player_data['age'])
    with col2:
        st.metric("Position", player_data['position'])
    with col3:
        st.metric("League", player_data['league'])
    with col4:
        if player_data['total_available_minutes'] > 0:
            playing_pct = (player_data['minutes_played'] / player_data['total_available_minutes']) * 100
            st.metric("Playing Time", f"{playing_pct:.1f}%")
        else:
            st.metric("Playing Time", "N/A")
    
    # Current value and recommendation
    st.markdown("### 💰 Current Valuation")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Market Value", f"€{analysis['current']['value']:.1f}M")
    with col2:
        st.metric("Asking Price", f"€{analysis['current']['asking_price']:.1f}M",
                 delta=f"+{((analysis['current']['asking_price']/analysis['current']['value']-1)*100):.0f}%")
    with col3:
        st.metric("Minimum Price", f"€{analysis['current']['minimum_price']:.1f}M")
    
    # Recommendation
    rec = analysis['recommendation']
    rec_class = f"recommendation-{rec['color']}"
    
    st.markdown(f"""
        <div class="{rec_class}">
            <h3>🎯 Recommendation: {rec['action']}</h3>
            <p>{rec['reasoning']}</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Future projections
    st.markdown("### 📈 Value Projections")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 1 Year Projection")
        st.metric("Projected Value", 
                 f"€{analysis['projection_1y']['projected_value']:.1f}M",
                 delta=f"{((analysis['projection_1y']['projected_value']/analysis['current']['value']-1)*100):.0f}%")
        st.write(f"Range: €{analysis['projection_1y']['low_estimate']:.1f}M - €{analysis['projection_1y']['high_estimate']:.1f}M")
        st.metric("Asking Price", f"€{analysis['projection_1y']['asking_price']:.1f}M")
        st.metric("Minimum Price", f"€{analysis['projection_1y']['minimum_price']:.1f}M")
    
    with col2:
        st.markdown("#### 2 Year Projection")
        st.metric("Projected Value", 
                 f"€{analysis['projection_2y']['projected_value']:.1f}M",
                 delta=f"{((analysis['projection_2y']['projected_value']/analysis['current']['value']-1)*100):.0f}%")
        st.write(f"Range: €{analysis['projection_2y']['low_estimate']:.1f}M - €{analysis['projection_2y']['high_estimate']:.1f}M")
        st.metric("Asking Price", f"€{analysis['projection_2y']['asking_price']:.1f}M")
        st.metric("Minimum Price", f"€{analysis['projection_2y']['minimum_price']:.1f}M")
    
    # Factors breakdown
    st.markdown("### 🔍 Analysis Factors")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Age Factor", f"{analysis['projection_2y']['age_factor']:.2f}x")
    with col2:
        st.metric("Momentum Factor", f"{analysis['projection_2y']['momentum_factor']:.2f}x")
    with col3:
        st.metric("Playing Time Factor", f"{analysis['projection_2y']['playing_time_factor']:.2f}x")
    with col4:
        st.metric("Premium Factor", f"{analysis['premium_factor']:.2f}x")
    
    # Value trajectory chart
    st.markdown("### 📊 Value Trajectory")
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    years = [0, 1, 2]
    values = [
        analysis['current']['value'],
        analysis['projection_1y']['projected_value'],
        analysis['projection_2y']['projected_value']
    ]
    asking_prices = [
        analysis['current']['asking_price'],
        analysis['projection_1y']['asking_price'],
        analysis['projection_2y']['asking_price']
    ]
    minimum_prices = [
        analysis['current']['minimum_price'],
        analysis['projection_1y']['minimum_price'],
        analysis['projection_2y']['minimum_price']
    ]
    
    ax.plot(years, values, 'o-', label='Projected Value', linewidth=2, markersize=8)
    ax.plot(years, asking_prices, 's--', label='Asking Price', linewidth=2, markersize=8)
    ax.plot(years, minimum_prices, '^:', label='Minimum Price', linewidth=2, markersize=8)
    
    ax.fill_between(years, 
                    [analysis['current']['value'],
                     analysis['projection_1y']['low_estimate'],
                     analysis['projection_2y']['low_estimate']],
                    [analysis['current']['value'],
                     analysis['projection_1y']['high_estimate'],
                     analysis['projection_2y']['high_estimate']],
                    alpha=0.2, label='Uncertainty Range')
    
    ax.set_xlabel('Years Ahead', fontsize=12)
    ax.set_ylabel('Value (€M)', fontsize=12)
    ax.set_title(f'{selected_name} - Value Projection (Conservative Model)', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    st.pyplot(fig)
    
    # Performance stats section
    st.markdown("### 📋 Performance Statistics")
    if player_data['position'] == 'Goalkeeper':
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Clean Sheets", player_data['clean_sheets'])
        with col2:
            st.metric("Goals Conceded", player_data['goals_conceded'])
        with col3:
            if player_data['matches_played'] > 0:
                cs_ratio = player_data['clean_sheets'] / player_data['matches_played']
                st.metric("Clean Sheet %", f"{cs_ratio*100:.1f}%")
    
    elif player_data['position'] == 'Defender':
        st.info("Defensive performance metrics tracked separately (not affecting valuation with goals/assists)")
        st.metric("Matches Played", player_data['matches_played'])
    
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Goals", player_data['goals'])
        with col2:
            st.metric("Assists", player_data['assists'])
        with col3:
            st.metric("Total Contributions", player_data['goals'] + player_data['assists'])


def show_squad_overview_page(estimator):
    st.subheader("👥 Squad Overview")
    
    if not st.session_state.players:
        st.warning("No players in database. Please add players first.")
        return
    
    # Analyze all players
    analyses = []
    for player in st.session_state.players:
        analysis = estimator.analyze_player(player)
        analyses.append(analysis)
    
    # Summary metrics
    total_current = sum(a['current']['value'] for a in analyses)
    total_asking = sum(a['current']['asking_price'] for a in analyses)
    total_1y = sum(a['projection_1y']['projected_value'] for a in analyses)
    total_2y = sum(a['projection_2y']['projected_value'] for a in analyses)
    
    st.markdown("### 💼 Portfolio Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Squad Value", f"€{total_current:.1f}M")
    with col2:
        st.metric("Total Asking Price", f"€{total_asking:.1f}M")
    with col3:
        st.metric("1Y Projection", f"€{total_1y:.1f}M",
                 delta=f"{((total_1y/total_current-1)*100):.0f}%")
    with col4:
        st.metric("2Y Projection", f"€{total_2y:.1f}M",
                 delta=f"{((total_2y/total_current-1)*100):.0f}%")
    
    # Players table
    st.markdown("### 📋 Squad Comparison")
    
    df_data = []
    for analysis in analyses:
        player = next(p for p in st.session_state.players if p['name'] == analysis['name'])
        playing_pct = (player['minutes_played'] / player['total_available_minutes'] * 100) if player['total_available_minutes'] > 0 else 0
        
        df_data.append({
            'Player': analysis['name'],
            'Age': player['age'],
            'Position': player['position'],
            'Playing Time %': f"{playing_pct:.0f}%",
            'Current Value': f"€{analysis['current']['value']:.1f}M",
            'Asking Price': f"€{analysis['current']['asking_price']:.1f}M",
            '1Y Projection': f"€{analysis['projection_1y']['projected_value']:.1f}M",
            '2Y Projection': f"€{analysis['projection_2y']['projected_value']:.1f}M",
            'Recommendation': analysis['recommendation']['action']
        })
    
    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True)
    
    # Distribution charts
    st.markdown("### 📊 Squad Distribution")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # By position
        position_counts = pd.Series([p['position'] for p in st.session_state.players]).value_counts()
        fig, ax = plt.subplots(figsize=(8, 6))
        position_counts.plot(kind='bar', ax=ax, color='skyblue')
        ax.set_title('Players by Position', fontsize=14, fontweight='bold')
        ax.set_xlabel('Position')
        ax.set_ylabel('Count')
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        st.pyplot(fig)
    
    with col2:
        # By age group
        ages = [p['age'] for p in st.session_state.players]
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.hist(ages, bins=[16, 21, 24, 27, 30, 35, 40], color='lightcoral', edgecolor='black')
        ax.set_title('Age Distribution', fontsize=14, fontweight='bold')
        ax.set_xlabel('Age')
        ax.set_ylabel('Count')
        ax.grid(True, alpha=0.3)
        st.pyplot(fig)
    
    # Recommendations summary
    st.markdown("### 🎯 Transfer Strategy Recommendations")
    
    recommendations = {}
    for analysis in analyses:
        action = analysis['recommendation']['action']
        if action not in recommendations:
            recommendations[action] = []
        recommendations[action].append(analysis['name'])
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if 'SELL' in recommendations:
            st.markdown('<div class="recommendation-sell">', unsafe_allow_html=True)
            st.markdown("#### 🔴 Recommend SELL")
            for name in recommendations['SELL']:
                st.write(f"• {name}")
            st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        if 'CONSIDER OFFERS' in recommendations:
            st.markdown('<div class="recommendation-consider">', unsafe_allow_html=True)
            st.markdown("#### 🟡 CONSIDER OFFERS")
            for name in recommendations['CONSIDER OFFERS']:
                st.write(f"• {name}")
            st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        if 'HOLD' in recommendations:
            st.markdown('<div class="recommendation-hold">', unsafe_allow_html=True)
            st.markdown("#### 🟢 Recommend HOLD")
            for name in recommendations['HOLD']:
                st.write(f"• {name}")
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Export functionality
    st.markdown("### 💾 Export Data")
    
    if st.button("📥 Download Squad Analysis (Excel)"):
        # Create Excel file
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Squad Overview', index=False)
            
            # Detailed sheet
            detailed_data = []
            for analysis in analyses:
                player = next(p for p in st.session_state.players if p['name'] == analysis['name'])
                playing_pct = (player['minutes_played'] / player['total_available_minutes'] * 100) if player['total_available_minutes'] > 0 else 0
                
                detailed_data.append({
                    'Player': analysis['name'],
                    'Age': player['age'],
                    'Position': player['position'],
                    'League': player['league'],
                    'Minutes Played': player['minutes_played'],
                    'Total Available Minutes': player['total_available_minutes'],
                    'Playing Time %': playing_pct,
                    'Current Value': analysis['current']['value'],
                    'Current Asking': analysis['current']['asking_price'],
                    'Current Minimum': analysis['current']['minimum_price'],
                    '1Y Projected': analysis['projection_1y']['projected_value'],
                    '1Y Asking': analysis['projection_1y']['asking_price'],
                    '1Y Minimum': analysis['projection_1y']['minimum_price'],
                    '2Y Projected': analysis['projection_2y']['projected_value'],
                    '2Y Asking': analysis['projection_2y']['asking_price'],
                    '2Y Minimum': analysis['projection_2y']['minimum_price'],
                    'Age Factor': analysis['projection_2y']['age_factor'],
                    'Momentum Factor': analysis['projection_2y']['momentum_factor'],
                    'Playing Time Factor': analysis['projection_2y']['playing_time_factor'],
                    'Premium Factor': analysis['premium_factor'],
                    'Recommendation': analysis['recommendation']['action'],
                    'Reasoning': analysis['recommendation']['reasoning']
                })
            
            pd.DataFrame(detailed_data).to_excel(writer, sheet_name='Detailed Analysis', index=False)
        
        output.seek(0)
        st.download_button(
            label="📥 Download Excel File",
            data=output,
            file_name=f"squad_analysis_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


if __name__ == "__main__":
    main()
