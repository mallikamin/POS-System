import { useEffect, useState } from "react";
import { Settings, Loader2, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { useConfigStore } from "@/stores/configStore";
import api from "@/lib/axios";

interface ConfigData {
  id: string;
  tenant_id: string;
  restaurant_name: string | null;
  payment_flow: string;
  currency: string;
  timezone: string;
  tax_inclusive: boolean;
  default_tax_rate: number;
  cash_tax_rate_bps: number;
  card_tax_rate_bps: number;
  receipt_header: string | null;
  receipt_footer: string | null;
  discount_approval_threshold_bps: number;
  discount_approval_threshold_fixed: number;
}

function SettingsPage() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [restaurantName, setRestaurantName] = useState("");
  const [paymentFlow, setPaymentFlow] = useState("order_first");
  const [currency, setCurrency] = useState("PKR");
  const [timezone, setTimezone] = useState("Asia/Karachi");
  const [taxInclusive, setTaxInclusive] = useState(true);
  const [taxRate, setTaxRate] = useState(16);
  const [cashTaxRate, setCashTaxRate] = useState(16);
  const [cardTaxRate, setCardTaxRate] = useState(5);
  const [receiptHeader, setReceiptHeader] = useState("");
  const [receiptFooter, setReceiptFooter] = useState("");
  const [discountThresholdPct, setDiscountThresholdPct] = useState(0);
  const [discountThresholdFixed, setDiscountThresholdFixed] = useState(0);

  useEffect(() => {
    fetchConfig();
  }, []);

  async function fetchConfig() {
    try {
      setLoading(true);
      const { data } = await api.get<ConfigData>("/config/restaurant");
      setPaymentFlow(data.payment_flow);
      setCurrency(data.currency);
      setTimezone(data.timezone);
      setTaxInclusive(data.tax_inclusive);
      setTaxRate(data.default_tax_rate / 100);
      setCashTaxRate(data.cash_tax_rate_bps / 100);
      setCardTaxRate(data.card_tax_rate_bps / 100);
      setReceiptHeader(data.receipt_header ?? "");
      setReceiptFooter(data.receipt_footer ?? "");

      setDiscountThresholdPct((data.discount_approval_threshold_bps ?? 0) / 100);
      setDiscountThresholdFixed((data.discount_approval_threshold_fixed ?? 0) / 100);
      setRestaurantName(data.restaurant_name ?? "Demo Restaurant");
    } catch {
      toast({ title: "Failed to load settings", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    try {
      setSaving(true);
      await api.patch("/config/restaurant", {
        restaurant_name: restaurantName || undefined,
        payment_flow: paymentFlow,
        currency,
        timezone,
        tax_inclusive: taxInclusive,
        default_tax_rate: Math.round(taxRate * 100),
        cash_tax_rate_bps: Math.round(cashTaxRate * 100),
        card_tax_rate_bps: Math.round(cardTaxRate * 100),
        receipt_header: receiptHeader || null,
        receipt_footer: receiptFooter || null,
        discount_approval_threshold_bps: Math.round(discountThresholdPct * 100),
        discount_approval_threshold_fixed: Math.round(discountThresholdFixed * 100),
      });
      // Refresh global config store so all POS pages see new values immediately
      await useConfigStore.getState().fetchConfig();
      toast({ title: "Settings saved", variant: "success" });
    } catch {
      toast({ title: "Failed to save settings", variant: "destructive" });
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
          <Settings className="h-7 w-7 text-primary-600" />
          <h1 className="text-pos-2xl font-bold text-secondary-900">
            Restaurant Settings
          </h1>
        </div>
        <Button
          onClick={handleSave}
          disabled={saving}
          className="min-h-[48px] gap-2"
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          Save Changes
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* General Settings */}
        <Card>
          <CardContent className="space-y-4 pt-6">
            <h2 className="text-pos-lg font-semibold text-secondary-800">
              General
            </h2>
            <div className="space-y-2">
              <Label htmlFor="name">Restaurant Name</Label>
              <Input
                id="name"
                value={restaurantName}
                onChange={(e) => setRestaurantName(e.target.value)}
                className="min-h-[48px]"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="currency">Currency</Label>
              <Input
                id="currency"
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="min-h-[48px]"
                maxLength={10}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="timezone">Timezone</Label>
              <Input
                id="timezone"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="min-h-[48px]"
              />
            </div>
          </CardContent>
        </Card>

        {/* Tax Settings */}
        <Card>
          <CardContent className="space-y-4 pt-6">
            <h2 className="text-pos-lg font-semibold text-secondary-800">
              Tax Configuration
            </h2>
            <div className="space-y-2">
              <Label htmlFor="taxRate">Tax Rate (%)</Label>
              <Input
                id="taxRate"
                type="number"
                min={0}
                max={100}
                step={0.5}
                value={taxRate}
                onChange={(e) => setTaxRate(parseFloat(e.target.value) || 0)}
                className="min-h-[48px]"
              />
              <p className="text-pos-sm text-secondary-500">
                Currently: {taxRate}% ({Math.round(taxRate * 100)} basis points)
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="cashTaxRate">Cash Tax Rate (%)</Label>
                <Input
                  id="cashTaxRate"
                  type="number"
                  min={0}
                  max={100}
                  step={0.5}
                  value={cashTaxRate}
                  onChange={(e) => setCashTaxRate(parseFloat(e.target.value) || 0)}
                  className="min-h-[48px]"
                />
                <p className="text-pos-sm text-secondary-500">{cashTaxRate}%</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="cardTaxRate">Card Tax Rate (%)</Label>
                <Input
                  id="cardTaxRate"
                  type="number"
                  min={0}
                  max={100}
                  step={0.5}
                  value={cardTaxRate}
                  onChange={(e) => setCardTaxRate(parseFloat(e.target.value) || 0)}
                  className="min-h-[48px]"
                />
                <p className="text-pos-sm text-secondary-500">{cardTaxRate}%</p>
              </div>
            </div>
            <div className="flex items-center justify-between rounded-lg border p-4">
              <div>
                <Label>Tax Inclusive</Label>
                <p className="text-pos-sm text-secondary-500">
                  Menu prices include tax
                </p>
              </div>
              <Switch
                checked={taxInclusive}
                onCheckedChange={setTaxInclusive}
              />
            </div>
          </CardContent>
        </Card>

        {/* Payment Flow */}
        <Card>
          <CardContent className="space-y-4 pt-6">
            <h2 className="text-pos-lg font-semibold text-secondary-800">
              Payment Flow
            </h2>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setPaymentFlow("order_first")}
                className={`rounded-lg border-2 p-4 text-left transition-colors min-h-[80px] ${
                  paymentFlow === "order_first"
                    ? "border-primary-500 bg-primary-50"
                    : "border-secondary-200 hover:border-secondary-300"
                }`}
              >
                <div className="font-medium text-secondary-900">
                  Order First
                </div>
                <p className="mt-1 text-pos-sm text-secondary-500">
                  Traditional dine-in. Kitchen fires before payment.
                </p>
                {paymentFlow === "order_first" && (
                  <Badge className="mt-2" variant="default">Active</Badge>
                )}
              </button>
              <button
                type="button"
                onClick={() => setPaymentFlow("pay_first")}
                className={`rounded-lg border-2 p-4 text-left transition-colors min-h-[80px] ${
                  paymentFlow === "pay_first"
                    ? "border-primary-500 bg-primary-50"
                    : "border-secondary-200 hover:border-secondary-300"
                }`}
              >
                <div className="font-medium text-secondary-900">Pay First</div>
                <p className="mt-1 text-pos-sm text-secondary-500">
                  QSR style (KFC). Payment before kitchen fires.
                </p>
                {paymentFlow === "pay_first" && (
                  <Badge className="mt-2" variant="default">Active</Badge>
                )}
              </button>
            </div>
          </CardContent>
        </Card>

        {/* Discount Approval Thresholds */}
        <Card>
          <CardContent className="space-y-4 pt-6">
            <h2 className="text-pos-lg font-semibold text-secondary-800">
              Discount Approval
            </h2>
            <p className="text-pos-sm text-secondary-500">
              Set thresholds for manager approval on discounts. Set to 0 to disable.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="discPct">Percent Threshold (%)</Label>
                <Input
                  id="discPct"
                  type="number"
                  min={0}
                  max={100}
                  step={0.5}
                  value={discountThresholdPct}
                  onChange={(e) => setDiscountThresholdPct(parseFloat(e.target.value) || 0)}
                  className="min-h-[48px]"
                />
                <p className="text-pos-sm text-secondary-500">
                  {discountThresholdPct > 0
                    ? `Discounts > ${discountThresholdPct}% need approval`
                    : "Disabled"}
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="discFixed">Fixed Threshold (PKR)</Label>
                <Input
                  id="discFixed"
                  type="number"
                  min={0}
                  step={1}
                  value={discountThresholdFixed}
                  onChange={(e) => setDiscountThresholdFixed(parseFloat(e.target.value) || 0)}
                  className="min-h-[48px]"
                />
                <p className="text-pos-sm text-secondary-500">
                  {discountThresholdFixed > 0
                    ? `Discounts > Rs ${discountThresholdFixed} need approval`
                    : "Disabled"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Receipt Settings */}
        <Card>
          <CardContent className="space-y-4 pt-6">
            <h2 className="text-pos-lg font-semibold text-secondary-800">
              Receipt Template
            </h2>
            <div className="space-y-2">
              <Label htmlFor="header">Receipt Header</Label>
              <Textarea
                id="header"
                value={receiptHeader}
                onChange={(e) => setReceiptHeader(e.target.value)}
                placeholder="Restaurant name, address, phone..."
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="footer">Receipt Footer</Label>
              <Textarea
                id="footer"
                value={receiptFooter}
                onChange={(e) => setReceiptFooter(e.target.value)}
                placeholder="Thank you for dining with us!..."
                rows={3}
              />
            </div>

            {/* Receipt Preview */}
            <div className="rounded-lg border-2 border-dashed border-secondary-200 bg-secondary-50 p-4">
              <p className="mb-2 text-pos-sm font-medium text-secondary-600">
                Preview
              </p>
              <div className="rounded bg-white p-3 font-mono text-pos-sm shadow-sm">
                <div className="whitespace-pre-wrap text-center">
                  {receiptHeader || "Restaurant Name"}
                </div>
                <div className="my-2 border-t border-dashed border-secondary-300" />
                <div className="text-secondary-400">Order #250223-001</div>
                <div className="text-secondary-400">--- items ---</div>
                <div className="my-2 border-t border-dashed border-secondary-300" />
                <div className="whitespace-pre-wrap text-center text-secondary-500">
                  {receiptFooter || "Thank you!"}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default SettingsPage;
