import { useEffect, useMemo, useState } from "react";
import { Loader2, Search, Layers, ChevronRight, CheckCircle2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useQuickBooksStore } from "@/stores/quickbooksStore";
import * as qbApi from "@/services/quickbooksApi";
import {
  TEMPLATE_CATEGORIES,
  CATEGORY_LABELS,
  MAPPING_TYPE_LABELS,
  type TemplateCategory,
  type QBTemplateInfo,
  type QBTemplateMappingDef,
} from "@/types/quickbooks";

function groupMappingsByType(mappings: QBTemplateMappingDef[]) {
  const groups: Record<string, QBTemplateMappingDef[]> = {};
  for (const m of mappings) {
    const key = m.mapping_type;
    if (!groups[key]) groups[key] = [];
    groups[key]!.push(m);
  }
  return groups;
}

interface TemplatesTabProps {
  isConnected: boolean;
}

export function TemplatesTab({ isConnected }: TemplatesTabProps) {
  const templates = useQuickBooksStore((s) => s.templates);
  const isLoading = useQuickBooksStore((s) => s.isLoadingTemplates);
  const loadTemplates = useQuickBooksStore((s) => s.loadTemplates);

  const [activeCategory, setActiveCategory] = useState<TemplateCategory>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTemplate, setSelectedTemplate] = useState<QBTemplateInfo | null>(null);

  useEffect(() => {
    if (templates.length === 0) loadTemplates();
  }, [templates.length, loadTemplates]);

  const filteredTemplates = useMemo(() => {
    let filtered = templates;

    if (activeCategory !== "all") {
      filtered = filtered.filter(
        (t) => (TEMPLATE_CATEGORIES[t.template_name] ?? "niche") === activeCategory,
      );
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          t.description.toLowerCase().includes(q) ||
          t.template_name.toLowerCase().includes(q),
      );
    }

    return filtered;
  }, [templates, activeCategory, searchQuery]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  const categories = Object.keys(CATEGORY_LABELS) as TemplateCategory[];

  return (
    <div className="flex gap-6 min-h-[500px]">
      {/* Left: Template List */}
      <div className="flex-1 space-y-4">
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                activeCategory === cat
                  ? "bg-primary-600 text-white"
                  : "bg-secondary-100 text-secondary-600 hover:bg-secondary-200",
              )}
            >
              {CATEGORY_LABELS[cat]}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-secondary-400" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search templates..."
            className="pl-9"
          />
        </div>

        {/* Template Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {filteredTemplates.map((t) => (
            <button
              key={t.template_name}
              onClick={() => setSelectedTemplate(t)}
              className={cn(
                "text-left rounded-lg border p-3 transition-all hover:shadow-md",
                selectedTemplate?.template_name === t.template_name
                  ? "border-primary-500 bg-primary-50 ring-1 ring-primary-500"
                  : "border-secondary-200 bg-white hover:border-secondary-300",
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-medium text-sm text-secondary-900 truncate">
                    {t.name}
                  </p>
                  <p className="text-xs text-secondary-500 mt-0.5 line-clamp-2">
                    {t.description}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <Badge variant="outline" className="text-[10px]">
                    {t.mapping_count}
                  </Badge>
                  <ChevronRight className="h-4 w-4 text-secondary-300" />
                </div>
              </div>
            </button>
          ))}
        </div>

        {filteredTemplates.length === 0 && (
          <div className="py-12 text-center text-sm text-secondary-400">
            No templates match your search.
          </div>
        )}
      </div>

      {/* Right: Detail Panel */}
      <div className="w-96 shrink-0">
        {selectedTemplate ? (
          <TemplateDetail template={selectedTemplate} isConnected={isConnected} />
        ) : (
          <div className="flex flex-col items-center justify-center h-full rounded-lg border border-dashed border-secondary-300 bg-secondary-50 p-8">
            <Layers className="h-10 w-10 text-secondary-300 mb-3" />
            <p className="text-sm text-secondary-400 text-center">
              Select a template to view its account mappings
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Template Detail Panel
// ---------------------------------------------------------------------------

function TemplateDetail({
  template,
  isConnected,
}: {
  template: QBTemplateInfo;
  isConnected: boolean;
}) {
  const [applying, setApplying] = useState(false);
  const [applyResult, setApplyResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  const groups = useMemo(
    () => groupMappingsByType(template.mappings),
    [template.mappings],
  );

  async function handleApply() {
    setApplying(true);
    setApplyResult(null);
    try {
      const result = await qbApi.applyTemplate(template.template_name);
      setApplyResult({
        success: true,
        message: `Created ${result.mappings_created} mappings, ${result.accounts_created} accounts. ${result.mappings_skipped} skipped.`,
      });
    } catch {
      setApplyResult({
        success: false,
        message: "Failed to apply template. Check connection and try again.",
      });
    } finally {
      setApplying(false);
    }
  }

  // Order groups logically
  const orderedKeys = [
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
    "gift_card_liability",
    "other_current_liability",
  ].filter((k) => k in groups);

  // Add any remaining keys not in the predefined order
  for (const key of Object.keys(groups)) {
    if (!orderedKeys.includes(key)) orderedKeys.push(key);
  }

  return (
    <Card className="sticky top-6">
      <CardContent className="p-4 space-y-4 max-h-[calc(100vh-200px)] overflow-y-auto">
        <div>
          <h3 className="font-semibold text-secondary-900">{template.name}</h3>
          <p className="text-xs text-secondary-500 mt-1">{template.description}</p>
          <div className="flex gap-2 mt-2">
            <Badge variant="outline">{template.mapping_count} mappings</Badge>
            <Badge variant="outline">
              {TEMPLATE_CATEGORIES[template.template_name] ?? "niche"}
            </Badge>
          </div>
        </div>

        {/* Apply Template Button */}
        <Button
          onClick={handleApply}
          disabled={!isConnected || applying}
          className="w-full"
          size="sm"
        >
          {applying ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <CheckCircle2 className="h-4 w-4 mr-2" />
          )}
          {isConnected ? "Apply Template" : "Connect to Apply"}
        </Button>

        {applyResult && (
          <div
            className={cn(
              "rounded-md px-3 py-2 text-xs",
              applyResult.success
                ? "bg-success-50 text-success-700"
                : "bg-danger-50 text-danger-700",
            )}
          >
            {applyResult.message}
          </div>
        )}

        <div className="border-t border-secondary-100" />

        {orderedKeys.map((mappingType) => {
          const items = groups[mappingType] ?? [];
          return (
            <div key={mappingType}>
              <h4 className="text-xs font-semibold text-secondary-600 uppercase tracking-wider mb-1.5">
                {MAPPING_TYPE_LABELS[mappingType] ?? mappingType}
                <span className="text-secondary-400 ml-1">({items.length})</span>
              </h4>
              <div className="space-y-1">
                {items.map((m, i) => (
                  <div
                    key={`${m.name}-${i}`}
                    className="flex items-start justify-between rounded-md bg-secondary-50 px-2.5 py-1.5 text-xs"
                  >
                    <div className="min-w-0">
                      <p className="font-medium text-secondary-800">{m.name}</p>
                      <p className="text-secondary-500 truncate">{m.description}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1 ml-2">
                      {m.is_default && (
                        <Badge variant="success" className="text-[9px] px-1 py-0">
                          default
                        </Badge>
                      )}
                      <span className="text-[10px] text-secondary-400">
                        {m.account_type}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
