import api from "@/lib/axios";
import type {
  Category,
  MenuItem,
  ModifierGroup,
  ModifierOption,
  FullMenu,
  CategoryCreate,
  CategoryUpdate,
  MenuItemCreate,
  MenuItemUpdate,
  ModifierGroupCreate,
  ModifierGroupUpdate,
  ModifierCreate,
  ModifierUpdate,
} from "@/types/menu";

// ---------------------------------------------------------------------------
// Full Menu (POS)
// ---------------------------------------------------------------------------

export async function fetchFullMenu(): Promise<FullMenu> {
  const { data } = await api.get<FullMenu>("/menu/full");
  return data;
}

// ---------------------------------------------------------------------------
// Categories
// ---------------------------------------------------------------------------

export async function fetchCategories(activeOnly = false): Promise<Category[]> {
  const { data } = await api.get<Category[]>("/menu/categories", {
    params: { active_only: activeOnly },
  });
  return data;
}

export async function createCategory(body: CategoryCreate): Promise<Category> {
  const { data } = await api.post<Category>("/menu/categories", body);
  return data;
}

export async function updateCategory(
  id: string,
  body: CategoryUpdate
): Promise<Category> {
  const { data } = await api.patch<Category>(`/menu/categories/${id}`, body);
  return data;
}

export async function deleteCategory(id: string): Promise<void> {
  await api.delete(`/menu/categories/${id}`);
}

// ---------------------------------------------------------------------------
// Menu Items
// ---------------------------------------------------------------------------

export async function fetchMenuItems(params?: {
  category_id?: string;
  available_only?: boolean;
}): Promise<MenuItem[]> {
  const { data } = await api.get<MenuItem[]>("/menu/items", { params });
  return data;
}

export async function createMenuItem(body: MenuItemCreate): Promise<MenuItem> {
  const { data } = await api.post<MenuItem>("/menu/items", body);
  return data;
}

export async function updateMenuItem(
  id: string,
  body: MenuItemUpdate
): Promise<MenuItem> {
  const { data } = await api.patch<MenuItem>(`/menu/items/${id}`, body);
  return data;
}

export async function deleteMenuItem(id: string): Promise<void> {
  await api.delete(`/menu/items/${id}`);
}

// ---------------------------------------------------------------------------
// Modifier Groups
// ---------------------------------------------------------------------------

export async function fetchModifierGroups(
  activeOnly = false
): Promise<ModifierGroup[]> {
  const { data } = await api.get<ModifierGroup[]>("/menu/modifier-groups", {
    params: { active_only: activeOnly },
  });
  return data;
}

export async function createModifierGroup(
  body: ModifierGroupCreate
): Promise<ModifierGroup> {
  const { data } = await api.post<ModifierGroup>("/menu/modifier-groups", body);
  return data;
}

export async function updateModifierGroup(
  id: string,
  body: ModifierGroupUpdate
): Promise<ModifierGroup> {
  const { data } = await api.patch<ModifierGroup>(
    `/menu/modifier-groups/${id}`,
    body
  );
  return data;
}

export async function deleteModifierGroup(id: string): Promise<void> {
  await api.delete(`/menu/modifier-groups/${id}`);
}

// ---------------------------------------------------------------------------
// Modifiers
// ---------------------------------------------------------------------------

export async function createModifier(
  groupId: string,
  body: ModifierCreate
): Promise<ModifierOption> {
  const { data } = await api.post<ModifierOption>(
    `/menu/modifier-groups/${groupId}/modifiers`,
    body
  );
  return data;
}

export async function updateModifier(
  id: string,
  body: ModifierUpdate
): Promise<ModifierOption> {
  const { data } = await api.patch<ModifierOption>(`/menu/modifiers/${id}`, body);
  return data;
}

export async function deleteModifier(id: string): Promise<void> {
  await api.delete(`/menu/modifiers/${id}`);
}
