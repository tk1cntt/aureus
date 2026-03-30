import React from 'react';
import { Brain, TrendingUp, TrendingDown, Minus, BrainCircuit } from 'lucide-react';

interface MarketPulseProps {
    analysis: {
        narrative: string;
        sentiment: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
        aci: number;
        timestamp: number;
        debate_log?: {
            trend: string;
            liquidity: string;
            skeptic: string;
            monologue?: string;
        };
        prompt_tokens?: number;
        completion_tokens?: number;
        llm_latency_ms?: number;
        total_latency_ms?: number;
    } | null;
}

export const MarketPulse: React.FC<MarketPulseProps> = ({ analysis }) => {
    if (!analysis) return null;

    const getSentimentIcon = () => {
        switch (analysis.sentiment) {
            case 'BULLISH': return <TrendingUp className="text-green-500 h-5 w-5" />;
            case 'BEARISH': return <TrendingDown className="text-red-500 h-5 w-5" />;
            default: return <Minus className="text-gray-400 h-5 w-5" />;
        }
    };

    const getSentimentColor = () => {
        switch (analysis.sentiment) {
            case 'BULLISH': return 'text-green-400';
            case 'BEARISH': return 'text-red-400';
            default: return 'text-gray-400';
        }
    };

    return (
        <div className="bg-transparent border-b border-gray-800/50 pb-6 mb-6 last:border-0 last:pb-0 animate-in fade-in duration-500">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-2">
                    <Brain className="h-5 w-5 text-purple-500/80" />
                    <h3 className="text-xs font-black text-gray-400 uppercase tracking-[0.2em]">Institutional Narrative</h3>
                </div>
                <div className="flex items-center space-x-4">
                    <div className="flex flex-col items-end">
                        <span className="text-[10px] text-gray-600 font-bold uppercase tracking-widest">Confidence</span>
                        <span className={`text-md font-mono font-black ${analysis.aci >= 70 ? 'text-green-500/80' : 'text-amber-500/80'}`}>
                            {analysis.aci}
                        </span>
                    </div>
                    {getSentimentIcon()}
                </div>
            </div>

            <div className="space-y-6">
                <div className={`relative pl-4 border-l-2 transition-colors duration-300 ${analysis.sentiment === 'BULLISH' ? 'border-green-500/50' : analysis.sentiment === 'BEARISH' ? 'border-red-500/50' : 'border-gray-500/50'}`}>
                    <span className={`font-black uppercase text-[10px] tracking-widest block mb-2 ${getSentimentColor()}`}>
                        {analysis.sentiment} BIAS
                    </span>
                    <p className="text-sm text-gray-200 font-medium leading-relaxed italic">
                        &ldquo;{analysis.narrative}&rdquo;
                    </p>
                </div>

                {analysis.debate_log && (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pl-4 border-l border-gray-800/30">
                        <div className="group">
                            <span className="text-[9px] font-black text-gray-600 uppercase tracking-widest block mb-1.5 opacity-60">Trend</span>
                            <p className="text-[11px] text-gray-400 leading-relaxed font-light">{analysis.debate_log.trend}</p>
                        </div>
                        <div className="group">
                            <span className="text-[9px] font-black text-gray-600 uppercase tracking-widest block mb-1.5 opacity-60">Liquidity</span>
                            <p className="text-[11px] text-gray-400 leading-relaxed font-light">{analysis.debate_log.liquidity}</p>
                        </div>
                        <div className="group">
                            <span className="text-[9px] font-black text-gray-600 uppercase tracking-widest block mb-1.5 opacity-60">Risk</span>
                            <p className="text-[11px] text-gray-400 leading-relaxed font-light">{analysis.debate_log.skeptic}</p>
                        </div>
                    </div>
                )}

                {analysis.debate_log?.monologue && (
                    <div className="pl-4 border-l border-blue-500/20">
                        <div className="text-[9px] font-black text-blue-400/60 uppercase tracking-widest mb-2 flex items-center space-x-1">
                            <BrainCircuit className="h-3 w-3" />
                            <span>Internal Monologue</span>
                        </div>
                        <p className="text-[11px] text-gray-500 leading-relaxed font-mono whitespace-pre-wrap max-h-40 overflow-y-auto scrollbar-hide">
                            {analysis.debate_log.monologue}
                        </p>
                    </div>
                )}
            </div>

            <div className="mt-4 flex justify-between items-center text-[9px] text-gray-600">
                <div className="flex items-center space-x-3">
                    <span>DeepSeek-R1 Operational</span>
                    {analysis.llm_latency_ms && (
                        <span className="bg-black/20 px-2 py-0.5 rounded border border-gray-800">
                            {analysis.llm_latency_ms}ms
                            {analysis.total_latency_ms && ` / ${analysis.total_latency_ms}ms`}
                        </span>
                    )}
                    {analysis.prompt_tokens !== undefined && (
                        <span className="text-gray-500">
                            {analysis.prompt_tokens + (analysis.completion_tokens || 0)} tokens
                        </span>
                    )}
                </div>
                <span>Last Updated: {new Date(analysis.timestamp * 1000).toLocaleTimeString()}</span>
            </div>
        </div>
    );
};
