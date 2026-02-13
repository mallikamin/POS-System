import { useEffect, useState, useCallback } from "react";
import {
  Plus,
  Pencil,
  Trash2,
  Loader2,
  UtensilsCrossed,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { formatPKR, rupeesToPaisa, paisaToRupees } from "@/utils/currency";
import { useMenuStore } from "@/stores/menuStore";
import * as menuApi from "@/services/menuApi";
import type {
  Category,
  MenuItem,
  ModifierGroup,
  ModifierOption,
  CategoryCreate,
  CategoryUpdate,
  MenuItemCreate,
  MenuItemUpdate,
  ModifierGroupCreate,
  ModifierGroupUpdate,
  ModifierCreate,
  ModifierUpdate,
} from "@/types/menu";

/* ==========================================================================
   MenuManagementPage — Admin CRUD for Categories, Items, Modifier Groups
   ========================================================================== */

function MenuManagementPage() {
  const [activeTab, setActiveTab] = useState("categories");

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <UtensilsCrossed className="h-7 w-7 text-primary-600" />
        <h1 className="text-pos-2xl font-bold text-secondary-900">
          Menu Management
        </h1>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="categories">Categories</TabsTrigger>
          <TabsTrigger value="items">Menu Items</TabsTrigger>
          <TabsTrigger value="modifiers">Modifier Groups</TabsTrigger>
        </TabsList>

        <TabsContent value="categories">
          <CategoriesTab />
        </TabsContent>
        <TabsContent value="items">
          <ItemsTab />
        </TabsContent>
        <TabsContent value="modifiers">
          <ModifierGroupsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ==========================================================================
   Categories Tab
   ========================================================================== */

function CategoriesTab() {
  const clearMenu = useMenuStore((s) => s.clearMenu);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Category | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [displayOrder, setDisplayOrder] = useState(0);
  const [icon, setIcon] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await menuApi.fetchCategories();
      setCategories(data);
    } catch {
      // silently fail, user sees empty list
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function openCreate() {
    setEditing(null);
    setName("");
    setDescription("");
    setDisplayOrder(categories.length);
    setIcon("");
    setDialogOpen(true);
  }

  function openEdit(cat: Category) {
    setEditing(cat);
    setName(cat.name);
    setDescription(cat.description || "");
    setDisplayOrder(cat.display_order);
    setIcon(cat.icon || "");
    setDialogOpen(true);
  }

  async function handleSave() {
    setSaving(true);
    try {
      if (editing) {
        const body: CategoryUpdate = {
          name,
          description: description || null,
          display_order: displayOrder,
          icon: icon || null,
        };
        await menuApi.updateCategory(editing.id, body);
      } else {
        const body: CategoryCreate = {
          name,
          description: description || null,
          display_order: displayOrder,
          icon: icon || null,
        };
        await menuApi.createCategory(body);
      }
      setDialogOpen(false);
      clearMenu();
      await load();
    } catch {
      // TODO: toast error
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive(cat: Category) {
    try {
      await menuApi.updateCategory(cat.id, { is_active: !cat.is_active });
      clearMenu();
      await load();
    } catch {
      // ignore
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await menuApi.deleteCategory(deleteTarget.id);
      setDeleteTarget(null);
      clearMenu();
      await load();
    } catch {
      // ignore
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-secondary-500">
          {categories.length} categor{categories.length === 1 ? "y" : "ies"}
        </p>
        <Button onClick={openCreate} className="min-h-touch gap-2">
          <Plus className="h-4 w-4" />
          Add Category
        </Button>
      </div>

      {categories.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-12">
            <p className="text-secondary-400">No categories yet</p>
            <Button variant="outline" onClick={openCreate}>
              Create your first category
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {categories.map((cat) => (
            <Card key={cat.id}>
              <CardContent className="flex items-center gap-4 p-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50 text-lg">
                  {cat.icon || "🍽️"}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-secondary-900 truncate">
                    {cat.name}
                  </p>
                  {cat.description && (
                    <p className="text-sm text-secondary-400 truncate">
                      {cat.description}
                    </p>
                  )}
                </div>
                <Badge variant={cat.is_active ? "success" : "secondary"}>
                  {cat.is_active ? "Active" : "Inactive"}
                </Badge>
                <Switch
                  checked={cat.is_active}
                  onCheckedChange={() => handleToggleActive(cat)}
                />
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => openEdit(cat)}
                  className="min-h-touch min-w-touch"
                >
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setDeleteTarget(cat)}
                  className="min-h-touch min-w-touch text-danger-600 hover:text-danger-700"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editing ? "Edit Category" : "New Category"}
            </DialogTitle>
            <DialogDescription>
              {editing
                ? "Update the category details below."
                : "Fill in the details to create a new menu category."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="cat-name">Name *</Label>
              <Input
                id="cat-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. BBQ & Grills"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cat-desc">Description</Label>
              <Textarea
                id="cat-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="cat-order">Display Order</Label>
                <Input
                  id="cat-order"
                  type="number"
                  value={displayOrder}
                  onChange={(e) => setDisplayOrder(Number(e.target.value))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cat-icon">Icon (emoji)</Label>
                <Input
                  id="cat-icon"
                  value={icon}
                  onChange={(e) => setIcon(e.target.value)}
                  placeholder="🔥"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDialogOpen(false)}
              className="min-h-touch"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={!name.trim() || saving}
              className="min-h-touch"
            >
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {editing ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Category</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &ldquo;{deleteTarget?.name}
              &rdquo;? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteTarget(null)}
              className="min-h-touch"
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              className="min-h-touch"
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ==========================================================================
   Items Tab
   ========================================================================== */

function ItemsTab() {
  const clearMenu = useMenuStore((s) => s.clearMenu);
  const [categories, setCategories] = useState<Category[]>([]);
  const [items, setItems] = useState<MenuItem[]>([]);
  const [modifierGroups, setModifierGroups] = useState<ModifierGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<MenuItem | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<MenuItem | null>(null);
  const [filterCategory, setFilterCategory] = useState("");

  // Form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [priceRupees, setPriceRupees] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [isAvailable, setIsAvailable] = useState(true);
  const [displayOrder, setDisplayOrder] = useState(0);
  const [prepTime, setPrepTime] = useState("");
  const [selectedModifierGroupIds, setSelectedModifierGroupIds] = useState<
    string[]
  >([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [cats, itms, mgs] = await Promise.all([
        menuApi.fetchCategories(),
        menuApi.fetchMenuItems(
          filterCategory ? { category_id: filterCategory } : undefined
        ),
        menuApi.fetchModifierGroups(),
      ]);
      setCategories(cats);
      setItems(itms);
      setModifierGroups(mgs);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [filterCategory]);

  useEffect(() => {
    load();
  }, [load]);

  function openCreate() {
    setEditing(null);
    setName("");
    setDescription("");
    setPriceRupees("");
    setCategoryId(categories[0]?.id || "");
    setIsAvailable(true);
    setDisplayOrder(items.length);
    setPrepTime("");
    setSelectedModifierGroupIds([]);
    setDialogOpen(true);
  }

  function openEdit(item: MenuItem) {
    setEditing(item);
    setName(item.name);
    setDescription(item.description || "");
    setPriceRupees(String(paisaToRupees(item.price)));
    setCategoryId(item.category_id);
    setIsAvailable(item.is_available);
    setDisplayOrder(item.display_order);
    setPrepTime(
      item.preparation_time_minutes != null
        ? String(item.preparation_time_minutes)
        : ""
    );
    setSelectedModifierGroupIds(
      item.modifier_groups?.map((mg) => mg.id) || []
    );
    setDialogOpen(true);
  }

  async function handleSave() {
    const price = rupeesToPaisa(Number(priceRupees) || 0);
    if (!name.trim() || !categoryId || price <= 0) return;

    setSaving(true);
    try {
      const base = {
        name,
        description: description || null,
        price,
        category_id: categoryId,
        is_available: isAvailable,
        display_order: displayOrder,
        preparation_time_minutes: prepTime ? Number(prepTime) : null,
        modifier_group_ids: selectedModifierGroupIds,
      };

      if (editing) {
        await menuApi.updateMenuItem(editing.id, base as MenuItemUpdate);
      } else {
        await menuApi.createMenuItem(base as MenuItemCreate);
      }
      setDialogOpen(false);
      clearMenu();
      await load();
    } catch {
      // TODO: toast
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleAvailable(item: MenuItem) {
    try {
      await menuApi.updateMenuItem(item.id, {
        is_available: !item.is_available,
      });
      clearMenu();
      await load();
    } catch {
      // ignore
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await menuApi.deleteMenuItem(deleteTarget.id);
      setDeleteTarget(null);
      clearMenu();
      await load();
    } catch {
      // ignore
    }
  }

  function toggleModifierGroup(id: string) {
    setSelectedModifierGroupIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  const categoryName = (id: string) =>
    categories.find((c) => c.id === id)?.name || "Unknown";

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            className="w-48"
          >
            <option value="">All Categories</option>
            {categories.map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.name}
              </option>
            ))}
          </Select>
          <p className="text-sm text-secondary-500">
            {items.length} item{items.length !== 1 && "s"}
          </p>
        </div>
        <Button onClick={openCreate} className="min-h-touch gap-2">
          <Plus className="h-4 w-4" />
          Add Item
        </Button>
      </div>

      {items.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-12">
            <p className="text-secondary-400">No menu items yet</p>
            <Button variant="outline" onClick={openCreate}>
              Create your first item
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <Card key={item.id}>
              <CardContent className="space-y-3 p-4">
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-secondary-900 truncate">
                      {item.name}
                    </p>
                    <p className="text-sm text-secondary-400 truncate">
                      {categoryName(item.category_id)}
                    </p>
                  </div>
                  <p className="text-lg font-bold text-primary-600 ml-2 whitespace-nowrap">
                    {formatPKR(item.price)}
                  </p>
                </div>
                {item.description && (
                  <p className="text-sm text-secondary-500 line-clamp-2">
                    {item.description}
                  </p>
                )}
                <div className="flex items-center gap-2">
                  <Badge
                    variant={item.is_available ? "success" : "destructive"}
                  >
                    {item.is_available ? "Available" : "Unavailable"}
                  </Badge>
                  {item.modifier_groups && item.modifier_groups.length > 0 && (
                    <Badge variant="outline">
                      {item.modifier_groups.length} modifier
                      {item.modifier_groups.length !== 1 && "s"}
                    </Badge>
                  )}
                  {item.preparation_time_minutes && (
                    <Badge variant="secondary">
                      {item.preparation_time_minutes} min
                    </Badge>
                  )}
                </div>
                <div className="flex items-center justify-between border-t border-secondary-100 pt-3">
                  <Switch
                    checked={item.is_available}
                    onCheckedChange={() => handleToggleAvailable(item)}
                  />
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => openEdit(item)}
                      className="min-h-touch min-w-touch"
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setDeleteTarget(item)}
                      className="min-h-touch min-w-touch text-danger-600 hover:text-danger-700"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>
              {editing ? "Edit Item" : "New Menu Item"}
            </DialogTitle>
            <DialogDescription>
              {editing
                ? "Update the menu item details."
                : "Fill in the details to add a new menu item."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
            <div className="space-y-2">
              <Label htmlFor="item-name">Name *</Label>
              <Input
                id="item-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Chicken Biryani"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="item-desc">Description</Label>
              <Textarea
                id="item-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="item-price">Price (PKR) *</Label>
                <Input
                  id="item-price"
                  type="number"
                  min="0"
                  step="1"
                  value={priceRupees}
                  onChange={(e) => setPriceRupees(e.target.value)}
                  placeholder="650"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="item-cat">Category *</Label>
                <Select
                  id="item-cat"
                  value={categoryId}
                  onChange={(e) => setCategoryId(e.target.value)}
                >
                  <option value="">Select category</option>
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.name}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="item-order">Display Order</Label>
                <Input
                  id="item-order"
                  type="number"
                  value={displayOrder}
                  onChange={(e) => setDisplayOrder(Number(e.target.value))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="item-prep">Prep Time (minutes)</Label>
                <Input
                  id="item-prep"
                  type="number"
                  min="0"
                  value={prepTime}
                  onChange={(e) => setPrepTime(e.target.value)}
                  placeholder="15"
                />
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Switch
                checked={isAvailable}
                onCheckedChange={setIsAvailable}
              />
              <Label>Available for ordering</Label>
            </div>
            {modifierGroups.length > 0 && (
              <div className="space-y-2">
                <Label>Modifier Groups</Label>
                <div className="space-y-2 rounded-lg border border-secondary-200 p-3">
                  {modifierGroups.map((mg) => (
                    <label
                      key={mg.id}
                      className="flex items-center gap-3 cursor-pointer min-h-touch"
                    >
                      <input
                        type="checkbox"
                        checked={selectedModifierGroupIds.includes(mg.id)}
                        onChange={() => toggleModifierGroup(mg.id)}
                        className="h-4 w-4 rounded border-secondary-300 text-primary-600 focus:ring-primary-500"
                      />
                      <span className="text-sm text-secondary-700">
                        {mg.name}
                      </span>
                      {mg.required && (
                        <Badge variant="warning" className="text-[10px]">
                          Required
                        </Badge>
                      )}
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDialogOpen(false)}
              className="min-h-touch"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={
                !name.trim() ||
                !categoryId ||
                !priceRupees ||
                Number(priceRupees) <= 0 ||
                saving
              }
              className="min-h-touch"
            >
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {editing ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Menu Item</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &ldquo;{deleteTarget?.name}
              &rdquo;? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteTarget(null)}
              className="min-h-touch"
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              className="min-h-touch"
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ==========================================================================
   Modifier Groups Tab
   ========================================================================== */

function ModifierGroupsTab() {
  const clearMenu = useMenuStore((s) => s.clearMenu);
  const [groups, setGroups] = useState<ModifierGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<ModifierGroup | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ModifierGroup | null>(null);
  const [expandedGroupId, setExpandedGroupId] = useState<string | null>(null);

  // Group form state
  const [name, setName] = useState("");
  const [required, setRequired] = useState(false);
  const [minSelections, setMinSelections] = useState(0);
  const [maxSelections, setMaxSelections] = useState(1);
  const [displayOrder, setDisplayOrder] = useState(0);

  // Modifier form state
  const [modDialogOpen, setModDialogOpen] = useState(false);
  const [modGroupId, setModGroupId] = useState("");
  const [editingMod, setEditingMod] = useState<ModifierOption | null>(null);
  const [modName, setModName] = useState("");
  const [modPriceRupees, setModPriceRupees] = useState("");
  const [modOrder, setModOrder] = useState(0);
  const [modSaving, setModSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await menuApi.fetchModifierGroups();
      setGroups(data);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function openCreate() {
    setEditing(null);
    setName("");
    setRequired(false);
    setMinSelections(0);
    setMaxSelections(1);
    setDisplayOrder(groups.length);
    setDialogOpen(true);
  }

  function openEdit(group: ModifierGroup) {
    setEditing(group);
    setName(group.name);
    setRequired(group.required);
    setMinSelections(group.min_selections);
    setMaxSelections(group.max_selections);
    setDisplayOrder(group.display_order);
    setDialogOpen(true);
  }

  async function handleSave() {
    setSaving(true);
    try {
      if (editing) {
        const body: ModifierGroupUpdate = {
          name,
          required,
          min_selections: minSelections,
          max_selections: maxSelections,
          display_order: displayOrder,
        };
        await menuApi.updateModifierGroup(editing.id, body);
      } else {
        const body: ModifierGroupCreate = {
          name,
          required,
          min_selections: minSelections,
          max_selections: maxSelections,
          display_order: displayOrder,
        };
        await menuApi.createModifierGroup(body);
      }
      setDialogOpen(false);
      clearMenu();
      await load();
    } catch {
      // TODO: toast
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive(group: ModifierGroup) {
    try {
      await menuApi.updateModifierGroup(group.id, {
        is_active: !group.is_active,
      });
      clearMenu();
      await load();
    } catch {
      // ignore
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await menuApi.deleteModifierGroup(deleteTarget.id);
      setDeleteTarget(null);
      clearMenu();
      await load();
    } catch {
      // ignore
    }
  }

  // Modifier CRUD
  function openCreateMod(groupId: string) {
    setEditingMod(null);
    setModGroupId(groupId);
    setModName("");
    setModPriceRupees("0");
    const group = groups.find((g) => g.id === groupId);
    setModOrder(group?.modifiers?.length || 0);
    setModDialogOpen(true);
  }

  function openEditMod(modifier: ModifierOption) {
    setEditingMod(modifier);
    setModGroupId(modifier.group_id);
    setModName(modifier.name);
    setModPriceRupees(String(paisaToRupees(modifier.price_adjustment)));
    setModOrder(modifier.display_order);
    setModDialogOpen(true);
  }

  async function handleSaveMod() {
    setModSaving(true);
    try {
      const priceAdj = rupeesToPaisa(Number(modPriceRupees) || 0);
      if (editingMod) {
        const body: ModifierUpdate = {
          name: modName,
          price_adjustment: priceAdj,
          display_order: modOrder,
        };
        await menuApi.updateModifier(editingMod.id, body);
      } else {
        const body: ModifierCreate = {
          name: modName,
          price_adjustment: priceAdj,
          display_order: modOrder,
        };
        await menuApi.createModifier(modGroupId, body);
      }
      setModDialogOpen(false);
      clearMenu();
      await load();
    } catch {
      // TODO: toast
    } finally {
      setModSaving(false);
    }
  }

  async function handleDeleteMod(modId: string) {
    try {
      await menuApi.deleteModifier(modId);
      clearMenu();
      await load();
    } catch {
      // ignore
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-secondary-500">
          {groups.length} group{groups.length !== 1 && "s"}
        </p>
        <Button onClick={openCreate} className="min-h-touch gap-2">
          <Plus className="h-4 w-4" />
          Add Modifier Group
        </Button>
      </div>

      {groups.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-12">
            <p className="text-secondary-400">No modifier groups yet</p>
            <Button variant="outline" onClick={openCreate}>
              Create your first modifier group
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {groups.map((group) => {
            const isExpanded = expandedGroupId === group.id;
            return (
              <Card key={group.id}>
                <CardContent className="p-0">
                  {/* Group Header */}
                  <div className="flex items-center gap-4 p-4">
                    <button
                      className="min-h-touch min-w-touch flex items-center justify-center"
                      onClick={() =>
                        setExpandedGroupId(isExpanded ? null : group.id)
                      }
                    >
                      {isExpanded ? (
                        <ChevronDown className="h-5 w-5 text-secondary-400" />
                      ) : (
                        <ChevronRight className="h-5 w-5 text-secondary-400" />
                      )}
                    </button>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-secondary-900">
                        {group.name}
                      </p>
                      <p className="text-sm text-secondary-400">
                        {group.modifiers?.length || 0} option
                        {(group.modifiers?.length || 0) !== 1 && "s"}
                        {" · "}
                        {group.required ? "Required" : "Optional"}
                        {" · "}
                        {group.min_selections}-{group.max_selections} selections
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={group.is_active ? "success" : "secondary"}
                      >
                        {group.is_active ? "Active" : "Inactive"}
                      </Badge>
                      <Switch
                        checked={group.is_active}
                        onCheckedChange={() => handleToggleActive(group)}
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEdit(group)}
                        className="min-h-touch min-w-touch"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeleteTarget(group)}
                        className="min-h-touch min-w-touch text-danger-600 hover:text-danger-700"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  {/* Expanded Modifiers List */}
                  {isExpanded && (
                    <div className="border-t border-secondary-100 bg-secondary-50 p-4 space-y-2">
                      {group.modifiers?.map((mod) => (
                        <div
                          key={mod.id}
                          className="flex items-center gap-3 rounded-lg bg-white p-3"
                        >
                          <span className="flex-1 text-sm text-secondary-700">
                            {mod.name}
                          </span>
                          {mod.price_adjustment > 0 && (
                            <Badge variant="outline">
                              +{formatPKR(mod.price_adjustment)}
                            </Badge>
                          )}
                          <Badge
                            variant={
                              mod.is_available ? "success" : "destructive"
                            }
                          >
                            {mod.is_available ? "Available" : "Unavailable"}
                          </Badge>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditMod(mod)}
                          >
                            <Pencil className="h-3 w-3" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-danger-600"
                            onClick={() => handleDeleteMod(mod.id)}
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      ))}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openCreateMod(group.id)}
                        className="mt-2 gap-1"
                      >
                        <Plus className="h-3 w-3" />
                        Add Option
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create / Edit Group Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editing ? "Edit Modifier Group" : "New Modifier Group"}
            </DialogTitle>
            <DialogDescription>
              {editing
                ? "Update the modifier group settings."
                : "Create a new modifier group (e.g. Spice Level, Drink Size)."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="mg-name">Name *</Label>
              <Input
                id="mg-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Spice Level"
              />
            </div>
            <div className="flex items-center gap-3">
              <Switch checked={required} onCheckedChange={setRequired} />
              <Label>Required (customer must select)</Label>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="mg-min">Min Selections</Label>
                <Input
                  id="mg-min"
                  type="number"
                  min="0"
                  value={minSelections}
                  onChange={(e) => setMinSelections(Number(e.target.value))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="mg-max">Max Selections</Label>
                <Input
                  id="mg-max"
                  type="number"
                  min="1"
                  value={maxSelections}
                  onChange={(e) => setMaxSelections(Number(e.target.value))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="mg-order">Display Order</Label>
                <Input
                  id="mg-order"
                  type="number"
                  value={displayOrder}
                  onChange={(e) => setDisplayOrder(Number(e.target.value))}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDialogOpen(false)}
              className="min-h-touch"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={!name.trim() || saving}
              className="min-h-touch"
            >
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {editing ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Group Confirmation */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Modifier Group</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &ldquo;{deleteTarget?.name}
              &rdquo; and all its modifiers? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteTarget(null)}
              className="min-h-touch"
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              className="min-h-touch"
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create / Edit Modifier Dialog */}
      <Dialog open={modDialogOpen} onOpenChange={setModDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingMod ? "Edit Modifier" : "New Modifier Option"}
            </DialogTitle>
            <DialogDescription>
              {editingMod
                ? "Update this modifier option."
                : "Add a new option to this modifier group."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="mod-name">Name *</Label>
              <Input
                id="mod-name"
                value={modName}
                onChange={(e) => setModName(e.target.value)}
                placeholder="e.g. Extra Spicy"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="mod-price">Price Adjustment (PKR)</Label>
                <Input
                  id="mod-price"
                  type="number"
                  min="0"
                  step="1"
                  value={modPriceRupees}
                  onChange={(e) => setModPriceRupees(e.target.value)}
                  placeholder="0"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="mod-order">Display Order</Label>
                <Input
                  id="mod-order"
                  type="number"
                  value={modOrder}
                  onChange={(e) => setModOrder(Number(e.target.value))}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setModDialogOpen(false)}
              className="min-h-touch"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSaveMod}
              disabled={!modName.trim() || modSaving}
              className="min-h-touch"
            >
              {modSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {editingMod ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default MenuManagementPage;
