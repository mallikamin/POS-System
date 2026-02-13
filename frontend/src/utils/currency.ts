/**
 * Format paisa amount to PKR display string.
 * @param paisa - Amount in paisa (integer, 100 paisa = 1 PKR)
 * @returns Formatted string like "Rs. 650" or "Rs. 1,800"
 */
export function formatPKR(paisa: number): string {
  const rupees = paisa / 100;
  return `Rs. ${rupees.toLocaleString("en-PK", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

/**
 * Convert rupees (user input) to paisa for storage.
 */
export function rupeesToPaisa(rupees: number): number {
  return Math.round(rupees * 100);
}

/**
 * Convert paisa to rupees for display in input fields.
 */
export function paisaToRupees(paisa: number): number {
  return paisa / 100;
}
