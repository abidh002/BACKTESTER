import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings
from datetime import datetime, timedelta
import io

warnings.filterwarnings("ignore")

# Page config
st.set_page_config(
    page_title="Stock & Futures Backtester",
    page_icon="📈",
    layout="wide"
)

# ============================================
# STRATEGY FUNCTIONS
# ============================================

def backtest_stock(prices, initial_inr=10000, add_inr=10000, drop_pct=2.0, profit_pct=5.0):
    trades = []
    equity = []
    realized_pnl = 0.0
    position_cost = 0.0
    position_shares = 0.0
    last_buy_price = None
    in_position = False

    for date, price in prices.items():
        if pd.isna(price) or price <= 0:
            continue
            
        if not in_position:
            shares = initial_inr / price
            position_shares = shares
            position_cost = initial_inr
            last_buy_price = price
            in_position = True
            trades.append({
                "date": date,
                "action": "BUY_INIT",
                "price": round(price, 2),
                "shares": round(shares, 4),
                "cost": initial_inr
            })
        else:
            drop = ((last_buy_price - price) / last_buy_price) * 100
            if drop >= drop_pct:
                add_shares = add_inr / price
                position_shares += add_shares
                position_cost += add_inr
                last_buy_price = price
                trades.append({
                    "date": date,
                    "action": "BUY_ADD",
                    "price": round(price, 2),
                    "shares": round(add_shares, 4),
                    "cost": add_inr
                })
            
            if position_shares > 0:
                avg_price = position_cost / position_shares
                if price >= avg_price * (1 + profit_pct / 100):
                    proceeds = price * position_shares
                    pnl = proceeds - position_cost
                    realized_pnl += pnl
                    trades.append({
                        "date": date,
                        "action": "SELL_ALL",
                        "price": round(price, 2),
                        "shares": round(position_shares, 4),
                        "pnl": round(pnl, 2)
                    })
                    in_position = False
                    position_cost = 0
                    position_shares = 0
                    last_buy_price = None
        
        unrealized = position_shares * price if in_position else 0
        equity.append(realized_pnl + unrealized)
    
    return pd.DataFrame(trades), pd.Series(equity, index=prices.index)


def backtest_futures(prices, initial_lots=1, add_lot_every_drop=2.0, profit_pct=5.0, lot_value=1.0):
    trades = []
    equity = []
    realized_pnl = 0.0
    total_cost = 0.0
    lots = 0
    last_buy_price = None
    in_position = False

    for date, price in prices.items():
        if pd.isna(price) or price <= 0:
            continue
            
        if not in_position:
            lots = initial_lots
            total_cost = lots * price * lot_value
            last_buy_price = price
            in_position = True
            trades.append({
                "date": date,
                "action": "BUY_INIT",
                "price": round(price, 2),
                "lots": lots,
                "cost": round(total_cost, 2)
            })
        else:
            drop = ((last_buy_price - price) / last_buy_price) * 100
            if drop >= add_lot_every_drop:
                lots += 1
                additional_cost = price * lot_value
                total_cost += additional_cost
                last_buy_price = price
                trades.append({
                    "date": date,
                    "action": "BUY_ADD",
                    "price": round(price, 2),
                    "lots": lots,
                    "cost": round(additional_cost, 2)
                })
            
            if lots > 0:
                avg_price = total_cost / (lots * lot_value)
                if price >= avg_price * (1 + profit_pct / 100):
                    proceeds = lots * price * lot_value
                    pnl = proceeds - total_cost
                    realized_pnl += pnl
                    trades.append({
                        "date": date,
                        "action": "SELL_ALL",
                        "price": round(price, 2),
                        "lots": lots,
                        "pnl": round(pnl, 2)
                    })
                    lots = 0
                    total_cost = 0
                    in_position = False
                    last_buy_price = None
        
        unrealized = lots * price * lot_value if in_position else 0
        equity.append(realized_pnl + unrealized)
    
    return pd.DataFrame(trades), pd.Series(equity, index=prices.index)


# ============================================
# STREAMLIT APP
# ============================================

st.title("📈 Universal Stock & Futures Backtester")
st.markdown("Test your buy-the-dip strategy on any Yahoo Finance ticker worldwide!")

# Sidebar inputs
st.sidebar.header("⚙️ Strategy Parameters")

ticker = st.sidebar.text_input("Ticker Symbol", value="RELIANCE.NS", 
                               help="e.g., AAPL, TSLA, RELIANCE.NS, BTC-USD, GC=F")

mode = st.sidebar.selectbox("Trading Mode", ["Stock", "Futures"])

col1, col2 = st.sidebar.columns(2)
with col1:
    start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=365))
with col2:
    end_date = st.date_input("End Date", value=datetime.now())

st.sidebar.markdown("---")
st.sidebar.subheader("💰 Strategy Settings")

initial_amount = st.sidebar.number_input("Initial Investment", value=10000, min_value=100, step=500)
add_amount = st.sidebar.number_input("Add on Dip (Stocks)", value=10000, min_value=100, step=500)
drop_pct = st.sidebar.slider("Drop % to Buy More", min_value=0.5, max_value=10.0, value=2.0, step=0.5)
profit_pct = st.sidebar.slider("Profit % to Sell", min_value=1.0, max_value=20.0, value=5.0, step=0.5)

run_backtest = st.sidebar.button("🚀 Run Backtest", type="primary", use_container_width=True)

# Popular tickers
st.sidebar.markdown("---")
st.sidebar.markdown("**📌 Popular Tickers:**")
st.sidebar.markdown("""
- **Indian**: RELIANCE.NS, TCS.NS, INFY.NS
- **US**: AAPL, TSLA, MSFT, GOOGL
- **Crypto**: BTC-USD, ETH-USD
- **Futures**: GC=F (Gold), CL=F (Oil)
- **Indices**: ^NSEI (Nifty), ^GSPC (S&P 500)
""")

# Main content
if run_backtest:
    with st.spinner(f"Fetching data for {ticker}..."):
        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            
            if df.empty:
                st.error("❌ No data found. Please check the ticker symbol and date range.")
                st.stop()
            
            prices = df["Close"].dropna()
            st.success(f"✅ Downloaded {len(prices)} data points")
            
            # Run backtest
            if mode == "Stock":
                trades, equity = backtest_stock(
                    prices, initial_amount, add_amount, drop_pct, profit_pct
                )
            else:
                trades, equity = backtest_futures(
                    prices, 1, drop_pct, profit_pct, 1.0
                )
            
            # Display results
            st.markdown("---")
            st.header("📊 Results")
            
            # Metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                final_equity = equity.iloc[-1]
                st.metric("Final Equity", f"₹{final_equity:,.2f}")
            
            with col2:
                total_return = ((final_equity - initial_amount) / initial_amount * 100)
                st.metric("Total Return", f"{total_return:.2f}%")
            
            with col3:
                st.metric("Total Trades", len(trades))
            
            with col4:
                if 'pnl' in trades.columns:
                    completed = trades[trades['pnl'].notna()]
                    if not completed.empty:
                        wins = len(completed[completed['pnl'] > 0])
                        win_rate = (wins / len(completed)) * 100
                        st.metric("Win Rate", f"{win_rate:.1f}%")
            
            # Charts
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📈 Price Chart with Signals")
                fig1, ax1 = plt.subplots(figsize=(10, 6))
                ax1.plot(prices.index, prices.values, label='Price', linewidth=1.5, alpha=0.7)
                
                if not trades.empty:
                    buys = trades[trades['action'].str.contains('BUY')]
                    sells = trades[trades['action'] == 'SELL_ALL']
                    
                    if not buys.empty:
                        ax1.scatter(buys['date'], buys['price'], color='green', 
                                   marker='^', s=100, label='Buy', zorder=5)
                    if not sells.empty:
                        ax1.scatter(sells['date'], sells['price'], color='red', 
                                   marker='v', s=100, label='Sell', zorder=5)
                
                ax1.set_xlabel('Date')
                ax1.set_ylabel('Price')
                ax1.legend()
                ax1.grid(True, alpha=0.3)
                st.pyplot(fig1)
            
            with col2:
                st.subheader("💰 Equity Curve")
                fig2, ax2 = plt.subplots(figsize=(10, 6))
                ax2.plot(equity.index, equity.values, linewidth=2, color='blue')
                ax2.fill_between(equity.index, equity.values, alpha=0.3)
                ax2.set_xlabel('Date')
                ax2.set_ylabel('Equity')
                ax2.grid(True, alpha=0.3)
                st.pyplot(fig2)
            
            # Trades table
            st.markdown("---")
            st.subheader("📋 Trade History")
            st.dataframe(trades, use_container_width=True)
            
            # Download buttons
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                # Excel download
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Price_Data')
                    trades.to_excel(writer, sheet_name='Trades', index=False)
                    pd.DataFrame({'Equity': equity}).to_excel(writer, sheet_name='Equity')
                
                st.download_button(
                    label="📥 Download Excel Report",
                    data=output.getvalue(),
                    file_name=f"{ticker.replace('.', '_')}_backtest.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            with col2:
                # CSV download
                csv = trades.to_csv(index=False)
                st.download_button(
                    label="📥 Download Trades CSV",
                    data=csv,
                    file_name=f"{ticker.replace('.', '_')}_trades.csv",
                    mime="text/csv"
                )
            
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.exception(e)

else:
    # Welcome screen
    st.info("👈 Configure your strategy in the sidebar and click 'Run Backtest'")
    
    st.markdown("---")
    st.markdown("""
    ### 🎯 How It Works
    
    **Buy-the-Dip Strategy:**
    1. **Initial Buy**: Start with your initial investment
    2. **Add on Dips**: When price drops by X%, add more capital
    3. **Take Profits**: When profit reaches Y%, sell everything
    4. **Repeat**: Start over with a new position
    
    ### 📚 Supported Markets
    - **Indian Stocks**: Add `.NS` or `.BO` (e.g., RELIANCE.NS)
    - **US Stocks**: Use ticker directly (e.g., AAPL)
    - **Crypto**: Add `-USD` (e.g., BTC-USD)
    - **Futures**: Add `=F` (e.g., GC=F for Gold)
    - **Indices**: Add `^` prefix (e.g., ^NSEI)
    
    ### ⚠️ Disclaimer
    This is for educational purposes only. Past performance does not guarantee future results.
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    Made with ❤️ using Streamlit | Data from Yahoo Finance
</div>
""", unsafe_allow_html=True)
