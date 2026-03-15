"use client";

import { useEffect, useRef, useCallback, useState } from 'react';
import { createChart, ColorType, ISeriesApi, IChartApi, CandlestickSeries, LineSeries, createSeriesMarkers } from 'lightweight-charts';
import { Target, Settings } from 'lucide-react';

interface SMCChartProps {
    symbol: string;
    data: any[];
    smcState: any;
    colors?: {
        backgroundColor?: string;
        lineColor?: string;
        textColor?: string;
    };
    chartType?: "candles" | "line";
    settings?: {
        lineColor: string;
        zigzagColor: string;
        bullishOBColor: string;
        bearishOBColor: string;
        showLabels: boolean;
        showZigzag: boolean;
        showOB: boolean;
        showCHOCH: boolean;
        visibleBars: number;
    };
    precision?: number;
}

export const SMCChart = ({
    symbol,
    data,
    smcState,
    chartType = "candles",
    colors: {
        backgroundColor = '#0B0E11',
        lineColor = '#2962FF',
        textColor = '#D9D9D9',
    } = {},
    settings = {
        lineColor: "#2962FF",
        zigzagColor: "#2962FF",
        bullishOBColor: "#00FF00",
        bearishOBColor: "#FF0000",
        showLabels: true,
        showZigzag: true,
        showOB: true,
        showCHOCH: true,
        visibleBars: 300,
    },
    precision = 2
}: SMCChartProps) => {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const mainSeriesRef = useRef<ISeriesApi<"Candlestick"> | ISeriesApi<"Line"> | null>(null);
    const zigzagSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
    const obSeriesPoolRef = useRef<ISeriesApi<"Candlestick">[]>([]);
    const chochSeriesPoolRef = useRef<ISeriesApi<"Line">[]>([]);
    const seriesMarkersRef = useRef<any>(null);
    const isInitialDataRef = useRef(true);
    const lastVisibleBarsRef = useRef<number>(settings.visibleBars || 150);
    const [isAutoFollow, setIsAutoFollow] = useState(true);
    const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    // Persistence Keys
    const getLayoutKey = (sym: string) => `aureus_chart_layout_${sym}`;

    const handleSaveView = useCallback(() => {
        if (!chartRef.current || !symbol) return;
        const timeScale = chartRef.current.timeScale();
        const logicalRange = timeScale.getVisibleLogicalRange();
        const priceRange = chartRef.current.priceScale('right').getVisibleRange();

        if (logicalRange && priceRange) {
            const layout = {
                logicalRange,
                priceRange,
                isManualPrice: true
            };
            localStorage.setItem(getLayoutKey(symbol), JSON.stringify(layout));
        }
    }, [symbol]);

    const debouncedSaveView = useCallback(() => {
        if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
        saveTimeoutRef.current = setTimeout(() => {
            handleSaveView();
        }, 1000); // 1s debounce
    }, [handleSaveView]);

    // Interaction detection: if user drags or zooms, we pause auto-follow
    const handleTimeScaleChange = useCallback(() => {
        if (!chartRef.current) return;

        // If it's the initial load, we don't want to trigger this
        if (isInitialDataRef.current) return;

        // Lightweight-charts doesn't explicitly tell us if a change was programmatic
        // so we check if the user is currently zoomed/scrolled away from the right edge
        // OR if they recently interacted. 
        // For simplicity, any timeScale change that isn't from our own setData effect
        // should ideally be user-driven.
        // However, a better way is to check the logical range.
    }, []);

    // Helper: Calculate Adaptive Zoom based on volatility
    const calculateAdaptiveZoom = useCallback((candles: any[]) => {
        if (candles.length < 50) return settings.visibleBars || 150;

        // Take last 150 candles for analysis
        const recent = candles.slice(-150);
        const highs = recent.map(c => c.high);
        const lows = recent.map(c => c.low);
        const maxH = Math.max(...highs);
        const minL = Math.min(...lows);
        const avgPrice = (maxH + minL) / 2;

        // Relative range percentage
        const rangePct = ((maxH - minL) / avgPrice) * 100;

        // Adaptive Logic:
        // - Low Volatility (< 0.5% range): Zoom in, show ~80-100 bars
        // - High Volatility (> 2.0% range): Zoom out, show ~250 bars
        // - Linear interpolation between
        let targetBars = 150;
        if (rangePct < 0.5) {
            targetBars = 80;
        } else if (rangePct > 2.5) {
            targetBars = 250;
        } else {
            // Simple linear mapping: 0.5 -> 80, 2.5 -> 250
            targetBars = 80 + ((rangePct - 0.5) / (2.5 - 0.5)) * (250 - 80);
        }

        // Smoothing: Don't jump instantly
        const alpha = 0.1; // Smoothing factor
        const smoothedBars = lastVisibleBarsRef.current * (1 - alpha) + targetBars * alpha;
        lastVisibleBarsRef.current = smoothedBars;

        return Math.round(smoothedBars);
    }, [settings.visibleBars]);

    // 1. Create chart ONCE (no data dependency)
    useEffect(() => {
        if (!chartContainerRef.current) return;

        const handleResize = () => {
            if (chartContainerRef.current && chartRef.current) {
                chartRef.current.applyOptions({
                    width: chartContainerRef.current.clientWidth,
                    height: chartContainerRef.current.clientHeight
                });
            }
        };

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: backgroundColor },
                textColor,
            },
            grid: {
                vertLines: { color: '#1E222D' },
                horzLines: { color: '#1E222D' },
            },
            rightPriceScale: {
                scaleMargins: {
                    top: 0.2, // 20% margin from top
                    bottom: 0.2, // 20% margin from bottom
                },
                autoScale: true,
            },
            width: chartContainerRef.current.clientWidth,
            height: chartContainerRef.current.clientHeight,
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
                rightOffset: 15, // Provide breathing room on the right
                barSpacing: 6,
            },
        });

        const mainSeries = chartType === "line"
            ? chart.addSeries(LineSeries, { color: settings.lineColor, lineWidth: 1 })
            : chart.addSeries(CandlestickSeries, {
                upColor: '#26a69a',
                downColor: '#ef5350',
                borderVisible: false,
                wickUpColor: '#26a69a',
                wickDownColor: '#ef5350',
            });

        // Apply Precision Formatting
        const priceFormat = {
            type: 'price' as const,
            precision: precision,
            minMove: 1 / Math.pow(10, precision),
        };

        mainSeries.applyOptions({ priceFormat });

        const zigzagSeries = chart.addSeries(LineSeries, {
            color: settings.zigzagColor,
            lineWidth: 1,
            crosshairMarkerVisible: false,
            lineType: 0,
            priceLineVisible: false,
            lastValueVisible: false,
            visible: settings.showZigzag,
            priceFormat,
        });

        const obSeries = chart.addSeries(CandlestickSeries, {
            upColor: 'rgba(38, 166, 154, 0.2)',
            downColor: 'rgba(239, 83, 80, 0.2)',
            borderVisible: true,
            wickVisible: false,
            borderColor: 'rgba(38, 166, 154, 0.5)',
            visible: settings.showOB,
            priceFormat,
        });

        const seriesMarkers = createSeriesMarkers(mainSeries, []);

        mainSeriesRef.current = mainSeries as any;
        zigzagSeriesRef.current = zigzagSeries as any;
        seriesMarkersRef.current = seriesMarkers;
        chartRef.current = chart;
        isInitialDataRef.current = true;

        // --- Manual Interaction Detection ---
        const timeScale = chart.timeScale();
        timeScale.subscribeVisibleLogicalRangeChange((range) => {
            if (!range || isInitialDataRef.current) return;
            // Auto-save the view
            debouncedSaveView();
        });

        // Detect price scale changes for auto-save (if manual scale is used)
        // Note: subscribeVisibleLogicalRangeChange handles most zoom/pan.
        // For price scale specifically, we can rely on the mouseup/touchend events.

        // Detecting clicks/drags specifically
        chartContainerRef.current?.addEventListener('mousedown', () => {
            setIsAutoFollow(false);
        });
        chartContainerRef.current?.addEventListener('mouseup', () => {
            debouncedSaveView();
        });
        chartContainerRef.current?.addEventListener('wheel', () => {
            setIsAutoFollow(false);
            debouncedSaveView();
        }, { passive: true });
        chartContainerRef.current?.addEventListener('touchstart', () => {
            setIsAutoFollow(false);
        });
        chartContainerRef.current?.addEventListener('touchend', () => {
            debouncedSaveView();
        });

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
            mainSeriesRef.current = null;
            zigzagSeriesRef.current = null;
            obSeriesPoolRef.current = [];
            chochSeriesPoolRef.current = [];
            seriesMarkersRef.current = null;
            chartRef.current = null;
            if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
        };
    }, [backgroundColor, textColor, chartType, settings, symbol, debouncedSaveView, precision]);

    // 2. Update candle data AND apply Adaptive Zoom
    useEffect(() => {
        if (!mainSeriesRef.current || !data || data.length === 0) return;

        if (chartType === "line") {
            const lineData = data.map(c => ({ time: c.time, value: c.close }));
            (mainSeriesRef.current as ISeriesApi<"Line">).setData(lineData);
        } else {
            (mainSeriesRef.current as ISeriesApi<"Candlestick">).setData(data);
        }

        // Apply Adaptive Zoom (ONLY if Auto-Follow is enabled)
        if (chartRef.current) {
            const timeScale = chartRef.current.timeScale();
            const priceScale = chartRef.current.priceScale('right');

            if (isInitialDataRef.current && data.length > 0) {
                // Try to load saved layout first
                const savedLayout = localStorage.getItem(getLayoutKey(symbol));
                if (savedLayout) {
                    try {
                        const layout = JSON.parse(savedLayout);
                        // Case 1: Legacy format (just logicalRange)
                        // Case 2: New format (object with logicalRange and priceRange)
                        const logicalRange = layout.logicalRange || layout;
                        const priceRange = layout.priceRange;

                        timeScale.setVisibleLogicalRange(logicalRange);

                        if (priceRange) {
                            priceScale.applyOptions({ autoScale: false });
                            priceScale.setVisibleRange(priceRange);
                        }

                        setIsAutoFollow(false); // If they have a saved view, stop auto-follow
                    } catch (e) {
                        console.error("Failed to load saved chart layout", e);
                    }
                } else {
                    // Default adaptive zoom
                    const adaptiveBars = calculateAdaptiveZoom(data);
                    timeScale.setVisibleLogicalRange({
                        from: data.length - adaptiveBars,
                        to: data.length + 15,
                    });
                }
                isInitialDataRef.current = false;
            } else if (isAutoFollow) {
                // For live updates, we keep the latest bar in view with the adaptive zoom level
                const adaptiveBars = calculateAdaptiveZoom(data);
                timeScale.setVisibleLogicalRange({
                    from: data.length - adaptiveBars,
                    to: data.length + 15,
                });
            }
        }
    }, [data, chartType, calculateAdaptiveZoom, isAutoFollow]);

    // 3. Update markers (HH, LL), ZigZag line, CHOCH lines, and OBs
    useEffect(() => {
        if (!mainSeriesRef.current || !smcState || !zigzagSeriesRef.current || !chartRef.current) return;

        // Cleanup old CHOCH lines
        chochSeriesPoolRef.current.forEach(series => {
            try {
                chartRef.current?.removeSeries(series);
            } catch (e) { } // Ignore if already removed
        });
        chochSeriesPoolRef.current = [];

        // --- 1. Markers & ZigZag & CHOCH Lines ---
        if (smcState.swing_points && data.length > 0) {
            const sortedPoints = [...smcState.swing_points].sort((a: any, b: any) => a.t - b.t);
            const markerItems: any[] = [];
            const zigzagItems: any[] = [];

            const firstCandleTime = data[0].time;
            const lastCandleTime = data[data.length - 1].time;
            let lastT = 0;

            sortedPoints.forEach((p: any) => {
                let t = p.t;
                if (t < firstCandleTime || t > lastCandleTime) return;

                // Marker
                markerItems.push({
                    time: t,
                    position: p.is_high ? 'aboveBar' : 'belowBar',
                    color: p.is_high ? '#FFFF00' : '#00FFFF', // High contrast Yellow/Cyan
                    shape: p.is_high ? 'arrowDown' : 'arrowUp',
                    text: p.type,
                    size: 2, // Make them larger
                });

                // ZigZag Point
                zigzagItems.push({ time: t, value: p.price });

                // Independent CHOCH Line Segment
                if (p.is_choch && p.breakout_t && settings.showCHOCH) {
                    let b_t = p.breakout_t;
                    // Only draw if within bounds
                    if (b_t >= firstCandleTime && b_t <= lastCandleTime) {
                        const chochSeries = chartRef.current!.addSeries(LineSeries, {
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
                        chochSeriesPoolRef.current.push(chochSeries);
                    }
                }


            });

            // Connect ZigZag to live price
            if (zigzagItems.length > 0) {
                const latestCandle = data[data.length - 1];
                if (latestCandle.time > zigzagItems[zigzagItems.length - 1].time) {
                    zigzagItems.push({ time: latestCandle.time, value: latestCandle.close });
                }
            }

            // --- FINAL DEDUPLICATION (Safety for crashes) ---
            const dedupeAndSort = (items: any[]) => {
                if (items.length === 0) return [];

                // 1. Sort by time ascending
                const sorted = [...items].sort((a, b) => a.time - b.time);

                // 2. Filter for strictly ascending time
                const unique = [];
                let seenT = -1;
                for (const item of sorted) {
                    // Skip invalid times and values
                    if (item.time == null || isNaN(item.time)) continue;

                    if (item.time > seenT) {
                        unique.push(item);
                        seenT = item.time;
                    }
                }
                return unique;
            };

            const finalMarkers = dedupeAndSort(markerItems);
            const finalZigzag = dedupeAndSort(zigzagItems);

            if (seriesMarkersRef.current) seriesMarkersRef.current.setMarkers(settings.showLabels ? finalMarkers : []);
            zigzagSeriesRef.current.setData(settings.showZigzag ? finalZigzag : []);
        }

        // --- 2. Order Blocks ---
        // Cleanup old OB pool
        obSeriesPoolRef.current.forEach(series => {
            try { chartRef.current?.removeSeries(series); } catch (e) { }
        });
        obSeriesPoolRef.current = [];

        if (smcState.obs && data.length > 0 && settings.showOB) {
            smcState.obs.forEach((ob: any) => {
                // Determine 3-color state: Fresh Green, Fresh Red, or Mitigated Grey
                const isFreshBullish = ob.ob_type === 'BULLISH' && !ob.mitigated;
                const isFreshBearish = ob.ob_type === 'BEARISH' && !ob.mitigated;

                let finalColor = 'rgba(150, 150, 150, 0.2)'; // Default: Touched (Grey)
                if (isFreshBullish) {
                    finalColor = settings.bullishOBColor.startsWith('#')
                        ? `${settings.bullishOBColor}4D` // 30% Alpha Fresh Green
                        : 'rgba(0, 255, 0, 0.3)';
                } else if (isFreshBearish) {
                    finalColor = settings.bearishOBColor.startsWith('#')
                        ? `${settings.bearishOBColor}4D` // 30% Alpha Fresh Red
                        : 'rgba(255, 0, 0, 0.3)';
                }

                // Determine effective end time
                const endTime = ob.mitigated ? ob.t_mitigation : (ob.capped_time || data[data.length - 1].time);
                // Drawing rule: OB always starts at its origin candle (t_start)
                const startTime = ob.t_start;

                const obCandleData: any[] = [];
                data.forEach((c: any) => {
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
                    const series = chartRef.current!.addSeries(CandlestickSeries, {
                        upColor: finalColor,
                        downColor: finalColor,
                        borderVisible: true,
                        wickVisible: false,
                        borderColor: ob.mitigated ? 'rgba(150, 150, 150, 0.4)' : finalColor,
                        priceLineVisible: false,
                        lastValueVisible: false,
                    });
                    series.setData(obCandleData);
                    obSeriesPoolRef.current.push(series);
                }
            });
        }
    }, [smcState, data, settings]);

    // Add interaction listeners for auto-save and cleanup UI
    useEffect(() => {
        const chart = chartRef.current;
        if (!chart) return;

        const handleVisibleRangeChange = (newVisibleRange: any) => {
            if (newVisibleRange) {
                const logicalRange = chart.timeScale().getVisibleLogicalRange();
                const priceRange = chart.priceScale('right').getVisibleRange();
                if (logicalRange && priceRange) {
                    localStorage.setItem(getLayoutKey(symbol), JSON.stringify({ logicalRange, priceRange }));
                }
            }
        };

        const handleResize = () => {
            if (chartContainerRef.current && chartRef.current) {
                chartRef.current.applyOptions({
                    width: chartContainerRef.current.clientWidth,
                    height: chartContainerRef.current.clientHeight,
                });
            }
        };

        chart.timeScale().subscribeVisibleLogicalRangeChange(handleVisibleRangeChange);
        window.addEventListener('resize', handleResize);

        return () => {
            chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleVisibleRangeChange);
            window.removeEventListener('resize', handleResize);
            // Cleanup chart instance on unmount
            if (chartRef.current) {
                chartRef.current.remove();
                chartRef.current = null;
            }
        };
    }, [symbol]); // Depend on symbol to ensure layout is saved per symbol

    return (
        <div className="relative w-full h-full rounded-xl overflow-hidden shadow-2xl group">
            <div ref={chartContainerRef} className="w-full h-full" />

        </div>
    );
};
