import { useEffect } from "react";
import { BookOpen } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useQuickBooksStore } from "@/stores/quickbooksStore";
import { ConnectionTab } from "./qb/ConnectionTab";
import { AccountSetupTab } from "./qb/AccountSetupTab";
import { MappingsTab } from "./qb/MappingsTab";
import { SyncTab } from "./qb/SyncTab";

function QuickBooksPage() {
  const connectionStatus = useQuickBooksStore((s) => s.connectionStatus);
  const loadConnectionStatus = useQuickBooksStore((s) => s.loadConnectionStatus);

  useEffect(() => {
    loadConnectionStatus();
    // If redirected from OAuth callback (?connected=1), clean the URL
    const params = new URLSearchParams(window.location.search);
    if (params.get("connected") === "1") {
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [loadConnectionStatus]);

  const isConnected = connectionStatus?.is_connected ?? false;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <BookOpen className="h-6 w-6 text-primary-600" />
        <h1 className="text-2xl font-bold text-secondary-900">
          QuickBooks Integration
        </h1>
        {isConnected ? (
          <Badge variant="success">Connected</Badge>
        ) : (
          <Badge variant="warning">Not Connected</Badge>
        )}
      </div>

      {!isConnected && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Connect your QuickBooks account to set up account matching and enable order syncing.
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue={isConnected ? "setup" : "connection"}>
        <TabsList>
          <TabsTrigger value="connection">Connection</TabsTrigger>
          <TabsTrigger value="setup">Account Setup</TabsTrigger>
          <TabsTrigger value="mappings">Mappings</TabsTrigger>
          <TabsTrigger value="sync">Sync</TabsTrigger>
        </TabsList>

        <TabsContent value="connection">
          <ConnectionTab />
        </TabsContent>
        <TabsContent value="setup">
          <AccountSetupTab isConnected={isConnected} />
        </TabsContent>
        <TabsContent value="mappings">
          <MappingsTab isConnected={isConnected} />
        </TabsContent>
        <TabsContent value="sync">
          <SyncTab isConnected={isConnected} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default QuickBooksPage;
