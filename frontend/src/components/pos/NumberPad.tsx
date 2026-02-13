import { useState, useCallback } from "react";
import { Delete, CornerDownLeft } from "lucide-react";
import { cn } from "@/lib/utils";

interface NumberPadProps {
  onSubmit: (value: string) => void;
  maxLength?: number;
  masked?: boolean;
  showDecimal?: boolean;
}

export function NumberPad({
  onSubmit,
  maxLength = 10,
  masked = false,
  showDecimal = false,
}: NumberPadProps) {
  const [value, setValue] = useState("");

  const handleDigit = useCallback(
    (digit: string) => {
      setValue((prev) => {
        if (prev.length >= maxLength) return prev;
        // Prevent multiple decimals
        if (digit === "." && prev.includes(".")) return prev;
        return prev + digit;
      });
    },
    [maxLength]
  );

  const handleBackspace = useCallback(() => {
    setValue((prev) => prev.slice(0, -1));
  }, []);

  const handleClear = useCallback(() => {
    setValue("");
  }, []);

  const handleSubmit = useCallback(() => {
    if (value.length > 0) {
      onSubmit(value);
      setValue("");
    }
  }, [value, onSubmit]);

  const displayValue = masked ? "\u2022".repeat(value.length) : value;

  const buttonBase =
    "touch-feedback flex items-center justify-center rounded-xl font-bold text-pos-xl transition-colors focus:outline-none focus:ring-2 focus:ring-primary-400 no-select";

  return (
    <div className="mx-auto w-full max-w-xs">
      {/* Display */}
      <div
        className="mb-4 flex h-16 items-center justify-center rounded-xl border-2 border-secondary-600 bg-secondary-900 px-4"
        aria-live="polite"
        aria-label={masked ? "PIN entry display" : "Number entry display"}
      >
        <span className="font-mono text-pos-2xl tracking-[0.3em] text-white">
          {displayValue || (
            <span className="text-secondary-500">
              {masked ? "Enter PIN" : "0"}
            </span>
          )}
        </span>
      </div>

      {/* Keypad grid */}
      <div className="grid grid-cols-3 gap-2">
        {/* Row 1 */}
        {["1", "2", "3"].map((digit) => (
          <button
            key={digit}
            type="button"
            onClick={() => handleDigit(digit)}
            className={cn(
              buttonBase,
              "h-[72px] bg-secondary-700 text-white hover:bg-secondary-600 active:bg-secondary-500"
            )}
          >
            {digit}
          </button>
        ))}

        {/* Row 2 */}
        {["4", "5", "6"].map((digit) => (
          <button
            key={digit}
            type="button"
            onClick={() => handleDigit(digit)}
            className={cn(
              buttonBase,
              "h-[72px] bg-secondary-700 text-white hover:bg-secondary-600 active:bg-secondary-500"
            )}
          >
            {digit}
          </button>
        ))}

        {/* Row 3 */}
        {["7", "8", "9"].map((digit) => (
          <button
            key={digit}
            type="button"
            onClick={() => handleDigit(digit)}
            className={cn(
              buttonBase,
              "h-[72px] bg-secondary-700 text-white hover:bg-secondary-600 active:bg-secondary-500"
            )}
          >
            {digit}
          </button>
        ))}

        {/* Row 4: decimal/clear, 0, backspace */}
        {showDecimal ? (
          <button
            type="button"
            onClick={() => handleDigit(".")}
            className={cn(
              buttonBase,
              "h-[72px] bg-secondary-700 text-white hover:bg-secondary-600 active:bg-secondary-500"
            )}
          >
            .
          </button>
        ) : (
          <button
            type="button"
            onClick={handleClear}
            className={cn(
              buttonBase,
              "h-[72px] bg-secondary-800 text-secondary-400 hover:bg-secondary-700 active:bg-secondary-600"
            )}
            aria-label="Clear"
          >
            C
          </button>
        )}

        <button
          type="button"
          onClick={() => handleDigit("0")}
          className={cn(
            buttonBase,
            "h-[72px] bg-secondary-700 text-white hover:bg-secondary-600 active:bg-secondary-500"
          )}
        >
          0
        </button>

        <button
          type="button"
          onClick={handleBackspace}
          className={cn(
            buttonBase,
            "h-[72px] bg-secondary-800 text-secondary-400 hover:bg-secondary-700 active:bg-secondary-600"
          )}
          aria-label="Backspace"
        >
          <Delete className="h-6 w-6" />
        </button>
      </div>

      {/* Submit button */}
      <button
        type="button"
        onClick={handleSubmit}
        disabled={value.length === 0}
        className={cn(
          buttonBase,
          "mt-2 h-[56px] w-full gap-2",
          value.length > 0
            ? "bg-primary-600 text-white hover:bg-primary-700 active:bg-primary-800"
            : "cursor-not-allowed bg-secondary-800 text-secondary-600"
        )}
        aria-label="Submit"
      >
        <CornerDownLeft className="h-5 w-5" />
        Enter
      </button>
    </div>
  );
}
