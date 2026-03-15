import { BrainCircuit, CheckCircle2, CircleDashed, Clock } from "lucide-react";

interface StepProgress {
    tag: string;
    weight: number;
    required: boolean;
    status: "matched" | "waiting" | "missed";
    time?: number;
}

interface StrategyProgress {
    strategy: string;
    progress_pct: number;
    sequence: StepProgress[];
}

interface ConfluenceOverlayProps {
    progressData: Record<string, StrategyProgress>;
}

export function ConfluenceOverlay({ progressData }: ConfluenceOverlayProps) {
    const strategies = Object.values(progressData || {});

    if (strategies.length === 0) return null;

    return (
        <div className="flex flex-col space-y-3 w-full">
            {strategies.map((prog, idx) => (
                <div key={idx} className="bg-[#1E222D] border border-gray-800 rounded-xl p-4 w-full shadow-lg transition-all">
                    <div className="flex justify-between items-center mb-3">
                        <div className="flex items-center space-x-2">
                            <BrainCircuit className="h-4 w-4 text-blue-500" />
                            <span className="font-bold text-sm text-gray-200">{prog.strategy}</span>
                        </div>
                        <span className="text-xs font-mono font-bold text-blue-400">
                            {prog.progress_pct.toFixed(0)}%
                        </span>
                    </div>

                    {/* Progress Bar */}
                    <div className="h-1.5 w-full bg-gray-800 rounded-full mb-4 overflow-hidden">
                        <div
                            className="h-full bg-blue-500 transition-all duration-500 ease-out"
                            style={{ width: `${prog.progress_pct}%` }}
                        />
                    </div>

                    <div className="space-y-2">
                        {prog.sequence.map((step, sIdx) => (
                            <div key={sIdx} className="flex items-center justify-between text-xs">
                                <div className="flex items-center space-x-2">
                                    {step.status === "matched" ? (
                                        <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                                    ) : step.status === "waiting" ? (
                                        <Clock className="h-3.5 w-3.5 text-yellow-500" />
                                    ) : (
                                        <CircleDashed className="h-3.5 w-3.5 text-gray-600" />
                                    )}
                                    <span className={
                                        step.status === "matched" ? "text-gray-300" :
                                            step.status === "waiting" ? "text-yellow-500/80" : "text-gray-500"
                                    }>
                                        {step.tag.toUpperCase()}
                                    </span>
                                </div>
                                <span className="text-[10px] text-gray-600 font-mono">W:{step.weight}</span>
                            </div>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}
