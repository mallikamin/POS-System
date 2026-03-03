import { useEffect, useState } from "react";
import { Loader2, Plus, Tag, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { formatPKR } from "@/utils/currency";
import {
  fetchDiscountTypes,
  createDiscountType,
  updateDiscountType,
  deleteDiscountType,
  type DiscountType,
} from "@/services/discountsApi";

function DiscountTypesPage() {
  const { toast } = useToast();
  const [types, setTypes] = useState<DiscountType[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [saving, setSaving] = useState(false);

  // Create form
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"percent" | "fixed">("percent");
  const [value, setValue] = useState("");

  useEffect(() => {
    void loadTypes();
  }, []);

  async function loadTypes() {
    try {
      setLoading(true);
      const data = await fetchDiscountTypes();
      setTypes(data);
    } catch {
      toast({ title: "Failed to load discount types", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    if (!code || !name || !value) return;
    setSaving(true);
    try {
      const numValue =
        kind === "percent"
          ? Math.round(parseFloat(value) * 100) // Convert % to bps
          : Math.round(parseFloat(value) * 100); // Convert PKR to paisa
      await createDiscountType({ code, name, kind, value: numValue });
      toast({ title: "Discount type created", variant: "success" });
      setShowCreate(false);
      setCode("");
      setName("");
      setValue("");
      await loadTypes();
    } catch {
      toast({ title: "Failed to create discount type", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(dt: DiscountType) {
    try {
      await updateDiscountType(dt.id, { is_active: !dt.is_active });
      await loadTypes();
    } catch {
      toast({ title: "Failed to update", variant: "destructive" });
    }
  }

  async function handleDelete(dt: DiscountType) {
    if (!confirm(`Delete discount type "${dt.name}"?`)) return;
    try {
      await deleteDiscountType(dt.id);
      toast({ title: "Deleted", variant: "success" });
      await loadTypes();
    } catch {
      toast({ title: "Failed to delete", variant: "destructive" });
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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Tag className="h-7 w-7 text-primary-600" />
          <h1 className="text-pos-2xl font-bold text-secondary-900">
            Discount Types
          </h1>
        </div>
        <Button onClick={() => setShowCreate(true)} className="gap-2 min-h-[48px]">
          <Plus className="h-4 w-4" />
          Add Discount Type
        </Button>
      </div>

      {types.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-secondary-400">
            No discount types configured. Add one to get started.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {types.map((dt) => (
            <Card key={dt.id}>
              <CardContent className="pt-4 space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-semibold text-secondary-900">{dt.name}</p>
                    <p className="text-sm text-secondary-500">Code: {dt.code}</p>
                  </div>
                  <Badge variant={dt.is_active ? "default" : "secondary"}>
                    {dt.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
                <div className="text-sm text-secondary-600">
                  {dt.kind === "percent"
                    ? `${dt.value / 100}% discount`
                    : `${formatPKR(dt.value)} fixed discount`}
                </div>
                <div className="flex items-center justify-between border-t border-secondary-100 pt-3">
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={dt.is_active}
                      onCheckedChange={() => void handleToggle(dt)}
                    />
                    <span className="text-sm text-secondary-500">
                      {dt.is_active ? "Enabled" : "Disabled"}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void handleDelete(dt)}
                    className="text-danger-500 hover:text-danger-700"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Discount Type</DialogTitle>
            <DialogDescription>
              Add a new discount category (e.g., Bank Promo, ESR, Customer Loyalty).
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Code</Label>
              <Input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="e.g. bank_promo"
              />
            </div>
            <div className="space-y-2">
              <Label>Name</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Bank Promotion"
              />
            </div>
            <div className="space-y-2">
              <Label>Type</Label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setKind("percent")}
                  className={`rounded-lg border-2 p-3 text-sm ${
                    kind === "percent"
                      ? "border-primary-500 bg-primary-50"
                      : "border-secondary-200"
                  }`}
                >
                  Percentage
                </button>
                <button
                  type="button"
                  onClick={() => setKind("fixed")}
                  className={`rounded-lg border-2 p-3 text-sm ${
                    kind === "fixed"
                      ? "border-primary-500 bg-primary-50"
                      : "border-secondary-200"
                  }`}
                >
                  Fixed Amount
                </button>
              </div>
            </div>
            <div className="space-y-2">
              <Label>{kind === "percent" ? "Percentage (%)" : "Amount (PKR)"}</Label>
              <Input
                type="number"
                min={0}
                step={kind === "percent" ? 0.5 : 1}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder={kind === "percent" ? "e.g. 10" : "e.g. 500"}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={saving || !code || !name || !value}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default DiscountTypesPage;
