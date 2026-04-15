import React from 'react';
import { Target, Shield, AlertTriangle, Activity } from 'lucide-react';

const SignalCard = ({ signalData, marketData }) => {
  const { action, confidence, target, stop_loss, suggested_strike, imbalance, status } = signalData;

  const isBuy = action === 'BUY';
  const isSell = action === 'SELL';
  
  const getBadgeClass = () => {
    if (isBuy) return 'buy';
    if (isSell) return 'sell';
    return 'neutral';
  };

  const calculateBuyWidth = () => {
    const total = marketData.bid_qty + marketData.ask_qty || 1;
    return `${(marketData.bid_qty / total) * 100}%`;
  };

  const calculateSellWidth = () => {
    const total = marketData.bid_qty + marketData.ask_qty || 1;
    return `${(marketData.ask_qty / total) * 100}%`;
  };

  return (
    <div className="panel signal-card">
      <div className="signal-header">
        <h3 style={{fontFamily: 'Outfit'}}>AI Signal Engine</h3>
        <div className={`signal-badge ${getBadgeClass()}`}>
          {action}
        </div>
      </div>

      {status === 'WARMUP' ? (
        <div className="strike-suggestion" style={{ background: 'rgba(255,255,255,0.05)', color: '#8F9BB3', borderColor: 'transparent' }}>
          <Activity size={20} className="animate-spin" />
          Analyzing Tick Data...
        </div>
      ) : (
        <>
          <div className="strike-suggestion">
            Suggest Trade: 
            <span>{suggested_strike || 'WAIT & WATCH'}</span>
          </div>

          <div className="stats-grid">
            <div className="stat-box">
              <div className="stat-label">
                <Target size={14} style={{display:'inline', marginRight: '5px', verticalAlign: 'text-bottom'}}/> 
                Target
              </div>
              <div className="stat-value">{target || '-'}</div>
            </div>
            
            <div className="stat-box">
              <div className="stat-label">
                <Shield size={14} style={{display:'inline', marginRight: '5px', verticalAlign: 'text-bottom'}}/>
                Stop Loss
              </div>
              <div className="stat-value" style={{color: 'var(--accent-red)'}}>{stop_loss || '-'}</div>
            </div>
            
            <div className="stat-box">
              <div className="stat-label">Confidence</div>
              <div className="stat-value">
                {confidence > 0 ? `${(confidence * 100).toFixed(1)}%` : '-'}
              </div>
            </div>
            
            <div className="stat-box">
              <div className="stat-label">Imbalance</div>
              <div className="stat-value">
                {imbalance !== undefined ? imbalance.toFixed(2) : '-'}
              </div>
            </div>
          </div>
        </>
      )}

      <div style={{marginTop: '1.5rem'}}>
        <div className="stat-label" style={{display: 'flex', justifyContent: 'space-between'}}>
          <span>Order Book Pressure</span>
          <span style={{fontSize: '0.7rem'}}>Live Bids vs Asks</span>
        </div>
        <div className="order-book-bar">
          <div className="buy-volume" style={{width: calculateBuyWidth()}}></div>
          <div className="sell-volume" style={{width: calculateSellWidth()}}></div>
        </div>
        <div style={{display: 'flex', justifyContent: 'space-between', marginTop: '5px', fontSize: '0.75rem', color: 'var(--text-muted)'}}>
          <span>Bid: {marketData.bid_qty}</span>
          <span>Ask: {marketData.ask_qty}</span>
        </div>
      </div>
    </div>
  );
};

export default SignalCard;
