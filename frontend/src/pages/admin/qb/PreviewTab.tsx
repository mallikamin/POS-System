import { useCallback, useEffect, useState } from "react";
import {
  Loader2,
  Eye,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  FileJson,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useQuickBooksStore } from "@/stores/quickbooksStore";
import * as qbApi from "@/services/quickbooksApi";
import {
  MAPPING_TYPE_LABELS,
  type QBPreviewResponse,
  type QBTemplateMappingDef,
} from "@/types/quickbooks";

interface OrderSummary {
  id: string;
  order_number: string;
  order_type: string;
  status: string;
  total: number;
  created_at: string;
}

export function PreviewTab() {
  const templates = useQuickBooksStore((s) => s.templates);
  const loadTemplates = useQuickBooksStore((s) => s.loadTemplates);

  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [loadingOrders, setLoadingOrders] = useState(false);
  const [selectedOrderId, setSelectedOrderId] = useState("");
  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [preview, setPreview] = useState<QBPreviewResponse | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Load templates if not cached
  useEffect(() => {
    if (templates.length === 0) loadTemplates();
  }, [templates.length, loadTemplates]);

  // Load orders (all statuses for preview)
  const loadOrders = useCallback(async () => {
    setLoadingOrders(true);
    try {
      // Use the existing orders API via axios
      const { default: api } = await import("@/lib/axios");
      const { data } = await api.get<{ items: OrderSummary[] } | OrderSummary[]>("/orders", {
        params: { page_size: 100 },
      });
      // Handle both paginated and array responses
      const items = Array.isArray(data) ? data : (data.items ?? []);
      setOrders(items);
    } catch {
      setError("Failed to load orders");
    } finally {
      setLoadingOrders(false);
    }
  }, []);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  // Set defaults once data loads
  useEffect(() => {
    if (orders.length > 0 && !selectedOrderId) {
      setSelectedOrderId(orders[0]!.id);
    }
  }, [orders, selectedOrderId]);

  useEffect(() => {
    if (templates.length > 0 && !selectedTemplate) {
      setSelectedTemplate(templates[0]!.template_name);
    }
  }, [templates, selectedTemplate]);

  async function handleGenerate() {
    if (!selectedOrderId || !selectedTemplate) return;
    setGenerating(true);
    setError(null);
    setPreview(null);
    try {
      const result = await qbApi.previewSalesReceipt(
        selectedOrderId,
        selectedTemplate,
      );
      setPreview(result);
    } catch {
      setError("Failed to generate preview. Make sure the order exists.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleCopy() {
    if (!preview) return;
    try {
      await navigator.clipboard.writeText(
        JSON.stringify(preview.payload, null, 2),
      );
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback: do nothing
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary-500">
        Select a completed order and a template to preview the QB Sales Receipt
        payload that would be generated. No data is sent to QuickBooks.
      </p>

      {error && (
        <div className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">
            dismiss
          </button>
        </div>
      )}

      {/* Controls */}
      <div className="flex flex-wrap gap-4 items-end">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs font-medium text-secondary-600 mb-1">
            Order
          </label>
          <select
            value={selectedOrderId}
            onChange={(e) => setSelectedOrderId(e.target.value)}
            className="w-full rounded-lg border border-secondary-200 bg-white px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
            disabled={loadingOrders}
          >
            {loadingOrders && <option>Loading orders...</option>}
            {orders.map((o) => (
              <option key={o.id} value={o.id}>
                #{o.order_number} — {o.order_type} — {o.status} — Rs.{" "}
                {(o.total / 100).toLocaleString()}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs font-medium text-secondary-600 mb-1">
            Template
          </label>
          <select
            value={selectedTemplate}
            onChange={(e) => setSelectedTemplate(e.target.value)}
            className="w-full rounded-lg border border-secondary-200 bg-white px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
          >
            {templates.map((t) => (
              <option key={t.template_name} value={t.template_name}>
                {t.name} ({t.mapping_count} mappings)
              </option>
            ))}
          </select>
        </div>

        <Button
          onClick={handleGenerate}
          disabled={generating || !selectedOrderId || !selectedTemplate}
        >
          {generating ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Eye className="h-4 w-4 mr-2" />
          )}
          Generate Preview
        </Button>
      </div>

      {/* Preview Result */}
      {preview && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Payload (2/3 width) */}
          <div className="lg:col-span-2 space-y-3">
            <Card>
              <CardHeader className="flex-row items-center justify-between py-3">
                <div className="flex items-center gap-2">
                  <FileJson className="h-5 w-5 text-primary-600" />
                  <CardTitle className="text-sm">
                    QB {preview.qb_entity_type} Payload
                  </CardTitle>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline">{preview.order_type}</Badge>
                  <Badge variant="outline">#{preview.order_number}</Badge>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCopy}
                    className="gap-1"
                  >
                    {copied ? (
                      <Check className="h-3.5 w-3.5 text-success-600" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                    {copied ? "Copied" : "Copy JSON"}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <JsonViewer data={preview.payload} />
              </CardContent>
            </Card>
          </div>

          {/* Mappings Used (1/3 width) */}
          <div>
            <Card>
              <CardHeader className="py-3">
                <CardTitle className="text-sm">Mappings Used</CardTitle>
              </CardHeader>
              <CardContent className="p-3 space-y-2 max-h-[600px] overflow-y-auto">
                <p className="text-xs text-secondary-400 mb-2">
                  Template: {preview.template_display_name}
                </p>
                <MappingsBreakdown mappings={preview.mappings_used} />
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// JSON Viewer (collapsible sections)
// ---------------------------------------------------------------------------

function JsonViewer({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="overflow-auto max-h-[600px] border-t border-secondary-100">
      <pre className="text-xs leading-relaxed p-4 font-mono text-secondary-800">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mappings Breakdown
// ---------------------------------------------------------------------------

function MappingsBreakdown({ mappings }: { mappings: QBTemplateMappingDef[] }) {
  const grouped: Record<string, QBTemplateMappingDef[]> = {};
  for (const m of mappings) {
    const key = m.mapping_type;
    if (!grouped[key]) grouped[key] = [];
    grouped[key]!.push(m);
  }

  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  function toggle(key: string) {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  return (
    <div className="space-y-1">
      {Object.entries(grouped).map(([type, items]) => (
        <div key={type}>
          <button
            onClick={() => toggle(type)}
            className="flex items-center gap-1 w-full text-left py-1 text-xs font-semibold text-secondary-600 hover:text-secondary-800"
          >
            {expanded[type] ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
            {MAPPING_TYPE_LABELS[type] ?? type}
            <span className="text-secondary-400 font-normal ml-1">
              ({items.length})
            </span>
          </button>
          {expanded[type] && (
            <div className="ml-4 space-y-0.5 mb-1">
              {items.map((m, i) => (
                <div
                  key={`${m.name}-${i}`}
                  className={cn(
                    "text-[11px] px-2 py-1 rounded",
                    m.is_default ? "bg-success-50 text-success-800" : "bg-secondary-50 text-secondary-700",
                  )}
                >
                  {m.name}
                  {m.is_default && (
                    <span className="ml-1 text-success-600">(default)</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
