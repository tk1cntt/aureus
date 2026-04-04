import React, { useState, useEffect } from "react";
import { BrainCircuit, ShieldCheck, ChevronDown, ChevronUp, Settings2, Check } from "lucide-react";

interface AuditLog {
    trend: string;
    liquidity: string;
    assassin: string;
    judgement: string;
    monologue?: string;
}

interface AI_Audit {
    aci: number;
    decision: string;
    key_insight: string;
    debate_log: AuditLog;
    llm_latency_ms?: number;
    prompt_tokens?: number;
    completion_tokens?: number;
    request_payload?: string;
    response_payload?: string;
    // Phase 6
    audit_source?: "AI" | "ALGO" | "HYBRID";
    algo_score?: number;
    algo_breakdown?: {
        Structure?: number;
        Liquidity?: number;
        Momentum?: number;
        [key: string]: number | undefined;
    };
}

interface ModelApiResponse {
    model: string;
}

interface AIInsightsProps {
    audit: AI_Audit;
}

const AVAILABLE_MODELS = [
    { id: "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B", label: "DeepSeek R1 (1.5B)", icon: "🧠" },
    { id: "meta-llama/Llama-3.2-3B-Instruct", label: "Llama 3.2 (3B)", icon: "🦙" },
    { id: "Qwen/Qwen2.5-3B-Instruct", label: "Qwen 2.5 (3B)", icon: "🦅" },
    { id: "Qwen/Qwen2.5-VL-3B-Instruct", label: "Qwen 2.5-VL (3B)", icon: "👁️" },
    { id: "Nanbeige/Nanbeige4.1-3B", label: "Nanbeige (3B)", icon: "🐼" },
    { id: "Qwen3.5-9B.Q4_K_M.gguf", label: "Qwen3.5-9B", icon: "🐼" }
];

export function ModelSelector() {
    const [currentModel, setCurrentModel] = useState<string>("meta-llama/Llama-3.2-3B-Instruct");
    const [isOpen, setIsOpen] = useState(false);
    const [isUpdating, setIsUpdating] = useState(false);

    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";

    useEffect(() => {
        fetch(`${API_BASE}/ai/model`)
            .then(res => res.json())
            .then((data: ModelApiResponse) => setCurrentModel(data.model))
            .catch(err => console.error("Error fetching model:", err));
    }, [API_BASE]);

    const handleSelect = async (modelId: string) => {
        setIsUpdating(true);
        setIsOpen(false);
        try {
            const res = await fetch(`${API_BASE}/ai/model`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model: modelId })
            });
            if (res.ok) {
                const data = (await res.json()) as ModelApiResponse;
                setCurrentModel(data.model);
            }
        } catch (err) {
            console.error("Error updating model:", err);
        } finally {
            setIsUpdating(false);
        }
    };

    const activeModelOpt = AVAILABLE_MODELS.find(m => m.id === currentModel) || AVAILABLE_MODELS[0];

    return (
        <div className="relative z-50">
            <div
                onClick={() => !isUpdating && setIsOpen(!isOpen)}
                className={`flex items-center justify-between bg-black/40 border border-gray-800 rounded px-3 py-1.5 cursor-pointer hover:bg-black/60 transition-colors ${isUpdating ? 'opacity-50' : ''}`}
            >
                <div className="flex items-center space-x-2">
                    <Settings2 className="h-3 w-3 text-gray-400" />
                    <span className="text-[10px] font-bold text-gray-300 font-mono tracking-tighter">
                        {activeModelOpt.icon} {activeModelOpt.label}
                    </span>
                </div>
                <ChevronDown className={`h-3 w-3 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </div>

            {isOpen && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-gray-900 border border-gray-700/50 rounded-lg shadow-2xl overflow-hidden animate-in fade-in slide-in-from-top-1">
                    {AVAILABLE_MODELS.map(model => (
                        <div
                            key={model.id}
                            onClick={() => handleSelect(model.id)}
                            className="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-blue-500/10 border-b border-gray-800/30 last:border-0"
                        >
                            <div className="flex items-center space-x-2">
                                <span className="text-xs">{model.icon}</span>
                                <span className={`text-[10px] font-mono tracking-tighter ${currentModel === model.id ? 'text-blue-400 font-bold' : 'text-gray-400'}`}>
                                    {model.label}
                                </span>
                            </div>
                            {currentModel === model.id && <Check className="h-3 w-3 text-blue-500" />}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

export function AIConfidenceMeter({ aci }: { aci: number }) {
    const color = aci >= 80 ? "text-green-500" : aci >= 70 ? "text-amber-500" : "text-red-500";
    const bgColor = aci >= 80 ? "bg-green-500/10" : aci >= 70 ? "bg-amber-500/10" : "bg-red-500/10";
    const borderColor = aci >= 80 ? "border-green-500/20" : aci >= 70 ? "border-amber-500/20" : "border-red-500/20";

    return (
        <div className={`p-4 rounded-xl border ${borderColor} ${bgColor} flex flex-col items-center justify-center space-y-1`}>
            <div className={`text-2xl font-black font-mono ${color}`}>{aci}</div>
            <div className="text-[10px] font-bold text-gray-500 uppercase tracking-tighter">ACI Score</div>
        </div>
    );
}

export function InstitutionalAudit({ audit }: AIInsightsProps) {
    const [verdictExpanded, setVerdictExpanded] = React.useState(false);

    if (!audit || (!audit.debate_log && !audit.algo_breakdown)) return null;

    const isRejected = audit.decision === "REJECTED";
    const isHybrid = audit.audit_source === "HYBRID";
    const isAlgoOnly = audit.audit_source === "ALGO";

    return (
        <div className="py-1 space-y-2 animate-in fade-in duration-300">
            {/* Verdict & Insight - Ultra Compact */}
            <div className="flex items-start space-x-2">
                <BrainCircuit className={`h-4 w-4 mt-1 flex-shrink-0 ${isRejected ? 'text-red-500' : 'text-blue-500'}`} />
                <div className="flex-1">
                    <div className="relative">
                        <p className={`text-[11px] text-gray-300 font-medium leading-[1.4] italic pr-6 ${verdictExpanded ? '' : 'line-clamp-2'}`}>
                            &ldquo;{audit.key_insight}&rdquo;
                        </p>
                        {audit.key_insight.length > 100 && (
                            <button
                                onClick={() => setVerdictExpanded(!verdictExpanded)}
                                className="absolute right-0 bottom-0 p-1 text-blue-500 hover:text-blue-400 transition-colors"
                            >
                                {verdictExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                            </button>
                        )}
                    </div>
                </div>
            </div>

            {/* Logical Breakdown - Horizontal & Tiny */}
            <div className="flex flex-wrap gap-x-6 gap-y-1 pl-6 pt-1 border-t border-gray-800/30">
                <AuditSection title="Trend" content={audit.debate_log.trend} />
                <AuditSection title="Liq" content={audit.debate_log.liquidity} />
                <AuditSection title="Risk" content={audit.debate_log.assassin} color="text-red-400" />
                <AuditSection title="Conf" content={audit.debate_log.judgement} color="text-green-400" />
            </div>

            {audit.debate_log.monologue && (
                <div className="pl-6">
                    <p className="text-[8px] text-gray-500 font-mono leading-tight bg-black/5 p-1 rounded truncate hover:whitespace-normal hover:bg-black/20 cursor-help transition-all">
                        Logic: {audit.debate_log.monologue}
                    </p>
                </div>
            )}

            {/* Request Source & vLLM Response Hovers - NEW */}
            <div className="pl-6 flex items-center justify-between">
                <div className="flex items-center space-x-4">
                    {audit.request_payload && (
                        <div className="group/req relative">
                            <div className="flex items-center space-x-1 cursor-help opacity-40 hover:opacity-100 transition-opacity">
                                <div className="w-1 h-1 rounded-full bg-blue-500"></div>
                                <span className="text-[7px] font-black uppercase tracking-tighter text-gray-500">View Engine Request</span>
                            </div>

                            <div className="absolute left-0 bottom-full mb-2 invisible group-hover/req:visible z-[100] w-[400px] max-h-[300px] overflow-y-auto bg-gray-950 border border-blue-500/30 rounded-lg shadow-2xl p-3 animate-in slide-in-from-bottom-2 duration-200">
                                <div className="flex items-center justify-between mb-2 border-b border-gray-800 pb-1">
                                    <span className="text-[9px] font-black text-blue-400 uppercase tracking-widest">vLLM Request Payload</span>
                                    <span className="text-[8px] text-gray-500 font-mono">{audit.request_payload.length} chars</span>
                                </div>
                                <pre className="text-[9px] text-gray-400 font-mono leading-relaxed whitespace-pre-wrap break-words selection:bg-blue-500/30">
                                    {audit.request_payload}
                                </pre>
                            </div>
                        </div>
                    )}

                    {audit.response_payload && (
                        <div className="group/res relative">
                            <div className="flex items-center space-x-1 cursor-help opacity-40 hover:opacity-100 transition-opacity">
                                <div className="w-1 h-1 rounded-full bg-purple-500"></div>
                                <span className="text-[7px] font-black uppercase tracking-tighter text-gray-500">View vLLM Response</span>
                            </div>

                            <div className="absolute left-0 bottom-full mb-2 invisible group-hover/res:visible z-[100] w-[400px] max-h-[300px] overflow-y-auto bg-gray-950 border border-purple-500/30 rounded-lg shadow-2xl p-3 animate-in slide-in-from-bottom-2 duration-200">
                                <div className="flex items-center justify-between mb-2 border-b border-gray-800 pb-1">
                                    <span className="text-[9px] font-black text-purple-400 uppercase tracking-widest">Raw vLLM Response</span>
                                    <span className="text-[8px] text-gray-500 font-mono">{audit.response_payload.length} chars</span>
                                </div>
                                <pre className="text-[9px] text-gray-400 font-mono leading-relaxed whitespace-pre-wrap break-words selection:bg-purple-500/30">
                                    {audit.response_payload}
                                </pre>
                            </div>
                        </div>
                    )}
                </div>

                {audit.audit_source && (
                    <div className="px-1.5 py-0.5 rounded-[3px] border border-gray-800 bg-gray-900/50">
                        <span className={`text-[7px] font-black uppercase tracking-widest ${isHybrid ? 'text-blue-400' : isAlgoOnly ? 'text-amber-400' : 'text-purple-400'}`}>
                            {audit.audit_source} SOURCE
                        </span>
                    </div>
                )}
            </div>

            {/* Phase 6: Algorithmic Breakdown */}
            {audit.algo_breakdown && (
                <div className="pl-6 pt-1 border-t border-gray-800/20 mt-1">
                    <div className="flex items-center space-x-1 mb-1">
                        <ShieldCheck className="h-2 w-2 text-amber-500/50" />
                        <span className="text-[7px] font-black text-gray-600 uppercase tracking-widest">Algorithmic Auditor Breakdown</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                        {Object.entries(audit.algo_breakdown).map(([label, score]) => (
                            <div key={label} className="bg-gray-900/30 p-1.5 rounded border border-gray-800/30 flex justify-between items-center group/algo">
                                <span className="text-[8px] font-black text-gray-500 uppercase tracking-tighter group-hover/algo:text-gray-300 transition-colors">{label}</span>
                                <span className={`text-[9px] font-black font-mono ${Number(score) > 70 ? 'text-green-500' : Number(score) > 40 ? 'text-amber-500' : 'text-red-500'}`}>
                                    {Math.round(Number(score))}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

function AuditSection({ title, content, color = "text-gray-400" }: { title: string, content: unknown, color?: string }) {
    // Robustness: LLM sometimes returns objects instead of strings
    const displayContent = React.useMemo(() => {
        if (!content) return "";
        if (typeof content === 'string') return content;
        if (typeof content === 'object') {
            // Try to extract a meaningful string from the object
            const values = Object.values(content);
            return values.length > 0 ? String(values[0]) : JSON.stringify(content);
        }
        return String(content);
    }, [content]);

    return (
        <div className="group relative flex flex-col cursor-help">
            <div className={`text-[8px] font-black uppercase tracking-widest ${color} opacity-80`}>
                {title}
            </div>
            <div className="text-[10px] text-gray-300 font-bold truncate max-w-[60px]">
                {displayContent}
            </div>

            {/* Tooltip */}
            <div className="absolute bottom-full left-0 mb-2 invisible group-hover:visible z-50 w-48 p-2 bg-gray-900 border border-gray-800 rounded shadow-2xl pointer-events-none transition-all">
                <div className={`text-[8px] font-black uppercase mb-1 ${color}`}>{title} Details</div>
                <div className="text-[10px] text-gray-300 leading-normal">{displayContent}</div>
                <div className="absolute top-full left-4 -mt-1 border-4 border-transparent border-t-gray-900"></div>
            </div>
        </div>
    );
}
