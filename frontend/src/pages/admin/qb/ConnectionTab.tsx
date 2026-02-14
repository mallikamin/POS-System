import { useState, useEffect } from "react";
import {
  Link2,
  Link2Off,
  Loader2,
  Building2,
  Clock,
  RefreshCw,
  Shield,
  Download,
  Database,
  Copy,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import type { QBSnapshotLatest } from "@/types/quickbooks";

export function ConnectionTab() {
  const connectionStatus = useQuickBooksStore((s) => s.connectionStatus);
  const isLoading = useQuickBooksStore((s) => s.isLoadingConnection);
  const loadConnectionStatus = useQuickBooksStore((s) => s.loadConnectionStatus);

  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [showDisconnectDialog, setShowDisconnectDialog] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [snapshots, setSnapshots] = useState<QBSnapshotLatest | null>(null);
  const [loadingSnapshots, setLoadingSnapshots] = useState(false);
  const [refreshingSnapshots, setRefreshingSnapshots] = useState(false);

  const isConnected = connectionStatus?.is_connected ?? false;

  // Load snapshots when connected
  useEffect(() => {
    if (isConnected) {
      setLoadingSnapshots(true);
      qbApi.fetchLatestSnapshots()
        .then(setSnapshots)
        .catch(() => { /* non-fatal */ })
        .finally(() => setLoadingSnapshots(false));
    }
  }, [isConnected]);

  async function handleRefreshSnapshots() {
    setRefreshingSnapshots(true);
    try {
      await qbApi.refreshSnapshots();
      const updated = await qbApi.fetchLatestSnapshots();
      setSnapshots(updated);
    } catch {
      setError("Failed to refresh CoA snapshots.");
    } finally {
      setRefreshingSnapshots(false);
    }
  }

  async function handleExportBackup() {
    if (!snapshots?.backup?.id) return;
    try {
      await qbApi.exportSnapshotJson(snapshots.backup.id);
    } catch {
      setError("Failed to download backup.");
    }
  }

  async function handleConnect() {
    setConnecting(true);
    setError(null);
    try {
      const { auth_url } = await qbApi.connectQuickBooks();
      const popup = window.open(auth_url, "qb_oauth", "width=600,height=700");

      // Poll for OAuth completion — the callback redirects to /admin/quickbooks?connected=1
      // which closes the popup or we detect it was closed / URL changed
      const pollInterval = setInterval(async () => {
        try {
          // If popup was closed by user or by the redirect, stop polling
          if (!popup || popup.closed) {
            clearInterval(pollInterval);
            setConnecting(false);
            // Refresh connection status to check if OAuth succeeded
            await loadConnectionStatus();
            return;
          }
        } catch {
          // Cross-origin errors are expected while on Intuit's domain
        }
      }, 1000);

      // Safety timeout: stop polling after 5 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        setConnecting(false);
      }, 300_000);
    } catch {
      setError("Failed to generate QuickBooks authorization URL. Check that QB_CLIENT_ID and QB_CLIENT_SECRET are configured.");
      setConnecting(false);
    }
  }

  async function handleDisconnect() {
    setDisconnecting(true);
    setError(null);
    try {
      await qbApi.disconnectQuickBooks();
      await loadConnectionStatus();
      setShowDisconnectDialog(false);
    } catch {
      setError("Failed to disconnect from QuickBooks.");
    } finally {
      setDisconnecting(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      {error && (
        <div className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">dismiss</button>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {isConnected ? (
              <Link2 className="h-5 w-5 text-success-600" />
            ) : (
              <Link2Off className="h-5 w-5 text-secondary-400" />
            )}
            Connection Status
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {isConnected ? (
            <>
              <div className="flex items-center gap-2">
                <Badge variant="success">Connected</Badge>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                {connectionStatus?.company_name && (
                  <div className="flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-secondary-400" />
                    <div>
                      <p className="text-secondary-500">Company</p>
                      <p className="font-medium text-secondary-900">
                        {connectionStatus.company_name}
                      </p>
                    </div>
                  </div>
                )}

                {connectionStatus?.realm_id && (
                  <div>
                    <p className="text-secondary-500">Realm ID</p>
                    <p className="font-mono text-sm text-secondary-700">
                      {connectionStatus.realm_id}
                    </p>
                  </div>
                )}

                {connectionStatus?.connected_at && (
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-secondary-400" />
                    <div>
                      <p className="text-secondary-500">Connected At</p>
                      <p className="text-secondary-700">
                        {new Date(connectionStatus.connected_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                )}

                {connectionStatus?.last_sync_at && (
                  <div>
                    <p className="text-secondary-500">Last Sync</p>
                    <p className="text-secondary-700">
                      {new Date(connectionStatus.last_sync_at).toLocaleString()}
                      {connectionStatus.last_sync_status && (
                        <Badge
                          variant={connectionStatus.last_sync_status === "success" ? "success" : "destructive"}
                          className="ml-2"
                        >
                          {connectionStatus.last_sync_status}
                        </Badge>
                      )}
                    </p>
                  </div>
                )}
              </div>

              <div className="flex gap-2 pt-2">
                <Button variant="outline" size="sm" onClick={loadConnectionStatus}>
                  <RefreshCw className="h-4 w-4 mr-1" />
                  Refresh Status
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-danger-600 hover:text-danger-700 hover:bg-danger-50"
                  onClick={() => setShowDisconnectDialog(true)}
                >
                  <Link2Off className="h-4 w-4 mr-1" />
                  Disconnect
                </Button>
              </div>
            </>
          ) : (
            <>
              <p className="text-sm text-secondary-600">
                Connect your QuickBooks Online account to automatically match
                POS accounts and start syncing orders and financial data.
              </p>

              <Button onClick={handleConnect} disabled={connecting}>
                {connecting ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Link2 className="h-4 w-4 mr-2" />
                )}
                Connect to QuickBooks
              </Button>
            </>
          )}
        </CardContent>
      </Card>

      {/* CoA Snapshot Status */}
      {isConnected && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-primary-600" />
              Chart of Accounts Backup
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {loadingSnapshots ? (
              <div className="flex items-center gap-2 text-sm text-secondary-500">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading snapshot info...
              </div>
            ) : snapshots?.backup ? (
              <>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="flex items-center gap-2">
                    <Database className="h-4 w-4 text-success-600" />
                    <div>
                      <p className="text-secondary-500">Original Backup</p>
                      <p className="font-medium text-secondary-900">
                        {snapshots.backup.account_count} accounts
                        <Badge variant="outline" className="ml-2 text-xs">
                          v{snapshots.backup.version}
                        </Badge>
                        <Badge variant="success" className="ml-1 text-xs">
                          Locked
                        </Badge>
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Copy className="h-4 w-4 text-primary-600" />
                    <div>
                      <p className="text-secondary-500">Working Copy</p>
                      <p className="font-medium text-secondary-900">
                        {snapshots.working_copy
                          ? `${snapshots.working_copy.account_count} accounts`
                          : "Not created"}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-secondary-400" />
                    <div>
                      <p className="text-secondary-500">Captured At</p>
                      <p className="text-secondary-700">
                        {new Date(snapshots.backup.fetched_at).toLocaleString()}
                      </p>
                    </div>
                  </div>

                  <div>
                    <p className="text-secondary-500">Company</p>
                    <p className="text-secondary-700">
                      {snapshots.backup.qb_company_name}
                    </p>
                  </div>
                </div>

                <div className="flex gap-2 pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleExportBackup}
                  >
                    <Download className="h-4 w-4 mr-1" />
                    Download Backup JSON
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRefreshSnapshots}
                    disabled={refreshingSnapshots}
                  >
                    {refreshingSnapshots ? (
                      <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    ) : (
                      <RefreshCw className="h-4 w-4 mr-1" />
                    )}
                    Re-fetch from QB
                  </Button>
                </div>

                <p className="text-xs text-secondary-400">
                  The original backup is immutable and never modified. Download it
                  and commit to git for an audit trail. All matching and mapping
                  happens on the working copy.
                </p>
              </>
            ) : (
              <div className="text-sm text-secondary-500">
                No CoA snapshot found. Snapshots are created automatically when
                you connect. Click &quot;Re-fetch from QB&quot; to create one now.
                <div className="mt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRefreshSnapshots}
                    disabled={refreshingSnapshots}
                  >
                    {refreshingSnapshots ? (
                      <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    ) : (
                      <RefreshCw className="h-4 w-4 mr-1" />
                    )}
                    Fetch CoA Now
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Disconnect Confirmation */}
      <Dialog open={showDisconnectDialog} onOpenChange={setShowDisconnectDialog}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Disconnect QuickBooks</DialogTitle>
            <DialogDescription>
              This will revoke the OAuth tokens and stop all syncing.
              You can reconnect at any time.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDisconnectDialog(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDisconnect}
              disabled={disconnecting}
            >
              {disconnecting && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
              Disconnect
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
