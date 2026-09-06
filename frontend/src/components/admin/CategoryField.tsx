/**
 * The ingredient category picker (Martin M11).
 *
 * > "Ingredients. Theres a fixed set of Categories. Don't see a menu or
 * >  drop-down menu where I can add a category"
 *
 * The set was never fixed -- the field was a free-text box, and typing anything
 * created that category. But there was no list, no dropdown and no way to see
 * what already existed, so it read as closed. And free text across forty
 * ingredients guarantees "Dairy", "dairy" and "Diary" all become real
 * categories.
 *
 * So: a dropdown of what exists, plus "+ New category" inline. The new name is
 * held in local state and sent with the ingredient; the server puts it on the
 * master list on save, matching case-insensitively so it cannot fork an
 * existing one.
 */

import { useState } from "react";
import { Plus, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import type { IngredientCategory } from "@/types/inventory";

interface CategoryFieldProps {
  idPrefix: string;
  value: string;
  onChange: (value: string) => void;
  categories: IngredientCategory[];
}

export function CategoryField({
  idPrefix,
  value,
  onChange,
  categories,
}: CategoryFieldProps) {
  /*
   * Typing a brand-new name is a distinct mode, not a value in the list. Kept
   * as its own boolean rather than inferred from "value is not in categories",
   * because the edit form legitimately opens on a category that has since been
   * deactivated and that must not silently switch the control into add mode.
   */
  const [adding, setAdding] = useState(false);

  const options = categories.map((c) => c.name);
  // An ingredient filed under a category that is no longer on the active list
  // still has to show its own value, or opening the edit form would silently
  // re-file it under whatever happens to be first.
  const missing = value && !options.includes(value) ? value : null;

  if (adding) {
    return (
      <div className="space-y-2">
        <Label htmlFor={`${idPrefix}-category-new`}>New category</Label>
        <div className="flex gap-2">
          <Input
            id={`${idPrefix}-category-new`}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="e.g. Packaging"
            autoFocus
            className="min-h-[48px]"
          />
          <button
            type="button"
            onClick={() => {
              setAdding(false);
              onChange(options[0] ?? "General");
            }}
            aria-label="Pick from the list instead"
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border border-secondary-300 text-secondary-500"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="text-xs text-secondary-500">
          It joins the list when you save. An existing name is reused rather
          than duplicated.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label htmlFor={`${idPrefix}-category`}>Category</Label>
        <button
          type="button"
          onClick={() => {
            setAdding(true);
            onChange("");
          }}
          className="inline-flex items-center gap-1 text-xs font-medium text-primary-600 hover:text-primary-700"
        >
          <Plus className="h-3 w-3" />
          New category
        </button>
      </div>
      <Select
        id={`${idPrefix}-category`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-[48px]"
      >
        {missing && <option value={missing}>{missing}</option>}
        {categories.map((c) => (
          <option key={c.name} value={c.name}>
            {c.name}
            {c.ingredient_count > 0 ? ` (${c.ingredient_count})` : ""}
          </option>
        ))}
      </Select>
    </div>
  );
}
