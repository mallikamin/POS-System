import { useEffect, useState, useCallback } from "react";
import { isAxiosError } from "axios";
import { Users, Plus, Pencil, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { useToast } from "@/hooks/use-toast";
import api from "@/lib/axios";

interface StaffRole {
  id: string;
  name: string;
}

interface StaffMember {
  id: string;
  email: string;
  full_name: string;
  role: StaffRole;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

interface PaginatedStaff {
  items: StaffMember[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

function StaffManagementPage() {
  const { toast } = useToast();
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [roles, setRoles] = useState<StaffRole[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<StaffMember | null>(null);
  const [saving, setSaving] = useState(false);

  // Create form
  const [cName, setCName] = useState("");
  const [cEmail, setCEmail] = useState("");
  const [cPassword, setCPassword] = useState("");
  const [cPin, setCPin] = useState("");
  const [cRole, setCRole] = useState("");

  // Edit form
  const [eName, setEName] = useState("");
  const [eEmail, setEEmail] = useState("");
  const [eRole, setERole] = useState("");

  const fetchStaff = useCallback(async (q?: string) => {
    try {
      setLoading(true);
      const params = new URLSearchParams({ page: "1", page_size: "50" });
      if (q) params.set("search", q);
      const { data } = await api.get<PaginatedStaff>(`/staff?${params}`);
      setStaff(data.items);
    } catch {
      toast({ title: "Failed to load staff", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const fetchRoles = useCallback(async () => {
    try {
      const { data } = await api.get<StaffRole[]>("/staff/roles");
      setRoles(data);
    } catch {
      // roles are optional for display
    }
  }, []);

  useEffect(() => {
    fetchStaff();
    fetchRoles();
  }, [fetchStaff, fetchRoles]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => fetchStaff(search), 300);
    return () => clearTimeout(timer);
  }, [search, fetchStaff]);

  function openCreate() {
    setCName("");
    setCEmail("");
    setCPassword("");
    setCPin("");
    setCRole(roles[0]?.id ?? "");
    setCreateOpen(true);
  }

  function openEdit(member: StaffMember) {
    setEditTarget(member);
    setEName(member.full_name);
    setEEmail(member.email);
    setERole(member.role.id);
    setEditOpen(true);
  }

  async function handleCreate() {
    if (!cName || !cEmail || !cPassword || !cRole) {
      toast({ title: "All fields required", variant: "destructive" });
      return;
    }
    try {
      setSaving(true);
      await api.post("/staff", {
        full_name: cName,
        email: cEmail,
        password: cPassword,
        pin_code: cPin || undefined,
        role_id: cRole,
      });
      toast({ title: "Staff member created", variant: "success" });
      setCreateOpen(false);
      fetchStaff(search);
    } catch (err: unknown) {
      const msg = isAxiosError(err) ? (err.response?.data?.detail ?? "Failed to create staff") : "Failed to create staff";
      toast({ title: msg, variant: "destructive" });
    } finally {
      setSaving(false);
    }
  }

  async function handleEdit() {
    if (!editTarget) return;
    try {
      setSaving(true);
      await api.patch(`/staff/${editTarget.id}`, {
        full_name: eName,
        email: eEmail,
        role_id: eRole,
      });
      toast({ title: "Staff member updated", variant: "success" });
      setEditOpen(false);
      fetchStaff(search);
    } catch (err: unknown) {
      const msg = isAxiosError(err) ? (err.response?.data?.detail ?? "Failed to update") : "Failed to update";
      toast({ title: msg, variant: "destructive" });
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(member: StaffMember) {
    try {
      await api.patch(`/staff/${member.id}`, {
        is_active: !member.is_active,
      });
      toast({
        title: member.is_active ? "Staff deactivated" : "Staff activated",
        variant: "success",
      });
      fetchStaff(search);
    } catch {
      toast({ title: "Failed to toggle status", variant: "destructive" });
    }
  }

  function formatDate(iso: string | null): string {
    if (!iso) return "Never";
    return new Intl.DateTimeFormat("en-PK", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Users className="h-7 w-7 text-primary-600" />
          <h1 className="text-pos-2xl font-bold text-secondary-900">
            Staff Management
          </h1>
        </div>
        <Button onClick={openCreate} className="min-h-[48px] gap-2">
          <Plus className="h-4 w-4" />
          Add Staff
        </Button>
      </div>

      {/* Search */}
      <Input
        placeholder="Search by name or email..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="min-h-[48px] max-w-md"
      />

      {/* Staff Table */}
      <Card>
        <CardContent className="pt-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
            </div>
          ) : staff.length === 0 ? (
            <div className="py-12 text-center text-secondary-500">
              No staff members found.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-pos-sm">
                <thead>
                  <tr className="border-b text-secondary-500">
                    <th className="pb-3 font-medium">Name</th>
                    <th className="pb-3 font-medium">Email</th>
                    <th className="pb-3 font-medium">Role</th>
                    <th className="pb-3 font-medium">Status</th>
                    <th className="pb-3 font-medium">Last Login</th>
                    <th className="pb-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {staff.map((m) => (
                    <tr
                      key={m.id}
                      className="border-b last:border-0 hover:bg-secondary-50"
                    >
                      <td className="py-3 font-medium text-secondary-900">
                        {m.full_name}
                      </td>
                      <td className="py-3 text-secondary-600">{m.email}</td>
                      <td className="py-3">
                        <Badge variant="outline">{m.role.name}</Badge>
                      </td>
                      <td className="py-3">
                        <Badge
                          className={
                            m.is_active
                              ? "bg-green-100 text-green-800"
                              : "bg-red-100 text-red-800"
                          }
                        >
                          {m.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </td>
                      <td className="py-3 text-secondary-500">
                        {formatDate(m.last_login_at)}
                      </td>
                      <td className="py-3">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="min-h-[40px]"
                            onClick={() => openEdit(m)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Switch
                            checked={m.is_active}
                            onCheckedChange={() => toggleActive(m)}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Staff Member</DialogTitle>
            <DialogDescription>
              Create a new staff account with role assignment.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label>Full Name</Label>
              <Input
                value={cName}
                onChange={(e) => setCName(e.target.value)}
                className="min-h-[48px]"
              />
            </div>
            <div className="space-y-2">
              <Label>Email</Label>
              <Input
                type="email"
                value={cEmail}
                onChange={(e) => setCEmail(e.target.value)}
                className="min-h-[48px]"
              />
            </div>
            <div className="space-y-2">
              <Label>Password</Label>
              <Input
                type="password"
                value={cPassword}
                onChange={(e) => setCPassword(e.target.value)}
                className="min-h-[48px]"
              />
            </div>
            <div className="space-y-2">
              <Label>PIN (optional, 4-6 digits)</Label>
              <Input
                value={cPin}
                onChange={(e) => setCPin(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="e.g. 1234"
                className="min-h-[48px]"
              />
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <select
                value={cRole}
                onChange={(e) => setCRole(e.target.value)}
                className="min-h-[48px] w-full rounded-md border border-secondary-300 bg-white px-3 py-2 text-pos-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="">Select role...</option>
                {roles.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={saving} className="gap-2">
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Staff Member</DialogTitle>
            <DialogDescription>
              Update staff profile and role assignment.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label>Full Name</Label>
              <Input
                value={eName}
                onChange={(e) => setEName(e.target.value)}
                className="min-h-[48px]"
              />
            </div>
            <div className="space-y-2">
              <Label>Email</Label>
              <Input
                type="email"
                value={eEmail}
                onChange={(e) => setEEmail(e.target.value)}
                className="min-h-[48px]"
              />
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <select
                value={eRole}
                onChange={(e) => setERole(e.target.value)}
                className="min-h-[48px] w-full rounded-md border border-secondary-300 bg-white px-3 py-2 text-pos-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {roles.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleEdit} disabled={saving} className="gap-2">
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Update
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default StaffManagementPage;
