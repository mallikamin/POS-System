import { useCallback, useEffect, useState } from "react";
import {
  Loader2,
  Trash2,
  Pencil,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { useQuickBooksStore } from "@/stores/quickbooksStore";
import * as qbApi from "@/services/quickbooksApi";
import type { QBAccountMapping } from "@/types/quickbooks";

const MAPPING_TYPES = [
  "all",
  "income",
  "cogs",
  "tax_payable",
  "bank",
  "expense",
  "discount",
  "rounding",
  "cash_over_short",
  "tips",
  "service_charge",
  "delivery_fee",
  "foodpanda_commission",
] as const;

interface MappingsTabProps {
  isConnected: boolean;
}

export function MappingsTab({ isConnected }: MappingsTabProps) {
  const mappings = useQuickBooksStore((s) => s.mappings);
  const isLoading = useQuickBooksStore((s) => s.isLoadingMappings);
  const loadMappings = useQuickBooksStore((s) => s.loadMappings);

  const [filterType, setFilterType] = useState("all");
  const [editMapping, setEditMapping] = useState<QBAccountMapping | null>(null);
  const [deleteMapping, setDeleteMapping] = useState<QBAccountMapping | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationResult, setValidationResult] = useState<{
    valid: boolean;
    errors: string[];
  } | null>(null);

  // Edit form state
  const [editAccountName, setEditAccountName] = useState("");
  const [editAccountType, setEditAccountType] = useState("");

  const load = useCallback(() => {
    loadMappings(filterType === "all" ? undefined : filterType);
  }, [loadMappings, filterType]);

  useEffect(() => {
    if (isConnected) load();
  }, [isConnected, load]);

  function openEdit(m: QBAccountMapping) {
    setEditMapping(m);
    setEditAccountName(m.qb_account_name);
    setEditAccountType(m.qb_account_type);
  }

  async function handleSave() {
    if (!editMapping) return;
    setSaving(true);
    setError(null);
    try {
      await qbApi.updateMapping(editMapping.id, {
        qb_account_name: editAccountName,
        qb_account_type: editAccountType,
      });
      setEditMapping(null);
      load();
    } catch {
      setError("Failed to update mapping");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteMapping) return;
    setDeleting(true);
    setError(null);
    try {
      await qbApi.deleteMapping(deleteMapping.id);
      setDeleteMapping(null);
      load();
    } catch {
      setError("Failed to delete mapping");
    } finally {
      setDeleting(false);
    }
  }

  async function handleValidate() {
    setError(null);
    try {
      const result = await qbApi.validateMappings();
      setValidationResult(result);
    } catch {
      setError("Failed to validate mappings");
    }
  }

  if (!isConnected) {
    return (
      <div className="py-16 text-center">
        <p className="text-secondary-400">
          Connect to QuickBooks to view and manage account mappings.
        </p>
        <p className="text-sm text-secondary-300 mt-1">
          Use the Templates tab to browse mapping templates in simulation mode.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">
            dismiss
          </button>
        </div>
      )}

      {validationResult && (
        <div
          className={`rounded-lg px-4 py-3 text-sm ${
            validationResult.valid
              ? "bg-success-50 text-success-700"
              : "bg-danger-50 text-danger-700"
          }`}
        >
          <div className="flex items-center gap-2 font-medium">
            {validationResult.valid ? (
              <CheckCircle2 className="h-4 w-4" />
            ) : (
              <AlertCircle className="h-4 w-4" />
            )}
            {validationResult.valid
              ? "All required mappings are configured."
              : "Missing required mappings:"}
          </div>
          {validationResult.errors.length > 0 && (
            <ul className="mt-1 ml-6 list-disc">
              {validationResult.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
          <button
            onClick={() => setValidationResult(null)}
            className="mt-1 underline text-xs"
          >
            dismiss
          </button>
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center gap-3">
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="rounded-lg border border-secondary-200 bg-white px-3 py-2 text-sm"
        >
          {MAPPING_TYPES.map((t) => (
            <option key={t} value={t}>
              {t === "all" ? "All Types" : t.replace(/_/g, " ")}
            </option>
          ))}
        </select>

        <Button variant="outline" size="sm" onClick={load}>
          <RefreshCw className="h-4 w-4 mr-1" />
          Refresh
        </Button>

        <Button variant="outline" size="sm" onClick={handleValidate}>
          <CheckCircle2 className="h-4 w-4 mr-1" />
          Validate
        </Button>

        <span className="text-xs text-secondary-400 ml-auto">
          {mappings.length} mapping{mappings.length !== 1 && "s"}
        </span>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
        </div>
      ) : mappings.length === 0 ? (
        <div className="py-12 text-center text-sm text-secondary-400">
          No mappings found. Apply a template first.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-secondary-200">
          <table className="w-full text-sm">
            <thead className="bg-secondary-50 text-xs text-secondary-600">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Type</th>
                <th className="px-3 py-2 text-left font-medium">Account Name</th>
                <th className="px-3 py-2 text-left font-medium">QB Type</th>
                <th className="px-3 py-2 text-left font-medium">Sub-Type</th>
                <th className="px-3 py-2 text-center font-medium">Default</th>
                <th className="px-3 py-2 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-secondary-100">
              {mappings.map((m) => (
                <tr key={m.id} className="hover:bg-secondary-50">
                  <td className="px-3 py-2">
                    <Badge variant="outline" className="text-[10px]">
                      {m.mapping_type}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 font-medium text-secondary-900">
                    {m.qb_account_name}
                  </td>
                  <td className="px-3 py-2 text-secondary-600">{m.qb_account_type}</td>
                  <td className="px-3 py-2 text-secondary-500">
                    {m.qb_account_sub_type ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {m.is_default && (
                      <Badge variant="success" className="text-[9px]">
                        default
                      </Badge>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <div className="flex justify-end gap-1">
                      <button
                        onClick={() => openEdit(m)}
                        className="rounded p-1 text-secondary-400 hover:text-primary-600 hover:bg-primary-50"
                        aria-label="Edit"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => setDeleteMapping(m)}
                        className="rounded p-1 text-secondary-400 hover:text-danger-600 hover:bg-danger-50"
                        aria-label="Delete"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Edit Dialog */}
      <Dialog open={!!editMapping} onOpenChange={() => setEditMapping(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Edit Mapping</DialogTitle>
            <DialogDescription>
              Update the QB account details for this mapping.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Account Name</Label>
              <Input
                value={editAccountName}
                onChange={(e) => setEditAccountName(e.target.value)}
              />
            </div>
            <div>
              <Label>Account Type</Label>
              <Input
                value={editAccountType}
                onChange={(e) => setEditAccountType(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditMapping(null)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={saving || !editAccountName}>
              {saving && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <Dialog open={!!deleteMapping} onOpenChange={() => setDeleteMapping(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete Mapping</DialogTitle>
            <DialogDescription>
              Delete the mapping "{deleteMapping?.qb_account_name}" (
              {deleteMapping?.mapping_type})? This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteMapping(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
