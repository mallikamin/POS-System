import { useEffect, useState } from "react";
import { Building2, Loader2, Pencil, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
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
import {
  fetchLocations,
  createLocation,
  updateLocation,
} from "@/services/locationsApi";
import type {
  InvoiceFormat,
  Location,
  LocationCreate,
  LocationType,
  LocationUpdate,
} from "@/types/location";

const LOCATION_TYPE_LABELS: Record<LocationType, string> = {
  production: "Production",
  delivery: "Delivery",
  retail: "Retail",
};

const INVOICE_FORMAT_LABELS: Record<InvoiceFormat, string> = {
  a4_tax_invoice: "A4 Tax Invoice",
  thermal_ticket: "Thermal Ticket",
};

interface FormState {
  name: string;
  code: string;
  location_type: LocationType;
  invoice_format: InvoiceFormat;
  legal_name: string;
  tax_registration_number: string;
  address_line1: string;
  address_line2: string;
  city: string;
  country: string;
  phone: string;
  email: string;
  invoice_prefix: string;
  is_default: boolean;
  is_active: boolean;
}

const EMPTY_FORM: FormState = {
  name: "",
  code: "",
  location_type: "retail",
  invoice_format: "thermal_ticket",
  legal_name: "",
  tax_registration_number: "",
  address_line1: "",
  address_line2: "",
  city: "",
  country: "",
  phone: "",
  email: "",
  invoice_prefix: "",
  is_default: false,
  is_active: true,
};

function toForm(loc: Location): FormState {
  return {
    name: loc.name,
    code: loc.code,
    location_type: loc.location_type,
    invoice_format: loc.invoice_format,
    legal_name: loc.legal_name ?? "",
    tax_registration_number: loc.tax_registration_number ?? "",
    address_line1: loc.address_line1 ?? "",
    address_line2: loc.address_line2 ?? "",
    city: loc.city ?? "",
    country: loc.country ?? "",
    phone: loc.phone ?? "",
    email: loc.email ?? "",
    invoice_prefix: loc.invoice_prefix,
    is_default: loc.is_default,
    is_active: loc.is_active,
  };
}

/** Blank optional strings go to the backend as null, not "". */
function orNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

function LocationsPage() {
  const { toast } = useToast();
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Location | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  useEffect(() => {
    void loadLocations();
  }, []);

  async function loadLocations() {
    try {
      setLoading(true);
      const data = await fetchLocations(true);
      setLocations(data);
    } catch {
      toast({ title: "Failed to load locations", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEdit(loc: Location) {
    setEditing(loc);
    setForm(toForm(loc));
    setDialogOpen(true);
  }

  // A tax invoice without a legal name and TRN is not a valid tax invoice, and
  // the backend rejects it with a 422, so block the request here.
  const needsTaxIdentity = form.invoice_format === "a4_tax_invoice";
  const missingTaxIdentity =
    needsTaxIdentity &&
    (form.legal_name.trim() === "" ||
      form.tax_registration_number.trim() === "");
  const missingBasics =
    form.name.trim() === "" || (!editing && form.code.trim() === "");
  const canSave = !saving && !missingBasics && !missingTaxIdentity;

  async function handleSave() {
    if (!canSave) return;
    setSaving(true);
    try {
      const shared = {
        name: form.name.trim(),
        location_type: form.location_type,
        invoice_format: form.invoice_format,
        legal_name: orNull(form.legal_name),
        tax_registration_number: orNull(form.tax_registration_number),
        address_line1: orNull(form.address_line1),
        address_line2: orNull(form.address_line2),
        city: orNull(form.city),
        country: orNull(form.country),
        phone: orNull(form.phone),
        email: orNull(form.email),
        is_default: form.is_default,
        is_active: form.is_active,
      };
      const prefix = form.invoice_prefix.trim();

      if (editing) {
        // `code` is deliberately absent: LocationUpdate omits it.
        const body: LocationUpdate = { ...shared };
        if (prefix !== "") body.invoice_prefix = prefix;
        await updateLocation(editing.id, body);
        toast({ title: "Location updated", variant: "success" });
      } else {
        const body: LocationCreate = { ...shared, code: form.code.trim() };
        if (prefix !== "") body.invoice_prefix = prefix;
        await createLocation(body);
        toast({ title: "Location created", variant: "success" });
      }
      setDialogOpen(false);
      setEditing(null);
      setForm(EMPTY_FORM);
      await loadLocations();
    } catch {
      toast({
        title: editing
          ? "Failed to update location"
          : "Failed to create location",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
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
          <Building2 className="h-7 w-7 text-primary-600" />
          <h1 className="text-pos-2xl font-bold text-secondary-900">
            Locations
          </h1>
        </div>
        <Button onClick={openCreate} className="gap-2 min-h-[48px]">
          <Plus className="h-4 w-4" />
          Add Location
        </Button>
      </div>

      {locations.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center space-y-4">
            <p className="text-secondary-600">
              No locations yet. A location is a physical site where stock is
              held and sales are recorded, so every order and every stock
              movement belongs to one.
            </p>
            <p className="text-sm text-secondary-400">
              A production site can issue A4 tax invoices, a delivery site
              prints thermal tickets.
            </p>
            <Button onClick={openCreate} className="gap-2 min-h-[48px]">
              <Plus className="h-4 w-4" />
              Add Location
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {locations.map((loc) => (
            <Card key={loc.id}>
              <CardContent className="pt-4 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-semibold text-secondary-900 truncate">
                      {loc.name}
                    </p>
                    <p className="text-sm text-secondary-500">
                      Code: {loc.code}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => openEdit(loc)}
                    aria-label={`Edit ${loc.name}`}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">
                    {LOCATION_TYPE_LABELS[loc.location_type]}
                  </Badge>
                  <Badge
                    variant={
                      loc.invoice_format === "a4_tax_invoice"
                        ? "warning"
                        : "secondary"
                    }
                  >
                    {INVOICE_FORMAT_LABELS[loc.invoice_format]}
                  </Badge>
                  {loc.is_default && <Badge variant="default">Default</Badge>}
                  <Badge variant={loc.is_active ? "success" : "secondary"}>
                    {loc.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>

                {(loc.legal_name || loc.tax_registration_number) && (
                  <div className="border-t border-secondary-100 pt-3 text-sm text-secondary-600 space-y-1">
                    {loc.legal_name && (
                      <p>
                        <span className="text-secondary-400">Legal name: </span>
                        {loc.legal_name}
                      </p>
                    )}
                    {loc.tax_registration_number && (
                      <p>
                        <span className="text-secondary-400">TRN: </span>
                        {loc.tax_registration_number}
                      </p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editing ? "Edit Location" : "Add Location"}
            </DialogTitle>
            <DialogDescription>
              A location is a physical site where stock is held and sales are
              recorded.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="loc-name">Name</Label>
                <Input
                  id="loc-name"
                  value={form.name}
                  onChange={(e) => setField("name", e.target.value)}
                  placeholder="e.g. Al Quoz Production"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="loc-code">Code</Label>
                <Input
                  id="loc-code"
                  value={form.code}
                  onChange={(e) => setField("code", e.target.value)}
                  placeholder="e.g. PROD01"
                  readOnly={editing !== null}
                  disabled={editing !== null}
                />
                {editing && (
                  <p className="text-xs text-secondary-400">
                    Code cannot be changed after a location is created.
                  </p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="loc-type">Location Type</Label>
                <Select
                  id="loc-type"
                  value={form.location_type}
                  onChange={(e) =>
                    setField("location_type", e.target.value as LocationType)
                  }
                >
                  <option value="production">Production</option>
                  <option value="delivery">Delivery</option>
                  <option value="retail">Retail</option>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="loc-invoice-format">Invoice Format</Label>
                <Select
                  id="loc-invoice-format"
                  value={form.invoice_format}
                  onChange={(e) =>
                    setField("invoice_format", e.target.value as InvoiceFormat)
                  }
                >
                  <option value="thermal_ticket">Thermal Ticket</option>
                  <option value="a4_tax_invoice">A4 Tax Invoice</option>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="loc-legal-name">
                Legal Name {needsTaxIdentity && <span>(required)</span>}
              </Label>
              <Input
                id="loc-legal-name"
                value={form.legal_name}
                onChange={(e) => setField("legal_name", e.target.value)}
                placeholder="e.g. Sunrise Bakery Foodstuff Trading LLC"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="loc-trn">
                Tax Registration Number{" "}
                {needsTaxIdentity && <span>(required)</span>}
              </Label>
              <Input
                id="loc-trn"
                value={form.tax_registration_number}
                onChange={(e) =>
                  setField("tax_registration_number", e.target.value)
                }
                placeholder="e.g. 100123456700003"
              />
            </div>

            {missingTaxIdentity && (
              <div className="rounded-lg border border-warning-200 bg-warning-50 p-3 text-sm text-warning-700">
                An A4 tax invoice must carry the legal entity name and the tax
                registration number, otherwise it is not a valid tax invoice.
                Fill both in, or switch this location to Thermal Ticket.
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="loc-address1">Address Line 1</Label>
              <Input
                id="loc-address1"
                value={form.address_line1}
                onChange={(e) => setField("address_line1", e.target.value)}
                placeholder="Street and building"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="loc-address2">Address Line 2</Label>
              <Input
                id="loc-address2"
                value={form.address_line2}
                onChange={(e) => setField("address_line2", e.target.value)}
                placeholder="Unit, floor, area"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="loc-city">City</Label>
                <Input
                  id="loc-city"
                  value={form.city}
                  onChange={(e) => setField("city", e.target.value)}
                  placeholder="e.g. Dubai"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="loc-country">Country</Label>
                <Input
                  id="loc-country"
                  value={form.country}
                  onChange={(e) => setField("country", e.target.value)}
                  placeholder="e.g. United Arab Emirates"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="loc-phone">Phone</Label>
                <Input
                  id="loc-phone"
                  value={form.phone}
                  onChange={(e) => setField("phone", e.target.value)}
                  placeholder="e.g. +971 4 000 0000"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="loc-email">Email</Label>
                <Input
                  id="loc-email"
                  type="email"
                  value={form.email}
                  onChange={(e) => setField("email", e.target.value)}
                  placeholder="e.g. orders@example.com"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="loc-invoice-prefix">Invoice Prefix</Label>
              <Input
                id="loc-invoice-prefix"
                value={form.invoice_prefix}
                onChange={(e) => setField("invoice_prefix", e.target.value)}
                placeholder="e.g. INV-PROD"
              />
              <p className="text-xs text-secondary-400">
                Prepended to invoice numbers issued at this location. Leave
                blank to keep the backend default.
              </p>
            </div>

            <div className="flex items-center justify-between border-t border-secondary-100 pt-4">
              <div>
                <p className="text-sm font-medium text-secondary-900">
                  Default location
                </p>
                <p className="text-xs text-secondary-400">
                  Used when an order does not name a location.
                </p>
              </div>
              <Switch
                checked={form.is_default}
                onCheckedChange={(checked) => setField("is_default", checked)}
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-secondary-900">Active</p>
                <p className="text-xs text-secondary-400">
                  Inactive locations are hidden from order and stock screens.
                </p>
              </div>
              <Switch
                checked={form.is_active}
                onCheckedChange={(checked) => setField("is_active", checked)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void handleSave()} disabled={!canSave}>
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : editing ? (
                "Save Changes"
              ) : (
                "Create"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default LocationsPage;
