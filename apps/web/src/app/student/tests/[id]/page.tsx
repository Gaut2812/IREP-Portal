"use client";

import React, { useState, useEffect } from "react";
import { AppShell } from "@/components/AppShell";
import { Clock, CheckCircle2, Bookmark, ArrowLeft, ArrowRight, Check } from "lucide-react";

export default function PracticeTestPage() {
  const [currentQ, setCurrentQ] = useState(12);
  const [selectedOption, setSelectedOption] = useState<string>("B");
  const [markedForReview, setMarkedForReview] = useState<number[]>([7, 14]);
  const [answeredList, setAnsweredList] = useState<number[]>([1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12]);
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  // Time remaining countdown simulation: 18:42
  const [secondsLeft, setSecondsLeft] = useState(1122);

  useEffect(() => {
    const timer = setInterval(() => {
      setSecondsLeft((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  const handleSelectOption = (opt: string) => {
    setSelectedOption(opt);
    if (!answeredList.includes(currentQ)) {
      setAnsweredList([...answeredList, currentQ]);
    }
  };

  const toggleReview = () => {
    if (markedForReview.includes(currentQ)) {
      setMarkedForReview(markedForReview.filter((q) => q !== currentQ));
    } else {
      setMarkedForReview([...markedForReview, currentQ]);
    }
  };

  const handleNext = () => {
    if (currentQ < 30) {
      setCurrentQ(currentQ + 1);
      setSelectedOption(answeredList.includes(currentQ + 1) ? "A" : "");
    }
  };

  const handlePrevious = () => {
    if (currentQ > 1) {
      setCurrentQ(currentQ - 1);
      setSelectedOption(answeredList.includes(currentQ - 1) ? "B" : "");
    }
  };

  return (
    <AppShell pageTitle="Practice Test: Service Company Pattern · Aptitude">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 max-w-7xl mx-auto">
        
        {/* MAIN QUESTION CARD (8 cols) */}
        <div className="lg:col-span-8 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6 flex flex-col justify-between space-y-6">
          <div className="space-y-4">
            {/* Top Bar with topic chip and question index */}
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <span className="chip-blue font-bold text-xs">Quantitative · Time & Work</span>
              <span className="text-xs font-bold text-[#64748B]">Question {currentQ} of 30</span>
            </div>

            {/* Question Text matching PDF 4 exactly */}
            <p className="text-sm font-medium text-[#0F1F3A] leading-relaxed pt-2">
              A can complete a piece of work in 12 days, and B can complete the same work in 20 days. If both of them work together for 3 days, and then A leaves, in how many more days will B finish the remaining work alone?
            </p>

            {/* 4 Options (A to D) */}
            <div className="space-y-3 pt-3">
              {[
                { id: "A", text: "6 days" },
                { id: "B", text: "7.5 days" },
                { id: "C", text: "8 days" },
                { id: "D", text: "9 days" }
              ].map((opt) => {
                const isSelected = selectedOption === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => handleSelectOption(opt.id)}
                    className={`w-full flex items-center gap-3.5 p-3.5 rounded-xl border text-left text-xs font-medium transition-all ${
                      isSelected
                        ? "border-[#2B5CD0] bg-[#EFF6FF] text-[#1D4ED8] font-bold shadow-sm ring-1 ring-[#2B5CD0]"
                        : "border-[#E2E8F0] bg-white text-[#0F1F3A] hover:bg-[#F8FAFC]"
                    }`}
                  >
                    <span
                      className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                        isSelected ? "bg-[#2B5CD0] text-white" : "bg-[#F1F5F9] text-[#64748B]"
                      }`}
                    >
                      {opt.id}
                    </span>
                    <span className="text-sm">{opt.text}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Navigation Buttons matching PDF 4 */}
          <div className="flex items-center justify-between border-t border-[#E2E8F0] pt-4">
            <button
              onClick={handlePrevious}
              disabled={currentQ === 1}
              className="flex items-center gap-1.5 px-4 py-2 border border-[#CBD5E1] text-[#0F1F3A] text-xs font-bold rounded-lg hover:bg-[#F1F5F9] disabled:opacity-40 transition-all cursor-pointer"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Previous</span>
            </button>

            <button
              onClick={toggleReview}
              className={`flex items-center gap-1.5 px-4 py-2 border rounded-lg text-xs font-bold transition-all cursor-pointer ${
                markedForReview.includes(currentQ)
                  ? "bg-[#FEF3C7] border-[#F59E0B] text-[#B45309]"
                  : "border-[#CBD5E1] text-[#64748B] hover:bg-[#F1F5F9]"
              }`}
            >
              <Bookmark className="w-3.5 h-3.5" />
              <span>{markedForReview.includes(currentQ) ? "Marked for review" : "Mark for review"}</span>
            </button>

            <button
              onClick={handleNext}
              className="flex items-center gap-1.5 px-5 py-2 bg-[#2B5CD0] hover:bg-[#1E46B0] text-white text-xs font-bold rounded-lg shadow transition-all cursor-pointer"
            >
              <span>Save & Next</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* RIGHT COLUMN (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          
          {/* Time Remaining Card (PDF 4: Large Red 18:42) */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-2">
            <div className="flex items-center justify-between text-xs text-[#64748B] font-medium">
              <span>Time remaining</span>
              <Clock className="w-3.5 h-3.5 text-[#D93636]" />
            </div>
            <div className="text-3xl font-black text-[#D93636] tracking-tight">
              {formatTime(secondsLeft)}
            </div>
            <div className="w-full bg-[#FEE2E2] h-1.5 rounded-full overflow-hidden">
              <div
                className="bg-[#D93636] h-full rounded-full transition-all duration-1000"
                style={{ width: `${(secondsLeft / 1800) * 100}%` }}
              />
            </div>
          </div>

          {/* Question Palette (6 columns grid) */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-3">
            <div className="flex items-center justify-between text-xs font-bold text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">
              <span>Question palette</span>
              <span className="text-[11px] text-[#64748B]">30 Questions</span>
            </div>

            {/* 6-column numbered squares */}
            <div className="grid grid-cols-6 gap-2 pt-1">
              {Array.from({ length: 30 }, (_, i) => i + 1).map((qNum) => {
                const isCurrent = qNum === currentQ;
                const isAnswered = answeredList.includes(qNum);
                const isReview = markedForReview.includes(qNum);

                let bgClass = "bg-[#F1F5F9] text-[#64748B] border-[#E2E8F0]";
                if (isCurrent) {
                  bgClass = "bg-[#2B5CD0] text-white border-[#2B5CD0] ring-2 ring-[#BFDBFE]";
                } else if (isReview) {
                  bgClass = "bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]";
                } else if (isAnswered) {
                  bgClass = "bg-[#DCFCE7] text-[#15803D] border-[#BBF7D0]";
                }

                return (
                  <button
                    key={qNum}
                    onClick={() => {
                      setCurrentQ(qNum);
                      setSelectedOption(answeredList.includes(qNum) ? (qNum === 12 ? "B" : "A") : "");
                    }}
                    className={`h-8 rounded-lg text-xs font-bold border flex items-center justify-center transition-all cursor-pointer ${bgClass}`}
                  >
                    {qNum}
                  </button>
                );
              })}
            </div>

            {/* Palette Legend */}
            <div className="flex items-center justify-between text-[11px] pt-3 border-t border-[#E2E8F0]">
              <span className="chip-green">Answered {answeredList.length}</span>
              <span className="chip-amber">Review {markedForReview.length}</span>
              <span className="chip-blue">Current</span>
            </div>
          </div>

          {/* Sections Card */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-2.5">
            <div className="text-xs font-bold text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">
              Sections
            </div>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between font-semibold">
                <span className="text-[#0F1F3A]">Quantitative</span>
                <span className="text-[#2B5CD0] font-bold">12 / 15</span>
              </div>
              <div className="flex items-center justify-between text-[#64748B]">
                <span>Logical reasoning</span>
                <span>0 / 10</span>
              </div>
              <div className="flex items-center justify-between text-[#64748B]">
                <span>Verbal ability</span>
                <span>0 / 5</span>
              </div>
            </div>

            <button
              onClick={() => setShowSubmitModal(true)}
              className="w-full mt-3 py-2.5 bg-[#2BB3A0] hover:bg-[#249B8A] text-white font-bold text-xs rounded-xl shadow transition-all cursor-pointer"
            >
              Submit Test
            </button>
          </div>

        </div>

      </div>

      {/* Submit Test Modal */}
      {showSubmitModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 space-y-4 shadow-2xl border border-[#E2E8F0]">
            <h3 className="text-base font-bold text-[#0F1F3A]">Ready to submit test?</h3>
            <div className="space-y-1 text-xs text-[#64748B]">
              <p>Answered: <strong className="text-[#15803D]">{answeredList.length} questions</strong></p>
              <p>Marked for review: <strong className="text-[#B45309]">{markedForReview.length} questions</strong></p>
              <p>Unanswered: <strong className="text-[#D93636]">{30 - answeredList.length} questions</strong></p>
            </div>
            <div className="flex gap-2.5 pt-2">
              <button
                onClick={() => setShowSubmitModal(false)}
                className="flex-1 py-2 bg-[#F1F5F9] text-[#0F1F3A] font-bold text-xs rounded-xl"
              >
                Back to Test
              </button>
              <button
                onClick={() => {
                  setShowSubmitModal(false);
                  setIsSubmitted(true);
                }}
                className="flex-1 py-2 bg-[#2BB3A0] text-white font-bold text-xs rounded-xl"
              >
                Confirm Submit
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Results View Modal */}
      {isSubmitted && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl border border-[#E2E8F0] text-center">
            <div className="w-12 h-12 rounded-full bg-[#DCFCE7] text-[#15803D] flex items-center justify-center mx-auto text-xl">
              ✓
            </div>
            <h3 className="text-lg font-bold text-[#0F1F3A]">Test Submitted Successfully!</h3>
            <div className="p-4 bg-[#F8FAFC] rounded-xl space-y-2 text-xs">
              <div className="text-2xl font-black text-[#2B5CD0]">26 / 30</div>
              <div className="text-[#64748B]">Accuracy: 86.7% · Time taken: 24 mins</div>
            </div>
            <button
              onClick={() => setIsSubmitted(false)}
              className="w-full py-2.5 bg-[#2B5CD0] text-white font-bold text-xs rounded-xl"
            >
              Done & Return
            </button>
          </div>
        </div>
      )}
    </AppShell>
  );
}
