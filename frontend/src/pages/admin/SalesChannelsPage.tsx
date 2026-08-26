import { useEffect, useState } from "react";
import { Loader2, Pencil, Plus, Store } from "lucide-react";
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
import { formatMoney, majorToMinor, minorToMajor } from "@/utils/currency";
import { useConfigStore } from "@/stores/configStore";
import {
  fetchChannels,
  createChannel,
  updateChannel,
} from "@/services/locationsApi";
import type { SalesChannel } from "@/types/location";

/**
 * Commission crosses the wire in BASIS POINTS (1500 bps = 15.00%) but the
 * operator types PERCENT. These three functions are the only place that
 * conversion happens. Off by a factor of 100 here and every order on the
 * channel is silently mispriced, so it is not inlined anywhere else.
 */
function percentToBps(percent: number): number {
  return Math.round(percent * 100);
}

function bpsToPercentInput(bps: number): string {
  return (bps / 100).toFixed(2);
}

function formatBpsAsPercent(bps: number): string {
  return `${(bps / 100).toFixed(2)}%`;
}

function SalesChannelsPage() {
  const { toast } = useToast();
  const config = useConfigStore((s) => s.config);
  const currency = config?.currency ?? "AED";

  const [channels, setChannels] = useState<SalesChannel[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showDialog, setShowDialog] = useState(false);
  const [editing, setEditing] = useState<SalesChannel | null>(null);

  // Form state. Percent and fee are held as raw strings so a half-typed
  // "2." does not get rounded away while the user is still typing.
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [commissionPercent, setCommissionPercent] = useState("");
  const [fixedFee, setFixedFee] = useState("");
  const [isActive, setIsActive] = useState(true);

  useEffect(() => {
    void loadChannels();
  }, []);

  async function loadChannels() {
    try {
      setLoading(true);
      const data = await fetchChannels(true);
      setChannels(data);
    } catch {
      toast({ title: "Failed to load sales channels", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }

  function openCreate() {
    setEditing(null);
    setName("");
    setCode("");
    setCommissionPercent("0");
    setFixedFee("0");
    setIsActive(true);
    setShowDialog(true);
  }

  function openEdit(channel: SalesChannel) {
    setEditing(channel);
    setName(channel.name);
    setCode(channel.code);
    setCommissionPercent(bpsToPercentInput(channel.commission_bps));
    setFixedFee(String(minorToMajor(channel.fixed_fee_minor, currency)));
    setIsActive(channel.is_active);
    setShowDialog(true);
  }

  const parsedPercent = parseFloat(commissionPercent);
  const percentIsNumber = commissionPercent !== "" && !Number.isNaN(parsedPercent);
  // Backend caps commission at 10000 bps, so 100% is the hard ceiling.
  const commissionError = !percentIsNumber
    ? "Enter a commission percentage (use 0 for a direct channel)."
    : parsedPercent < 0 || parsedPercent > 100
      ? "Commission must be between 0% and 100%."
      : null;

  const parsedFee = parseFloat(fixedFee);
  const feeIsNumber = fixedFee !== "" && !Number.isNaN(parsedFee);
  const feeError = !feeIsNumber
    ? "Enter a fixed fee (use 0 if the channel charges none)."
    : parsedFee < 0
      ? "Fixed fee cannot be negative."
      : null;

  const canSave =
    name.trim() !== "" &&
    code.trim() !== "" &&
    commissionError === null &&
    feeError === null;

  async function handleSave() {
    if (!canSave) return;
    setSaving(true);
    try {
      const commissionBps = percentToBps(parsedPercent);
      const fixedFeeMinor = majorToMinor(parsedFee, currency);

      if (editing) {
        // `code` is deliberately not sent: the backend rejects code changes.
        await updateChannel(editing.id, {
          name: name.trim(),
          commission_bps: commissionBps,
          fixed_fee_minor: fixedFeeMinor,
          is_active: isActive,
        });
        toast({ title: "Sales channel updated", variant: "success" });
      } else {
        await createChannel({
          name: name.trim(),
          code: code.trim(),
          commission_bps: commissionBps,
          fixed_fee_minor: fixedFeeMinor,
          is_active: isActive,
        });
        toast({ title: "Sales channel created", variant: "success" });
      }
      setShowDialog(false);
      await loadChannels();
    } catch {
      toast({
        title: editing
          ? "Failed to update sales channel"
          : "Failed to create sales channel",
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
          <Store className="h-7 w-7 text-primary-600" />
          <div>
            <h1 className="text-pos-2xl font-bold text-secondary-900">
              Sales Channels
            </h1>
            <p className="text-sm text-secondary-500">
              Commission and fees per channel. These feed the profitability
              report.
            </p>
          </div>
        </div>
        <Button onClick={openCreate} className="gap-2 min-h-[48px]">
          <Plus className="h-4 w-4" />
          Add Channel
        </Button>
      </div>

      {channels.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center space-y-3">
            <p className="font-semibold text-secondary-900">
              No sales channels configured yet
            </p>
            <p className="mx-auto max-w-xl text-sm text-secondary-500">
              A sales channel is where the order came from: a delivery
              aggregator, a phone order, a walk-in, your own website. Each one
              keeps a different cut of the sale, so the same basket does not
              earn the same money everywhere. Record the commission here and
              the profitability report can subtract it order by order.
            </p>
            <Button onClick={openCreate} className="gap-2">
              <Plus className="h-4 w-4" />
              Add your first channel
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-secondary-200 text-left text-secondary-500">
                  <th className="px-4 py-3 font-medium">Channel</th>
                  <th className="px-4 py-3 font-medium">Code</th>
                  <th className="px-4 py-3 font-medium text-right">
                    Commission
                  </th>
                  <th className="px-4 py-3 font-medium text-right">Fixed Fee</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {channels.map((channel) => (
                  <tr
                    key={channel.id}
                    className="border-b border-secondary-100 last:border-0"
                  >
                    <td className="px-4 py-3 font-medium text-secondary-900">
                      {channel.name}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-secondary-500">
                      {channel.code}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-secondary-900">
                      {formatBpsAsPercent(channel.commission_bps)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-secondary-900">
                      {formatMoney(channel.fixed_fee_minor, currency)}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={channel.is_active ? "success" : "secondary"}>
                        {channel.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="gap-2"
                        onClick={() => openEdit(channel)}
                      >
                        <Pencil className="h-4 w-4" />
                        Edit
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editing ? "Edit Sales Channel" : "Add Sales Channel"}
            </DialogTitle>
            <DialogDescription>
              Commission is what the channel keeps from each order. Enter it as
              a percentage, exactly as it appears on the channel's contract.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Talabat"
              />
            </div>

            <div className="space-y-2">
              <Label>Code</Label>
              <Input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="e.g. talabat"
                readOnly={editing !== null}
                disabled={editing !== null}
              />
              {editing !== null && (
                <p className="text-xs text-secondary-500">
                  Code cannot be changed after the channel is created. Orders
                  already reference it.
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label>Commission (%)</Label>
              <Input
                type="number"
                min={0}
                max={100}
                step={0.25}
                value={commissionPercent}
                onChange={(e) => setCommissionPercent(e.target.value)}
                placeholder="e.g. 15 or 2.5"
              />
              {commissionError ? (
                <p className="text-xs text-danger-600">{commissionError}</p>
              ) : (
                <p className="text-xs text-secondary-500">
                  Stored as {percentToBps(parsedPercent)} basis points.
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label>Fixed fee per order ({currency})</Label>
              <Input
                type="number"
                min={0}
                step={0.5}
                value={fixedFee}
                onChange={(e) => setFixedFee(e.target.value)}
                placeholder="e.g. 2"
              />
              {feeError ? (
                <p className="text-xs text-danger-600">{feeError}</p>
              ) : (
                <p className="text-xs text-secondary-500">
                  Charged once per order, on top of the percentage.
                </p>
              )}
            </div>

            <div className="flex items-center justify-between border-t border-secondary-100 pt-4">
              <div>
                <Label>Active</Label>
                <p className="text-xs text-secondary-500">
                  Inactive channels stay in reports but cannot take new orders.
                </p>
              </div>
              <Switch checked={isActive} onCheckedChange={setIsActive} />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)}>
              Cancel
            </Button>
            <Button onClick={() => void handleSave()} disabled={saving || !canSave}>
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : editing ? (
                "Save Changes"
              ) : (
                "Create Channel"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default SalesChannelsPage;
