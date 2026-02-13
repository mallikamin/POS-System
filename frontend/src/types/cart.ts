import type { MenuItem } from "@/types/menu";

export interface SelectedModifier {
  modifier_option_id: string;
  name: string;
  price_adjustment: number;
  group_id: string;
}

export interface CartItem {
  menuItem: MenuItem;
  quantity: number;
  modifiers: SelectedModifier[];
}
