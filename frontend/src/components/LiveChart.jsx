import React, { useEffect, useRef, useState } from 'react';
import { createChart } from 'lightweight-charts';

const LiveChart = ({ currentPrice }) => {
  const chartContainerRef = useRef();
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const [data, setData] = useState([]);

  useEffect(() => {
    chartRef.current = createChart(chartContainerRef.current, {
      layout: {
        background: { type: 'solid', color: 'transparent' },
        textColor: '#8F9BB3',
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: true,
      },
      crosshair: {
        mode: 0,
      },
      rightPriceScale: {
        borderColor: 'rgba(255, 255, 255, 0.1)',
      },
    });

    seriesRef.current = chartRef.current.addLineSeries({
      color: '#3366FF',
      lineWidth: 2,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 6,
      crosshairMarkerBorderColor: '#fff',
      crosshairMarkerBackgroundColor: '#3366FF',
      lineType: 0, 
    });

    return () => {
      chartRef.current.remove();
    };
  }, []);

  useEffect(() => {
    if (seriesRef.current && currentPrice) {
      const timestamp = Math.floor(Date.now() / 1000);
      try {
        const newDataPoint = { time: timestamp, value: currentPrice };
        // We only use update. 
        // Important: in a real environment, you pass history items first with .setData,
        // then append with .update. Here we just continuously update.
        seriesRef.current.update(newDataPoint);
      } catch (e) {
        // Ignored. lightweight-charts requires strictly increasing timestamps
      }
    }
  }, [currentPrice]);

  return (
    <div 
      ref={chartContainerRef} 
      style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }} 
    />
  );
};

export default LiveChart;
