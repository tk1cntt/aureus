"use client";

import { useEffect, useRef, useState, useCallback } from 'react';
import { createChart, ColorType, IChartApi, ISeriesApi, CandlestickSeries, LineSeries, createSeriesMarkers } from 'lightweight-charts';
import { Settings } from 'lucide-react';

interface BacktestChartProps {
    candles: any[];
    signalEvents: any[];
    trades: any[];
    equityCurve: any[];
    swingPoints?: any[];
    obs?: any[];
    digits?: number;
    onEventHover?: (event: any | null) => void;
}

// Color map for different signal event types
const SIGNAL_COLORS: Record<string, { color: string; shape: string; label: string }> = {
    'CHOCH_UP': { color: '#00E676', shape: 'arrowUp', label: 'CHoCH↑' },
    'CHOCH_DOWN': { color: '#FF1744', shape: 'arrowDown', label: 'CHoCH↓' },
    'BOS_UP': { color: '#00BCD4', shape: 'arrowUp', label: 'BOS↑' },
    'BOS_DOWN': { color: '#FF9100', shape: 'arrowDown', label: 'BOS↓' },
    'SWEEP_BULL': { color: '#76FF03', shape: 'circle', label: '🎯' },
    'SWEEP_BEAR': { color: '#F44336', shape: 'circle', label: '🎯' },
    'EMA_CROSS_UP': { color: '#4FC3F7', shape: 'arrowUp', label: 'EMA↑' },
    'EMA_CROSS_DOWN': { color: '#EF5350', shape: 'arrowDown', label: 'EMA↓' },
};

function getSignalStyle(tag: string) {
    for (const [key, style] of Object.entries(SIGNAL_COLORS)) {
        if (tag.toUpperCase().includes(key)) return style;
    }
    return { color: '#9E9E9E', shape: 'circle' as any, label: '•' };
}

// Deduplication helper (from SMCChart)
function dedupeAndSort(items: any[]) {
    if (items.length === 0) return [];
    const sorted = [...items].sort((a, b) => a.time - b.time);
    const unique = [];
    let seenT = -1;
    for (const item of sorted) {
        if (item.time == null || isNaN(item.time)) continue;
        if (item.time > seenT) {
            unique.push(item);
            seenT = item.time;
        }
    }
    return unique;
}

export default function BacktestChart({
    candles,
    signalEvents,
    trades,
    equityCurve,
    swingPoints = [],
    obs = [],
    digits = 2,
    onEventHover,
}: BacktestChartProps) {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const equityContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const equityChartRef = useRef<IChartApi | null>(null);
    const [hoveredEvent, setHoveredEvent] = useState<any | null>(null);
    const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

    // Chart display settings (matching SMCChart)
    const [settings, setSettings] = useState({
        showZigzag: true,
        showOB: true,
        showCHOCH: true,
        showLabels: true,
    });
    const [showSettings, setShowSettings] = useState(false);

    // Main chart
    useEffect(() => {
        if (!chartContainerRef.current || !candles.length) return;

        const container = chartContainerRef.current;

        const chart = createChart(container, {
            layout: {
                background: { type: ColorType.Solid, color: '#0B0E11' },
                textColor: '#D9D9D9',
            },
            grid: {
                vertLines: { color: '#1E222D' },
                horzLines: { color: '#1E222D' },
            },
            rightPriceScale: {
                scaleMargins: { top: 0.15, bottom: 0.15 },
                borderColor: '#2B2F3A',
            },
            timeScale: {
                borderColor: '#2B2F3A',
                timeVisible: true,
                secondsVisible: false,
                rightOffset: 10,
                barSpacing: 6,
            },
            crosshair: {
                mode: 0,
                vertLine: { color: '#555', width: 1, style: 2 },
                horzLine: { color: '#555', width: 1, style: 2 },
            },
            width: container.clientWidth,
            height: container.clientHeight,
        });

        chartRef.current = chart;

        const priceFormat = {
            type: 'price' as const,
            precision: digits,
            minMove: Math.pow(10, -digits),
        };

        // 1. Candlestick series
        const candleSeries = chart.addSeries(CandlestickSeries, {
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderVisible: false,
            wickUpColor: '#26a69a',
            wickDownColor: '#ef5350',
            priceFormat,
        });

        candleSeries.setData(candles);

        // 2. ZigZag line (from SMCChart logic)
        let zigzagSeries: ISeriesApi<"Line"> | null = null;
        if (settings.showZigzag && swingPoints.length > 0) {
            zigzagSeries = chart.addSeries(LineSeries, {
                color: '#2962FF',
                lineWidth: 1,
                crosshairMarkerVisible: false,
                lineType: 0,
                priceLineVisible: false,
                lastValueVisible: false,
                priceFormat,
            });

            const firstCandleTime = candles[0].time;
            const lastCandleTime = candles[candles.length - 1].time;
            const sortedPoints = [...swingPoints].sort((a: any, b: any) => a.t - b.t);
            const zigzagItems: any[] = [];

            sortedPoints.forEach((p: any) => {
                const t = p.t;
                if (t < firstCandleTime || t > lastCandleTime) return;
                zigzagItems.push({ time: t, value: p.price });
            });

            // Connect to last candle
            if (zigzagItems.length > 0) {
                const latestCandle = candles[candles.length - 1];
                if (latestCandle.time > zigzagItems[zigzagItems.length - 1].time) {
                    zigzagItems.push({ time: latestCandle.time, value: latestCandle.close });
                }
            }

            zigzagSeries.setData(dedupeAndSort(zigzagItems));
        }

        // 3. HH/LL Markers + CHOCH lines (from SMCChart logic)
        const markers: any[] = [];
        const chochSeriesPool: ISeriesApi<"Line">[] = [];

        if (swingPoints.length > 0) {
            const firstCandleTime = candles[0].time;
            const lastCandleTime = candles[candles.length - 1].time;
            const sortedPoints = [...swingPoints].sort((a: any, b: any) => a.t - b.t);

            sortedPoints.forEach((p: any) => {
                const t = p.t;
                if (t < firstCandleTime || t > lastCandleTime) return;

                // HH/LL Markers
                if (settings.showLabels) {
                    markers.push({
                        time: t,
                        position: p.is_high ? 'aboveBar' : 'belowBar',
                        color: p.is_high ? '#FFFF00' : '#00FFFF',
                        shape: p.is_high ? 'arrowDown' : 'arrowUp',
                        text: p.type,
                        size: 2,
                    });
                }

                // CHOCH dotted lines
                if (p.is_choch && p.breakout_t && settings.showCHOCH) {
                    const b_t = p.breakout_t;
                    if (b_t >= firstCandleTime && b_t <= lastCandleTime) {
                        const chochSeries = chart.addSeries(LineSeries, {
                            color: p.choch_type === 'Up' ? '#00E676' : p.choch_type === 'Down' ? '#FF5252' : '#FFD700',
                            lineWidth: 1,
                            lineStyle: 2, // Dotted
                            crosshairMarkerVisible: false,
                            priceLineVisible: false,
                            lastValueVisible: false,
                        });
                        chochSeries.setData([
                            { time: t, value: p.price },
                            { time: b_t, value: p.price }
                        ]);
                        chochSeriesPool.push(chochSeries);
                    }
                }
            });
        }

        // 4. Signal event markers
        for (const evt of signalEvents) {
            const tag = evt.tag || '';
            const style = getSignalStyle(tag);
            markers.push({
                time: evt.time,
                position: style.shape === 'arrowDown' ? 'aboveBar' : 'belowBar',
                color: style.color,
                shape: style.shape === 'arrowUp' ? 'arrowUp' : style.shape === 'arrowDown' ? 'arrowDown' : 'circle',
                text: style.label,
                size: 1,
            });
        }

        // 5. Trade entry/exit markers
        for (const trade of trades) {
            markers.push({
                time: trade.entry_time,
                position: trade.side === 'BUY' ? 'belowBar' : 'aboveBar',
                color: trade.side === 'BUY' ? '#00E5FF' : '#FF6D00',
                shape: trade.side === 'BUY' ? 'arrowUp' : 'arrowDown',
                text: `${trade.side} ${trade.entry_price.toFixed(digits)}`,
                size: 2,
            });

            if (trade.exit_time && trade.status === 'CLOSED') {
                const isWin = trade.pnl > 0;
                markers.push({
                    time: trade.exit_time,
                    position: trade.side === 'BUY' ? 'aboveBar' : 'belowBar',
                    color: isWin ? '#00E676' : '#FF1744',
                    shape: 'square',
                    text: `${trade.exit_reason || 'EXIT'} ${isWin ? '+' : ''}${trade.pnl.toFixed(digits)}`,
                    size: 2,
                });
            }
        }

        // Sort and set all markers
        createSeriesMarkers(candleSeries, dedupeAndSort(markers));

        // 6. Order Block boxes (from SMCChart logic)
        const obSeriesPool: ISeriesApi<"Candlestick">[] = [];
        if (settings.showOB && obs.length > 0) {
            obs.forEach((ob: any) => {
                const isFreshBullish = ob.ob_type === 'BULLISH' && !ob.mitigated;
                const isFreshBearish = ob.ob_type === 'BEARISH' && !ob.mitigated;

                let finalColor = 'rgba(150, 150, 150, 0.2)'; // Mitigated: grey
                if (isFreshBullish) finalColor = 'rgba(0, 255, 0, 0.3)';
                else if (isFreshBearish) finalColor = 'rgba(255, 0, 0, 0.3)';

                const endTime = ob.mitigated ? ob.t_mitigation : (ob.capped_time || candles[candles.length - 1].time);
                const startTime = ob.t_start;

                const obCandleData: any[] = [];
                candles.forEach((c: any) => {
                    if (c.time >= startTime && c.time <= endTime) {
                        obCandleData.push({
                            time: c.time,
                            open: ob.top,
                            high: ob.top,
                            low: ob.bottom,
                            close: ob.bottom,
                        });
                    }
                });

                if (obCandleData.length > 0) {
                    const series = chart.addSeries(CandlestickSeries, {
                        upColor: finalColor,
                        downColor: finalColor,
                        borderVisible: true,
                        wickVisible: false,
                        borderColor: ob.mitigated ? 'rgba(150, 150, 150, 0.4)' : finalColor,
                        priceLineVisible: false,
                        lastValueVisible: false,
                    });
                    series.setData(obCandleData);
                    obSeriesPool.push(series);
                }
            });
        }

        // 7. SL/TP lines for trades
        for (const trade of trades) {
            if (trade.entry_time && trade.sl && trade.tp) {
                const endTime = trade.exit_time || candles[candles.length - 1]?.time || trade.entry_time + 3600;

                const slSeries = chart.addSeries(LineSeries, {
                    color: '#FF1744',
                    lineWidth: 1,
                    lineStyle: 2,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });
                slSeries.setData([
                    { time: trade.entry_time, value: trade.sl },
                    { time: endTime, value: trade.sl },
                ]);

                const tpSeries = chart.addSeries(LineSeries, {
                    color: '#00E676',
                    lineWidth: 1,
                    lineStyle: 2,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });
                tpSeries.setData([
                    { time: trade.entry_time, value: trade.tp },
                    { time: endTime, value: trade.tp },
                ]);
            }
        }

        // 8. Crosshair move for tooltip
        chart.subscribeCrosshairMove((param) => {
            if (!param.time || !param.point) {
                setHoveredEvent(null);
                onEventHover?.(null);
                return;
            }

            const time = param.time as number;
            const nearby = signalEvents.find(e => Math.abs(e.time - time) < 120);
            if (nearby) {
                setHoveredEvent(nearby);
                setTooltipPos({ x: param.point.x, y: param.point.y });
                onEventHover?.(nearby);
            } else {
                setHoveredEvent(null);
                onEventHover?.(null);
            }
        });

        // Fit content
        chart.timeScale().fitContent();

        // Resize handler
        const handleResize = () => {
            if (container && chart) {
                chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
            }
        };
        const resizeObserver = new ResizeObserver(handleResize);
        resizeObserver.observe(container);

        return () => {
            resizeObserver.disconnect();
            chart.remove();
        };
    }, [candles, signalEvents, trades, swingPoints, obs, digits, settings]);

    // Equity curve chart
    useEffect(() => {
        if (!equityContainerRef.current || !equityCurve.length) return;

        const container = equityContainerRef.current;
        const chart = createChart(container, {
            layout: {
                background: { type: ColorType.Solid, color: '#0B0E11' },
                textColor: '#D9D9D9',
            },
            grid: {
                vertLines: { color: '#1E222D' },
                horzLines: { color: '#1E222D' },
            },
            rightPriceScale: {
                borderColor: '#2B2F3A',
            },
            timeScale: {
                borderColor: '#2B2F3A',
                timeVisible: true,
            },
            width: container.clientWidth,
            height: container.clientHeight,
        });

        equityChartRef.current = chart;

        const areaSeries = chart.addSeries(LineSeries, {
            color: '#3b82f6',
            lineWidth: 2,
            priceFormat: { type: 'price', precision: 4 },
        });

        areaSeries.setData(equityCurve.map(p => ({
            time: p.time,
            value: p.value,
        })));

        chart.timeScale().fitContent();

        const handleResize = () => {
            chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
        };
        const resizeObserver = new ResizeObserver(handleResize);
        resizeObserver.observe(container);

        return () => {
            resizeObserver.disconnect();
            chart.remove();
        };
    }, [equityCurve]);

    return (
        <div className="space-y-4">
            {/* Main Chart */}
            <div className="relative bg-[#0B0E11] rounded-xl border border-gray-800 overflow-hidden" style={{ height: '500px' }}>
                {/* Settings Toggle */}
                <div className="absolute top-3 right-3 z-30">
                    <button
                        onClick={() => setShowSettings(!showSettings)}
                        className="p-1.5 rounded-md bg-gray-800/60 hover:bg-gray-700/80 transition-colors"
                        title="Chart Settings"
                    >
                        <Settings className="h-3.5 w-3.5 text-gray-400" />
                    </button>

                    {showSettings && (
                        <div className="absolute right-0 mt-1 bg-[#1E222D] border border-gray-700 rounded-lg p-3 shadow-2xl min-w-[180px] space-y-2">
                            {([
                                { key: 'showZigzag', label: 'ZigZag Line' },
                                { key: 'showOB', label: 'Order Blocks' },
                                { key: 'showCHOCH', label: 'CHOCH Lines' },
                                { key: 'showLabels', label: 'HH/LL Labels' },
                            ] as const).map(({ key, label }) => (
                                <label key={key} className="flex items-center space-x-2 cursor-pointer text-xs text-gray-300 hover:text-white">
                                    <input
                                        type="checkbox"
                                        checked={settings[key]}
                                        onChange={(e) => setSettings(prev => ({ ...prev, [key]: e.target.checked }))}
                                        className="rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500/20"
                                    />
                                    <span>{label}</span>
                                </label>
                            ))}
                        </div>
                    )}
                </div>

                <div ref={chartContainerRef} className="w-full h-full" />

                {/* Signal Event Tooltip */}
                {hoveredEvent && (
                    <div
                        className="absolute z-50 pointer-events-none bg-[#1E222D]/95 backdrop-blur-sm border border-gray-700 rounded-lg p-3 shadow-2xl max-w-xs"
                        style={{
                            left: Math.min(tooltipPos.x + 16, (chartContainerRef.current?.clientWidth || 600) - 250),
                            top: Math.max(tooltipPos.y - 60, 0),
                        }}
                    >
                        <div className="text-xs font-bold text-blue-400 mb-1">
                            {hoveredEvent.tag}
                        </div>
                        <div className="text-[10px] text-gray-400 mb-2">
                            {new Date(hoveredEvent.time * 1000).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' })}
                        </div>
                        {hoveredEvent.price && (
                            <div className="text-xs text-gray-300">
                                Price: <span className="font-mono text-white">{Number(hoveredEvent.price).toFixed(digits)}</span>
                            </div>
                        )}
                        {hoveredEvent.direction && (
                            <div className="text-xs text-gray-300">
                                Direction: <span className={`font-bold ${hoveredEvent.direction === 'BULLISH' ? 'text-green-400' : 'text-red-400'}`}>
                                    {hoveredEvent.direction}
                                </span>
                            </div>
                        )}
                        {hoveredEvent.ob_type && (
                            <div className="text-xs text-gray-300">
                                OB: <span className="font-mono text-yellow-400">{hoveredEvent.ob_type}</span>
                            </div>
                        )}
                        {Object.entries(hoveredEvent).filter(([k]) => !['tag', 'time', 'price', 'direction', 'ob_type'].includes(k)).map(([k, v]) => (
                            <div key={k} className="text-[10px] text-gray-500">
                                {k}: <span className="text-gray-400 font-mono">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Equity Curve */}
            {equityCurve.length > 0 && (
                <div className="bg-[#1E222D] rounded-xl border border-gray-800 overflow-hidden p-4">
                    <div className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">
                        Equity Curve
                    </div>
                    <div ref={equityContainerRef} style={{ height: '160px' }} />
                </div>
            )}
        </div>
    );
}
