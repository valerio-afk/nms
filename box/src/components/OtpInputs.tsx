import React from "react";

interface OtpInputsProps {
  startIndex: number;
  endIndex: number;
  otp: string[];
  inputRefs: React.MutableRefObject<(HTMLInputElement | null)[]>;
  handleChange: (e: React.ChangeEvent<HTMLInputElement>, index: number) => void;
  handleKeyDown: (e: React.KeyboardEvent<HTMLInputElement>, index: number) => void;
}

export default function OtpInputs({
  startIndex,
  endIndex,
  otp,
  inputRefs,
  handleChange,
  handleKeyDown
}: OtpInputsProps) {
  return (
    <>
      {Array.from({ length: endIndex - startIndex + 1 }, (_, i) => {
        const index = startIndex + i;
        return (
          <div key={index} className="w-14 flex justify-center items-center">
            <input
              ref={(el) => { inputRefs.current[index] = el; }}
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={1}
              value={otp[index]}
              onChange={(e) => handleChange(e, index)}
              onKeyDown={(e) => handleKeyDown(e, index)}
              className="w-12 h-14 sm:w-14 sm:h-16 flex-none box-border text-center text-2xl font-bold bg-gray-50 border-2 border-transparent rounded-xl text-gray-900 shadow-sm outline-none focus:outline-none focus:ring-2 focus:ring-inset focus:ring-offset-2 focus:ring-indigo-500 focus:border-white ring-gray-900/5 dark:bg-zinc-950 dark:text-white dark:focus:ring-indigo-500 dark:focus:border-zinc-900 transition-all duration-200"
            />
          </div>
        );
      })}
    </>
  );
}