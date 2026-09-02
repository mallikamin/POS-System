/**
 * Customers (back-office CRM)
 *
 * Martin (FZ LLC, 2026-09-02): "i didnt see a menu in back office with crm
 * options (where i can add customer name/phone/contact details/ trn if it is
 * a company)". Customer records always existed, but only the call-centre
 * screen could reach them. This is the admin view: list, search, create,
 * edit, and the two business fields (company name, TRN) that turn a receipt
 * to a company into a tax invoice it can reclaim VAT against.
 */

import { useCallback, useEffect, useState } from "react";
import { Contact, Loader2, Pencil, Plus, Search, Building2, ShieldAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { formatPKR } from "@/utils/currency";
import {
  createCustomer,
  listCustomers,
  updateCustomer,
} from "@/services/customerApi";
import type { CustomerCreate, CustomerResponse, CustomerUpdate } from "@/types/customer";

const PAGE_SIZE = 50;

export default function CustomersPage() {
  const { toast } = useToast();

  const [customers, setCustomers] = useState<CustomerResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<CustomerResponse | null>(null);
  const [saving, setSaving] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [isCompany, setIsCompany] = useState(false);
  const [companyName, setCompanyName] = useState("");
  const [trn, setTrn] = useState("");
  const [altContact, setAltContact] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [notes, setNotes] = useState("");
  const [riskFlag, setRiskFlag] = useState("normal");

  useEffect(() => {
    const handle = setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => clearTimeout(handle);
  }, [query]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listCustomers({
        q: debouncedQuery || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setCustomers(data.items);
      setTotal(data.total);
      setPages(Math.max(data.pages, 1));
    } catch {
      toast({ title: "Failed to load customers", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [debouncedQuery, page, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  // A new search always starts at the first page.
  useEffect(() => {
    setPage(1);
  }, [debouncedQuery]);

  function resetForm() {
    setName("");
    setPhone("");
    setEmail("");
    setIsCompany(false);
    setCompanyName("");
    setTrn("");
    setAltContact("");
    setAddress("");
    setCity("");
    setNotes("");
    setRiskFlag("normal");
  }

  function openCreate() {
    setEditing(null);
    resetForm();
    setDialogOpen(true);
  }

  function openEdit(customer: CustomerResponse) {
    setEditing(customer);
    setName(customer.name);
    setPhone(customer.phone);
    setEmail(customer.email ?? "");
    setIsCompany(!!(customer.company_name || customer.trn));
    setCompanyName(customer.company_name ?? "");
    setTrn(customer.trn ?? "");
    setAltContact(customer.alt_contact ?? "");
    setAddress(customer.default_address ?? "");
    setCity(customer.city ?? "");
    setNotes(customer.notes ?? "");
    setRiskFlag(customer.risk_flag ?? "normal");
    setDialogOpen(true);
  }

  const phoneDigits = phone.replace(/\D/g, "");
  const phoneError =
    phoneDigits.length > 0 && (phoneDigits.length < 7 || phoneDigits.length > 20)
      ? "Phone needs 7 to 20 digits."
      : null;
  const canSave = name.trim() !== "" && phoneDigits.length >= 7 && phoneError === null && !saving;

  async function handleSave() {
    if (!canSave) return;
    setSaving(true);
    try {
      const shared = {
        name: name.trim(),
        phone: phoneDigits,
        email: email.trim() || null,
        company_name: isCompany ? companyName.trim() || null : null,
        trn: isCompany ? trn.trim() || null : null,
        alt_contact: altContact.trim() || null,
        default_address: address.trim() || null,
        city: city.trim() || null,
        notes: notes.trim() || null,
      };
      if (editing) {
        const payload: CustomerUpdate = { ...shared, risk_flag: riskFlag };
        await updateCustomer(editing.id, payload);
        toast({ title: "Customer updated", variant: "success" });
      } else {
        const payload: CustomerCreate = shared;
        await createCustomer(payload);
        toast({ title: "Customer created", variant: "success" });
      }
      setDialogOpen(false);
      await load();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast({
        title: detail ?? (editing ? "Failed to update customer" : "Failed to create customer"),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Contact className="h-7 w-7 text-primary-600" />
          <div>
            <h1 className="text-pos-2xl font-bold text-secondary-900">Customers</h1>
            <p className="text-sm text-secondary-500">
              Contact details, delivery addresses, and the company name and TRN for
              business customers.
            </p>
          </div>
        </div>
        <Button onClick={openCreate} className="min-h-[48px] gap-2">
          <Plus className="h-4 w-4" />
          Add Customer
        </Button>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-secondary-400" />
        <Input
          placeholder="Search by name, company, phone or TRN..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="min-h-[48px] pl-9"
        />
      </div>

      {/* Table */}
      <Card>
        <CardContent className="pt-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
            </div>
          ) : customers.length === 0 ? (
            <div className="py-12 text-center text-secondary-500">
              {debouncedQuery
                ? `No customers match "${debouncedQuery}".`
                : "No customers yet. Add the first one, or they will appear here as the call centre records them."}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-pos-sm">
                <thead>
                  <tr className="border-b text-secondary-500">
                    <th className="pb-3 font-medium">Customer</th>
                    <th className="pb-3 font-medium">Phone</th>
                    <th className="pb-3 font-medium">Company / TRN</th>
                    <th className="pb-3 font-medium">Address</th>
                    <th className="pb-3 font-medium text-right">Orders</th>
                    <th className="pb-3 font-medium text-right">Spent</th>
                    <th className="pb-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {customers.map((customer) => (
                    <tr key={customer.id} className="border-b last:border-0 hover:bg-secondary-50">
                      <td className="py-3">
                        <div className="font-medium text-secondary-900">{customer.name}</div>
                        {customer.email && (
                          <div className="text-xs text-secondary-500">{customer.email}</div>
                        )}
                        {customer.risk_flag !== "normal" && (
                          <Badge
                            variant={customer.risk_flag === "blocked" ? "destructive" : "warning"}
                            className="mt-1 gap-1 text-xs"
                          >
                            <ShieldAlert className="h-3 w-3" />
                            {customer.risk_flag === "blocked" ? "Blocked" : "High risk"}
                          </Badge>
                        )}
                      </td>
                      <td className="py-3 font-mono text-secondary-700">
                        {customer.phone}
                        {customer.alt_contact && (
                          <div className="text-xs text-secondary-400">{customer.alt_contact}</div>
                        )}
                      </td>
                      <td className="py-3 text-secondary-700">
                        {customer.company_name || customer.trn ? (
                          <div className="flex items-start gap-1.5">
                            <Building2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-secondary-400" />
                            <div>
                              {customer.company_name && <div>{customer.company_name}</div>}
                              {customer.trn && (
                                <div className="font-mono text-xs text-secondary-500">TRN {customer.trn}</div>
                              )}
                            </div>
                          </div>
                        ) : (
                          <span className="text-secondary-400">Individual</span>
                        )}
                      </td>
                      <td className="py-3 text-secondary-600">
                        {customer.default_address ? (
                          <>
                            <div className="max-w-xs truncate">{customer.default_address}</div>
                            {customer.city && <div className="text-xs text-secondary-400">{customer.city}</div>}
                          </>
                        ) : (
                          <span className="text-secondary-300">—</span>
                        )}
                      </td>
                      <td className="py-3 text-right tabular-nums text-secondary-700">
                        {customer.order_count}
                      </td>
                      <td className="py-3 text-right tabular-nums text-secondary-700">
                        {formatPKR(customer.total_spent)}
                      </td>
                      <td className="py-3">
                        <div className="flex justify-end">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="min-h-[40px] gap-2"
                            onClick={() => openEdit(customer)}
                          >
                            <Pencil className="h-4 w-4" />
                            Edit
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {pages > 1 && (
            <div className="mt-4 flex items-center justify-between text-sm text-secondary-500">
              <span>
                {total} customer{total === 1 ? "" : "s"}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </Button>
                <span>
                  Page {page} of {pages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= pages}
                  onClick={() => setPage((p) => Math.min(pages, p + 1))}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create / Edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Customer" : "Add Customer"}</DialogTitle>
            <DialogDescription>
              {editing
                ? "Update the customer's details. The phone number is how orders find them."
                : "The phone number is the customer's key: orders and history attach to it."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="cust-name">Name *</Label>
              <Input
                id="cust-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Contact person"
                className="min-h-[48px]"
              />
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="cust-phone">Phone *</Label>
                <Input
                  id="cust-phone"
                  type="tel"
                  inputMode="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="0501234567"
                  className="min-h-[48px]"
                />
                {phoneError ? (
                  <p className="text-xs text-danger-600">{phoneError}</p>
                ) : (
                  <p className="text-xs text-secondary-500">Digits only are kept.</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="cust-alt">Alternative contact</Label>
                <Input
                  id="cust-alt"
                  value={altContact}
                  onChange={(e) => setAltContact(e.target.value)}
                  placeholder="Second phone, for the rider"
                  className="min-h-[48px]"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="cust-email">Email</Label>
              <Input
                id="cust-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Optional"
                className="min-h-[48px]"
              />
            </div>

            {/* Company */}
            <div className="rounded-lg border border-secondary-200 p-3 space-y-3">
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={isCompany}
                  onChange={(e) => setIsCompany(e.target.checked)}
                  className="h-4 w-4 rounded border-secondary-300"
                />
                <span className="flex items-center gap-1.5 font-medium text-secondary-800">
                  <Building2 className="h-4 w-4 text-secondary-400" />
                  This customer is a company
                </span>
              </label>
              {isCompany && (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="cust-company">Company name</Label>
                    <Input
                      id="cust-company"
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                      placeholder="Legal or trading name"
                      className="min-h-[48px]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="cust-trn">TRN</Label>
                    <Input
                      id="cust-trn"
                      value={trn}
                      onChange={(e) => setTrn(e.target.value)}
                      placeholder="100123456700003"
                      maxLength={50}
                      className="min-h-[48px] font-mono"
                    />
                    <p className="text-xs text-secondary-500">
                      Printed on tax invoices issued to this company.
                    </p>
                  </div>
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-[2fr_1fr]">
              <div className="space-y-2">
                <Label htmlFor="cust-address">Address</Label>
                <Input
                  id="cust-address"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="Delivery address"
                  className="min-h-[48px]"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cust-city">City / area</Label>
                <Input
                  id="cust-city"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  className="min-h-[48px]"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="cust-notes">Notes</Label>
              <Textarea
                id="cust-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Preferences, allergies, gate codes..."
                rows={3}
                className="resize-none"
              />
            </div>

            {editing && (
              <div className="space-y-2">
                <Label htmlFor="cust-risk">Status</Label>
                <select
                  id="cust-risk"
                  value={riskFlag}
                  onChange={(e) => setRiskFlag(e.target.value)}
                  className="min-h-[48px] w-full rounded-md border border-secondary-300 px-3 text-pos-sm"
                >
                  <option value="normal">Normal</option>
                  <option value="high">High risk (many voided orders)</option>
                  <option value="blocked">Blocked (cannot order)</option>
                </select>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} className="min-h-touch">
              Cancel
            </Button>
            <Button onClick={() => void handleSave()} disabled={!canSave} className="min-h-touch gap-2">
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {editing ? "Save Changes" : "Create Customer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
