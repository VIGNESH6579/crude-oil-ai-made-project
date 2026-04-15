import React, { useState, useEffect, useRef } from 'react';
import LiveChart from './components/LiveChart';
import SignalCard from './components/SignalCard';

function App() {
  const [marketData, setMarketData] = useState({
    price: 6500.0,
    volume: 0,
    bid_qty: 100,
    ask_qty: 100
  });

  const [signalData, setSignalData] = useState({
    status: 'WAITING',
    action: 'NEUTRAL',
    confidence: 0,
    imbalance: 0,
    suggested_strike: null,
    target: null,
    stop_loss: null
  });

  const [connectionStatus, setConnectionStatus] = useState('Connecting...');
  
  const wsRef = useRef(null);

  useEffect(() => {
    // Connect to Python FastAPI WebSocket
    const connectWs = () => {
      // In production, this would be an env variable
      wsRef.current = new WebSocket('wss://crude-oil-ai-made-project.onrender.com/ws/market-data');

      wsRef.current.onopen = () => {
        setConnectionStatus('Live Server Connected');
      };

      wsRef.current.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.tick) {
          setMarketData(payload.tick);
        }
        if (payload.signal) {
          setSignalData(payload.signal);
        }
      };

      wsRef.current.onerror = () => {
        setConnectionStatus('Connection Error');
      };

      wsRef.current.onclose = () => {
        setConnectionStatus('Disconnected - Retrying...');
        setTimeout(connectWs, 3000);
      };
    };

    connectWs();

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  return (
    <div className="dashboard-container">
      <header className="header animate-slide-in">
        <h1 className="app-title">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
          </svg>
          Nexus Options Terminal
        </h1>
        <div className="live-badge">
          {connectionStatus}
        </div>
      </header>

      <main className="chart-section animate-slide-in" style={{animationDelay: '0.1s'}}>
        <div className="panel" style={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
          <div className="price-display">
            <div>
              <div className="price-sub">MCX CRUDEOIL</div>
              <div className={`current-price ${marketData.price > 6500 ? 'up' : 'down'}`}>
                ₹{marketData.price.toFixed(2)}
              </div>
            </div>
          </div>
          
          <div style={{ flexGrow: 1, marginTop: '20px', position: 'relative' }}>
            <LiveChart currentPrice={marketData.price} />
          </div>
        </div>
      </main>

      <aside className="signal-section animate-slide-in" style={{animationDelay: '0.2s'}}>
        <SignalCard signalData={signalData} marketData={marketData} />
      </aside>
    </div>
  );
}

export default App;
