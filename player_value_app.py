import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import io

# Page configuration
st.set_page_config(
    page_title="Player Value Estimator",
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
        self.age_peak_curves = {
            'Attacker': {'peak_age': 27, 'decline_rate': 0.08},
            'Midfielder': {'peak_age': 28, 'decline_rate': 0.07},
            'Defender': {'peak_age': 29, 'decline_rate': 0.06},
            'Goalkeeper': {'peak_age': 31, 'decline_rate': 0.05}
        }
        
    def calculate_age_factor(self, current_age, position, years_ahead=2):
        """Calculate value multiplier based on age curve"""
        curve = self.age_peak_curves.get(position, self.age_peak_curves['Midfielder'])
        peak_age = curve['peak_age']
        decline_rate = curve['decline_rate']
        
        future_age = current_age + years_ahead
        
        if current_age < peak_age:
            if future_age <= peak_age:
                years_to_grow = years_ahead
                growth_rate = 0.15
                return (1 + growth_rate) ** years_to_grow
            else:
                years_to_peak = peak_age - current_age
                years_past_peak = future_age - peak_age
                growth_factor = (1 + 0.15) ** years_to_peak
                decline_factor = (1 - decline_rate) ** years_past_peak
                return growth_factor * decline_factor
        else:
            years_past_peak = future_age - peak_age
            return (1 - decline_rate) ** years_past_peak
    
    def calculate_momentum_factor(self, value_history):
        """Calculate momentum based on recent value changes"""
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
        
        if weighted_growth > 0.3:
            return 1.5
        elif weighted_growth > 0.2:
            return 1.35
        elif weighted_growth > 0.1:
            return 1.2
        elif weighted_growth > 0:
            return 1.1
        elif weighted_growth > -0.1:
            return 1.0
        else:
            return 0.85
    
    def calculate_premium_factor(self, player_data):
        """Calculate premium factors for asking price"""
        premium = 1.0
        
        # League premium
        top_tier_1 = ['Premier League']
        top_tier_2 = ['La Liga', 'Bundesliga', 'Serie A']
        top_tier_3 = ['Ligue 1', 'Primeira Liga', 'Eredivisie']
        
        league = str(player_data.get('league', '')).strip()
        
        if league in top_tier_1:
            premium += 0.15
        elif league in top_tier_2:
            premium += 0.12
        elif league in top_tier_3:
            premium += 0.08
        else:
            premium += 0.02
        
        # Age premium
        age = player_data.get('age', 25)
        if age < 23:
            premium += 0.25
        elif age < 25:
            premium += 0.15
        elif age < 27:
            premium += 0.05
        
        # Performance premium
        try:
            goals = float(player_data.get('goals', 0))
            assists = float(player_data.get('assists', 0))
            total_contributions = goals + assists
            
            if total_contributions > 20:
                premium += 0.20
            elif total_contributions > 10:
                premium += 0.12
            elif total_contributions > 5:
                premium += 0.06
        except (ValueError, TypeError):
            pass
        
        # Contract premium
        try:
            contract_year = int(player_data.get('contract_expires', 2025))
            current_year = 2025
            years_remaining = contract_year - current_year
            
            if years_remaining >= 4:
                premium += 0.15
            elif years_remaining >= 3:
                premium += 0.10
            elif years_remaining >= 2:
                premium += 0.05
        except (ValueError, TypeError):
            pass
        
        return premium

    def estimate_future_value(self, current_value, age, position, value_history, years_ahead=2):
        """Estimate player value in future years"""
        age_factor = self.calculate_age_factor(age, position, years_ahead)
        momentum_factor = self.calculate_momentum_factor(value_history)
        
        base_projection = current_value * age_factor * momentum_factor
        
        uncertainty = 0.15 + (0.05 * years_ahead)
        low_estimate = base_projection * (1 - uncertainty)
        high_estimate = base_projection * (1 + uncertainty * 1.5)
        
        return {
            'projected_value': base_projection,
            'low_estimate': low_estimate,
            'high_estimate': high_estimate,
            'age_factor': age_factor,
            'momentum_factor': momentum_factor
        }

    def analyze_player(self, player_data):
        """Complete analysis for a single player"""
        name = player_data['name']
        age = int(player_data['age'])
        position = player_data['position']
        current_value = float(player_data['current_value'])
        value_history = player_data['value_history']
        
        # Get projections
        projection_1y = self.estimate_future_value(current_value, age, position, value_history, 1)
        projection_2y = self.estimate_future_value(current_value, age, position, value_history, 2)
        
        # Calculate premium
        premium = self.calculate_premium_factor(player_data)
        
        # Recommended asking prices
        asking_price_now = current_value * premium * 1.2
        asking_price_1y = projection_1y['projected_value'] * premium
        asking_price_2y = projection_2y['projected_value'] * premium
        
        minimum_now = asking_price_now * 0.85
        minimum_2y = asking_price_2y * 0.85
        
        return {
            'name': name,
            'age': age,
            'position': position,
            'current_value': current_value,
            'projection_1y': projection_1y,
            'projection_2y': projection_2y,
            'premium_factor': premium,
            'asking_price_now': asking_price_now,
            'asking_price_1y': asking_price_1y,
            'asking_price_2y': asking_price_2y,
            'minimum_now': minimum_now,
            'minimum_2y': minimum_2y,
            'value_history': value_history,
            'player_data': player_data
        }


def get_recommendation(analysis):
    """Generate recommendation for each player"""
    momentum = analysis['projection_2y']['momentum_factor']
    age_factor = analysis['projection_2y']['age_factor']
    age = analysis['age']
    
    if momentum > 1.3 and age < 24:
        return ("HOLD", "High potential, value rising rapidly", "hold")
    elif momentum > 1.15 and age_factor > 1.1:
        return ("HOLD", "Good momentum and age trajectory", "hold")
    elif age > 30 and momentum < 1.0:
        return ("SELL NOW", "Declining value window", "sell")
    elif momentum < 0.9:
        return ("SELL NOW", "Negative momentum", "sell")
    elif age >= 27 and age <= 29 and momentum > 1.0:
        return ("CONSIDER OFFERS", "At peak value", "consider")
    else:
        return ("EVALUATE", "Monitor performance", "consider")


def plot_player_projection(analysis):
    """Create value projection chart for a player"""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Historical values
    history = analysis['value_history']
    years_history = list(range(-len(history) + 1, 1))
    
    ax.plot(years_history, history, 'o-', linewidth=3, markersize=10, 
           label='Historical Value', color='#2E86AB', alpha=0.8)
    
    # Future projections
    future_years = [0, 1, 2]
    future_values = [
        analysis['current_value'],
        analysis['projection_1y']['projected_value'],
        analysis['projection_2y']['projected_value']
    ]
    
    ax.plot(future_years, future_values, 's--', linewidth=3, markersize=10,
           label='Projected Value', color='#A23B72', alpha=0.8)
    
    # Asking prices
    asking_prices = [
        analysis['asking_price_now'],
        analysis['asking_price_1y'],
        analysis['asking_price_2y']
    ]
    
    ax.plot(future_years, asking_prices, '^-', linewidth=2.5, markersize=9,
           label='Our Asking Price', color='#F18F01', alpha=0.9)
    
    # Uncertainty band for 2Y
    proj_2y = analysis['projection_2y']
    ax.fill_between([1.5, 2], 
                    [proj_2y['low_estimate'], proj_2y['low_estimate']], 
                    [proj_2y['high_estimate'], proj_2y['high_estimate']], 
                    alpha=0.2, color='#A23B72', label='Value Range')
    
    # Current market value line
    ax.axhline(y=analysis['current_value'], color='gray', 
              linestyle=':', alpha=0.5, linewidth=2)
    
    ax.set_xlabel('Years (0 = Present)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Value (€M)', fontsize=12, fontweight='bold')
    ax.set_title(f"{analysis['name']} - Value Projection", 
                fontsize=14, fontweight='bold', pad=20)
    
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='best', fontsize=10, framealpha=0.9)
    
    plt.tight_layout()
    return fig


def create_comparison_table(analyses):
    """Create comparison table for all players"""
    rows = []
    for analysis in analyses:
        rec_action, rec_reason, rec_type = get_recommendation(analysis)
        rows.append({
            'Player': analysis['name'],
            'Age': analysis['age'],
            'Position': analysis['position'],
            'Current Value (€M)': f"€{analysis['current_value']:.1f}m",
            'Asking Price (€M)': f"€{analysis['asking_price_now']:.1f}m",
            'Projected 2Y (€M)': f"€{analysis['projection_2y']['projected_value']:.1f}m",
            'Momentum': f"{analysis['projection_2y']['momentum_factor']:.2f}x",
            'Recommendation': rec_action
        })
    return pd.DataFrame(rows)


# Initialize session state
if 'players' not in st.session_state:
    st.session_state.players = []
if 'estimator' not in st.session_state:
    st.session_state.estimator = PlayerValueEstimator()


# Main App
st.markdown('<h1 class="main-header">⚽ Player Resale Value Estimator 💰</h1>', unsafe_allow_html=True)

# Sidebar for navigation
with st.sidebar:
    st.header("📋 Navigation")
    page = st.radio("Go to", ["Add Players", "Player Analysis", "Squad Overview", "User Guide"])
    
    st.markdown("---")
    st.markdown("### 📊 Quick Stats")
    if st.session_state.players:
        st.metric("Total Players", len(st.session_state.players))
        avg_value = np.mean([p['current_value'] for p in st.session_state.players])
        st.metric("Avg Market Value", f"€{avg_value:.1f}m")


# PAGE 1: Add Players
if page == "Add Players":
    st.header("➕ Add Player Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Basic Information")
        player_name = st.text_input("Player Name", key="player_name")
        player_age = st.number_input("Age", min_value=16, max_value=40, value=22, key="player_age")
        player_position = st.selectbox("Position", 
                                      ["Attacker", "Midfielder", "Defender", "Goalkeeper"],
                                      key="player_position")
        current_value = st.number_input("Current Market Value (€M)", 
                                       min_value=0.1, max_value=300.0, value=25.0, step=0.5,
                                       key="current_value")
    
    with col2:
        st.subheader("Historical Values (€M)")
        value_3y = st.number_input("Value 3 Years Ago", min_value=0.0, value=0.0, step=0.5,
                                   key="value_3y", help="Leave 0 if not available")
        value_2y = st.number_input("Value 2 Years Ago", min_value=0.0, value=0.0, step=0.5,
                                   key="value_2y")
        value_1y = st.number_input("Value 1 Year Ago", min_value=0.0, value=0.0, step=0.5,
                                   key="value_1y")
    
    col3, col4 = st.columns(2)
    
    with col3:
        st.subheader("Additional Details")
        league = st.selectbox("League", 
                             ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1",
                              "Primeira Liga", "Eredivisie", "Other"],
                             key="league")
        contract_expires = st.number_input("Contract Expires (Year)", 
                                          min_value=2025, max_value=2035, value=2027,
                                          key="contract")
    
    with col4:
        st.subheader("Performance (This Season)")
        goals = st.number_input("Goals", min_value=0, max_value=100, value=0, key="goals")
        assists = st.number_input("Assists", min_value=0, max_value=100, value=0, key="assists")
        status = st.selectbox("Status", 
                             ["Rising Star", "Established", "Peak", "Declining", "Unknown"],
                             key="status")
    
    st.markdown("---")
    
    col_add, col_clear = st.columns([1, 4])
    
    with col_add:
        if st.button("➕ Add Player", type="primary", use_container_width=True):
            if player_name:
                # Build value history
                value_history = []
                if value_3y > 0:
                    value_history.append(value_3y)
                if value_2y > 0:
                    value_history.append(value_2y)
                if value_1y > 0:
                    value_history.append(value_1y)
                value_history.append(current_value)
                
                player_data = {
                    'name': player_name,
                    'age': player_age,
                    'position': player_position,
                    'current_value': current_value,
                    'value_history': value_history,
                    'league': league,
                    'contract_expires': contract_expires,
                    'goals': goals,
                    'assists': assists,
                    'status': status
                }
                
                st.session_state.players.append(player_data)
                st.success(f"✅ Added {player_name} to the squad!")
                st.balloons()
            else:
                st.error("⚠️ Please enter a player name!")
    
    with col_clear:
        if st.button("🗑️ Clear All Players", use_container_width=True):
            st.session_state.players = []
            st.success("All players cleared!")
    
    # Display current squad
    if st.session_state.players:
        st.markdown("---")
        st.subheader("📋 Current Squad")
        
        for idx, player in enumerate(st.session_state.players):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{player['name']}** - {player['age']} years, {player['position']}, €{player['current_value']}m")
            with col2:
                st.write(f"{player['league']}")
            with col3:
                if st.button("🗑️", key=f"delete_{idx}"):
                    st.session_state.players.pop(idx)
                    st.rerun()


# PAGE 2: Player Analysis
elif page == "Player Analysis":
    st.header("📊 Individual Player Analysis")
    
    if not st.session_state.players:
        st.warning("⚠️ No players added yet! Go to 'Add Players' to add your squad.")
    else:
        # Player selector
        player_names = [p['name'] for p in st.session_state.players]
        selected_player_name = st.selectbox("Select Player", player_names)
        
        # Find selected player
        selected_player = next((p for p in st.session_state.players if p['name'] == selected_player_name), None)
        
        if selected_player:
            # Analyze player
            analysis = st.session_state.estimator.analyze_player(selected_player)
            rec_action, rec_reason, rec_type = get_recommendation(analysis)
            
            # Display player info header
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Age", f"{analysis['age']} years")
            with col2:
                st.metric("Position", analysis['position'])
            with col3:
                st.metric("League", selected_player.get('league', 'N/A'))
            with col4:
                st.metric("Status", selected_player.get('status', 'Unknown'))
            
            st.markdown("---")
            
            # Key metrics
            st.subheader("💰 Valuation Summary")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Current Market Value",
                    f"€{analysis['current_value']:.1f}m",
                    help="Current Transfermarkt value"
                )
            
            with col2:
                st.metric(
                    "Our Asking Price (Now)",
                    f"€{analysis['asking_price_now']:.1f}m",
                    delta=f"+{((analysis['asking_price_now']/analysis['current_value']-1)*100):.0f}%",
                    help="Recommended asking price for immediate sale"
                )
            
            with col3:
                st.metric(
                    "Projected Value (2Y)",
                    f"€{analysis['projection_2y']['projected_value']:.1f}m",
                    delta=f"+{((analysis['projection_2y']['projected_value']/analysis['current_value']-1)*100):.0f}%",
                    help="Estimated value in 2 years"
                )
            
            with col4:
                st.metric(
                    "Asking Price (2Y)",
                    f"€{analysis['asking_price_2y']:.1f}m",
                    delta=f"+{((analysis['asking_price_2y']/analysis['current_value']-1)*100):.0f}%",
                    help="Recommended asking price if sold in 2 years"
                )
            
            st.markdown("---")
            
            # Value projection chart
            st.subheader("📈 Value Projection")
            fig = plot_player_projection(analysis)
            st.pyplot(fig)
            
            st.markdown("---")
            
            # Detailed Analysis
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🔍 Analysis Factors")
                
                st.markdown("**Age Trajectory**")
                age_factor = analysis['projection_2y']['age_factor']
                if age_factor > 1.1:
                    st.success(f"📈 Growing: {age_factor:.2f}x multiplier")
                    st.write(f"Player is {analysis['age']} years old, still developing toward peak age")
                elif age_factor > 0.95:
                    st.info(f"➡️ Stable: {age_factor:.2f}x multiplier")
                    st.write(f"Player at or near peak age for {analysis['position']}")
                else:
                    st.warning(f"📉 Declining: {age_factor:.2f}x multiplier")
                    st.write(f"Player past peak age, value declining")
                
                st.markdown("**Momentum Factor**")
                momentum = analysis['projection_2y']['momentum_factor']
                if momentum > 1.2:
                    st.success(f"🚀 Strong Growth: {momentum:.2f}x multiplier")
                    st.write("Recent value growth is exceptional")
                elif momentum > 1.0:
                    st.info(f"📊 Positive: {momentum:.2f}x multiplier")
                    st.write("Value growing steadily")
                else:
                    st.error(f"📉 Negative: {momentum:.2f}x multiplier")
                    st.write("Value declining or stagnant")
                
                st.markdown("**Premium Factor**")
                premium = analysis['premium_factor']
                st.info(f"⭐ {premium:.2f}x multiplier")
                st.write(f"Based on league quality, age, performance, and contract")
            
            with col2:
                st.subheader("💡 Recommendation")
                
                if rec_type == "hold":
                    st.markdown(f"""
                    <div class="recommendation-hold">
                        <h3>🟢 {rec_action}</h3>
                        <p><strong>Reason:</strong> {rec_reason}</p>
                    </div>
                    """, unsafe_allow_html=True)
                elif rec_type == "sell":
                    st.markdown(f"""
                    <div class="recommendation-sell">
                        <h3>🔴 {rec_action}</h3>
                        <p><strong>Reason:</strong> {rec_reason}</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="recommendation-consider">
                        <h3>🟡 {rec_action}</h3>
                        <p><strong>Reason:</strong> {rec_reason}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("---")
                
                st.markdown("**Pricing Strategy**")
                st.write(f"**Asking Price (Now):** €{analysis['asking_price_now']:.1f}m")
                st.write(f"**Minimum Acceptable:** €{analysis['minimum_now']:.1f}m")
                st.write(f"**Target Range:** €{analysis['minimum_now']:.1f}m - €{analysis['asking_price_now']:.1f}m")
                
                st.markdown("**Future Pricing (2 Years)**")
                st.write(f"**Asking Price:** €{analysis['asking_price_2y']:.1f}m")
                st.write(f"**Minimum Acceptable:** €{analysis['minimum_2y']:.1f}m")
                
                # Potential gain/loss
                potential_change = ((analysis['asking_price_2y'] / analysis['asking_price_now']) - 1) * 100
                if potential_change > 0:
                    st.success(f"📈 Potential gain if held: +{potential_change:.1f}%")
                else:
                    st.error(f"📉 Potential loss if held: {potential_change:.1f}%")
            
            st.markdown("---")
            
            # Value history table
            st.subheader("📊 Value History")
            history_data = []
            value_history = analysis['value_history']
            
            if len(value_history) > 3:
                history_data.append(["3 Years Ago", f"€{value_history[0]:.1f}m"])
                history_data.append(["2 Years Ago", f"€{value_history[1]:.1f}m"])
                history_data.append(["1 Year Ago", f"€{value_history[2]:.1f}m"])
            elif len(value_history) > 2:
                history_data.append(["2 Years Ago", f"€{value_history[0]:.1f}m"])
                history_data.append(["1 Year Ago", f"€{value_history[1]:.1f}m"])
            elif len(value_history) > 1:
                history_data.append(["1 Year Ago", f"€{value_history[0]:.1f}m"])
            
            history_data.append(["Current", f"€{analysis['current_value']:.1f}m"])
            history_data.append(["Projected (1Y)", f"€{analysis['projection_1y']['projected_value']:.1f}m"])
            history_data.append(["Projected (2Y)", f"€{analysis['projection_2y']['projected_value']:.1f}m"])
            
            df_history = pd.DataFrame(history_data, columns=["Period", "Value"])
            st.table(df_history)


# PAGE 3: Squad Overview
elif page == "Squad Overview":
    st.header("🏆 Squad Overview")
    
    if not st.session_state.players:
        st.warning("⚠️ No players added yet! Go to 'Add Players' to add your squad.")
    else:
        # Analyze all players
        analyses = []
        for player in st.session_state.players:
            analysis = st.session_state.estimator.analyze_player(player)
            analyses.append(analysis)
        
        # Summary metrics
        st.subheader("📊 Squad Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        
        total_current_value = sum([a['current_value'] for a in analyses])
        total_asking_price = sum([a['asking_price_now'] for a in analyses])
        total_projected_2y = sum([a['projection_2y']['projected_value'] for a in analyses])
        avg_age = np.mean([a['age'] for a in analyses])
        
        with col1:
            st.metric("Total Squad Value", f"€{total_current_value:.1f}m")
        with col2:
            st.metric("Total Asking Price", f"€{total_asking_price:.1f}m",
                     delta=f"+{((total_asking_price/total_current_value-1)*100):.0f}%")
        with col3:
            st.metric("Projected Value (2Y)", f"€{total_projected_2y:.1f}m",
                     delta=f"+{((total_projected_2y/total_current_value-1)*100):.0f}%")
        with col4:
            st.metric("Average Age", f"{avg_age:.1f} years")
        
        st.markdown("---")
        
        # Comparison table
        st.subheader("📋 All Players Comparison")
        df_comparison = create_comparison_table(analyses)
        
        # Color code recommendations
        def highlight_recommendation(val):
            if 'HOLD' in str(val):
                return 'background-color: #d4edda'
            elif 'SELL' in str(val):
                return 'background-color: #f8d7da'
            elif 'CONSIDER' in str(val):
                return 'background-color: #fff3cd'
            return ''
        
        styled_df = df_comparison.style.applymap(highlight_recommendation, subset=['Recommendation'])
        st.dataframe(styled_df, use_container_width=True)
        
        st.markdown("---")
        
        # Squad breakdown charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Squad by Position")
            position_counts = pd.Series([a['position'] for a in analyses]).value_counts()
            fig, ax = plt.subplots(figsize=(8, 6))
            position_counts.plot(kind='bar', ax=ax, color='steelblue')
            ax.set_xlabel("Position", fontweight='bold')
            ax.set_ylabel("Number of Players", fontweight='bold')
            ax.set_title("Squad Distribution by Position", fontweight='bold')
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig)
        
        with col2:
            st.subheader("Squad by Age Group")
            age_groups = []
            for a in analyses:
                if a['age'] < 23:
                    age_groups.append("Under 23")
                elif a['age'] < 27:
                    age_groups.append("23-26")
                elif a['age'] < 30:
                    age_groups.append("27-29")
                else:
                    age_groups.append("30+")
            
            age_counts = pd.Series(age_groups).value_counts()
            fig, ax = plt.subplots(figsize=(8, 6))
            age_counts.plot(kind='bar', ax=ax, color='coral')
            ax.set_xlabel("Age Group", fontweight='bold')
            ax.set_ylabel("Number of Players", fontweight='bold')
            ax.set_title("Squad Distribution by Age", fontweight='bold')
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig)
        
        st.markdown("---")
        
        # Recommendations summary
        st.subheader("💡 Transfer Strategy Recommendations")
        
        hold_players = []
        sell_players = []
        consider_players = []
        
        for analysis in analyses:
            rec_action, rec_reason, rec_type = get_recommendation(analysis)
            if rec_type == "hold":
                hold_players.append(analysis['name'])
            elif rec_type == "sell":
                sell_players.append(analysis['name'])
            else:
                consider_players.append(analysis['name'])
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**🟢 HOLD**")
            if hold_players:
                for player in hold_players:
                    st.write(f"• {player}")
            else:
                st.write("None")
        
        with col2:
            st.markdown("**🔴 SELL NOW**")
            if sell_players:
                for player in sell_players:
                    st.write(f"• {player}")
            else:
                st.write("None")
        
        with col3:
            st.markdown("**🟡 CONSIDER OFFERS**")
            if consider_players:
                for player in consider_players:
                    st.write(f"• {player}")
            else:
                st.write("None")
        
        st.markdown("---")
        
        # Export functionality
        st.subheader("📥 Export Data")
        
        if st.button("Download Squad Analysis (Excel)", type="primary"):
            # Create Excel file in memory
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_comparison.to_excel(writer, sheet_name='Squad Overview', index=False)
                
                # Detailed sheet
                detailed_data = []
                for analysis in analyses:
                    rec_action, rec_reason, rec_type = get_recommendation(analysis)
                    detailed_data.append({
                        'Player': analysis['name'],
                        'Age': analysis['age'],
                        'Position': analysis['position'],
                        'Current Value (€M)': analysis['current_value'],
                        'Asking Price Now (€M)': analysis['asking_price_now'],
                        'Minimum Now (€M)': analysis['minimum_now'],
                        'Projected 1Y (€M)': analysis['projection_1y']['projected_value'],
                        'Projected 2Y (€M)': analysis['projection_2y']['projected_value'],
                        'Asking Price 2Y (€M)': analysis['asking_price_2y'],
                        'Minimum 2Y (€M)': analysis['minimum_2y'],
                        'Momentum': analysis['projection_2y']['momentum_factor'],
                        'Age Factor': analysis['projection_2y']['age_factor'],
                        'Premium': analysis['premium_factor'],
                        'Recommendation': rec_action,
                        'Reason': rec_reason
                    })
                
                df_detailed = pd.DataFrame(detailed_data)
                df_detailed.to_excel(writer, sheet_name='Detailed Analysis', index=False)
            
            output.seek(0)
            st.download_button(
                label="📥 Download Excel File",
                data=output,
                file_name=f"squad_analysis_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )


# PAGE 4: User Guide
else:
    st.header("📖 User Guide")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Quick Start", "Methodology", "How to Use", "Tips & Tricks"])
    
    with tab1:
        st.subheader("🚀 Quick Start Guide")
        
        st.markdown("""
        ### Getting Started in 3 Steps
        
        #### 1️⃣ Add Your Players
        - Go to the **Add Players** page
        - Enter player information from Transfermarkt
        - Include historical values for better accuracy
        - Add performance stats (goals/assists)
        
        #### 2️⃣ Analyze Individual Players
        - Go to **Player Analysis** page
        - Select a player from dropdown
        - View detailed valuation, projections, and charts
        - Get specific recommendations
        
        #### 3️⃣ Review Squad Overview
        - Go to **Squad Overview** page
        - Compare all players side-by-side
        - See squad distribution and strategies
        - Export analysis to Excel
        
        ### 💡 Pro Tips
        - Enter at least 2-3 years of historical values for best projections
        - Update player data regularly (monthly)
        - Re-run analysis before each transfer window
        - Use the Excel export for negotiation meetings
        """)
    
    with tab2:
        st.subheader("🔬 Methodology")
        
        st.markdown("""
        ### How We Calculate Value
        
        #### 1. Age-Based Trajectory
        Each position has a peak age:
        - **Attackers:** Peak at 27 years
        - **Midfielders:** Peak at 28 years
        - **Defenders:** Peak at 29 years
        - **Goalkeepers:** Peak at 31 years
        
        Before peak: Value grows ~15% per year  
        After peak: Value declines at position-specific rates
        
        #### 2. Momentum Factor
        Analyzes value changes over past 2-3 years:
        - **Strong growth (+30%):** 1.4-1.5x multiplier 🚀
        - **Moderate growth (+15%):** 1.2-1.35x multiplier 📈
        - **Stable (0-5%):** 1.0x multiplier ➡️
        - **Declining (-10%+):** 0.85-0.9x multiplier 📉
        
        #### 3. Premium Factors
        
        **League Quality:**
        - Premier League: +15%
        - La Liga, Bundesliga, Serie A: +12%
        - Ligue 1, Eredivisie: +8%
        - Other leagues: +2%
        
        **Age & Potential:**
        - Under 23: +25% (high potential)
        - 23-25: +15% (development)
        - 25-27: +5% (entering peak)
        
        **Performance:**
        - 20+ goals+assists: +20%
        - 10-20: +12%
        - 5-10: +6%
        
        **Contract Length:**
        - 4+ years: +15%
        - 3 years: +10%
        - 2 years: +5%
        - 1 year: -20%
        
        #### 4. Final Calculation
        ```
        Projected Value = Current Value × Age Factor × Momentum
        Premium Factor = 1.0 + (all premiums)
        Asking Price = Projected Value × Premium × 1.2
        Minimum Price = Asking Price × 0.85
        ```
        """)
    
    with tab3:
        st.subheader("📚 How to Use This Tool")
        
        st.markdown("""
        ### Step-by-Step Instructions
        
        #### Adding Players
        1. Navigate to **Add Players** page
        2. Fill in basic information (name, age, position)
        3. Enter current market value from Transfermarkt
        4. **Important:** Add historical values for accuracy
           - Go to player's Transfermarkt page
           - Click "Data & Facts" tab
           - Note values from 1-3 years ago
        5. Add contract expiration date
        6. Enter current season stats (optional but recommended)
        7. Click "Add Player"
        
        #### Analyzing Individual Players
        1. Go to **Player Analysis** page
        2. Select player from dropdown
        3. Review:
           - Current value vs. asking price
           - Value projection chart
           - Age trajectory and momentum analysis
           - Specific recommendation (Hold/Sell/Consider)
           - Pricing strategy with minimum acceptable
        
        #### Squad Overview
        1. Go to **Squad Overview** page
        2. View:
           - Total squad value and projections
           - Comparison table of all players
           - Squad distribution by position and age
           - Transfer strategy recommendations
        3. Click "Download Squad Analysis" to export Excel
        
        #### Best Practices
        - **Update regularly:** Refresh data monthly during season
        - **Use real data:** Get values from Transfermarkt.com
        - **Include history:** More historical data = better projections
        - **Track performance:** Update goals/assists regularly
        - **Export before negotiations:** Use Excel report in meetings
        
        #### Data Sources
        - **Market Values:** www.transfermarkt.com
        - **Transfer Fees:** www.transfermarkt.com/transfers
        - **Contract Info:** Player profiles on Transfermarkt
        - **Performance Stats:** League official websites or Transfermarkt
        """)
    
    with tab4:
        st.subheader("💡 Tips & Negotiation Strategies")
        
        st.markdown("""
        ### Transfer Strategy Tips
        
        #### When to SELL NOW 🔴
        - Player is 29+ and at peak value
        - Contract expires within 18 months
        - Negative momentum (value declining)
        - Multiple good offers received
        - Player wants to leave
        
        **Example:** 30-year-old with €40m offer, contract ending 2026
        → **Action:** Sell - peak value window closing
        
        #### When to HOLD 🟢
        - Player under 24 with rising value
        - Long contract (3+ years remaining)
        - Strong positive momentum (+20%+ growth)
        - Key to team success
        - Offers below minimum acceptable
        
        **Example:** 21-year-old worth €25m, growing 50%/year
        → **Action:** Hold - potential for €60m+ in 2 years
        
        #### When to CONSIDER OFFERS 🟡
        - Player at peak age (26-29)
        - Good form but stable value
        - Strong offers from top clubs (1.3x+ market value)
        - Contract has 2-3 years
        - Team has good replacement options
        
        **Example:** 27-year-old worth €45m, offer of €55m
        → **Action:** Consider - at peak, premium offer received
        
        ### Negotiation Guidelines
        
        #### Setting Your Prices
        1. **Start with asking price** (not minimum)
        2. **First offer sets anchor** - go high
        3. **Never go below minimum** unless emergency
        4. **Create negotiating room** - expect 10-15% reduction
        
        #### Negotiation Timeline
        ```
        Week 1-2: Market player, communicate asking price
        Week 3-4: Serious negotiations begin
        Week 5-6: Counter-offers, move toward middle  
        Week 7-8: Final decision, accept or reject
        ```
        
        #### Justifying Your Price
        ✅ Show value projection charts from this tool  
        ✅ Reference similar transfers (use Transfermarkt)  
        ✅ Highlight age trajectory and momentum  
        ✅ Emphasize contract length  
        ✅ Point to recent performance stats  
        ✅ Mention other interested clubs (if true)  
        
        #### Common Buyer Arguments & Your Responses
        
        **"That's too expensive!"**
        → *"Based on age trajectory and recent performance, he'll be worth even more in 2 years. Our price reflects future potential."*
        
        **"Market value is only €Xm"**
        → *"Market value is a reference, but doesn't account for contract length, proven performance in our league, and increasing trajectory."*
        
        **"Other clubs aren't paying that much"**
        → *"Here are 3 comparable transfers where similar players went for similar or higher fees..."* (show Transfermarkt data)
        
        **"He's not worth it"**
        → *"Let's look at the data..."* (show your charts and analysis)
        
        ### Red Flags - Be Careful! 🚩
        
        ❌ **Contract <18 months:** Must discount 20-30%  
        ❌ **Injury prone:** Reduce asking by 20-30%  
        ❌ **Disciplinary issues:** Reduce by 10-20%  
        ❌ **Only 1 good season:** Reduce momentum factor  
        ❌ **Player forcing move:** Lose negotiating leverage  
        
        ### Market Timing
        
        **Best time to sell:**
        - ✅ After strong performances
        - ✅ Early in transfer window (more time)
        - ✅ Before major tournaments (speculation premium)
        - ✅ When multiple clubs interested
        
        **Worst time to sell:**
        - ❌ Last days of window (pressure)
        - ❌ After injuries or poor form
        - ❌ When player publicly wants to leave
        - ❌ When contract <6 months
        
        ### Creating Competition
        
        1. **Mention interest** (only if true) from other clubs
        2. **Set deadlines** for offers
        3. **Don't show desperation** even if you want to sell
        4. **Let clubs compete** by leaking controlled info
        5. **Have backup plan** - be ready to keep player
        
        ### Final Price Range Guide
        
        ```
        Your Asking Price:          100% ████████████
        Strong Offer (90-95%):       95% ███████████   ✅ Consider
        Good Offer (85-90%):         88% ██████████    ✅ Negotiate
        Your Minimum (85%):          85% █████████     🟡 Floor
        Fair Offer (75-85%):         80% ████████      ⚠️ Below minimum
        Low Offer (70-75%):          73% ███████       ❌ Reject
        Insulting (<70%):            60% ██████        ❌ Ignore
        ```
        
        ### Remember
        - These are **estimates**, not guarantees
        - **Market conditions** vary
        - **Club needs** affect prices
        - **Player desire** impacts leverage
        - **Timing matters** enormously
        
        Use this tool as a starting point, but always combine with:
        - Your scouting assessment
        - Team's financial needs
        - Squad planning requirements
        - Market intelligence
        """)

# Footer
st.markdown("---")
st.markdown("""
    <div style='text-align: center; color: #666; padding: 2rem;'>
        <p>⚽ Player Resale Value Estimator | Built with Streamlit</p>
        <p>Data-driven transfer valuations for smart negotiations</p>
    </div>
""", unsafe_allow_html=True)