import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import api from "@/lib/axios";

interface Permission {
  id: string;
  code: string;
  description: string | null;
}

interface Role {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  permissions: Permission[];
}

function RoleManagementPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [formName, setFormName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formPermIds, setFormPermIds] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);

  async function loadData() {
    setLoading(true);
    try {
      const [rolesRes, permsRes] = await Promise.all([
        api.get<Role[]>("/staff/roles"),
        api.get<Permission[]>("/staff/permissions"),
      ]);
      setRoles(rolesRes.data);
      setPermissions(permsRes.data);
    } catch {
      // toast handled by global interceptor
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, []);

  function openCreate() {
    setEditingRole(null);
    setFormName("");
    setFormDescription("");
    setFormPermIds(new Set());
    setDialogOpen(true);
  }

  function openEdit(role: Role) {
    setEditingRole(role);
    setFormName(role.name);
    setFormDescription(role.description ?? "");
    setFormPermIds(new Set(role.permissions.map((p) => p.id)));
    setDialogOpen(true);
  }

  function togglePerm(id: string) {
    setFormPermIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleSave() {
    setSaving(true);
    try {
      const payload = {
        name: formName,
        description: formDescription || null,
        permission_ids: Array.from(formPermIds),
      };
      if (editingRole) {
        await api.patch(`/staff/roles/${editingRole.id}`, payload);
      } else {
        await api.post("/staff/roles", payload);
      }
      setDialogOpen(false);
      await loadData();
    } catch {
      // global interceptor
    } finally {
      setSaving(false);
    }
  }

  // Group permissions by prefix (e.g. "order.create" → "order")
  const permGroups = permissions.reduce<Record<string, Permission[]>>((acc, p) => {
    const group = p.code.split(".")[0] ?? "other";
    (acc[group] ??= []).push(p);
    return acc;
  }, {});

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Role Management</h1>
          <p className="text-sm text-secondary-500 mt-1">
            Create and manage roles with granular permissions
          </p>
        </div>
        <Button onClick={openCreate}>Create Role</Button>
      </div>

      {/* Roles Table */}
      <div className="rounded-lg border border-secondary-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-secondary-200 bg-secondary-50">
              <th className="px-4 py-3 text-left font-semibold text-secondary-700">Role</th>
              <th className="px-4 py-3 text-left font-semibold text-secondary-700">Description</th>
              <th className="px-4 py-3 text-left font-semibold text-secondary-700">Permissions</th>
              <th className="px-4 py-3 text-right font-semibold text-secondary-700">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-secondary-100">
            {roles.map((role) => (
              <tr key={role.id} className="hover:bg-secondary-50">
                <td className="px-4 py-3 font-medium text-secondary-900">{role.name}</td>
                <td className="px-4 py-3 text-secondary-600">{role.description ?? "-"}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {role.permissions.length === 0 ? (
                      <span className="text-secondary-400">None</span>
                    ) : (
                      role.permissions.map((p) => (
                        <span
                          key={p.id}
                          className="rounded bg-blue-50 px-2 py-0.5 text-xs text-blue-700"
                        >
                          {p.code}
                        </span>
                      ))
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <Button size="sm" variant="outline" onClick={() => openEdit(role)}>
                    Edit
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingRole ? "Edit Role" : "Create Role"}</DialogTitle>
            <DialogDescription>
              {editingRole
                ? "Update the role name, description, and permissions."
                : "Define a new role with specific permissions."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <label className="text-sm font-medium text-secondary-700">Name</label>
              <input
                type="text"
                className="mt-1 w-full rounded border border-secondary-300 px-3 py-2 text-sm"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g. supervisor"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-secondary-700">Description</label>
              <input
                type="text"
                className="mt-1 w-full rounded border border-secondary-300 px-3 py-2 text-sm"
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                placeholder="Optional description"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-secondary-700 mb-2 block">
                Permissions
              </label>
              <div className="space-y-3 max-h-60 overflow-y-auto rounded border border-secondary-200 p-3">
                {Object.entries(permGroups).map(([group, perms]) => (
                  <div key={group}>
                    <p className="text-xs font-semibold uppercase tracking-wide text-secondary-500 mb-1">
                      {group}
                    </p>
                    <div className="space-y-1">
                      {perms.map((p) => (
                        <label
                          key={p.id}
                          className="flex items-center gap-2 cursor-pointer text-sm"
                        >
                          <input
                            type="checkbox"
                            checked={formPermIds.has(p.id)}
                            onChange={() => togglePerm(p.id)}
                            className="rounded border-secondary-300"
                          />
                          <span className="text-secondary-800">{p.code}</span>
                          {p.description && (
                            <span className="text-xs text-secondary-400">
                              — {p.description}
                            </span>
                          )}
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
                {permissions.length === 0 && (
                  <p className="text-sm text-secondary-400">No permissions defined yet.</p>
                )}
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
              disabled={saving || !formName.trim()}
              className="min-h-touch"
            >
              {saving ? "Saving..." : editingRole ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default RoleManagementPage;
